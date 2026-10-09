#!/usr/bin/env python3
"""Synthetic noisy worker verifies bounded Linux stderr transport and parent recovery."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        'replay', Path(__file__).resolve().parents[1] / 'crash/replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    engine, compiler = replay.executable(args.engine), replay.executable(args.clang)
    assert replay.platform_name().startswith('linux-'), 'FIFO diagnostic transport gate requires Linux'
    args.workdir.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix='noisy-worker-', dir=args.workdir.resolve()))
    module, use, control = [project / name for name in ('M.cppm', 'Use.cpp', 'Control.cpp')]
    module.write_text('export module M;\nexport int fn_m() { return 42; }\n')
    use.write_text('import M;\nint probe() { return fn_m(); }\n')
    control.write_text('int ControlValue = 73;\n')
    originals = {path: path.read_bytes() for path in (module, use, control)}
    (project / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(project), 'file': str(path),
         'arguments': [str(compiler), '-std=c++20', '-c', path.name]}
        for path in (module, use, control)]))

    def opened(path):
        return {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': path.as_uri(), 'languageId': 'cpp',
                             'version': 1, 'text': path.read_text()}}}

    worker = project / 'noisy-worker.py'
    worker.write_text("#!/usr/bin/env python3\n" + r'''import json, os, stat, sys
from pathlib import Path
request = json.loads(Path(sys.argv[2]).read_text())
root = Path(request['directory'])
def record(finished):
    info = os.fstat(2)
    (root / 'writer.json').write_text(json.dumps({
        'fifo': stat.S_ISFIFO(info.st_mode), 'size': info.st_size,
        'allocated_bytes': info.st_blocks * 512, 'finished': finished}))
record(False)
os.write(2, b'diagnostic-prefix\n')
for _ in range(2048):
    os.write(2, b'X' * 4096)
record(True)
sys.exit(1)
''')
    worker.chmod(0o755)
    manifest = project / 'case.json' 
    manifest.write_text(json.dumps({
        'id': 'module-worker-bounded-diagnostic-transport', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--background-index=false',
                  '--log=verbose', '--modules-builder-workers=1',
                  '--modules-builder-worker-policy=required',
                  '--modules-builder-worker-executable=' + str(worker)],
        'sequence': [
            {'method': 'initialize', 'params': {
                'rootUri': project.as_uri(), 'capabilities': {}}},
            {'method': 'initialized', 'notify': True, 'params': {}},
            opened(use),
            # This event is emitted after a launched worker exits unsuccessfully,
            # not on unsupported-filesystem fallback or admission rejection.
            {'action': 'await-log', 'contains': 'diagnostics truncated'},
            opened(control),
            {'method': 'textDocument/documentSymbol', 'params': {
                'textDocument': {'uri': control.as_uri()}},
             'expect': {'/result/0/name': 'ControlValue'}},
        ],
    }))
    result = replay.replay(engine, manifest)
    writer = json.loads((project / 'writer.json').read_text())
    result.update(writer=writer, synthetic_transport_check=True, engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                  disk_unchanged=all(path.read_bytes() == data
                                     for path, data in originals.items()),
                  remaining_bmis=[str(path) for path in project.rglob('*.pcm')],
                  remaining_worker_units=[str(path) for path
                                          in project.rglob('unit-*') if path.is_dir()])
    report = args.workdir / 'result.json'
    report.write_text(json.dumps(result, indent=2) + '\n')
    assert writer['fifo'] and writer['size'] == 0 and writer['allocated_bytes'] == 0, writer
    assert writer['finished'], 'noisy worker did not finish its 8 MiB write'
    assert result['outcome'] == 'pass', result.get('detail')
    assert result['exit_code'] == 0 and result['readers_stopped'], result
    assert result['disk_unchanged'], 'server changed the source files'
    assert 'module worker failed' in result['stderr'], 'no actual failed-worker event'
    assert 'Built module M to ' not in result['stderr'], 'failed worker fell back to compilation'
    assert not result['remaining_bmis'], result['remaining_bmis']
    assert not result['remaining_worker_units'], result['remaining_worker_units']
    print(json.dumps({'outcome': 'pass', 'worker_failed': True, 'writer': writer,
                      'scope': 'synthetic transport check, not real compiler/crash qualification',
                      'parent_semantic_response': 'ControlValue', 'exit_code': 0,
                      'report': str(report)}))


if __name__ == '__main__':
    main()
