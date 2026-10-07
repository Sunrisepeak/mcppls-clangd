#!/usr/bin/env python3
"""Bound module DAG jobs, preserve dependencies, and recover from failed siblings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
START = re.compile(r'Module build task (\S+) started \(active=(\d+), limit=(\d+)\)')
FINISH = re.compile(r'Module build task (\S+) finished')
HEADERS = 'module;\n#include <vector>\n#include <map>\n#include <string>\n#include <algorithm>\n'


def generate(root, clang, shape, heavy=False):
    root.mkdir(parents=True, exist_ok=True)
    if (root / '.cache').exists():
        raise ValueError('use a fresh workdir: this fixture requires a cold cache')
    if shape == 'textual':
        dependencies = {'A': ['foreign_missing'], 'C': []}
        imports = ['A', 'C']
    elif shape == 'prebuilt':
        dependencies = {'A': ['B']}
        imports = ['A']
    elif shape in ('wide', 'concurrent'):
        dependencies = {f'm{i}': [] for i in range(1, 5)}
        imports = list(dependencies)
    else:
        dependencies = {'D': [], 'B': ['D'], 'C': ['D'], 'A': ['B', 'C']}
        imports = ['A']
    sources = {}
    for name, required in dependencies.items():
        text = HEADERS if heavy else ''
        text += f'export module {name};\n'
        text += ''.join(f'export import {dependency};\n' for dependency in required)
        text += f'export int fn{name}() {{ return 1; }}\n'
        if shape == 'failure' and name == 'B':
            text += 'export int broken = unknown_name;\n'
        source = root / (name + '.cppm')
        source.write_text(text)
        sources[name] = source
    source = root / 'Use.cpp'
    text = ''.join(f'import {name};\n' for name in imports) + 'void caller(){\n  fn\n}\n'
    source.write_text(text)
    commands = [
        {'directory': str(root), 'file': str(path),
         'arguments': [str(clang), '-std=c++20', '-c', str(path)]}
        for path in [*sources.values(), source]]
    if shape == 'concurrent':
        peer = root / 'Peer.cpp'
        peer.write_text(text)
        commands.append({'directory': str(root), 'file': str(peer),
                         'arguments': [str(clang), '-std=c++20', '-c', str(peer)]})
    if shape == 'prebuilt':
        prebuilt_source = root / 'B.cppm'
        prebuilt_source.write_text('export module B;\nexport int fnB() { return 1; }\n')
        prebuilt = root / 'B.pcm'
        subprocess.run([str(clang), '-std=c++20', '--precompile', str(prebuilt_source),
                        '-o', str(prebuilt)], check=True, capture_output=True, timeout=20)
        commands[0]['arguments'].append('-fmodule-file=B=' + str(prebuilt))
    (root / 'compile_commands.json').write_text(json.dumps(commands))
    return source, text, dependencies


def run_case(engine, clang, root, shape, workers, baseline=False):
    source, text, dependencies = generate(root, clang, shape, heavy=shape in ('wide', 'concurrent'))
    document = {'textDocument': {'uri': source.as_uri()}}
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
            'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
        {'method': 'textDocument/documentSymbol', 'params': document,
         'expect': {'/result/0/name': 'caller'}},
    ]
    if shape == 'concurrent':
        peer = root / 'Peer.cpp'
        sequence.insert(3, {'method': 'textDocument/didOpen', 'notify': True,
                           'params': {'textDocument': {'uri': peer.as_uri(),
                            'languageId': 'cpp', 'version': 1, 'text': text}}})
        sequence.append({'method': 'textDocument/documentSymbol',
                         'params': {'textDocument': {'uri': peer.as_uri()}},
                         'expect': {'/result/0/name': 'caller'}})
    if shape == 'failure':
        sequence += [
            {'action': 'await-log', 'contains': 'Failed to build module prerequisites'},
            {'method': 'textDocument/didChange', 'notify': True, 'params': {
                'textDocument': {'uri': source.as_uri(), 'version': 2},
                'contentChanges': [{'text': 'int healthy;\n'}]}},
            {'method': 'textDocument/documentSymbol', 'params': document,
             'expect': {'/result/0/name': 'healthy'}},
        ]
    else:
        position = {'line': text.splitlines().index('  fn'), 'character': 4}
        sequence.append({'method': 'textDocument/completion', 'params': {
            **document, 'position': position},
            'expected_symbols': (['fnC'] if shape == 'textual' else
                                 ['fn' + name for name in dependencies])
            + (['fnB'] if shape == 'prebuilt' else [])})
    if shape == 'concurrent':
        sequence.append({'method': 'textDocument/completion', 'params': {
            'textDocument': {'uri': (root / 'Peer.cpp').as_uri()},
            'position': position}, 'expected_symbols': ['fn' + name for name in dependencies]})
    flags = ['--experimental-modules-support', '--background-index=false', '-j=4', '--log=verbose']
    if not baseline:
        flags.append(f'--modules-builder-workers={workers}')
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({'id': f'{shape}-{workers}', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass',
        'timeout_seconds': 30, 'flags': flags, 'sequence': sequence}))
    result = replay.replay(engine, manifest)
    if result['outcome'] != 'pass':
        raise RuntimeError(f'{shape}/{workers}: {result.get("detail", result["outcome"])}')
    if shape != 'failure' and 'Failed to build' in result['stderr']:
        raise RuntimeError('a valid DAG failed to build')
    if baseline:
        result['document_symbol_ms'] = next(item['elapsed_ms'] for item in result['raw_responses']
                                           if item['method'] == 'textDocument/documentSymbol')
        return result
    starts, finished = {}, {}
    maximum, limit = 0, 0
    for index, line in enumerate(result['stderr'].splitlines()):
        if match := START.search(line):
            name, active, bound = match[1], int(match[2]), int(match[3])
            if (name in starts and shape != 'concurrent') or not 1 <= active <= bound <= workers:
                raise RuntimeError('duplicate task or worker bound violated: ' + line)
            starts[name] = index
            maximum, limit = max(maximum, active), max(limit, bound)
        if match := FINISH.search(line):
            finished[match[1]] = index
    required = set(dependencies)
    if shape == 'textual':
        required = {'C'}
        if 'Keeping import of third-party module foreign_missing textual' not in result['stderr']:
            raise RuntimeError('unavailable transitive provider lost textual behavior')
    if shape == 'failure':
        required -= {'A'}
        if workers == 1:
            required -= {'C'}
    if set(starts) != required or set(finished) != required:
        raise RuntimeError(f'wrong tasks: started={set(starts)}, finished={set(finished)}')
    for name in required:
        for dependency in dependencies[name]:
            if dependency in finished and finished[dependency] >= starts[name]:
                raise RuntimeError(f'{name} started before dependency {dependency} finished')
    if shape in ('wide', 'concurrent') and workers > 1 and limit > 1 and maximum < 2:
        raise RuntimeError('independent compilation tasks never overlapped')
    result.update(max_active=maximum, worker_limit=limit,
                  document_symbol_ms=next(item['elapsed_ms'] for item in result['raw_responses']
                    if item['method'] == 'textDocument/documentSymbol'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--baseline-engine', type=Path)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    results = []
    for shape, workers in [('wide', 1), ('wide', 2), ('wide', 4), ('diamond', 1),
                           ('diamond', 4), ('failure', 1), ('failure', 4), ('prebuilt', 4), ('concurrent', 2), ('textual', 4)]:
        result = run_case(engine, clang, root / f'{shape}-{workers}', shape, workers)
        results.append(result)
        print(result['id'], result['outcome'], 'max_active', result['max_active'],
              'document_symbol_ms', round(result['document_symbol_ms'], 2))
    report = {'ok': True, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'results': results, 'limits': [
                  'One cold run per shape; timings are exploratory, not a release performance gate.',
                  'Worker count bounds concurrent compiler instances, not process RSS bytes.',
                  'No scan-result or provider-table reuse claim.']}
    if args.baseline_engine:
        baseline = replay.executable(args.baseline_engine)
        report['baseline'] = run_case(baseline, clang, root / 'wide-before', 'wide', 1, True)
        report['baseline_sha256'] = hashlib.sha256(baseline.read_bytes()).hexdigest()
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
