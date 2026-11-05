#!/usr/bin/env python3
"""Bounded attached kernel-CPU observation of a frozen, unmodified engine."""
from pathlib import Path
import argparse, collections, gzip, hashlib, json, os, re, select
import signal, subprocess, sys, time

from ready_role_observer import stat


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class AttachedPerf:
    def __init__(self, directory, identity, perf, sudo):
        self.directory, self.identity = directory, identity
        self.prefix = ['sudo', '-n', perf] if sudo else [perf]
        self.sudo = sudo
        self.data = directory / 'perf.data'
        self.ctl_path, self.ack_path = directory / 'ctl', directory / 'ack'
        for path in (self.ctl_path, self.ack_path):
            os.mkfifo(path, 0o600)
        self.ctl = os.open(self.ctl_path, os.O_RDWR | os.O_NONBLOCK)
        self.ack = os.open(self.ack_path, os.O_RDWR | os.O_NONBLOCK)
        self.log = (directory / 'perf-record.log').open('w')
        self.command = self.prefix + ['record', '-e', 'cpu-clock:k', '-F', '499',
            '--strict-freq', '-g', '-k', 'mono', '--no-buildid-cache', '-m', '1024',
            '--max-size=128M', '--delay=-1',
            f'--control=fifo:{self.ctl_path},{self.ack_path}',
            '-p', str(identity['pid']), '-o', str(self.data)]
        assert stat(identity['pid'])['birth'] == identity['birth']
        self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT)
        self.ack_bytes = b''
        self.enabled_ns = None
        self.closed = False

    def enable(self):
        os.write(self.ctl, b'enable\n')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('perf exited before acknowledging enable')
            if select.select([self.ack], [], [], .1)[0]:
                self.ack_bytes += os.read(self.ack, 4096)
                if self.ack_bytes.strip(b'\0\r\n ') == b'ack':
                    assert stat(self.identity['pid'])['birth'] == self.identity['birth']
                    self.enabled_ns = time.monotonic_ns()
                    return
        raise TimeoutError('perf enable acknowledgement')

    def finish(self):
        self.close()
        assert self.process.returncode == 0, 'perf collection failed'
        assert self.data.is_file() and not self.data.is_symlink()
        report = dict(command=self.command, root=self.identity,
                      enable_ack_hex=self.ack_bytes.hex(), exit=self.process.returncode,
                      enabled_ns=self.enabled_ns,
                      data_bytes=self.data.stat().st_size, data_sha256=digest(self.data))
        save(self.directory / 'perf-collection.json', report)
        assert 0 < report['data_bytes'] < 128 * 1024 * 1024
        return report

    def close(self):
        if self.closed:
            return
        if self.process.poll() is None:
            os.write(self.ctl, b'stop\n')
        self.process.wait(timeout=15)
        self.log.close()
        os.close(self.ctl)
        os.close(self.ack)
        self.closed = True
        if self.sudo and self.data.is_file() and not self.data.is_symlink():
            subprocess.run(['sudo', '-n', 'chown', f'{os.getuid()}:{os.getgid()}',
                            str(self.data)], check=True)

    def decode(self):
        output = self.directory / 'events.txt'
        command = self.prefix + ['script', '-i', str(self.data), '--ns',
             '--show-task-events', '--show-lost-events',
             '-F', 'comm,pid,tid,time,event,ip,sym,dso,period']
        with output.open('w') as stream, (self.directory / 'perf-decode.log').open('w') as errors:
            subprocess.run(command, stdout=stream, stderr=errors, check=True, timeout=60)
        return output


