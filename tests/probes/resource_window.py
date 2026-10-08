"""Summarize observed engine resources in a verified stable request window.

Periodic RSS observations and main-process CPU counters exclude descendants.
This module does not certify a memory ceiling or complete release qualification.
"""
import math


def stable_window(raw):
    if raw.get('outcome') != 'pass' or not raw.get('readers_stopped'):
        raise ValueError('replay/readers did not complete successfully')
    resources = raw.get('resources', {})
    if resources.get('errors') or not resources.get('sampler_stopped'):
        raise ValueError('resource sampling failed or remains active')
    tick = resources.get('cpu_tick_ms')
    if not isinstance(tick, (int, float)) or not math.isfinite(tick) or tick <= 0:
        raise ValueError('CPU counter resolution is missing')
    answers = raw.get('context_answers', [])
    if not answers or any(a.get('semantic_pass') is not True for a in answers):
        raise ValueError('semantic failures cannot qualify a resource window')
    if any(a.get('phase') not in ('cold-open', 'settled-warm', 'edited') for a in answers):
        raise ValueError('unknown request phase')
    stable = [a for a in answers if a['phase'] in ('settled-warm', 'edited')]
    if not stable or stable[0]['phase'] != 'settled-warm':
        raise ValueError('stable window must begin with an AST-ready request')
    snapshots = []
    previous_end = None
    for answer in stable:
        boundary = answer.get('resource_snapshots') or {}
        start, end = boundary.get('start', {}), boundary.get('end', {})
        try:
            ordered = (start['sample_started_monotonic_ns'] <= start['monotonic_ns']
                       <= answer['started_monotonic_ns'] <= answer['completed_monotonic_ns']
                       <= end['sample_started_monotonic_ns'] <= end['monotonic_ns'])
            if not ordered or previous_end is not None and start['sample_started_monotonic_ns'] < previous_end:
                raise ValueError('snapshot/request clocks overlap or are out of order')
            for sample in (start, end):
                if any(not isinstance(sample[k], (int, float)) or not math.isfinite(sample[k])
                       or sample[k] < 0 for k in ('cpu_ms', 'rss_kib')):
                    raise ValueError('invalid CPU/RSS counter')
            if end['cpu_ms'] < start['cpu_ms'] or snapshots and start['cpu_ms'] < snapshots[-1]['cpu_ms']:
                raise ValueError('CPU counters moved backwards')
            previous_end = end['monotonic_ns']
        except KeyError as error:
            raise ValueError('request boundary snapshot is missing') from error
        snapshots.extend((start, end))
    first, last = snapshots[0], snapshots[-1]
    periodic = [s for s in resources.get('samples', [])
                if first['monotonic_ns'] <= s.get('sample_started_monotonic_ns', -1)
                <= s.get('monotonic_ns', -1) <= last['sample_started_monotonic_ns']]
    if any(not isinstance(s.get('rss_kib'), (int, float))
           or not math.isfinite(s['rss_kib']) or s['rss_kib'] < 0 for s in periodic):
        raise ValueError('invalid periodic RSS observation')
    rss = sorted(s['rss_kib'] for s in snapshots + periodic)
    delta = last['cpu_ms'] - first['cpu_ms']
    # utime and stime each have one-tick endpoint quantization uncertainty.
    uncertainty = 2 * tick
    return {'stable_requests': len(stable),
            'start_monotonic_ns': first['sample_started_monotonic_ns'],
            'end_monotonic_ns': last['monotonic_ns'],
            'cpu_ms': delta, 'cpu_lower_ms': max(0, delta - uncertainty),
            'cpu_upper_ms': delta + uncertainty,
            'cpu_ms_per_completion': delta / len(stable),
            'rss_observations': len(rss), 'rss_p95_kib': rss[math.ceil(.95 * len(rss)) - 1],
            'rss_observed_max_kib': max(rss),
            'scope': 'Observed stable main-process window including intervening AST work; no descendants or hard RSS ceiling.'}
