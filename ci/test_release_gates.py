#!/usr/bin/env python3
"""Fast negative controls for release eligibility and corpus replay."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
            case['sequence'][1]['expect']['/result/items/0/label'] = 'wrong'
            self.assertEqual(run(), 'error')
            fake.write_text('import sys; sys.exit(7)\n')
            self.assertEqual(run(), 'crash')
            fake.write_text('import time; time.sleep(60)\n')
            case['timeout_seconds'] = 0.1
            self.assertEqual(run(), 'timeout')


if __name__ == '__main__':
    unittest.main()
