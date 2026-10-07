#!/usr/bin/env python3
"""Controlled checks for debugger evidence eligibility and launch cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import windows_crash_capture as capture


class Capture(unittest.TestCase):
    def test_forced_or_incomplete_observations_never_qualify(self):
        with tempfile.TemporaryDirectory() as temp:
            dump = Path(temp) / 'exception.dmp'
            dump.write_bytes(b'MDMP' + bytes(64))
            result = {'outcome': 'crash', 'exit_code': 0x80000003, 'readers_stopped': True}
            frame = ('00000030`dcd5c920 00007ff6`b83bf1ba : '
                     '00000200`3c4a91b0 00000207`3c4a91b0 00000030`dcd5cfe0 00000000`00000000 : '
                     'clangd!clang::syntax::TokenCollector::Builder::build+0x2ff [D:/llvm/clang/lib/Tooling/Syntax/Tokens.cpp @ 1]')
            log = 'MCPPLS_SECOND_CHANCE\nExceptionCode: 80000003\n' + frame + '\n'
            # Synthetic data exercises the classifier only; it is not native proof.
            self.assertTrue(capture.evidence(result, log, dump, False)['captured'])
            for field, value in [('outcome', 'timeout'), ('exit_code', 1), ('readers_stopped', False)]:
                changed = dict(result, **{field: value})
                self.assertFalse(capture.evidence(changed, log, dump, False)['captured'])
            self.assertFalse(capture.evidence(result, log, dump, True)['captured'])
            self.assertFalse(capture.evidence(result, log.replace('80000003', 'c0000005'), dump, False)['captured'])
            self.assertFalse(capture.evidence(result, log.replace('MCPPLS_SECOND_CHANCE',
                '0:000> .echo MCPPLS_SECOND_CHANCE'), dump, False)['captured'])
            self.assertFalse(capture.evidence(result, log.replace('clangd!', 'clangd+'), dump, False)['captured'])
            self.assertFalse(capture.evidence(result, log.replace(' [D:/llvm/clang/lib/Tooling/Syntax/Tokens.cpp @ 1]', ''), dump, False)['captured'])
            self.assertFalse(capture.evidence(result, log.replace(
                frame,
                '0:000> x clangd!clang::syntax::TokenCollector'), dump, False)['captured'])
            dump.write_bytes(b'not-a-minidump')
            self.assertFalse(capture.evidence(result, log, dump, False)['captured'])

    def test_attachment_breakpoint_is_handled_and_later_exception_is_not(self):
        with tempfile.TemporaryDirectory(prefix='capture-') as temp:
            script = capture.debugger_script(Path(temp) / 'exception.dmp')
            self.assertIn('sxd -h bpe', script)
            self.assertIn('.lines -e\n.reload /f', script)
            self.assertIn('sxd -c2 ', script)
            self.assertTrue(script.endswith('MCPPLS_CDB_ATTACHED\ngh\n'))
            self.assertIn('.dump /m /o ', script)
            self.assertIn('; gn" bpe', script)
            with self.assertRaises(ValueError):
                capture.debugger_script(Path(temp) / 'unsafe path.dmp')

    @unittest.skipIf(os.name == 'nt', 'POSIX process ownership control')
    def test_attach_exception_cleans_the_real_child_and_readers(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            script = project / 'idle.py'
            script.write_text('import time\ntime.sleep(60)\n')
            manifest = project / 'case.json'
            manifest.write_text(json.dumps({'id': 'attach-failure',
                'platform': capture.replay.platform_name(), 'baseline': 'crash',
                'project': '.', 'flags': [str(script)], 'timeout_seconds': 0.2,
                'sequence': [{'method': 'initialize', 'params': {}},
                    {'method': 'textDocument/hover', 'params': {}, 'expect': {'/result': 'answer'}}]}))
            children = []
            def fail(proc, deadline):
                children.append(proc)
                self.assertGreater(deadline, time.monotonic())
                raise RuntimeError('controlled attach setup failure')
            result = capture.replay.replay(Path(sys.executable), manifest, process_started=fail)
            self.assertEqual(result['outcome'], 'error')
            self.assertTrue(result['readers_stopped'])
            self.assertIsNotNone(children[0].poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(children[0].pid, 0)

    @unittest.skipIf(os.name == 'nt', 'POSIX process ownership control')
    def test_attach_wait_consumes_the_replay_deadline(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            script = project / 'idle.py'
            script.write_text('import time\ntime.sleep(60)\n')
            manifest = project / 'case.json'
            manifest.write_text(json.dumps({'id': 'attach-timeout',
                'platform': capture.replay.platform_name(), 'baseline': 'crash',
                'project': '.', 'flags': [str(script)], 'timeout_seconds': 0.1,
                'sequence': [{'method': 'initialize', 'params': {}},
                    {'method': 'textDocument/hover', 'params': {}, 'expect': {'/result': 'answer'}}]}))
            def timeout(proc, deadline):
                time.sleep(max(0, deadline - time.monotonic()))
                raise subprocess.TimeoutExpired('controlled attach timeout', 0.1)
            started = time.monotonic()
            result = capture.replay.replay(Path(sys.executable), manifest, process_started=timeout)
            self.assertEqual(result['outcome'], 'timeout')
            self.assertTrue(result['readers_stopped'])
            self.assertLess(time.monotonic() - started, 1)


if __name__ == '__main__':
    unittest.main()
