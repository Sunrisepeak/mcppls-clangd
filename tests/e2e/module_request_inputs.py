#!/usr/bin/env python3
"""Unsaved imports are scanned from the exact request buffer, not disk."""
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
    parser.add_argument('--replay', type=Path, default=Path(__file__).resolve().parents[2] / 'tests/crash/replay.py')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('replay', args.replay)
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'Use.cpp'
    disk = 'int disk_value;\n'
    source.write_text(disk)
    modules = {'M': 'draft_value', 'N': 'next_value'}
    commands = []
    for module, symbol in modules.items():
        path = root / f'{module}.cppm'
        path.write_text(f'export module {module};\nexport int {symbol}() {{ return 1; }}\n')
        commands.append({'directory': str(root), 'file': str(path),
                         'arguments': [str(clang), '-std=c++20', '-c', str(path)]})
    commands.append({'directory': str(root), 'file': str(source),
                     'arguments': [str(clang), '-std=c++20', '-c', str(source)]})
    (root / 'compile_commands.json').write_text(json.dumps(commands))
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}}]
    document = {'textDocument': {'uri': source.as_uri()}}
    drafts = ['import M;\nint probe() { return draft_value(); }\n',
              'int request_value;\n',
              'import N;\nint probe() { return next_value(); }\n']
    for version, text in enumerate(drafts, 1):
        if version == 1:
            sequence.append({'method': 'textDocument/didOpen', 'notify': True,
                'params': {'textDocument': {'uri': source.as_uri(), 'languageId': 'cpp',
                                           'version': version, 'text': text}}})
        else:
            sequence.append({'method': 'textDocument/didChange', 'notify': True,
                'params': {'textDocument': {'uri': source.as_uri(), 'version': version},
                           'contentChanges': [{'text': text}]}})
        sequence.append({'method': 'textDocument/documentSymbol', 'params': document,
                         'expect': {'/result/0/name': 'request_value' if version == 2 else 'probe'}})
        if version != 2:
            symbol = 'draft_value' if version == 1 else 'next_value'
            sequence.append({'method': 'textDocument/completion',
                             'params': {**document, 'position': {'line': 1, 'character': 28}},
                             'expected_symbols': [symbol]})
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({'id': 'module-request-inputs', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 30,
        'flags': ['--experimental-modules-support', '--background-index=false', '--log=verbose'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)
    result['engine_sha256'] = hashlib.sha256(engine.read_bytes()).hexdigest()
    result['disk_contents_unchanged'] = source.read_text() == disk
    (root / 'result.json').write_text(json.dumps(result, indent=2))
    if result['outcome'] != 'pass' or not result['disk_contents_unchanged']:
        raise RuntimeError(result.get('detail', 'disk buffer changed'))
    # A superseded AST or shutdown can cancel a concurrent module task after
    # the requested symbols have already been returned. Keep genuine build
    # failures fatal while accepting this explicit cancellation outcome.
    failures = [line for line in result['stderr'].splitlines()
                if 'Failed to build module prerequisites' in line
                and not line.endswith('; due to Task was cancelled.')]
    if failures:
        raise RuntimeError('valid unsaved imports failed')
    print(json.dumps({'outcome': 'pass', 'disk_contents_unchanged': True,
                      'report': str(root / 'result.json')}))


if __name__ == '__main__':
    main()
