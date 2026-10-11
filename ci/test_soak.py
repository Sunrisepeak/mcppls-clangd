#!/usr/bin/env python3
"""Negative controls: lifecycle evidence must prove semantics and teardown."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("soak", ROOT / "tests/soak_loop.py")
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)

FAKE = r'''
import json, subprocess, sys, time
mode = sys.argv[1]
while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line: sys.exit(0)
        if line == b"\r\n": break
        key, value = line.decode().split(":", 1); headers[key.lower()] = value.strip()
    msg = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    if msg['method'] == 'exit':
        if mode == 'shutdown-hang': time.sleep(30)
        sys.exit(7 if mode == 'exit-crash' else 0)
    if 'id' not in msg: continue
    result = None
    if msg['method'] == 'initialize': result = {'capabilities': {}}
    if msg['method'] == 'textDocument/completion':
        if mode == 'crash': sys.exit(7)
        if mode == 'child-hang':
            child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
            open('child.pid', 'w').write(str(child.pid))
            sys.exit(7)
        if mode == 'timeout': time.sleep(30)
        names = ['fn1', 'fn2'] if mode != 'wrong-symbols' else ['unrelated']
        result = {'items': [{'label': name + '()', 'filterText': name, 'kind': 1 if mode == 'lexical' else 3} for name in names]}
    reply = {'jsonrpc': '2.0', 'id': msg['id'], 'result': result}
    if mode == 'request-error' and msg['method'] == 'textDocument/completion':
        reply = {'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32800, 'message': 'cancelled'}}
    data = json.dumps(reply).encode()
    sys.stdout.buffer.write(b'Content-Length: %d\r\n\r\n' % len(data) + data)
    sys.stdout.buffer.flush()
'''


class Soak(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project / 'Use.cpp').write_text('import m1;\nimport m2;\nint main() {\n    fn\n}\n')
        self.fake = self.project / 'fake.py'
        self.fake.write_text(FAKE)

    def run_case(self, mode, kill=False):
        return soak.run_engine(Path(sys.executable), self.project, 0.8, kill,
                               [str(self.fake), mode])

    def test_semantics_and_clean_shutdown(self):
        result = self.run_case('pass')
        self.assertEqual(result['outcome'], 'pass', result)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['observed_symbols'], ['fn1', 'fn2'])
        for mode in ('wrong-symbols', 'request-error', 'crash', 'exit-crash', 'lexical'):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_case(mode)['outcome'], 'error')

    def test_deadlines_include_shutdown(self):
        for mode in ('timeout', 'shutdown-hang'):
            with self.subTest(mode=mode):
                result = self.run_case(mode)
                self.assertEqual(result['outcome'], 'timeout', result)
                self.assertTrue(result['readers_stopped'])
                self.assertLess(result['elapsed_ms'], 2500)

    def test_intentional_kill_requires_a_reaped_engine(self):
        result = self.run_case('timeout', kill=True)
        self.assertEqual(result['outcome'], 'killed', result)
        self.assertNotEqual(result['exit_code'], 0)
        self.assertTrue(result['readers_stopped'])
        self.assertEqual(self.run_case('pass')['outcome'], 'pass')

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group descendant regression')
    def test_crashed_leader_does_not_leave_inherited_pipes(self):
        result = self.run_case('child-hang')
        self.assertEqual(result['outcome'], 'timeout', result)
        self.assertTrue(result['readers_stopped'])
        child_pid = int((self.project / 'child.pid').read_text())
        # A container PID 1 may leave a killed child zombie temporarily; its
        # kernel state must nevertheless show it is no longer running, once the
        # kill has been delivered (a loaded runner can show it running briefly).
        stat = Path(f'/proc/{child_pid}/stat')
        state = None
        for _ in range(100):
            try:
                state = stat.read_text().split(') ')[1].split()[0]
            except (FileNotFoundError, ProcessLookupError):
                return
            if state == 'Z':
                return
            time.sleep(0.05)
        self.assertEqual(state, 'Z')


if __name__ == '__main__':
    unittest.main()
