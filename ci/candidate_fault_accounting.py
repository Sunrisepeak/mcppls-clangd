"""Compare readiness sampling with whole-run kernel accounting on frozen inputs."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys


parser = argparse.ArgumentParser(description=__doc__)
for name in ('native', 'image', 'runner'):
    parser.add_argument('--' + name, required=True, type=lambda value: Path(value).resolve())
parser.add_argument('--std-args', default='')
args = parser.parse_args()
root = Path('fault-accounting').resolve()
root.mkdir()
probe = Path('ci/warm_prime.py').resolve()


def measured(command, env, cwd, log):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with log.open('w') as output:
        process = subprocess.run(command, env=env, cwd=cwd, stdout=output,
                                 stderr=subprocess.STDOUT, timeout=1500)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    process.check_returncode()
    return dict(user_seconds=after.ru_utime - before.ru_utime,
                system_seconds=after.ru_stime - before.ru_stime,
                minor_faults=after.ru_minflt - before.ru_minflt,
                major_faults=after.ru_majflt - before.ru_majflt)


# A middle process reaps its own child: prove the outer kernel total sees
# faults of a descendant too short-lived for a periodic process-tree sample.
touch = "import os; b=bytearray(64*1024*1024); b[::os.sysconf('SC_PAGESIZE')]=bytes([1])*len(b[::os.sysconf('SC_PAGESIZE')])"
middle = 'import subprocess,sys; subprocess.run([sys.executable,"-c",' + repr(touch) + '],check=True)'
control = measured([sys.executable, '-c', middle], os.environ.copy(), root, root / 'control.log')
control['minimum_touched_pages'] = 64 * 1024 * 1024 // os.sysconf('SC_PAGESIZE')
assert control['minor_faults'] >= control['minimum_touched_pages'], control
(root / 'control.json').write_text(json.dumps(control, indent=2) + '\n')
for lane in ('native', 'image'):
    out = root / lane
    out.mkdir()
    env = os.environ.copy()
    env.pop('OKRUN_PROF', None)
    env.pop('OKRUN_SNAPSHOT', None)
    env['KAL_RESOURCES'] = 'balanced'
    for key, name in [('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                      ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'state'),
                      ('XDG_RUNTIME_DIR', 'runtime'), ('TMPDIR', 'tmp')]:
        directory = out / name
        directory.mkdir(mode=0o700)
        env[key] = str(directory)
    command = [sys.executable, str(probe), '--label', lane, '--workdir', str(out / 'work'),
               '--out', str(out / 'result.json'), '--sessions', '3', '--std-args=' + args.std_args, '--']
    command += [str(args.native)] if lane == 'native' else [str(args.runner), str(args.image)]
    whole = measured(command, env, out, out / 'driver.log')
    result = json.loads((out / 'result.json').read_text())
    assert result['units'] == 304 and len(result['sessions']) == 4
    assert all(session['ok'] and session['waited_usage'] for session in result['sessions'])
    assert all(session['modules_built'] == 0 for session in result['sessions'][1:])
    for session in result['sessions']:
        usage = session['waited_usage']
        assert usage['minor_faults'] >= 0 and usage['major_faults'] >= 0
        assert usage['user_seconds'] + usage['system_seconds'] > 0
    waited_faults = sum(session['waited_usage']['minor_faults'] + session['waited_usage']['major_faults']
                        for session in result['sessions'])
    assert whole['minor_faults'] + whole['major_faults'] >= waited_faults
    observation = dict(command=command, sessions=result['sessions'], kernel_whole_run=whole,
                       complete_engine_waited_faults=waited_faults,
                       scope='Kernel total includes the Python harness, complete engine lifetime and waited descendants. '
                             'Each session separately records its engine-only complete-lifetime kernel counters, excluding Python. '
                             'The original sample is at readiness. These differ in boundary; neither the gate '
                             'nor the original probe is changed by this diagnostic.')
    (out / 'observed.json').write_text(json.dumps(observation, indent=2) + '\n')
    print(json.dumps(observation), flush=True)
