"""Accounting boundaries shared by the warm-prime probe and its controls."""
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
                    scope='Complete engine lifetime including shutdown and waited descendants; '
                          'excludes the Python harness and descendants reparented elsewhere.')
