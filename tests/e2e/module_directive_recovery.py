#!/usr/bin/env python3
"""Raw clangd malformed-directive recovery, with real semantic edits and clean shutdown.

The two optional before/after baselines must actually time out. A forced kill
is recorded as a failed baseline, never successful candidate recovery. This
probe does not claim request-cancellation or missing-module deadlock repairs.
"""
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
    parser.add_argument('--baseline-engine', type=Path)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    baseline = replay.executable(args.baseline_engine) if args.baseline_engine else None
    project = args.workdir.resolve()
    project.mkdir(parents=True, exist_ok=True)
    variants = [
        ('import-dot', 'import hello.\n'),
        ('module-dot', 'export module hello.\n'),
        ('qualified-import', 'import a.b.\n'),
        ('import-comment', 'import hello. // unfinished\n'),
        ('import-next-line-semicolon', 'import hello.\n;\n'),
        ('global-fragment-module', 'module;\nexport module hello.\n'),
    ]
    results, controls = [], []
    for name, malformed in variants:
        root = project / name
        root.mkdir(exist_ok=True)
        source = root / 'Use.cpp'
        text = malformed + 'int discardedByRecovery;\n'
        source.write_text(text)
        uri = source.as_uri()
        (root / 'compile_commands.json').write_text(json.dumps([{
            'directory': str(root), 'file': str(source),
            'arguments': [str(clang), '-std=c++20', '-c', str(source)]}]))
        doc = {'textDocument': {'uri': uri}}
        opened = lambda version, contents: {'textDocument': {
            'uri': uri, 'languageId': 'cpp', 'version': version, 'text': contents}}
        fixed = 'int marker;\n'
        sequence = [
            {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
            {'method': 'initialized', 'notify': True, 'params': {}},
            {'method': 'textDocument/didOpen', 'notify': True, 'params': opened(1, text)},
            {'method': 'textDocument/documentSymbol', 'params': doc},
            {'method': 'textDocument/didChange', 'notify': True, 'params': {
                'textDocument': {'uri': uri, 'version': 2}, 'contentChanges': [{'text': fixed}]}},
            {'method': 'textDocument/documentSymbol', 'params': doc, 'expect': {'/result/0/name': 'marker'}},
            {'method': 'textDocument/didClose', 'notify': True, 'params': doc},
            {'method': 'textDocument/didOpen', 'notify': True, 'params': opened(3, fixed)},
            {'method': 'textDocument/documentSymbol', 'params': doc, 'expect': {'/result/0/name': 'marker'}},
            {'method': 'textDocument/didClose', 'notify': True, 'params': doc},
        ]
        manifest = root / 'case.json'
        case = {'id': name, 'platform': replay.platform_name(), 'baseline': 'hang',
                'project': '.', 'timeout_seconds': 10,
                'flags': ['--sync', '--background-index=false'], 'sequence': sequence}
        manifest.write_text(json.dumps(case, indent=2))
        result = replay.replay(engine, manifest)
        results.append(result)
        print(name, result['outcome'], result.get('detail', ''))
        if baseline and name in ('import-dot', 'module-dot'):
            control = {**case, 'timeout_seconds': 4}
            control_path = root / 'baseline.json'
            control_path.write_text(json.dumps(control, indent=2))
            controls.append(replay.replay(baseline, control_path))
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'results': results, 'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest() if baseline else None,
              'controls': controls, 'limits': ['No cancellation or missing-module deadlock claim.']}
    (project / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if all(r['outcome'] == 'pass' for r in results) and all(r['outcome'] == 'timeout' for r in controls) else 1


if __name__ == '__main__':
    raise SystemExit(main())
