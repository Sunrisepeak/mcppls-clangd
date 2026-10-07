#!/usr/bin/env python3
"""Reject a cyclic prerequisite graph and recover after a document edit."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    paths = [root / name for name in ('A.cppm', 'B.cppm', 'Use.cpp')]
    for path, contents in zip(paths, [
        'export module A;\nimport B;\nexport int a;\n',
        'export module B;\nimport A;\nexport int b;\n', 'import A;\nint marker;\n']):
        path.write_text(contents)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]} for p in paths]))
    source = paths[-1]
    document = {'textDocument': {'uri': source.as_uri()}}
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': source.read_text()}}},
        {'method': 'textDocument/documentSymbol', 'params': document},
        {'action': 'await-log', 'contains': 'Cyclic module dependency involving A'},
        {'method': 'textDocument/didChange', 'notify': True, 'params': {
            'textDocument': {'uri': source.as_uri(), 'version': 2},
            'contentChanges': [{'text': 'int healthy;\n'}]}},
        {'method': 'textDocument/documentSymbol', 'params': document,
         'expect': {'/result/0/name': 'healthy'}},
    ]
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({'id': 'cyclic-module-recovery', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'hang', 'timeout_seconds': 10,
        'flags': ['--experimental-modules-support', '--background-index=false', '-j=2'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'result': result, 'limits': ['No parallel DAG scheduling claim.']}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result['outcome'], result.get('detail', ''))
    return 0 if result['outcome'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
