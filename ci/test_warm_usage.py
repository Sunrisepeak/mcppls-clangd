"""Control the Linux CPU boundary and kernel accounting of short descendants."""
import ast
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import warm_usage


def session_result(source):
    """Drive the actual reporting function after the kernel process disappeared."""
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'session')

    class Session:
        own_cpu = 2.0
        waited_usage = SimpleNamespace(finish=lambda: dict(minor_faults=1000, major_faults=7,
                                                          scope_id=warm_usage.FAULT_SCOPE))

        def __init__(self, at):
            pass

        def run(self, probes):
            return {'main.cpp': 0.1}, 12.345, 999

        def stop(self):
            return 'Module worker built m in 10 ms: CPU 10 ms\n'

        def reaped(self):
            return None

    with tempfile.TemporaryDirectory() as directory:
        namespace = dict(Session=Session, sys=SimpleNamespace(platform='linux'),
                         ready_cpu=warm_usage.ready_cpu, os=os, re=re, statistics=statistics,
                         a=SimpleNamespace(workdir=directory))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<probe session>', 'exec'), namespace)
        return namespace['session']('cold', directory, ['main.cpp'], 0)


class WarmUsageTests(unittest.TestCase):
    def test_actual_session_preserves_ready_cpu_when_proc_is_gone_after_shutdown(self):
        result = session_result(Path(__file__).with_name('warm_prime.py').read_text())
        self.assertTrue(result['ok'])
        self.assertEqual(result['cpu_seconds'], 12.345)
        self.assertEqual(result['page_faults'], 999)
        self.assertEqual(result['complete_page_faults'], 1007)
        self.assertEqual(result['waited_usage']['scope_id'], warm_usage.FAULT_SCOPE)

    def test_linux_retains_the_kernel_cpu_reading_after_the_process_disappears(self):
        self.assertEqual(warm_usage.ready_cpu('linux', 12.345, 2.0, [10, 20]), 12.345)
        self.assertEqual(warm_usage.ready_cpu('linux2', 12.345, 2.0, [10, 20]), 12.345)

    def test_other_hosts_retain_the_existing_worker_cpu_fallback(self):
        for platform in ('darwin', 'win32'):
            self.assertEqual(warm_usage.ready_cpu(platform, 12.345, 2.0, [10, 20]), 2.03)
            self.assertEqual(warm_usage.ready_cpu(platform, 12.345, 2.0, []), 12.345)

    def test_unavailable_kernel_accounting_is_explicit(self):
        with patch.object(warm_usage, 'resource', None):
            self.assertIsNone(warm_usage.WaitedUsage().finish())

    @unittest.skipUnless(warm_usage.resource, 'POSIX waited-child accounting')
    def test_kernel_counts_a_reaped_grandchild_without_process_tree_sampling(self):
        touch = "import os; b=bytearray(16*1024*1024); b[::os.sysconf('SC_PAGESIZE')]=bytes([1])*len(b[::os.sysconf('SC_PAGESIZE')])"
        middle = 'import subprocess,sys; subprocess.run([sys.executable,"-c",' + repr(touch) + '],check=True)'
        usage = warm_usage.WaitedUsage()
        subprocess.run([sys.executable, '-c', middle], check=True)
        observed = usage.finish()
        self.assertGreaterEqual(observed['minor_faults'], 16 * 1024 * 1024 // os.sysconf('SC_PAGESIZE'))
        self.assertGreater(observed['user_seconds'] + observed['system_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
