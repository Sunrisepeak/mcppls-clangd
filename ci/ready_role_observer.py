#!/usr/bin/python3
"""Observe original warm-prime accounting without changing its readiness formula."""
from pathlib import Path
import argparse, ctypes, datetime, gzip, hashlib, json, os, re
import shutil, signal, subprocess, sys, threading, time
import psutil

ROOT = Path('accounting-control')
HZ = os.sysconf('SC_CLK_TCK')


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def stat(pid, tid=None):
    path = Path(f'/proc/{pid}/stat' if tid is None else f'/proc/{pid}/task/{tid}/stat')
    t = time.monotonic_ns()
    raw = path.read_text()
    f = raw.rsplit(')', 1)[1].split()
    return dict(pid=pid, tid=tid, time_ns=t, comm=raw.split('(', 1)[1].rsplit(')', 1)[0],
                state=f[0], ppid=int(f[1]), pgrp=int(f[2]), session=int(f[3]),
                minflt=int(f[7]), cminflt=int(f[8]), majflt=int(f[9]), cmajflt=int(f[10]),
                utime=int(f[11]), stime=int(f[12]), cutime=int(f[13]), cstime=int(f[14]),
                priority=int(f[15]), nice=int(f[16]), threads=int(f[17]),
                birth=int(f[19]), vsize=int(f[20]), rss_pages=int(f[21]), policy=int(f[38]))


def times(row):
    return {k: row[k] / HZ for k in ('utime', 'stime', 'cutime', 'cstime')}


def child_pids(pid):
    found = set()
    for task in Path(f'/proc/{pid}/task').iterdir():
        try:
            found.update(int(x) for x in (task / 'children').read_text().split())
        except (FileNotFoundError, ProcessLookupError):
            pass
    return found


def tree(root_pid):
    rows = {}
    pending = [root_pid]
    while pending:
        pid = pending.pop()
        if pid in rows:
            continue
        try:
            row = stat(pid)
            descendants = child_pids(pid)
            check = stat(pid)
            if check['birth'] != row['birth']:
                continue
            rows[pid] = row
            pending.extend(descendants)
        except (FileNotFoundError, ProcessLookupError):
            pass
    return rows


def bracket(root_pid):
    before = stat(root_pid)
    rows = tree(root_pid)
    after = stat(root_pid)
    stable = before['birth'] == after['birth'] and all(
        before[k] == after[k] for k in ('cutime', 'cstime', 'cminflt', 'cmajflt'))
    children = [r for pid, r in rows.items() if pid != root_pid]
    return dict(before=before, processes=list(rows.values()), after=after,
                waited_fields_stable=stable, span_ns=after['time_ns'] - before['time_ns'],
                root_own_seconds=(before['utime'] + before['stime']) / HZ,
                root_waited_seconds=(before['cutime'] + before['cstime']) / HZ,
                live_own_seconds=sum(r['utime'] + r['stime'] for r in children) / HZ,
                live_waited_seconds=sum(r['cutime'] + r['cstime'] for r in children) / HZ)


def resources():
    return dict(host_free=shutil.disk_usage('/tmp').free,
                ramfs_free=shutil.disk_usage('/dev/shm').free,
                load=list(os.getloadavg()), memory_available=psutil.virtual_memory().available)


