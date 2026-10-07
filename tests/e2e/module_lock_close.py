#!/usr/bin/env python3
"""Close a document blocked by a live-owner BMI lock; require clean exit."""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--clang', required=True, type=Path)
    parser.add_argument('--workdir', required=True, type=Path)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    module, source, healthy = [root / name for name in ('A.cppm', 'Use.cpp', 'Healthy.cpp')]
    for path, contents in [(module, 'export module A;\nexport int item;\n'),
                           (source, 'import A;\nint marker;\n'), (healthy, 'int healthy;\n')]:
        path.write_text(contents)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]}
        for p in (module, source, healthy)]))

    def opened(path):
        return {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': path.as_uri(), 'languageId': 'cpp',
                             'version': 1, 'text': path.read_text()}}}

    def symbols(path, **extra):
        return {'method': 'textDocument/documentSymbol',
                'params': {'textDocument': {'uri': path.as_uri()}}, **extra}

    init = [{'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
            {'method': 'initialized', 'notify': True, 'params': {}}]
    manifest = root / 'case.json'

    def run(sequence):
        manifest.write_text(json.dumps({'id': 'live-owner-close', 'project': '.',
            'platform': replay.platform_name(), 'baseline': 'hang', 'timeout_seconds': 15,
            'flags': ['--experimental-modules-support', '--background-index=false', '-j=2'],
            'sequence': sequence}))
        return replay.replay(engine, manifest)

    warm = run(init + [opened(source), symbols(source, expect={'/result/0/name': 'marker'})])
    if warm['outcome'] != 'pass':
        raise RuntimeError(f'module warmup failed: {warm["outcome"]}')
    cache = root / '.cache/clangd/modules'
    anchors = [p for p in (cache / '.locks').iterdir() if p.is_file() and '.' not in p.name]
    if len(anchors) != 1:
        raise RuntimeError('expected one real source lock anchor from the module builder')
    lock = anchors[0].with_name(anchors[0].name + '.lock')
    owner = f'{platform.node()} {os.getpid()}'
    with lock.open('x') as stream:
        stream.write(owner)  # LLVM integer parser requires no trailing newline.
    try:
        for bmi in cache.rglob('*.pcm'):
            bmi.unlink()
        result = run(init + [opened(source), symbols(source, defer='blocked'),
            {'action': 'await-log', 'contains': 'Still waiting for module lock'},
            {'method': '$/cancelRequest', 'notify': True, 'params': {'id': '${REQUEST:blocked}'}},
            {'method': 'textDocument/didClose', 'notify': True,
             'params': {'textDocument': {'uri': source.as_uri()}}},
            opened(healthy), symbols(healthy, expect={'/result/0/name': 'healthy'}),
            {'action': 'await', 'request': 'blocked', 'allow_error': True,
             'expect': {'/error/code': -32800}}])
        result['live_lock_preserved'] = lock.exists() and lock.read_text() == owner
        report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
                  'warmup': warm, 'result': result}
        (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(result['outcome'], 'live lock preserved:', result['live_lock_preserved'])
        return 0 if result['outcome'] == 'pass' and result['live_lock_preserved'] else 1
    finally:
        if lock.exists() and lock.read_text() == owner:
            lock.unlink()


if __name__ == '__main__':
    raise SystemExit(main())
