"""Exercise the actual acceptance CLI with complete and deliberately incomplete measurements."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION, READY_CPU_SCOPE

ACCEPTED, FAILED, INVALID = 0, 1, 2


def report(cold_cpu=1, cold_ready=1):
    session = dict(kind='cold', ok=True, ready_seconds=1, cpu_seconds=1,
                   page_faults=10, complete_page_faults=100,
                   cpu_sample=dict(valid=True, scope_id=READY_CPU_SCOPE, cpu_seconds=1, page_faults=10,
                                   attempts=1, processes=1, observation_ns=1000),
                   waited_usage=dict(scope_id=FAULT_SCOPE, minor_faults=99, major_faults=1),
                   builds='in supervised workers', owned_cache='/cache', cache='owned')
    sessions = [copy.deepcopy(session) for _ in range(4)]
    for s in sessions[1:]:
        s['kind'] = 'warm'
    sessions[0]['cpu_seconds'] = sessions[0]['cpu_sample']['cpu_seconds'] = cold_cpu
    sessions[0]['ready_seconds'] = cold_ready
    return dict(measurement_version=MEASUREMENT_VERSION, fault_scope=FAULT_SCOPE,
                units=304, probes=['main.cpp', 'deep.cppm', 'test.cpp'], sessions=sessions,
                warm=dict(ready_seconds=1, cpu_seconds=1, page_faults=10,
                          complete_page_faults=100, modules_built=0))


def pairs(images, native=None):
    """One pair per image report, each against the same native report."""
    return [(copy.deepcopy(native if native is not None else report()), copy.deepcopy(i)) for i in images]


class WarmAcceptanceTests(unittest.TestCase):
    def check_cli(self, measured, expected, platform='linux-x64', extra_args=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = []
            for k, (native, image) in enumerate(measured, 1):
                (root / f'native-{k}.json').write_text(json.dumps(native))
                (root / f'image-{k}.json').write_text(json.dumps(image))
                args += ['--pair', str(root / f'native-{k}.json'), str(root / f'image-{k}.json')]
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('warm_prime_accept.py')),
                                     '--platform', platform, *args, '--out', str(root / 'result.json'),
                                     *extra_args], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            evidence = json.loads((root / 'result.json').read_text())
            self.assertEqual(evidence['accepted'], expected == ACCEPTED)
            self.assertEqual(evidence['valid'], expected != INVALID)
            return evidence

    def test_four_equal_pairs_are_accepted_on_every_gated_host(self):
        for host in ('linux-x64', 'linux-arm64', 'darwin-arm64'):
            with self.subTest(host=host):
                evidence = self.check_cli(pairs([report()] * 4), ACCEPTED, host)
                self.assertEqual(evidence['ratios']['cold']['cpu_seconds'], 1)

    def test_fewer_than_four_pairs_is_an_invalid_measurement(self):
        evidence = self.check_cli(pairs([report()] * 3), INVALID)
        self.assertIn('fewer than 4', evidence['invalid'][0])

    def test_the_gate_is_the_median_of_the_pairs(self):
        # 1.10, 1.12, 1.14, 1.16: median 1.13, every pair within 0.03 of it.
        self.check_cli(pairs([report(cold_cpu=c) for c in (1.10, 1.12, 1.14, 1.16)]), ACCEPTED)
        # 1.14, 1.15, 1.16, 1.17: median 1.155.
        evidence = self.check_cli(pairs([report(cold_cpu=c) for c in (1.14, 1.15, 1.16, 1.17)]), FAILED)
        self.assertTrue(any('cold cpu_seconds' in f and 'over 1.15' in f for f in evidence['failures']))

    def test_the_median_is_compared_unrounded(self):
        self.check_cli(pairs([report(cold_cpu=1.15)] * 4), ACCEPTED)
        self.check_cli(pairs([report(cold_cpu=1.150001)] * 4), FAILED)

    def test_one_pair_outside_the_spread_is_tolerated_and_two_invalidate(self):
        evidence = self.check_cli(pairs([report(cold_cpu=c) for c in (1.08, 1.08, 1.08, 1.30)]), ACCEPTED)
        self.assertEqual(evidence['spread']['pairs_outside'], [4])
        evidence = self.check_cli(pairs([report(cold_cpu=c) for c in (1.00, 1.08, 1.08, 1.20)]), INVALID)
        self.assertIn('further than 0.03', evidence['invalid'][0])

    def test_readiness_uses_the_median_without_a_spread_bound(self):
        self.check_cli(pairs([report(cold_ready=r) for r in (0.95, 1.5, 1.0, 1.05)]), ACCEPTED, 'darwin-arm64')
        self.check_cli(pairs([report(cold_ready=r) for r in (1.16, 1.2, 1.0, 1.17)]), FAILED, 'darwin-arm64')

    def test_warm_medians_and_faults_are_gated(self):
        image = report()
        for session in image['sessions'][1:]:
            session['cpu_seconds'] = session['cpu_sample']['cpu_seconds'] = 1.16
        image['warm']['cpu_seconds'] = 1.16
        self.check_cli(pairs([image] * 4), FAILED)
        image = report()
        image['sessions'][0]['complete_page_faults'] = 201
        image['sessions'][0]['waited_usage']['minor_faults'] = 200
        self.check_cli(pairs([image] * 4), FAILED)

    def test_readiness_samples_do_not_substitute_for_complete_kernel_counters(self):
        image = report()
        image['sessions'][0]['page_faults'] = image['sessions'][0]['cpu_sample']['page_faults'] = 1000
        evidence = self.check_cli(pairs([image] * 4), ACCEPTED)
        self.assertEqual(evidence['ratios']['cold']['page_faults'], 100)
        self.assertEqual(evidence['ratios']['cold']['complete_page_faults'], 1)

    def test_a_malformed_sample_invalidates_the_whole_measurement(self):
        cases = []
        for field, value in (('measurement_version', 2), ('fault_scope', 'readiness'), ('units', 303)):
            image = report()
            image[field] = value
            cases.append(image)
        for field, value in (('valid', False), ('scope_id', 'sampled'), ('attempts', 0),
                             ('processes', 0), ('observation_ns', -1), ('cpu_seconds', 0)):
            image = report()
            image['sessions'][0]['cpu_sample'][field] = value
            cases.append(image)
        for value in (None, dict(scope_id='outer-includes-python', minor_faults=99, major_faults=1),
                      dict(scope_id=FAULT_SCOPE, minor_faults=-1, major_faults=101),
                      dict(scope_id=FAULT_SCOPE, minor_faults=99, major_faults=2)):
            image = report()
            image['sessions'][0]['waited_usage'] = value
            cases.append(image)
        image = report()
        image['warm']['complete_page_faults'] = 1
        cases.append(image)
        image = report()
        image['warm']['cpu_seconds'] = 0.5
        cases.append(image)
        image = report()
        image['sessions'].pop()
        cases.append(image)
        for broken in cases:
            with self.subTest(broken=broken):
                self.check_cli(pairs([report(), report(), broken, report()]), INVALID)

    def test_a_session_that_is_not_ready_or_another_path_fails_the_gate(self):
        for field, value in (('ok', False), ('cache', 'copied')):
            with self.subTest(field=field):
                image = report()
                image['sessions'][0][field] = value
                self.check_cli(pairs([report(), image, report(), report()]), FAILED)

    def test_windows_records_the_path_comparison_without_gating(self):
        native = report()
        native['sessions'][0].update(builds='in clangd', owned_cache='not used')
        evidence = self.check_cli(pairs([report(cold_cpu=2)] * 4, native), ACCEPTED, 'win32-x64')
        self.assertFalse(evidence['gated'])
        self.assertEqual(evidence['ratios']['cold']['cpu_seconds'], 2)


if __name__ == '__main__':
    unittest.main()
