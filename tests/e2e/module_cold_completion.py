#!/usr/bin/env python3
"""Require imported symbols on the first request, without an AST barrier."""
import argparse
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('replay', root / 'tests/crash/replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    engine, compiler = replay.executable(args.engine), replay.executable(args.clang)
    work = args.workdir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    # A unique directory ensures this test never borrows a prior run's BMI.
    project = Path(tempfile.mkdtemp(prefix='cold-', dir=work))
    module, source = project / 'M.cppm', project / 'Use.cpp'
    module.write_text('export module M;\nexport int fn_m() { return 1; }\n')
    text = 'import M;\nvoid probe() { fn; }\n'
    source.write_text(text)
    (project / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(project), 'file': str(path),
         'arguments': [str(compiler), '-std=c++20', '-c', str(path)]}
        for path in (module, source)]))
    case = project / 'case.json'
    case.write_text(json.dumps({
        'id': 'module-first-completion', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--background-index=false'],
        'sequence': [
            {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {}}},
            {'method': 'initialized', 'notify': True, 'params': {}},
            {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
                'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
            {'method': 'textDocument/completion', 'expected_symbols': ['fn_m'], 'params': {
                'textDocument': {'uri': source.as_uri()}, 'position': {'line': 1, 'character': 17}}},
        ],
    }))
    result = replay.replay(engine, case)
    checksum = hashlib.sha256()
    with engine.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            checksum.update(chunk)
    result['engine_sha256'] = checksum.hexdigest()
    result['source_unchanged'] = source.read_text() == text
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result.get(key) for key in
                      ['outcome', 'detail', 'exit_code', 'readers_stopped', 'source_unchanged']}))
    return 0 if (result['outcome'] == 'pass' and result['exit_code'] == 0
                 and result['readers_stopped'] and result['source_unchanged']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
