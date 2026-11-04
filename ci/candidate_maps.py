"""Observe idle native/image mappings before any project or module is opened."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import psutil


parser = argparse.ArgumentParser(description=__doc__)
for name in ('native', 'image', 'runner'):
    parser.add_argument('--' + name, required=True, type=lambda value: Path(value).resolve())
args = parser.parse_args()
root = Path('mapping-observations').resolve()
root.mkdir()
for lane in ('native', 'image'):
    out = root / lane
    out.mkdir()
    env = os.environ.copy()
    env.pop('OKRUN_PROF', None)
    env.pop('OKRUN_SNAPSHOT', None)
    env['KAL_RESOURCES'] = 'balanced'
    for key, name in [('XDG_CACHE_HOME', 'cache'), ('XDG_RUNTIME_DIR', 'runtime'), ('TMPDIR', 'tmp')]:
        directory = out / name
        directory.mkdir(mode=0o700)
        env[key] = str(directory)
    command = [str(args.native)] if lane == 'native' else [str(args.runner), str(args.image)]
    command += ['--experimental-modules-support', '--background-index=false', '-j=4', '--log=info']
    with (out / 'stderr.log').open('w') as log:
        process = subprocess.Popen(command, env=env, cwd=out, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log)
        try:
            time.sleep(1)
            assert process.poll() is None, 'engine did not remain alive before initialize'
            observed = psutil.Process(process.pid)
            facts = dict(command=command, pid=process.pid, cpu_times=observed.cpu_times()._asdict(),
                         memory=observed.memory_info()._asdict(),
                         scope='Idle before LSP initialize or opening a project; no sampling or call profiling.')
            for label, options in [('resident', ['-w', '-resident']), ('summary', ['-summary'])]:
                with (out / (label + '.txt')).open('w') as report:
                    result = subprocess.run(['vmmap', *options, str(process.pid)], stdout=report,
                                            stderr=subprocess.STDOUT, timeout=30)
                facts[label + '_exit'] = result.returncode
            (out / 'observed.json').write_text(json.dumps(facts, indent=2) + '\n')
            print(json.dumps(facts), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
