#!/usr/bin/env python3
"""Fresh module facades share provider inventory without losing real symbols."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

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
    if (root / 'case.json').exists():
        raise ValueError('use a fresh workdir')
    dep, pcm = root / 'dep.cppm', root / 'dep.pcm'
    dep.write_text('export module dep;\nexport int dep_value() { return 1; }\n')
    subprocess.run([str(clang), '-std=c++20', '--precompile', str(dep), '-o', str(pcm)], check=True)
    entries = [{'directory': str(root), 'file': str(dep),
                'arguments': [str(clang), '-std=c++20', '--precompile', str(dep), '-o', str(pcm)]}]
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}}]
    text = 'import dep;\nint probe() { return dep_value(); }\n'
    for number in range(3):
        source = root / f'Use{number}.cpp'
        source.write_text(text)
        entries.append({'directory': str(root), 'file': str(source),
                        'arguments': [str(clang), '-std=c++20', '-c', str(source),
                                      '-fmodule-file=dep=' + str(pcm)]})
        document = {'textDocument': {'uri': source.as_uri()}}
        sequence += [
            {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
                'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
            {'method': 'textDocument/documentSymbol', 'params': document,
             'expect': {'/result/0/name': 'probe'}},
            {'method': 'textDocument/completion', 'params': {
                **document, 'position': {'line': 1, 'character': 27}},
             'expected_symbols': ['dep_value']}]
    for number in range(128):
        source = root / f'Unrelated{number}.cpp'
        source.write_text('int unrelated;\n')
        entries.append({'directory': str(root), 'file': str(source),
                        'arguments': [str(clang), '-std=c++20', '-c', str(source)]})
    (root / 'compile_commands.json').write_text(json.dumps(entries))
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({'id': 'provider-cache', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 30,
        'flags': ['--experimental-modules-support', '--background-index=false', '--log=verbose'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)
    result['engine_sha256'] = hashlib.sha256(engine.read_bytes()).hexdigest()
    result['provider_inventory_count'] = result['stderr'].count('Module provider inventory:')
    result['provider_index_reuses'] = result['stderr'].count('Module provider index reused:')
    (root / 'result.json').write_text(json.dumps(result, indent=2))
    if result['outcome'] != 'pass':
        raise RuntimeError(result.get('detail', result['outcome']))
    if result['provider_inventory_count'] != 1 or result['provider_index_reuses'] < 2:
        raise RuntimeError('fresh module facades did not reuse their CDB generation')
    if 'Failed to build' in result['stderr']:
        raise RuntimeError('valid module failed to build')
    print(json.dumps({'outcome': 'pass', 'provider_inventory_count': 1,
                      'provider_index_reuses': result['provider_index_reuses'],
                      'report': str(root / 'result.json')}))


if __name__ == '__main__':
    main()
