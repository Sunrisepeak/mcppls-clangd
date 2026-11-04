"""Profile frozen engine candidates; these observations do not qualify a release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import sys


parser = argparse.ArgumentParser(description=__doc__)
for name in ('native', 'image', 'runner', 'profiler'):
    parser.add_argument('--' + name, required=True, type=lambda value: Path(value).resolve())
parser.add_argument('--std-args', default='')
args = parser.parse_args()
root = Path('diagnostic').resolve()
root.mkdir()
probe = Path('ci/warm_prime.py').resolve()
identities = {name: dict(path=str(path), bytes=path.stat().st_size,
                        sha256=hashlib.file_digest(path.open('rb'), 'sha256').hexdigest())
              for name, path in [('native', args.native), ('image', args.image), ('runner', args.runner),
                                 ('profiler', args.profiler), ('probe', probe),
                                 ('fixture', Path('ci/fixtures/ux-mcpp-modules.json'))]}
identities['scope'] = ('Run41807943117/head6fc37a8 candidates with source-built public platform0.23.5 tools. '
                       'Unchanged304-unit graph. Profiled sessions have instrumentation overhead and '
                       'supply no acceptance ratios. No source rebuild, ledger promotion or release qualification.')
identities['host'] = dict(uname=list(os.uname()), cpu_count=os.cpu_count())
(root / 'inputs.json').write_text(json.dumps(identities, indent=2) + '\n')
for lane in ('native', 'image', 'image-profile'):
    out = root / lane
    out.mkdir()
    env = os.environ.copy()
    for key in ('OKRUN_PROF', 'OKRUN_SNAPSHOT'):
        env.pop(key, None)
    env['KAL_RESOURCES'] = 'balanced'
    for key, name in [('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                      ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'state'),
                      ('XDG_RUNTIME_DIR', 'runtime'), ('TMPDIR', 'tmp')]:
        directory = out / name
        directory.mkdir(mode=0o700)
        env[key] = str(directory)
    if lane == 'image-profile':
        profiles = out / 'profiles'
        profiles.mkdir()
    command = [sys.executable, str(probe), '--label', lane, '--workdir', str(out / 'work'),
               '--out', str(out / 'result.json'), '--sessions', '0',
               '--std-args=' + args.std_args, '--']
    if lane == 'native':
        command += [str(args.native)]
    else:
        command += [str(args.runner)]
        if lane == 'image-profile':
            # CLI configuration is process-local. The child worker command
            # receives neither this option nor an OKRUN_PROF environment value.
            command += ['--prof=phases,samples=500:' + str(profiles)]
        command += [str(args.image)]
    start = time.monotonic()
    with (out / 'driver.log').open('w') as log:
        result = subprocess.run(command, env=env, cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=1500)
    facts = dict(command=command, exit=result.returncode, wall_seconds=time.monotonic() - start)
    (out / 'invocation.json').write_text(json.dumps(facts, indent=2) + '\n')
    result.check_returncode()
    observed = json.loads((out / 'result.json').read_text())
    assert observed['units'] == 304 and all(session['ok'] for session in observed['sessions'])
    assert len(observed['sessions']) == 1 and observed['sessions'][0]['workers'] == 176
    print(json.dumps(dict(lane=lane, sessions=observed['sessions'])), flush=True)
    if lane == 'image-profile':
        count = len(list(profiles.glob('okprof-*.json')))
        assert 1 <= count <= 3, f'parent and optional snapshot helper only, not 176 workers: {count}'
        (out / 'profile-scope.json').write_text(json.dumps(dict(profiles=count, workers=176,
            scope='Parent CLI-only sampler; no profiler environment inherited by supervised workers. Instrumented timing is not acceptance.')) + '\n')
        with (out / 'profile.txt').open('w') as log:
            subprocess.run([str(args.profiler), 'report', str(profiles)], check=True, stdout=log)