class Observer:
    def __init__(self, pid, path):
        self.pid, self.path = pid, path
        self.stop = threading.Event()
        self.catalog, self.errors, self.intervals = {}, [], []
        self.frames = 0
        self.reason = None
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def start(self):
        self.thread.start()

    def loop(self):
        last = None
        try:
            with gzip.open(self.path / 'process-thread-samples.jsonl.gz', 'wt', compresslevel=1) as out:
                while not self.stop.is_set():
                    now = time.monotonic_ns()
                    if last is not None:
                        self.intervals.append(now - last)
                    last = now
                    procs = tree(self.pid)
                    if self.pid not in procs:
                        break
                    thread_rows = []
                    for pid, row in procs.items():
                        key = f"{pid}:{row['birth']}"
                        if key not in self.catalog:
                            try:
                                argv = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                                argv = [x.decode(errors='replace') for x in argv if x]
                            except (FileNotFoundError, ProcessLookupError):
                                argv = []
                            role = 'engine' if pid == self.pid else (
                                'module-worker' if '--module-build-worker' in argv else 'other-child')
                            self.catalog[key] = dict(first=row, argv=argv, role=role)
                        self.catalog[key]['last'] = row
                        try:
                            tids = [int(x.name) for x in Path(f'/proc/{pid}/task').iterdir()]
                        except (FileNotFoundError, ProcessLookupError):
                            continue
                        for tid in tids:
                            try:
                                r = stat(pid, tid)
                                sched = Path(f'/proc/{pid}/task/{tid}/schedstat').read_text().split()
                                r.update(sched_runtime_ns=int(sched[0]), sched_wait_ns=int(sched[1]))
                                thread_rows.append(r)
                            except (FileNotFoundError, ProcessLookupError):
                                pass
                    out.write(json.dumps(dict(time_ns=now, processes=list(procs.values()),
                                              threads=thread_rows), separators=(',', ':')) + '\n')
                    self.frames += 1
                    if self.frames % 40 == 0:
                        free = resources()
                        if free['host_free'] < 2_000_000_000 or free['memory_available'] < 1_000_000_000:
                            self.reason = 'resource stop threshold'
                            os.kill(self.pid, signal.SIGTERM)
                            break
                    self.stop.wait(0.025)
        except BaseException as e:
            self.errors.append(type(e).__name__ + ': ' + str(e))

    def close(self):
        self.stop.set()
        self.thread.join(5)
        assert not self.thread.is_alive(), 'observer failed to end'
        save(self.path / 'process-catalog-private.json', self.catalog)
        report = dict(frames=self.frames, errors=self.errors, resource_stop=self.reason,
                      hz=HZ, period_ms=25, affinity=sorted(os.sched_getaffinity(0)),
                      interval_ms={k: v / 1e6 for k, v in {
                          'min': min(self.intervals, default=0),
                          'max': max(self.intervals, default=0),
                          'mean': sum(self.intervals) / max(1, len(self.intervals))}.items()})
        save(self.path / 'observer.json', report)
        return report


def drained():
    result = []
    deadline = time.monotonic() + 5
    while True:
        try:
            pid, status, r = os.wait4(-1, os.WNOHANG)
        except ChildProcessError:
            return result
        if pid:
            result.append(dict(pid=pid, exit=os.waitstatus_to_exitcode(status),
                               user=r.ru_utime, system=r.ru_stime,
                               minflt=r.ru_minflt, majflt=r.ru_majflt))
            continue
        if time.monotonic() > deadline:
            raise TimeoutError('owned adopted descendants did not end')
        time.sleep(.01)


