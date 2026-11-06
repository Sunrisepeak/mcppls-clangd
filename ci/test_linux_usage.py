"""Exercise stable-reap accounting with real Linux descendants and wait4."""
from contextlib import contextmanager
import json
import os
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

from warm_usage import LinuxTreeUsage, READY_CPU_SCOPE


PROGRAM = r'''
import json,os,sys,time
ready_r,ready_w=os.pipe();exit_r,exit_w=os.pipe()
child=os.fork()
if child==0:
    os.close(ready_r);os.close(exit_w)
    grand=os.fork() if sys.argv[1]=='nested' else 0
    if grand==0:
        end=time.process_time()+0.2
        while time.process_time()<end: pass
        if sys.argv[1]=='nested':os._exit(0)
    else:os.waitpid(grand,0)
    os.write(ready_w,b'R');os.read(exit_r,1);os._exit(0)
os.close(ready_w);os.close(exit_r);os.read(ready_r,1)
print(json.dumps({'child':child}),flush=True)
assert sys.stdin.readline().strip()=='reap'
os.write(exit_w,b'X');os.waitpid(child,0)
print('reaped',flush=True)
assert sys.stdin.readline().strip()=='exit'
'''


@contextmanager
def process_tree(nested=False):
    import psutil
    child = subprocess.Popen([sys.executable, '-u', '-c', PROGRAM, 'nested' if nested else 'direct'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, start_new_session=True)
    class Control:
        released = False
        cpu = None

        def release(self):
            if self.released:
                return
            child.stdin.write('reap\n')
            child.stdin.flush()
            assert child.stdout.readline().strip() == 'reaped'
            self.released = True

        def finish(self):
            self.release()
            child.stdin.write('exit\n')
            child.stdin.flush()
            pid, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
            assert pid == child.pid and child.returncode == 0
            self.cpu = usage.ru_utime + usage.ru_stime

    control = Control()
    try:
        control.descendant = json.loads(child.stdout.readline())['child']
        control.sampler = LinuxTreeUsage(psutil.Process(child.pid))
        yield control
    finally:
        if child.returncode is None:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        child.stdin.close()
        child.stdout.close()
        child.stderr.close()


@unittest.skipUnless(sys.platform.startswith('linux'), 'Linux /proc and fork controls')
class LinuxUsageTests(unittest.TestCase):
    def assert_kernel_agrees(self, sample, control):
        self.assertTrue(sample['valid'])
        self.assertEqual(sample['scope_id'], READY_CPU_SCOPE)
        self.assertGreater(sample['cpu_seconds'], .15)
        # /proc rounds each own/waited field to clock ticks; wait4 also includes
        # the parent's short final shutdown after the observation.
        self.assertLess(abs(sample['cpu_seconds']-control.cpu), .08)

    def test_live_and_already_reaped_children_are_each_counted_once(self):
        for reaped in [False, True]:
            with self.subTest(reaped=reaped), process_tree() as control:
                if reaped:
                    control.release()
                sample = control.sampler.read()
                control.finish()
                self.assert_kernel_agrees(sample, control)

    def test_reap_between_reads_retries_without_double_counting(self):
        with process_tree() as control:
            original = control.sampler._sample
            def reap_after_first_read():
                rows = original()
                control.release()
                return rows
            with patch.object(control.sampler, '_sample', side_effect=reap_after_first_read):
                sample = control.sampler.read()
            control.finish()
            self.assertGreaterEqual(sample['attempts'], 2)
            self.assert_kernel_agrees(sample, control)

    def test_live_intermediate_keeps_usage_of_its_reaped_child(self):
        with process_tree(nested=True) as control:
            sample = control.sampler.read()
            control.finish()
            self.assertEqual(sample['processes'], 2)
            self.assert_kernel_agrees(sample, control)

    def test_other_process_trees_are_excluded(self):
        with process_tree() as control, process_tree() as unrelated:
            sample = control.sampler.read()
            control.finish()
            unrelated.finish()
            self.assertEqual(sample['processes'], 2)
            self.assert_kernel_agrees(sample, control)
            self.assertLess(sample['cpu_seconds'], control.cpu+unrelated.cpu-.1)

    def test_missing_or_unstable_observation_fails_closed(self):
        with process_tree() as control:
            with patch.object(control.sampler, '_sample', side_effect=OSError('injected read failure')) as read:
                with self.assertRaisesRegex(RuntimeError, 'no stable Linux'):
                    control.sampler.read(attempts=3)
                self.assertEqual(read.call_count, 3)
                self.assertFalse(control.sampler.last['valid'])
            control.finish()
            with self.assertRaisesRegex(RuntimeError, 'no stable Linux'):
                control.sampler.read()
            self.assertFalse(control.sampler.last['valid'])


if __name__ == '__main__':
    unittest.main()
