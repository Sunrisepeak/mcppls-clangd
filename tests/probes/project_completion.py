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
import platform
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


class Resources:
    """Sample the owned engine only; do not infer descendant or hard RSS bounds."""
    def __init__(self):
        self.stop = threading.Event()
        self.samples = []
        self.errors = []
        self.thread = None

    def started(self, proc, deadline):
        if not platform.system() == 'Linux':
            self.errors.append('Linux /proc sampler unavailable on this platform')
            return
        ticks = os.sysconf('SC_CLK_TCK')
        began = time.monotonic()
        def sample():
            while not self.stop.is_set():
                try:
                    root = Path('/proc') / str(proc.pid)
                    stat = (root / 'stat').read_text().rsplit(')', 1)[1].split()
                    values = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines() if ':' in line)
                    self.samples.append({
                        'elapsed_ms': (time.monotonic() - began) * 1000,
                        'cpu_ms': (int(stat[11]) + int(stat[12])) * 1000 / ticks,
                        'rss_kib': int(values.get('VmRSS', '0 kB').split()[0]),
                        'high_water_rss_kib': int(values.get('VmHWM', '0 kB').split()[0]),
                    })
                except FileNotFoundError:
                    break
                except (OSError, ValueError, IndexError) as error:
                    self.errors.append(str(error))
                    break
                self.stop.wait(0.1)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()

    def finish(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        return {'interval_ms': 100, 'scope': 'Engine process only; sampled CPU lower bound, observed VmHWM, no descendants or hard memory ceiling.',
                'samples': self.samples, 'errors': self.errors,
                'sampler_stopped': self.thread is None or not self.thread.is_alive()}


def statistics(samples, requested):
    ordered = sorted(samples)
    return {'requested': requested, 'answered': len(samples),
            'missing': requested - len(samples), 'samples_ms': samples,
            'p50_ms': ordered[max(0, math.ceil(len(ordered) * .5) - 1)] if ordered else None,
            'p95_ms': ordered[max(0, math.ceil(len(ordered) * .95) - 1)] if ordered else None}


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
    parser.add_argument('--phases', action='store_true', help='Separate cold open, settled warm and edited requests; cold failures remain failures')
    parser.add_argument('--resources', action='store_true', help='Sample engine CPU/RSS using Linux /proc')
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
            phases = []
            completion = {'method': 'textDocument/completion', 'expected_symbols': args.expected,
                          'params': {'textDocument': {'uri': source.as_uri()}, 'position': position}}
            if args.phases:
                sequence.insert(3, completion)
                sequence.append(completion)
                phases += ['cold-open', 'settled-warm']
            for round_index in range(args.rounds):
                sequence += [
                    {'method': 'textDocument/didChange', 'notify': True, 'params': {
                        'textDocument': {'uri': source.as_uri(), 'version': round_index + 2},
                        'contentChanges': [{'text': text + f'\n// probe {start} {round_index}\n'}]}},
                    {'method': 'textDocument/completion', 'expected_symbols': args.expected,
                     'params': {'textDocument': {'uri': source.as_uri()}, 'position': position}},
                ]
                phases.append('edited')
                if args.phases:
                    sequence += [{'method': 'textDocument/documentSymbol',
                                  'params': {'textDocument': {'uri': source.as_uri()}}}, completion]
                    phases.append('settled-warm')
            manifest.write_text(json.dumps({'id': 'project-completion', 'project': str(project),
                'platform': replay.platform_name(), 'baseline': 'pass',
                'timeout_seconds': max(120, args.rounds * 10),
                'flags': ['--experimental-modules-support', '--background-index=false',
                          '--header-insertion=never', '-j=4'], 'sequence': sequence}))
            previous_trace = os.environ.get('CLANGD_TRACE')
            try:
                if args.trace:
                    os.environ['CLANGD_TRACE'] = str(args.trace.resolve())
                sampler = Resources() if args.resources else None
                try:
                    result = replay.replay(engine, manifest, process_started=sampler.started if sampler else None)
                finally:
                    resource_result = sampler.finish() if sampler else None
                result['requested_phases'] = phases
                if resource_result is not None:
                    result['resources'] = resource_result
                results.append(result)
            finally:
                if args.trace:
                    if previous_trace is None:
                        os.environ.pop('CLANGD_TRACE', None)
                    else:
                        os.environ['CLANGD_TRACE'] = previous_trace
        phase_samples = {}
        phase_requests = {}
        for result in results:
            for phase in result['requested_phases']:
                phase_requests[phase] = phase_requests.get(phase, 0) + 1
            for phase, response in zip(result['requested_phases'], result['responses']):
                phase_samples.setdefault(phase, []).append(response['elapsed_ms'])
        report = {'schema': 2, 'engine_sha256': digest(engine),
                  'source_sha256': hashlib.sha256(original).hexdigest(), 'position': position,
                  'expression': args.expression, 'starts': args.starts, 'rounds': args.rounds,
                  'phases': {phase: statistics(phase_samples.get(phase, []), count)
                             for phase, count in phase_requests.items()},
                  'all_semantic_requests_passed': all(r['outcome'] == 'pass' for r in results),
                  'raw_results': results,
                  'limits': ['Single context exploratory probe; no release performance gate claim.',
                             'Cold-open includes fallback responses: missing symbols fail, not excluded.',
                             'No insertion compilation or baseline speedup proof.',
                             'Settled-warm is AST-ready, not proof of a particular cache hit.']}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print('phases:', report['phases'], 'outcomes:', [r['outcome'] for r in results])
        return 0 if all(r['outcome'] == 'pass' for r in results) else 1
    finally:
        if source.read_bytes() != original:
            raise RuntimeError('project source changed during the probe')


if __name__ == '__main__':
    raise SystemExit(main())
