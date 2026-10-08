#!/usr/bin/env python3
"""Exercise default Linux module workers through real LSP and dirty headers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--engine-flag', action='append', default=[])
    parser.add_argument('--dependency-mode', choices=('none', 'MD', 'MMD'), default='none',
                        help='exercise owned-default admission of real dependency-output CDB flags')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        'replay', Path(__file__).resolve().parents[1] / 'crash/replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    engine, compiler = replay.executable(args.engine), replay.executable(args.clang)
    args.workdir.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix='default-worker-', dir=args.workdir.resolve()))
    module, source, header = [project / name for name in ('M.cppm', 'Use.cpp', 'header.h')]
    header.write_text('inline constexpr int Captured = 41;\n')
    body = ('module;\n#include "header.h"\nexport module M;\n'
            'constexpr int work() { int v=0; for(int i=0;i<200000;++i) v+=i%7; return v; }\n'
            'static_assert(work()>0);\nstatic_assert(Captured == 42);\n'
            'export int fn_m() { return Captured; }\n')
    module.write_text(body)
    text = 'import M;\nvoid probe() { fn; }\n'
    source.write_text(text)
    originals = {path: path.read_bytes() for path in (module, source, header)}
    dependency = project / 'M.d'
    if args.dependency_mode != 'none':
        dependency.write_bytes(b'existing dependency output must survive\n')
        originals[dependency] = dependency.read_bytes()
    (project / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(project), 'file': str(path),
         'arguments': [str(compiler), '-std=c++20', '-fconstexpr-steps=0', '-c', path.name,
                       *(['-' + args.dependency_mode, '-MF', path.stem + '.d',
                          '-MT', 'ordinary-target'] if args.dependency_mode != 'none' else [])]}
        for path in (module, source)]))
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': header.as_uri(), 'languageId': 'cpp', 'version': 1,
            'text': 'inline constexpr int Captured = 42;\n'}}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
        {'method': 'textDocument/completion', 'expected_symbols': ['fn_m'], 'params': {
            'textDocument': {'uri': source.as_uri()}, 'position': {'line': 1, 'character': 17}}},
    ]
    manifest = project / 'case.json'
    manifest.write_text(json.dumps({
        'id': 'default-module-worker', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--use-dirty-headers',
                  '--background-index=false', '--log=verbose',
                  *args.engine_flag],
        'sequence': sequence,
    }))
    stopped, observations, monitors = threading.Event(), {}, []
    captured = {}

    def started(proc, deadline):
        def observe():
            # Pool children belong to the launching thread, not necessarily the
            # leader. Read every task's child list instead of missing those PIDs.
            while not stopped.wait(0.001) and proc.poll() is None:
                for task in Path(f'/proc/{proc.pid}/task').glob('*'):
                    try:
                        children = (task / 'children').read_text().split()
                    except OSError:
                        continue
                    for child in children:
                        try:
                            command = Path(f'/proc/{child}/cmdline').read_bytes().split(b'\0')
                            if b'--module-build-worker' not in command:
                                continue
                            if args.dependency_mode != 'none' and child not in captured:
                                try:
                                    captured[child] = json.loads(Path(command[2].decode()).read_text())
                                except (OSError, ValueError):
                                    pass
                            limits = Path(f'/proc/{child}/limits').read_text()
                            line = next(x for x in limits.splitlines() if x.startswith('Max address space'))
                            columns = line[len('Max address space'):].split()
                            # Bootstrap may still be applying the bound. Keep
                            # the observed checked state, not an earlier max.
                            if columns[:2] != ['unlimited', 'unlimited']:
                                observations[child] = {'command': [x.decode() for x in command if x],
                                                       'address_space': columns[:2],
                                                       'cgroup': Path(f'/proc/{child}/cgroup').read_text()}
                        except (OSError, StopIteration):
                            pass
        thread = threading.Thread(target=observe)
        monitors.append(thread)
        thread.start()

    try:
        result = replay.replay(engine, manifest, process_started=started)
    finally:
        stopped.set()
        for thread in monitors:
            thread.join()
    result.update(engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                  observed_workers=observations,
                  dependency_mode=args.dependency_mode, captured_requests=captured,
                  dependency_output_absent=not (project / 'Use.d').exists(),
                  disk_unchanged=all(path.read_bytes() == data for path, data in originals.items()))
    (args.workdir / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    assert result['outcome'] == 'pass', result.get('detail')
    assert result['exit_code'] == 0 and result['readers_stopped'] and result['disk_unchanged']
    failures = [line for line in result['stderr'].splitlines()
                if 'Failed to build module prerequisites' in line
                and not line.endswith('; due to Task was cancelled.')]
    assert not failures, failures
    assert observations, 'default server did not launch a checked module worker'
    if args.dependency_mode != 'none':
        assert captured, 'no real owned-default worker request captured'
        for request in captured.values():
            assert request['version'] == 4, 'dependency canary requires owned-default admission'
            assert '-dependency-file' not in request['cc1Arguments'], request
        assert result['dependency_output_absent'], 'Use.d dependency output escaped'
        assert dependency.read_bytes() == originals[dependency], 'existing M.d was modified'
    for item in observations.values():
        soft, hard = map(int, item['address_space'])
        assert soft == hard and 0 < hard <= 4096 * 1024 * 1024
        request = Path(item['command'][2])
        assert not request.parent.exists(), f'worker unit survives normal shutdown: {request.parent}'
        if any(flag.startswith('--modules-builder-worker-cgroup-root=') for flag in args.engine_flag):
            assert '/clangd-module-workers-' in item['cgroup'], item
            group = Path(item['command'][4].split(':', 3)[3])
            assert not group.exists(), f'owned memory group survives normal shutdown: {group}'
    print(json.dumps({'outcome': 'pass', 'observed_workers': len(observations),
                      'dependency_mode': args.dependency_mode,
                      'disk_unchanged': True, 'report': str(args.workdir / 'result.json')}))


if __name__ == '__main__':
    main()
