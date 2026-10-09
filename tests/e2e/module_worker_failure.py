#!/usr/bin/env python3
"""A worker failure under a small address cap must leave its LSP parent usable."""
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
    assert replay.platform_name().startswith('linux-'), 'default worker failure gate requires Linux'
    args.workdir.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix='failed-worker-', dir=args.workdir.resolve()))
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

    manifest = project / 'case.json'
    manifest.write_text(json.dumps({
        'id': 'module-worker-low-address-failure', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--background-index=false',
                  '--log=verbose', '--modules-builder-workers=2',
                  '--modules-builder-worker-aggregate-address-space-mib=32'],
        'sequence': [
            {'method': 'initialize', 'params': {
                'rootUri': project.as_uri(), 'capabilities': {}}},
            {'method': 'initialized', 'notify': True, 'params': {}},
            opened(use),
            # This event is emitted after a launched worker exits unsuccessfully,
            # not on unsupported-filesystem fallback or admission rejection.
            {'action': 'await-log', 'contains': 'module worker failed'},
            opened(control),
            {'method': 'textDocument/documentSymbol', 'params': {
                'textDocument': {'uri': control.as_uri()}},
             'expect': {'/result/0/name': 'ControlValue'}},
        ],
    }))
    result = replay.replay(engine, manifest)
    result.update(engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                  disk_unchanged=all(path.read_bytes() == data
                                     for path, data in originals.items()),
                  remaining_bmis=[str(path) for path in project.rglob('*.pcm')],
                  remaining_worker_units=[str(path) for path
                                          in project.rglob('unit-*') if path.is_dir()])
    report = args.workdir / 'result.json'
    report.write_text(json.dumps(result, indent=2) + '\n')
    assert result['outcome'] == 'pass', result.get('detail')
    assert result['exit_code'] == 0 and result['readers_stopped'], result
    assert result['disk_unchanged'], 'server changed the source files'
    assert 'module worker failed' in result['stderr'], 'no actual failed-worker event'
    assert 'Built module M to ' not in result['stderr'], 'failed worker fell back to compilation'
    assert not result['remaining_bmis'], result['remaining_bmis']
    assert not result['remaining_worker_units'], result['remaining_worker_units']
    print(json.dumps({'outcome': 'pass', 'worker_failed': True,
                      'parent_semantic_response': 'ControlValue', 'exit_code': 0,
                      'report': str(report)}))


if __name__ == '__main__':
    main()
