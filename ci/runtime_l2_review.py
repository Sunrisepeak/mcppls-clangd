"""Compare frozen runtime artifacts and record source-workload fingerprints."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path.cwd()
runner = os.environ['OKRUN']
records = []
for n in range(1, 6):
    for label, argv in (
        ('clang', [str(root / 'bench-clang')]),
        ('cc', [str(root / 'bench-cc')]),
        ('old', [runner, str(root / 'old/aarch64/bench.oke')]),
        ('current', [runner, str(root / 'current/aarch64/bench.oke')]),
    ):
        log = root / f'{label}-{n}.txt'
        with log.open('w') as stream:
            subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
        assert '-- done --' in log.read_text()
        values = {s.split()[1]: float(s.split()[2]) for s in log.read_text().splitlines() if s.startswith('bench ')}
        assert len(values) == 5
        records.append(dict(label=label, sequence=n, values=values, log=log.name))
        Path('timings.json').write_text(json.dumps(records, indent=2) + '\n')

fingerprints = {}
for label, argv in (
    ('clang', [str(root / 'audit-clang'), '--quick']),
    ('cc', [str(root / 'audit-cc'), '--quick']),
    ('image', [runner, os.environ['AUDIT_IMAGE'], '--quick']),
):
    result = subprocess.run(argv, text=True, capture_output=True, check=True, timeout=180)
    log = root / f'audit-{label}.txt'
    log.write_text(result.stdout + result.stderr)
    assert '-- done --' in result.stdout
    fingerprints[label] = [s for s in (result.stdout + result.stderr).splitlines() if s.startswith('audit ')]
    assert len(fingerprints[label]) == 3
Path('fingerprints.json').write_text(json.dumps(fingerprints, indent=2) + '\n')
print(json.dumps(fingerprints), flush=True)
summary = {}
for label in ('old', 'current', 'clang', 'cc'):
    summary[label] = {name: min(r['values'][name] for r in records if r['label'] == label)
                      for name in records[0]['values']}
Path('minimums.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary), flush=True)
