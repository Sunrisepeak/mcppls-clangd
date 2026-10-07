#!/usr/bin/env python3
"""Fast negative controls for release eligibility and corpus replay."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class Gates(unittest.TestCase):
    def test_release_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / 'patches').mkdir()
            (repo / 'patches/series').write_text('one.patch\n')
            (repo / 'patches/one.patch').write_text('+++ b/clang/test/case.cpp\n')
            def check(state, test):
                (repo / 'patches/PATCHES.md').write_text(
                    f'| one.patch | UP-01 | {state} | {test} | upstream fix |\n')
                return subprocess.run([sys.executable, str(ROOT / 'ci/check_ledger.py'),
                                       '--release', '--repo', str(repo)], capture_output=True).returncode
            self.assertNotEqual(check('stabilizing', 'clang/test/case.cpp'), 0)
            self.assertNotEqual(check('steady', 'a benchmark'), 0)
            self.assertNotEqual(check('steady', 'clang/test/missing.cpp'), 0)
            self.assertEqual(check('steady', 'clang/test/case.cpp'), 0)

    def test_empty_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / 'tests/crash/replay.py'),
                                     '--engine', sys.executable, '--corpus', tmp,
                                     '--output', str(Path(tmp) / 'out.json')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'empty corpus', result.stderr)

    def test_replay_outcomes(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fake = project / 'fake.py'
            fake.write_text('''import json, sys
while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line: sys.exit(0)
        if line == b"\\r\\n": break
        k, v = line.decode().split(":", 1); headers[k.lower()] = v.strip()
    msg = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    if msg['method'] == 'exit': sys.exit(0)
    if 'id' not in msg: continue
    result = {'jsonrpc': '2.0', 'id': msg['id'], 'result': {'items': [{'label': 'member'}]}}
    data = json.dumps(result).encode()
    sys.stdout.buffer.write(b'Content-Length: %d\\r\\n\\r\\n' % len(data) + data)
    sys.stdout.buffer.flush()
''')
            case = {'id': 'controlled', 'platform': replay.platform_name(), 'baseline': 'pass',
                    'project': '.', 'flags': [str(fake)], 'timeout_seconds': 2,
                    'sequence': [{'method': 'initialize', 'params': {}},
                                 {'method': 'textDocument/completion', 'params': {},
                                  'expect': {'/result/items/0/label': 'member'}}]}
            manifest = project / 'case.json'
            def run():
                manifest.write_text(json.dumps(case))
                return replay.replay(Path(sys.executable), manifest)['outcome']
            self.assertEqual(run(), 'pass')
            source = project / 'export.cppm'
            source.write_text('addOption')
            os.utime(source, ns=(10500000000, 10500000000))
            original_stamp = source.stat().st_mtime_ns
            case['sequence'].insert(1, {'action': 'replace-file', 'file': source.name,
                'from': 'addOption', 'with': 'freshItem', 'same-second': True})
            real_utime = os.utime
            stamps = []
            def ntfs_utime(path, *, ns):
                rounded = tuple(t // 100 * 100 for t in ns)
                stamps.append(rounded[1])
                return real_utime(path, ns=rounded)
            with patch.object(replay.os, 'utime', ntfs_utime):
                self.assertEqual(run(), 'pass')
            self.assertNotEqual(stamps[0], original_stamp)
            self.assertEqual(stamps[0] // 1000000000, original_stamp // 1000000000)
            self.assertEqual(source.read_text(), 'addOption')
            case['sequence'].pop(1)
            case['sequence'][1]['expect']['/result/items/0/label'] = 'wrong'
            self.assertEqual(run(), 'error')
            fake.write_text('import sys; sys.exit(7)\n')
            self.assertEqual(run(), 'crash')
            fake.write_text('import time; time.sleep(60)\n')
            case['timeout_seconds'] = 0.1
            self.assertEqual(run(), 'timeout')

    @unittest.skipIf(os.name == 'nt', 'POSIX process-group cleanup')
    def test_crashed_leader_reaps_output_holding_helpers(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fake = project / 'crashed.py'
            fake.write_text("import subprocess, sys\n"
                            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                            "open('child.pid', 'w').write(str(child.pid))\n"
                            "sys.exit(7)\n")
            manifest = project / 'case.json'
            manifest.write_text(json.dumps({
                'id': 'crashed-leader', 'platform': replay.platform_name(),
                'baseline': 'crash', 'project': '.', 'flags': [str(fake)],
                'timeout_seconds': 0.3, 'sequence': [
                    {'method': 'initialize', 'params': {}},
                    {'method': 'textDocument/completion', 'params': {},
                     'expect': {'/result/items/0/label': 'member'}}]}))
            result = replay.replay(Path(sys.executable), manifest)
            self.assertNotEqual(result['outcome'], 'pass')
            self.assertEqual(result['exit_code'], 7)
            self.assertTrue(result['readers_stopped'], result)
            stat = Path(f"/proc/{int((project / 'child.pid').read_text())}/stat")
            if stat.exists():
                self.assertEqual(stat.read_text().split(') ')[1].split()[0], 'Z')


if __name__ == '__main__':
    unittest.main()
