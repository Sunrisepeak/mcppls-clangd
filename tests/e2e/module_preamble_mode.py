#!/usr/bin/env python3
"""Check current module symbols across preamble mode changes without AST barriers."""
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
    parser.add_argument('--engine-flag', action='append', default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('replay', root / 'tests/crash/replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    engine, compiler = replay.executable(args.engine), replay.executable(args.clang)
    work = args.workdir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix='mode-', dir=work))
    source, header = project / 'Use.cpp', project / 'imports.h'
    text = '#include "imports.h"\nvoid probe() { fn; }\n'
    source.write_text(text)
    header.write_text('import M;\n')
    paths = []
    for name in ('M', 'N'):
        module = project / (name + '.cppm')
        module.write_text('export module ' + name + ';\nexport int fn_' +
                          name.lower() + '() { return 1; }\n')
        paths.append(module)
    (project / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(project), 'file': str(path),
         'arguments': [str(compiler), '-std=c++20', '-c', str(path)]}
        for path in paths + [source]]))
    document = {'textDocument': {'uri': source.as_uri()}}
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
    ]

    def complete(character, required, forbidden):
        sequence.append({'method': 'textDocument/completion',
                         'params': {**document, 'position': {'line': 1, 'character': character}},
                         'expected_symbols': [required], 'forbidden_symbols': forbidden})

    complete(17, 'fn_m', ['fn_n'])
    sequence.append({'action': 'replace-file', 'file': 'imports.h',
                     'from': 'import M;', 'with': 'import N;', 'preserve-mtime': True})
    complete(17, 'fn_n', ['fn_m'])
    for version, draft, character, required, forbidden in (
        (2, 'int textual_value;\nvoid probe() { tex; }\n', 18,
         'textual_value', ['fn_m', 'fn_n']),
        (3, 'import M;\nvoid probe() { fn; }\n', 17, 'fn_m', ['fn_n']),
    ):
        sequence.append({'method': 'textDocument/didChange', 'notify': True,
                         'params': {'textDocument': {'uri': source.as_uri(), 'version': version},
                                    'contentChanges': [{'text': draft}]}})
        complete(character, required, forbidden)
    case = project / 'case.json'
    case.write_text(json.dumps({
        'id': 'completion-preamble-mode-transitions', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--background-index=false'] + args.engine_flag,
        'sequence': sequence,
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
