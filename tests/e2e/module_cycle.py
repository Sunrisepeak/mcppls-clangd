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
    # A second process sees a real diamond after the cyclic providers change.
    # Successful BMI construction proves shared D is not treated as a cycle.
    diamond_sources = {
        'A.cppm': 'export module A;\nexport import B;\nexport import C;\n',
        'B.cppm': 'export module B;\nexport import D;\nexport int b;\n',
        'C.cppm': 'export module C;\nexport import D;\nexport int c;\n',
        'D.cppm': 'export module D;\nexport int d;\nexport int diamond_value;\n',
        'Use.cpp': 'import A;\nint marker = b + c + d;\nvoid probe() { diamond_; }\n',
    }
    for name, contents in diamond_sources.items():
        (root / name).write_text(contents)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(root / name),
         'arguments': [str(clang), '-std=c++20', '-c', str(root / name)]}
        for name in diamond_sources]))
    diamond = sequence[:4]
    diamond[2] = {'method': 'textDocument/didOpen', 'notify': True, 'params': {
        'textDocument': {'uri': source.as_uri(), 'languageId': 'cpp',
                         'version': 1, 'text': source.read_text()}}}
    diamond[3] = {'method': 'textDocument/documentSymbol', 'params': document,
                  'expect': {'/result/0/name': 'marker'}}
    diamond.append({'action': 'await-log', 'contains': 'Built module A to '})
    diamond.append({'method': 'textDocument/completion', 'params': {
        **document, 'position': {'line': 2, 'character': len('void probe() { diamond_')}},
        'expected_symbols': ['diamond_value']})
    case = json.loads(manifest.read_text())
    case.update(id='diamond-module-recovery', sequence=diamond)
    manifest.write_text(json.dumps(case))
    shared = replay.replay(engine, manifest)
    if 'Failed to build module' in shared['stderr']:
        shared['outcome'] = 'error'
        shared['detail'] = 'valid diamond failed to build'
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'result': result, 'diamond': shared, 'limits': ['No parallel DAG scheduling claim.']}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('cycle', result['outcome'], result.get('detail', ''))
    print('diamond', shared['outcome'], shared.get('detail', ''))
    return 0 if result['outcome'] == 'pass' and shared['outcome'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