def validate():
    ROOT.mkdir(exist_ok=True)
    # A real reaped child and a still-live parent establish the accounting fields.
    burn = 'import time\nt=time.process_time()\nwhile time.process_time()-t < .15: pass\n'
    script = (f'import subprocess,sys,time\np=subprocess.Popen([sys.executable,"-c",{burn!r}])\n'
              't=time.process_time()\nwhile time.process_time()-t < .15: pass\n'
              'p.wait()\nprint("ready",flush=True)\ntime.sleep(.3)\n')
    p = subprocess.Popen(['/usr/bin/python3', '-c', script], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == 'ready'
    b = bracket(p.pid)
    reference = psutil.Process(p.pid).cpu_times()
    _, status, usage = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(status)
    assert p.returncode == 0 and b['waited_fields_stable']
    assert b['root_own_seconds'] >= .14 and b['root_waited_seconds'] >= .14
    assert b['live_own_seconds'] == 0
    assert abs(b['root_own_seconds'] - reference.user - reference.system) <= 2 / HZ
    assert 0 <= usage.ru_utime + usage.ru_stime - b['root_own_seconds'] - b['root_waited_seconds'] < .08
    receipt = dict(scope='real ended-child accounting parser control', bracket=b,
                   psutil=list(reference), wait4_cpu=usage.ru_utime + usage.ru_stime, passed=True)
    save(ROOT / 'accounting-control.json', receipt)
    print(json.dumps(dict(accounting_control=True, own=b['root_own_seconds'],
                          waited=b['root_waited_seconds'], wait4=receipt['wait4_cpu'])), flush=True)


def observe(source, output, arguments):
    output.mkdir(parents=True, exist_ok=False)
    original = source.read_text()
    before, marker, after = original.partition('# ---- the run ')
    assert marker, 'Frozen warm-prime entry boundary is absent'
    sys.path.insert(0, str(source.parent))
    sys.argv = [str(source)] + arguments
    ns = dict(__file__=str(source), __name__='warm_prime_role_observation')
    exec(compile(before, str(source), 'exec'), ns)
    BaseSession = ns['Session']
    holders = []

    class ObservedSession(BaseSession):
        def __init__(self, at):
            self.reaped_observations, self.usage_observations = [], []
            self.role_output = output / f'session-{len(holders)}'
            self.role_output.mkdir()
            super().__init__(at)
            self.observer = Observer(self.p.pid, self.role_output)
            self.observer.start()
            holders.append(self)

        def reaped(self):
            # Retain the exact Linux formula; save the fields from the SAME read.
            try:
                row = stat(self.p.pid)
            except OSError:
                return None
            self.reaped_observations.append(dict(root=row, seen=dict(self.seen)))
            cpu = sum(row[k] for k in ('utime', 'stime', 'cutime', 'cstime')) / HZ
            faults = sum(row[k] for k in ('minflt', 'cminflt', 'majflt', 'cmajflt'))
            return cpu, faults

        def usage(self):
            started = time.monotonic_ns()
            value = super().usage()
            ended = time.monotonic_ns()
            # This extra read cannot enter the value returned to the original probe.
            observation = dict(started_ns=started, ended_ns=ended,
                               original_cpu=value[0], original_faults=value[1],
                               seen_after=dict(self.seen))
            try:
                observation['bracket_after_original_measurement'] = bracket(self.p.pid)
            except OSError as error:
                observation['bracket_error'] = type(error).__name__
            self.usage_observations.append(observation)
            return value

    ns['Session'] = ObservedSession
    libc = ctypes.CDLL(None, use_errno=True)
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    start = resources()
    assert start['host_free'] >= 3_000_000_000 and start['memory_available'] >= 2_000_000_000
    try:
        exec(compile('# ---- the run ' + after, str(source), 'exec'), ns)
    finally:
        observers = []
        for session in holders:
            observers.append(session.observer.close())
            save(session.role_output / 'readiness-components.json',
                 dict(reaped=session.reaped_observations, usage=session.usage_observations))
        adopted = drained()
        save(output / 'observation.json', dict(source_sha256=sha(source),
             observer_sha256=sha(__file__), before=start, after=resources(),
             observers=observers, adopted=adopted,
             scope='Diagnostic CPU components; original formula retained; not producer qualification'))
    result = json.loads(Path(ns['a'].out).read_text())
    assert result['units'] == 304 and len(result['probes']) == 3
    assert all(s['ok'] for s in result['sessions'])
    assert result['sessions'][0]['workers'] == 176
    assert result['sessions'][0]['modules_built'] == 176
    assert all(s['cache'] == 'owned' and s['builds'] == 'in supervised workers'
               for s in result['sessions'])
    assert all(not o['errors'] and not o['resource_stop'] for o in observers)
    assert all(child['exit'] == 0 for child in adopted)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['validate', 'observe'])
    parser.add_argument('--source', type=Path, default=Path(__file__).with_name('warm_prime.py'))
    parser.add_argument('--output', type=Path, default=Path('role-observation'))
    args, rest = parser.parse_known_args()
    if args.mode == 'validate':
        ROOT = args.output
        validate()
    else:
        if rest[:1] == ['--']:
            rest = rest[1:]
        observe(args.source.resolve(), args.output.resolve(), rest)
