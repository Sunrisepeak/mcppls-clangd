"""Accounting boundaries shared by the warm-prime probe and its controls."""
import os
from pathlib import Path
import time

MEASUREMENT_VERSION = 3
FAULT_SCOPE = 'complete-engine-and-waited-descendants-v1'
READY_CPU_SCOPE = 'readiness-tree-stable-reaps-v1'
try:
    import resource
except ImportError:  # Windows keeps the existing process-tree samples.
    resource = None


def ready_cpu(platform, measured, own, worker_milliseconds):
    # Linux already captured exact waited-child totals while /proc still
    # existed. Rechecking /proc after shutdown must not discard that reading.
    if not platform.startswith('linux') and worker_milliseconds:
        return round(own + sum(worker_milliseconds) / 1000, 3)
    return measured


def _linux_stat(pid):
    fields = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, parent=int(fields[1]), start=int(fields[19]),
                own_cpu=int(fields[11]) + int(fields[12]),
                own_faults=int(fields[7]) + int(fields[9]),
                waited=(int(fields[13]), int(fields[14]), int(fields[8]), int(fields[10])))


class LinuxTreeUsage:
    """Disjoint own/waited totals across two reads with stable reap counters.

    A child may be reaped between reading its own CPU and reading its parent's
    waited CPU. Adding both double-counts that child. A still-live intermediate
    process may also have reaped children, whose usage must remain included.
    Reject changes in membership, identity, parentage or any waited counter;
    never replace a failed Linux reading with an apparently valid sampled sum.
    Own CPU can advance during this finite observation window, recorded below.
    """
    def __init__(self, process):
        self.process = process
        self.identity = _linux_stat(process.pid)['start']
        self.last = None

    def _sample(self):
        processes = [self.process] + self.process.children(recursive=True)
        rows = {p.pid: _linux_stat(p.pid) for p in processes}
        if rows[self.process.pid]['start'] != self.identity:
            raise RuntimeError('engine process identity changed during CPU observation')
        for pid, row in rows.items():
            ancestors = set()
            while pid != self.process.pid:
                if pid in ancestors or row['parent'] not in rows:
                    raise RuntimeError('process ancestry changed during CPU observation')
                ancestors.add(pid)
                pid = row['parent']
                row = rows[pid]
        return rows

    def read(self, attempts=8):
        import psutil
        begin = time.monotonic_ns()
        reason = 'process membership or waited counters changed'
        for attempt in range(1, attempts + 1):
            try:
                before, after = self._sample(), self._sample()
                stable = before.keys() == after.keys() and all(
                    (before[pid]['start'], before[pid]['parent'], before[pid]['waited']) ==
                    (row['start'], row['parent'], row['waited']) for pid, row in after.items())
                if not stable:
                    continue
                ticks = os.sysconf('SC_CLK_TCK')
                cpu = sum(row['own_cpu'] + sum(row['waited'][:2]) for row in after.values())
                faults = sum(row['own_faults'] + sum(row['waited'][2:]) for row in after.values())
                self.last = dict(valid=True, scope_id=READY_CPU_SCOPE, attempts=attempt,
                                 observation_ns=time.monotonic_ns()-begin, processes=len(after),
                                 cpu_seconds=round(cpu/ticks, 3), page_faults=faults,
                                 own_cpu_seconds=after[self.process.pid]['own_cpu']/ticks)
                return self.last
            except (OSError, psutil.Error, RuntimeError, ValueError, IndexError) as error:
                reason = type(error).__name__
        self.last = dict(valid=False, scope_id=READY_CPU_SCOPE, attempts=attempts,
                         observation_ns=time.monotonic_ns()-begin, reason=reason)
        raise RuntimeError('no stable Linux process-tree CPU observation: ' + reason)


class WaitedUsage:
    """The engine's complete lifetime and descendants it reaped, after wait()."""
    def __init__(self):
        self.before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None

    def finish(self):
        if self.before is None:
            return None
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return dict(user_seconds=after.ru_utime - self.before.ru_utime,
                    system_seconds=after.ru_stime - self.before.ru_stime,
                    minor_faults=after.ru_minflt - self.before.ru_minflt,
                    major_faults=after.ru_majflt - self.before.ru_majflt,
                    scope_id=FAULT_SCOPE,
                    scope='Complete engine lifetime including shutdown and waited descendants; '
                          'excludes the Python harness and descendants reparented elsewhere.')
