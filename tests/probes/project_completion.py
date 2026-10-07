#!/usr/bin/env python3
"""Measure semantic completion in an existing project using unsaved drafts.

Exploratory defaults are deliberately small. Release evidence requires the
plan's rounds/start counts and all contexts, actual insertion and baseline.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--before', required=True, help='unique source anchor before the probe')
    parser.add_argument('--expression', required=True)
    parser.add_argument('--expected', action='append', required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--starts', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--trace', type=Path, help='clangd trace path (one process only)')
    args = parser.parse_args()
    if args.trace and args.starts != 1:
        parser.error('trace requires a single process')
    if args.rounds < 1 or args.starts < 1:
        parser.error('rounds and starts must be positive')
    engine, source, project = replay.executable(args.engine), args.source.resolve(), args.project.resolve()
    original = source.read_bytes()
    base = original.decode()
    if base.count(args.before) != 1:
        parser.error('source anchor must appear exactly once')
    offset = base.index(args.before)
    prefix = base[:offset] + args.expression
    position = {'line': prefix.count('\n'),
                'character': len(prefix.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}
    text = prefix + ';\n' + base[offset:]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = args.output.with_suffix('.case.json')
    results = []
    try:
        for start in range(args.starts):
            sequence = [
                {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {}}},
                {'method': 'initialized', 'notify': True, 'params': {}},
                {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
                    'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
                {'method': 'textDocument/documentSymbol',
                 'params': {'textDocument': {'uri': source.as_uri()}}},
            ]
            for round_index in range(args.rounds):
                sequence += [
                    {'method': 'textDocument/didChange', 'notify': True, 'params': {
                        'textDocument': {'uri': source.as_uri(), 'version': round_index + 2},
                        'contentChanges': [{'text': text + f'\n// probe {start} {round_index}\n'}]}},
                    {'method': 'textDocument/completion', 'expected_symbols': args.expected,
                     'params': {'textDocument': {'uri': source.as_uri()}, 'position': position}},
                ]
            manifest.write_text(json.dumps({'id': 'project-completion', 'project': str(project),
                'platform': replay.platform_name(), 'baseline': 'pass',
                'timeout_seconds': max(120, args.rounds * 10),
                'flags': ['--experimental-modules-support', '--background-index=false',
                          '--header-insertion=never', '-j=4'], 'sequence': sequence}))
            previous_trace = os.environ.get('CLANGD_TRACE')
            try:
                if args.trace:
                    os.environ['CLANGD_TRACE'] = str(args.trace.resolve())
                results.append(replay.replay(engine, manifest))
            finally:
                if args.trace:
                    if previous_trace is None:
                        os.environ.pop('CLANGD_TRACE', None)
                    else:
                        os.environ['CLANGD_TRACE'] = previous_trace
        samples = [r['elapsed_ms'] for result in results for r in result['responses']]
        ordered = sorted(samples)
        report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
                  'source_sha256': hashlib.sha256(original).hexdigest(), 'position': position,
                  'expression': args.expression, 'starts': args.starts, 'rounds': args.rounds,
                  'samples_ms': samples,
                  'p95_ms': ordered[max(0, math.ceil(len(ordered) * .95) - 1)] if ordered else None,
                  'raw_results': results,
                  'limits': ['Single context exploratory probe; no release performance gate claim.',
                             'No insertion compilation or baseline speedup proof.']}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print('p95_ms:', report['p95_ms'], 'outcomes:', [r['outcome'] for r in results])
        return 0 if all(r['outcome'] == 'pass' for r in results) else 1
    finally:
        if source.read_bytes() != original:
            raise RuntimeError('project source changed during the probe')


if __name__ == '__main__':
    raise SystemExit(main())
