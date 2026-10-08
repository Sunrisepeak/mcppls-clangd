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
import re
import threading
import time
from pathlib import Path
from completion_insertion import apply, compile_insertion

def completion_origins(stderr, count):
    """Keep one engine summary per request; missing/ambiguous evidence fails closed."""
    matches = re.findall(r"Code complete: (\d+) results from Sema, (\d+) from Index, "
                         r"(\d+) matched, (\d+) from identifiers,", stderr)
    if len(matches) != count:
        return [None] * count
    return [dict(zip(('sema', 'index', 'matched', 'identifiers'), map(int, row)))
            for row in matches]


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
        self.began = time.monotonic()
        if not platform.system() == 'Linux':
            self.errors.append('Linux /proc sampler unavailable on this platform')
            return
        def sample():
            while not self.stop.is_set():
                try:
                    self.samples.append(self.read(proc))
                except FileNotFoundError:
                    break
                except (OSError, ValueError, IndexError) as error:
                    self.errors.append(str(error))
                    break
                self.stop.wait(0.1)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()

    def read(self, proc):
        sample_started_ns = time.monotonic_ns()
        root = Path('/proc') / str(proc.pid)
        stat = (root / 'stat').read_text().rsplit(')', 1)[1].split()
        values = dict(line.split(':', 1) for line in (root / 'status').read_text().splitlines() if ':' in line)
        return {'monotonic_ns': time.monotonic_ns(),
                'sample_started_monotonic_ns': sample_started_ns,
                'elapsed_ms': (time.monotonic() - self.began) * 1000,
                'cpu_ms': (int(stat[11]) + int(stat[12])) * 1000 / os.sysconf('SC_CLK_TCK'),
                'rss_kib': int(values.get('VmRSS', '0 kB').split()[0]),
                'high_water_rss_kib': int(values.get('VmHWM', '0 kB').split()[0])}

    def snapshot(self, proc, method):
        if platform.system() != 'Linux' or method != 'textDocument/completion':
            return None
        try:
            return self.read(proc)
        except (OSError, ValueError, IndexError) as error:
            self.errors.append(str(error))
            return {'error': str(error)}

    def finish(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        return {'interval_ms': 100, 'clock': 'time.monotonic_ns; shared with replay request spans', 'scope': 'Engine process only; periodic CPU coverage is a lower bound, completion boundary snapshots delimit CPU windows; observed VmHWM, no descendants or hard memory ceiling.',
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
    parser.add_argument('--draft-source', type=Path,
                        help='Alternate unsaved base text; retains the actual source URI and CDB')
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--before', help='unique source anchor before the probe')
    parser.add_argument('--expression')
    parser.add_argument('--expected', action='append')
    parser.add_argument('--context-file', type=Path, help='Legal draft context JSON; enables non-aborting semantic accounting')
    parser.add_argument('--compile-insertions', action='store_true', help='Compile every actual selected insertion after timing completes')
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--starts', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phases', action='store_true', help='Separate cold open, settled warm and edited requests; cold failures remain failures')
    parser.add_argument('--settled-only', action='store_true', help='With phases, request completions only after AST readiness; cold completion is explicitly not measured')
    parser.add_argument('--resources', action='store_true', help='Sample engine CPU/RSS using Linux /proc')
    parser.add_argument('--settled-index-log', help='Wait for this literal index log before settled phases; each settled reply must actually match an index symbol')
    parser.add_argument('--engine-flag', action='append', default=[],
                        help='Additional engine argument retained in the replay manifest')
    parser.add_argument('--trace', type=Path, help='clangd trace path (one process only)')
    args = parser.parse_args()
    if args.settled_only and not args.phases:
        parser.error('settled-only requires phases')
    if args.settled_index_log and not args.phases:
        parser.error('settled-index-log requires phases')
    if args.trace and args.starts != 1:
        parser.error('trace requires a single process')
    if args.rounds < 1 or args.starts < 1:
        parser.error('rounds and starts must be positive')
    engine, source, project = replay.executable(args.engine), args.source.resolve(), args.project.resolve()
    original = source.read_bytes()
    base_bytes = args.draft_source.read_bytes() if args.draft_source else original
    base = base_bytes.decode()
    context = json.loads(args.context_file.read_text()) if args.context_file else None
    if context:
        args.before = context['before']
        args.expression = context['prefix']
        args.expected = context.get('expected', [])
    elif not args.before or args.expression is None or not args.expected:
        parser.error('provide context-file or before/expression/expected')
    if base.count(args.before) != 1:
        parser.error('source anchor must appear exactly once')
    offset = base.index(args.before)
    prefix = base[:offset] + args.expression
    position = {'line': prefix.count('\n'),
                'character': len(prefix.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}
    text = prefix + (context['suffix'] if context else ';\n') + base[offset + (len(args.before) if context and context.get('replace_anchor') else 0):]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = args.output.with_suffix('.case.json')
    engine_flags = ['--experimental-modules-support', '--background-index=false',
                    '--header-insertion=never', '-j=4', *args.engine_flag]
    results = []
    try:
        for start in range(args.starts):
            sequence = [
                {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {
                    'textDocument': {'completion': {'completionItem': {'snippetSupport': True}}}} if context else {}}},
                {'method': 'initialized', 'notify': True, 'params': {}},
                {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
                    'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
                {'method': 'textDocument/documentSymbol',
                 'params': {'textDocument': {'uri': source.as_uri()}}},
            ]
            phases = []
            phase_drafts = []
            completion = {'method': 'textDocument/completion', 'expected_symbols': args.expected,
                          'params': {'textDocument': {'uri': source.as_uri()}, 'position': position}}
            if context:
                completion.pop('expected_symbols')
                completion['expect'] = {'/jsonrpc': '2.0'}
            if args.phases:
                if not args.settled_only:
                    sequence.insert(3, completion)
                    phases.append('cold-open')
                    phase_drafts.append(text)
                if args.settled_index_log:
                    sequence.append({'action': 'await-log', 'contains': args.settled_index_log})
                sequence.append(completion)
                phases.append('settled-warm')
                phase_drafts.append(text)
            for round_index in range(args.rounds):
                # Independent starts use the same thirty distinct edit inputs.
                # Every round still changes bytes. This permits exact-byte
                # insertion proofs to be shared across starts, without any
                # token/comment normalization of the server's actual drafts.
                edit_label = str(round_index) if context else f'{start} {round_index}'
                sequence += [
                    {'method': 'textDocument/didChange', 'notify': True, 'params': {
                        'textDocument': {'uri': source.as_uri(), 'version': round_index + 2},
                        'contentChanges': [{'text': text + f'\n// probe {edit_label}\n'}]}},
                    completion,
                ]
                phases.append('edited')
                phase_drafts.append(text + f'\n// probe {edit_label}\n')
                if args.phases:
                    sequence += [{'method': 'textDocument/documentSymbol',
                                  'params': {'textDocument': {'uri': source.as_uri()}}}, completion]
                    phases.append('settled-warm')
                    phase_drafts.append(text + f'\n// probe {edit_label}\n')
            manifest.write_text(json.dumps({'id': 'project-completion', 'project': str(project),
                'platform': replay.platform_name(), 'baseline': 'pass',
                'timeout_seconds': max(120, args.rounds * 10),
                'flags': engine_flags, 'sequence': sequence}))
            previous_trace = os.environ.get('CLANGD_TRACE')
            try:
                if args.trace:
                    os.environ['CLANGD_TRACE'] = str(args.trace.resolve())
                sampler = Resources() if args.resources else None
                try:
                    result = replay.replay(engine, manifest, process_started=sampler.started if sampler else None,
                                           request_snapshot=sampler.snapshot if sampler else None)
                finally:
                    resource_result = sampler.finish() if sampler else None
                result['requested_phases'] = phases
                if context:
                    answers = [r for r in result['raw_responses'] if r['method'] == 'textDocument/completion']
                    origins = completion_origins(result.get('stderr', ''), len(answers))
                    result['context_answers'] = []
                    for index, (phase, answer) in enumerate(zip(phases, answers)):
                        payload = answer['reply'].get('result')
                        items = payload.get('items', []) if isinstance(payload, dict) else payload or []
                        names = {re.split(r'[(<]', item.get('filterText', item.get('label', '')))[0].strip() for item in items}
                        missing = sorted(set(args.expected) - names)
                        require_sema = context.get('require_sema', False)
                        origin = origins[index]
                        semantic_origin_failed = bool(require_sema and
                            (origin is None or origin['sema'] == 0))
                        index_origin_failed = bool(args.settled_index_log and phase != 'cold-open' and
                            (origin is None or origin['index'] == 0 or origin['matched'] == 0))
                        # Identifier fallback items can compile while only guessing a spelling.
                        typed_names = {re.split(r'[(<]', item.get('filterText', item.get('label', '')))[0].strip()
                                       for item in items if item.get('kind') not in (None, 1)}
                        untyped = sorted(set(args.expected) - typed_names) if require_sema else []
                        polluted = sorted(set(context.get('forbidden', [])) & names)
                        empty_failure = bool(context.get('expect_empty') and items)
                        draft = phase_drafts[index]
                        result['context_answers'].append({'phase': phase, 'elapsed_ms': answer['elapsed_ms'],
                            'started_monotonic_ns': answer['started_monotonic_ns'],
                            'completed_monotonic_ns': answer['completed_monotonic_ns'],
                            'resource_snapshots': answer.get('resource_snapshots'),
                            'missing': missing, 'polluted': polluted, 'unexpected_nonempty': empty_failure,
                            'semantic_pass': not (missing or polluted or empty_failure or semantic_origin_failed or index_origin_failed or untyped or 'error' in answer['reply']),
                            'origin': origin, 'semantic_origin_failed': semantic_origin_failed,
                            'index_origin_failed': index_origin_failed,
                            'untyped_expected': untyped,
                            'isIncomplete': payload.get('isIncomplete') if isinstance(payload, dict) else None,
                            'items': items, 'draft': draft})
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
            for phase, response in zip(result['requested_phases'], result.get('context_answers', result['responses'])):
                phase_samples.setdefault(phase, []).append(response['elapsed_ms'])
        semantic_counts = {}
        for result in results:
            for answer in result.get('context_answers', []):
                counts = semantic_counts.setdefault(answer['phase'], {'answered': 0, 'passed': 0, 'failed': 0})
                counts['answered'] += 1
                counts['passed' if answer['semantic_pass'] else 'failed'] += 1
        insertions = []
        if args.compile_insertions:
            if not context:
                parser.error('compile-insertions requires legal context-file')
            # No compiler subprocess runs during engine latency collection.
            for start, result in enumerate(results):
                for index, answer in enumerate(result.get('context_answers', [])):
                    for name in args.expected:
                        candidates = [item for item in answer['items'] if re.split(r'[(<]', item.get('filterText', item.get('label', '')))[0].strip() == name]
                        preferred = context.get('kind', {}).get(name)
                        if preferred is not None:
                            candidates = [item for item in candidates if item.get('kind') == preferred]
                        proof = {'start': start, 'answer': index, 'phase': answer['phase'], 'symbol': name}
                        try:
                            if not candidates:
                                raise ValueError('no candidate of required symbol/kind')
                            item = candidates[0]
                            proof['item'] = item
                            applied = apply(answer['draft'], position, item, context.get('bindings', {}).get(name, {}))
                            proof.update(compile_insertion(project, source, applied))
                        except (ValueError, OSError) as error:
                            proof['error'] = str(error)
                        insertions.append(proof)
        report = {'schema': 4 if context else 2, 'engine_sha256': digest(engine), 'engine_flags': engine_flags,
                  'source_sha256': hashlib.sha256(original).hexdigest(), 'position': position,
                  'draft_source_sha256': hashlib.sha256(base_bytes).hexdigest(),
                  'draft_source': str(args.draft_source.resolve()) if args.draft_source else None,
                  'expression': args.expression, 'starts': args.starts, 'rounds': args.rounds,
                  'cold_completion_requested': args.phases and not args.settled_only,
                  'measurement_mode': 'ast-ready-only' if args.settled_only else ('cold-warm-edited' if args.phases else 'edited-only'),
                  'phases': {phase: statistics(phase_samples.get(phase, []), count)
                             for phase, count in phase_requests.items()},
                  'all_semantic_requests_passed': all(r['outcome'] == 'pass' and all(a['semantic_pass'] for a in r.get('context_answers', [])) for r in results),
                  'context': context, 'insertions': insertions,
                  'semantic_counts': semantic_counts,
                  'all_insertions_compiled': bool(insertions) and all(p.get('exit_code') == 0 for p in insertions),
                  'raw_results': results,
                  'limits': ['Single context probe; aggregate context/baseline gate requires separate matrix evidence.',
                             'Cold-open includes fallback responses; semantic contexts require per-request Sema evidence and typed expected items.',
                             'Insertion compilation is opt-in; no baseline speedup proof in this individual report.',
                             'Settled-warm is AST-ready, not proof of a particular cache hit.']}
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print('phases:', report['phases'], 'outcomes:', [r['outcome'] for r in results])
        return 0 if report['all_semantic_requests_passed'] and (not args.compile_insertions or report['all_insertions_compiled']) else 1
    finally:
        if source.read_bytes() != original:
            raise RuntimeError('project source changed during the probe')


if __name__ == '__main__':
    raise SystemExit(main())
