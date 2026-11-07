#!/usr/bin/env python3
"""Fast negative controls for release eligibility and corpus replay."""
import json
import time
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class Gates(unittest.TestCase):
    def test_image_probes_share_the_declared_platform(self):
        # The platform of the images is stated once, in openkal/clangd/mcpp.toml: a
        # warm-prime bootstrap or a probe left on another platform installs another
        # runner than the image and acceptance use. Every probe is written by
        # ci/scripts/probe-platform.sh, which reads that manifest.
        pattern = r'openkal-platform@[0-9]+(?:\.[0-9]+)*'
        expected = set(re.findall(pattern, (ROOT / 'openkal/clangd/mcpp.toml').read_text()))
        self.assertEqual(len(expected), 1)
        for workflow in ('build-test.yml', 'openkal.yml'):
            with self.subTest(workflow=workflow):
                text = (ROOT / '.github/workflows' / workflow).read_text()
                self.assertEqual(set(re.findall(pattern, text)), set())
                self.assertIn('ci/scripts/probe-platform.sh', text)
                self.assertNotIn('openkal-tools@*', text)
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / 'h'
            subprocess.run(['bash', str(ROOT / 'ci/scripts/probe-platform.sh'), str(probe)], check=True)
            self.assertEqual(set(re.findall(pattern, (probe / 'mcpp.toml').read_text())), expected)

    def test_native_engines_are_compared_not_released(self):
        # ci/performance-policy.md, "Comparison runs": a push or a pull request builds one native engine for
        # the series' tests; only a dispatched comparison run builds, packages and measures the others.
        import importlib.util
        spec = importlib.util.spec_from_file_location('comparison_matrix', ROOT / 'ci/comparison_matrix.py')
        cm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cm)
        for event in ('pull_request', 'push'):
            daily = cm.matrices(event, 'all')
            self.assertEqual([r['platform'] for r in daily['build']], ['linux-x64'])
            self.assertEqual((daily['floor'], daily['compare']), ([], []))
        full = cm.matrices('workflow_dispatch', 'all')
        self.assertEqual([r['platform'] for r in full['compare']], list(cm.PLATFORMS))
        self.assertEqual([r['platform'] for r in full['floor']], ['linux-x64', 'linux-arm64'])
        one = cm.matrices('workflow_dispatch', 'win32-x64')
        self.assertEqual(([r['platform'] for r in one['build']], one['floor']), (['win32-x64'], []))
        with self.assertRaises(SystemExit):
            cm.matrices('workflow_dispatch', 'win32-arm64')
        test = (ROOT / '.github/workflows/build-test.yml').read_text()
        for output in ('build', 'floor', 'compare'):
            self.assertIn(f'fromJSON(needs.setup.outputs.{output})', test)
        release = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertNotIn('ci_build.sh', release)
        self.assertNotIn('package.sh', release)
        self.assertIn('needs: [openkal]', release)
        self.assertIn('Comparison run: https://github', release)

    def test_release_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / 'patches').mkdir()
            name = '0001-UP-01-one.patch'
            (repo / 'patches/series').write_text(name + '\n')
            (repo / f'patches/{name}').write_text('+++ b/clang/test/case.cpp\n')
            def check(state, test, rows='UP-01'):
                (repo / 'patches/PATCHES.md').write_text(
                    f'| {name} | {rows} | {state} | {test} | upstream fix |\n')
                return subprocess.run([sys.executable, str(ROOT / 'ci/check_ledger.py'),
                                       '--release', '--repo', str(repo)], capture_output=True).returncode
            self.assertNotEqual(check('stabilizing', 'clang/test/case.cpp'), 0)
            self.assertNotEqual(check('steady', 'a benchmark'), 0)
            self.assertNotEqual(check('steady', 'clang/test/missing.cpp'), 0)
            self.assertNotEqual(check('steady', 'clang/test/case.cpp', 'UP-02, UP-01'), 0)
            self.assertEqual(check('steady', 'clang/test/case.cpp', 'UP-01, UP-02'), 0)
            self.assertEqual(check('steady', 'clang/test/case.cpp'), 0)

    def test_empty_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / 'tests/crash/replay.py'),
                                     '--engine', sys.executable, '--corpus', tmp,
                                     '--output', str(Path(tmp) / 'out.json')], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'empty corpus', result.stderr)

    def test_stdout_closes_before_natural_exit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fake = project / 'early_eof.py'
            manifest = project / 'case.json'
            manifest.write_text(json.dumps({'id': 'early-eof',
                'platform': replay.platform_name(), 'baseline': 'crash',
                'project': '.', 'flags': [str(fake)], 'timeout_seconds': 3,
                'sequence': [{'method': 'initialize', 'params': {}},
                    {'method': 'textDocument/hover', 'params': {},
                     'expect': {'/result': 'answer'}}]}))
            for code, outcome in ((9, 'crash'), (0, 'error')):
                fake.write_text('import os,time\nos.close(1)\ntime.sleep(0.1)\nos._exit(%d)\n' % code)
                result = replay.replay(Path(sys.executable), manifest)
                self.assertEqual(result['outcome'], outcome)
                self.assertEqual(result['exit_code'], code)
                self.assertTrue(result['readers_stopped'])

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

            def state():
                try:
                    return stat.read_text().split(') ')[1].split()[0]
                except (FileNotFoundError, ProcessLookupError):
                    return None
            # The group's kill is delivered asynchronously: the helper has
            # ended once it is a zombie or gone, a moment after the signal.
            deadline = time.monotonic() + 5
            while state() not in (None, 'Z') and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertIn(state(), (None, 'Z'))


if __name__ == '__main__':
    unittest.main()
