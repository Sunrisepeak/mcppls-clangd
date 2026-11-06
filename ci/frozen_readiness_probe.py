#!/usr/bin/env python3
"""Validate stable-reap CPU measurement on a fixed delivered engine pair."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from prefetch_probe import environment, save, sha

ap = argparse.ArgumentParser()
ap.add_argument('--native', type=Path, required=True)
ap.add_argument('--bundle', type=Path, required=True)
ap.add_argument('--backend-variants', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
args.output = args.output.resolve()
args.backend_variants = args.backend_variants.resolve()
args.output.mkdir(exist_ok=False)
here = Path(__file__).resolve().parent
backend = json.loads((args.backend_variants / 'verified.json').read_text())
runner_row = next(row for row in backend['results'] if row['label'] == 'filtered')
runner = Path(runner_row['path']).resolve()
native, bundle = args.native.resolve(), args.bundle.resolve()
assert sha(native) == '176b8da15867a90edf3059ba4ad384920953839477df49f8e2249cce825f3c72'
assert sha(bundle) == '72fe2ebb7558ff2bdd5dae2f1bccf65ae2357dff6bcf21d73258a2991bde0e25'
assert sha(runner) == runner_row['sha256']
resource = native.parent.parent / 'lib/clang/23'
resources = {str(p.relative_to(resource)): sha(p) for p in resource.rglob('*') if p.is_file()}
assert len(resources) == 303
inputs = {str(p): sha(p) for p in [native, bundle, runner]}
order = ['native', 'image', 'image', 'native']
save(args.output / 'plan.json', dict(order=order, inputs=inputs,
     purpose='Fixed N/F/F/N on unchanged delivered engines, one cold/three warm each; stable-reap measurement on both.',
     stopping='No extra cases after results. Semantic/identity/accounting failure aborts. Original1.15 ratio limits retained; diagnostic only.',
     qualification=False))
env = environment(args.output / 'loader', 'default')
seed = subprocess.run([str(runner), str(bundle), '--version'], env=env, text=True, capture_output=True, timeout=30)
save(args.output / 'seed.json', dict(exit=seed.returncode, stdout=seed.stdout, stderr=seed.stderr))
assert seed.returncode == 0
until = time.monotonic() + 30
while True:
    markers = list((args.output / 'loader/placed').rglob('*.sealing'))
    snapshots = list((args.output / 'loader/placed').rglob('*.oksnap'))
    if len(markers) == len(snapshots) == 1 and markers[0].read_text().strip() == 'made':
        break
    assert time.monotonic() < until
    time.sleep(.02)
snapshot_hash = sha(snapshots[0])
rows = []
driver_identities = set()
for index, lane in enumerate(order):
    case = args.output / f'case{index}-{lane}'
    case.mkdir()
    prefix = [str(native)] if lane == 'native' else [str(runner), str(bundle)]
    prefix.append('--resource-dir=' + str(resource))
    command = [sys.executable, str(here / 'ready_role_observer.py'), 'observe',
               '--source', str(here / 'warm_prime.py'), '--output', str(case / 'roles'), '--',
               '--label', lane, '--workdir', str(case / 'work'), '--out', str(case / 'result.json'),
               '--sessions', '3', '--'] + prefix
    with (case / 'harness.log').open('w') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    assert result.returncode == 0, (index, lane, 'workload or observation failed')
    report = json.loads((case / 'result.json').read_text())
    assert report['measurement_version'] == 3 and report['units'] == 304 and len(report['probes']) == 3
    assert len(report['sessions']) == 4 and report['sessions'][0]['workers'] == 176
    for session_index, session in enumerate(report['sessions']):
        assert session['ok'] and session['cpu_sample']['valid']
        text = (case / 'work' / f'session-{session_index}-{session["kind"]}.log').read_text()
        commands = [line.split(' ', 1)[0] for line in text.splitlines() if ' -resource-dir=' in line]
        assert len(commands) == 3
        driver_identities.update(hashlib.sha256(command.encode()).hexdigest() for command in commands)
    row = dict(index=index, lane=lane, report=str(case / 'result.json'),
               cold_cpu=report['sessions'][0]['cpu_seconds'], warm_cpu=report['warm']['cpu_seconds'])
    rows.append(row)
    save(args.output / 'progress.json', rows)
    print(json.dumps(row), flush=True)
assert len(driver_identities) == 1
pairs = []
for image_index, native_index in [(1, 0), (2, 3)]:
    output = args.output / f'accept-{image_index}-{native_index}.json'
    result = subprocess.run([sys.executable, str(here / 'warm_prime_accept.py'), '--platform', 'linux-x64',
                             '--native', rows[native_index]['report'], '--image', rows[image_index]['report'],
                             '--out', str(output)], capture_output=True, text=True)
    assert result.returncode in (0, 1)
    report = json.loads(output.read_text())
    pairs.append(dict(image=image_index, native=native_index, accepted=report['accepted'],
                      ratios=report['ratios'], failures=report['failures']))
assert all(sha(Path(path)) == digest for path, digest in inputs.items())
assert all(sha(resource / path) == digest for path, digest in resources.items())
assert sha(snapshots[0]) == snapshot_hash
save(args.output / 'verified.json', dict(valid=True, qualification=False, rows=rows, pairs=pairs,
     driver_identities=list(driver_identities), inputs_unchanged=True, resources_unchanged=True))
print(json.dumps(dict(valid=True, pairs=pairs)), flush=True)
