#!/usr/bin/env python3
"""Response edits must refresh module inputs with unchanged JSON and draft."""
import argparse
import hashlib
import importlib.util
import json
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
    use = work / 'Use.cpp'
    modules = []
    for name in ('M', 'N'):
        provider = work / (name + '.cppm')
        provider.write_text(f'export module {name};\nexport int fn_{name.lower()}() {{ return 1; }}\n')
        modules.append(provider)
    (work / 'flags.rsp').write_text('-DMODE=1\n')
    text_m = '#if MODE == 1\nimport M;\n#else\nimport N;\n#endif\nvoid probe() { fn; }\n'
    use.write_text(text_m)
    commands = [{'directory': str(work), 'file': str(provider),
                 'arguments': [str(compiler), '-std=c++20', '-c', str(provider)]}
                for provider in modules]
    commands.append({'directory': str(work), 'file': str(use),
                     'arguments': [str(compiler), '-std=c++20', '@flags.rsp', '-c', str(use)]})
    cdb = work / 'compile_commands.json'
    cdb.write_text(json.dumps(commands))
    original_cdb = cdb.read_bytes()
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': work.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': use.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text_m}}},
    ]
    def probe(symbol):
        sequence.extend([
            {'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': use.as_uri()}}},
            {'method': 'textDocument/completion', 'expected_symbols': [symbol], 'params': {
                'textDocument': {'uri': use.as_uri()}, 'position': {'line': 5, 'character': 17}}},
        ])
    probe('fn_m')
    sequence.append({'action': 'replace-file', 'file': 'flags.rsp', 'from': '-DMODE=1',
                     'with': '-DMODE=2', 'preserve-mtime': True})
    sequence.append({'method': 'textDocument/didChange', 'notify': True, 'params': {
        'textDocument': {'uri': use.as_uri(), 'version': 2}, 'contentChanges': [{'text': text_m}]}})
    probe('fn_n')
    case = work / 'case.json'
    case.write_text(json.dumps({'id': 'response-command-generation', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 40,
        'flags': ['--experimental-modules-support', '--background-index=false', '--log=verbose'],
        'sequence': sequence}))
    result = replay.replay(engine, case)
    checksum = hashlib.sha256()
    with engine.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            checksum.update(chunk)
    result['engine_sha256'] = checksum.hexdigest()
    result['cdb_unchanged'] = cdb.read_bytes() == original_cdb
    result['disk_importer_unchanged'] = use.read_text() == text_m
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result.get(key) for key in
                      ['outcome', 'detail', 'exit_code', 'cdb_unchanged', 'disk_importer_unchanged']}))
    return 0 if (result['outcome'] == 'pass' and result['exit_code'] == 0
                 and result['readers_stopped'] and result['cdb_unchanged']
                 and result['disk_importer_unchanged']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