def analyze(path, root_pid, forbidden=()):
    text = path.read_text()
    assert 'PERF_RECORD_LOST' not in text, 'lost perf records'
    forks = [tuple(map(int, groups)) for groups in re.findall(
        r'PERF_RECORD_FORK\((\d+):(\d+)\):\((\d+):(\d+)\)', text)]
    exits = [tuple(map(int, groups)) for groups in re.findall(
        r'PERF_RECORD_EXIT\((\d+):(\d+)\):\((\d+):(\d+)\)', text)]
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, tid, ppid, ptid in forks:
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    assert any(pid == root_pid and tid == root_pid for pid, tid, _, _ in exits), 'root exit not captured'
    sample = re.compile(r'^.*?\s(\d+)/(\d+)\s+(\d+\.\d+):\s+(\d+)\s+cpu-clock:k:\s*$', re.M)
    matches = list(sample.finditer(text))
    assert matches, 'no kernel CPU samples'
    counts = collections.Counter()
    leaf = {'root': collections.Counter(), 'descendants': collections.Counter()}
    inclusive = {'root': collections.Counter(), 'descendants': collections.Counter()}
    unresolved = collections.Counter()
    pids = collections.Counter()
    samples = []
    for index, match in enumerate(matches):
        pid, tid, timestamp, period = match.groups()
        pid, tid, period = int(pid), int(tid), int(period)
        assert pid in descendants and pid not in forbidden, ('sample escaped target subtree', pid)
        role = 'root' if pid == root_pid else 'descendants'
        end = matches[index+1].start() if index+1 < len(matches) else len(text)
        body = text[match.end():end]
        frames = re.findall(r'^\s*([0-9a-f]+)\s+(.+?)\s+\((.+)\)\s*$', body, re.M)
        kernel = [symbol for address, symbol, dso in frames
                  if int(address, 16) >= 0xffff800000000000]
        known = [symbol for symbol in kernel
                 if symbol != '[unknown]' and not re.fullmatch(r'(?:0x)?[0-9a-f]+', symbol)]
        counts[role] += 1
        pids[pid] += 1
        if not known:
            unresolved[role] += 1
        if kernel:
            leaf[role][kernel[0]] += period
            for symbol in set(known):
                inclusive[role][symbol] += period
        samples.append(dict(pid=pid, tid=tid, time=timestamp, period=period,
                            role=role, kernel_frames=kernel))
    report = dict(root_pid=root_pid, sampled_pids=dict(pids), process_ids=sorted(descendants),
                  forks=forks, exits=exits, sample_counts=dict(counts),
                  unresolved_stacks=dict(unresolved),
                  known_stack_fraction=1-sum(unresolved.values())/len(samples),
                  leaf_period_ns={role:dict(values.most_common(35)) for role,values in leaf.items()},
                  inclusive_period_ns={role:dict(values.most_common(45)) for role,values in inclusive.items()},
                  scope='Attached target and inherited descendants only; samples are not exact CPU counters',
                  text_sha256=digest(path))
    with gzip.open(path.with_name('kernel-samples.json.gz'), 'wt') as stream:
        json.dump(samples, stream)
    save(path.with_name('kernel-summary.json'), report)
    return report


def preflight(directory, perf, sudo, require_symbols):
    directory.mkdir(parents=True, exist_ok=False)
    worker = ('import json,os,time\nprint(json.dumps({"worker":os.getpid()}),flush=True)\n'
              'start=time.process_time()\nwhile time.process_time()-start < .35:\n'
              ' with open("/proc/self/stat","rb") as stream: stream.read()\n')
    program = ('import os,sys,subprocess,json\nprint(json.dumps({"root":os.getpid()}),flush=True)\n'
               'sys.stdin.readline()\np=subprocess.Popen([sys.executable,"-c",' + repr(worker) + '])\np.wait()\n')
    root = subprocess.Popen([sys.executable, '-c', program], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    initial = json.loads(root.stdout.readline())
    identity = dict(pid=initial['root'], birth=stat(root.pid)['birth'], harness_pid=os.getpid())
    outside = None
    recording = None
    try:
        recording = AttachedPerf(directory, identity, perf, sudo)
        recording.enable()
        outside = subprocess.Popen([sys.executable, '-c', worker], stdout=subprocess.DEVNULL)
        root.stdin.write('go\n')
        root.stdin.flush()
        output, errors = root.communicate(timeout=10)
        outside.wait(timeout=10)
        recording.finish()
        assert root.returncode == outside.returncode == 0 and not errors
        child = json.loads(output)['worker']
        summary = analyze(recording.decode(), root.pid, (os.getpid(), outside.pid))
        assert child in summary['process_ids'] and summary['sampled_pids'].get(child, 0) >= 10
        valid = not require_symbols or summary['known_stack_fraction'] >= .95
        receipt = dict(control='actual child inheritance and busy sibling exclusion',
                       engine=identity, worker_pid=child, excluded_sibling_pid=outside.pid,
                       kernel_symbols_required=require_symbols, valid=valid, summary=summary)
        save(directory / 'preflight.json', receipt)
        assert valid, 'kernel symbols unavailable for attribution'
        return receipt
    finally:
        for process in (root, outside):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        if recording is not None:
            recording.close()


def profile(directory, lane, prefix, perf, sudo):
    directory.mkdir(parents=True, exist_ok=False)
    gate = directory / 'gate'
    gate.mkdir()
    roles = directory / 'roles'
    record = directory / 'record'
    record.mkdir()
    env = dict(os.environ, MCPPLS_DIAGNOSTIC_PERF_GATE=str(gate))
    command = [sys.executable, str(Path(__file__).with_name('ready_role_observer.py')),
         'observe', '--output', str(roles), '--', '--label', 'kernel-'+lane,
         '--workdir', str(directory/'work'), '--out', str(directory/'result.json'),
         '--sessions', '0', '--'] + prefix
    recording = None
    with (directory/'harness.log').open('w') as log:
        harness = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 20
            while not (gate/'engine.json').exists():
                assert harness.poll() is None, 'harness ended before profiler gate'
                if time.monotonic() > deadline:
                    raise TimeoutError('engine identity gate')
                time.sleep(.01)
            identity = json.loads((gate/'engine.json').read_text())
            recording = AttachedPerf(record, identity, perf, sudo)
            recording.enable()
            save(gate/'go.json', dict(identity, perf_enabled_ns=recording.enabled_ns))
            harness.wait(timeout=1400)
            recording.finish()
            assert harness.returncode == 0, 'profiled semantic workload failed'
            summary = analyze(recording.decode(), identity['pid'], (os.getpid(), harness.pid))
            assert summary['known_stack_fraction'] >= .95, 'insufficient resolved kernel stacks'
            assert summary['sample_counts'].get('descendants', 0) >= 100
            original = json.loads((directory/'result.json').read_text())
            engine_log = (directory/'work/session-0-cold.log').read_text()
            stdlib = re.findall(r'Indexed c\+\+23 standard library: ([^\n]+)', engine_log)
            assert len(stdlib)==1 and 'incomplete' not in stdlib[0]
            assert 'Failed to auto-detect resource directory' not in engine_log
            assert 'falling back' not in engine_log.lower()
            report = dict(lane=lane, command=command, stdlib=stdlib,
                          original=original, kernel=summary,
                          qualification=False, engine_unchanged=True)
            save(directory/'verified.json', report)
            return report
        except BaseException as error:
            save(gate/'abort.json', dict(error=type(error).__name__+': '+str(error)))
            save(directory/'failed.json', dict(error=type(error).__name__+': '+str(error)))
            if harness.poll() is None:
                try:
                    harness.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    harness.terminate()
                    harness.wait(timeout=10)
            raise
        finally:
            if recording is not None:
                recording.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preflight', 'pair'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--perf', default='perf')
    parser.add_argument('--sudo-perf', action='store_true')
    parser.add_argument('--allow-unresolved-preflight', action='store_true')
    parser.add_argument('--native')
    parser.add_argument('--runner')
    parser.add_argument('--bundle')
    args = parser.parse_args()
    output = args.output.resolve()
    if args.mode == 'preflight':
        report = preflight(output, args.perf, args.sudo_perf, not args.allow_unresolved_preflight)
        print(json.dumps(dict(valid=report['valid'], known_stack_fraction=report['summary']['known_stack_fraction'])))
    else:
        assert args.native and args.runner and args.bundle
        assert not args.allow_unresolved_preflight
        output.mkdir(parents=True, exist_ok=False)
        inputs = {name:dict(path=str(Path(value).resolve()), sha256=digest(value))
                  for name,value in [('native',args.native),('runner',args.runner),('bundle',args.bundle)]}
        save(output/'plan.json', dict(inputs=inputs, order=['native','image'],
             frequency=499, event='cpu-clock:k', only_owned_pid_tree=True,
             gate='perf enable acknowledged before initialize and module workers',
             workload='original304units/3probes/176workers',
             initial_engine_startup_profiled=False, qualification=False))
        rows=[]
        for lane in ['native','image']:
            prefix=[inputs['native']['path']] if lane=='native' else [inputs['runner']['path'],inputs['bundle']['path']]
            row=profile(output/lane,lane,prefix,args.perf,args.sudo_perf)
            rows.append(row)
            if len(rows)==2: assert rows[0]['stdlib']==rows[1]['stdlib']
            save(output/'progress.json', rows)
        assert all(digest(item['path'])==item['sha256'] for item in inputs.values())
        save(output/'verified.json', dict(inputs=inputs, rows=rows, valid=True, qualification=False))
