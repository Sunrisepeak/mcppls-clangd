"""Exercise the actual acceptance CLI with complete and deliberately incomplete reports."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION, READY_CPU_SCOPE


def report():
    session = dict(kind='cold', ok=True, ready_seconds=1, cpu_seconds=1,
                   page_faults=10, complete_page_faults=100,
                   cpu_sample=dict(valid=True, scope_id=READY_CPU_SCOPE, cpu_seconds=1, page_faults=10,
                                   attempts=1, processes=1, observation_ns=1000),
                   waited_usage=dict(scope_id=FAULT_SCOPE, minor_faults=99, major_faults=1),
                   builds='in supervised workers', owned_cache='/cache', cache='owned')
    sessions = [copy.deepcopy(session) for _ in range(4)]
    for s in sessions[1:]:
        s['kind'] = 'warm'
    return dict(measurement_version=MEASUREMENT_VERSION, fault_scope=FAULT_SCOPE,
                units=304, probes=['main.cpp', 'deep.cppm', 'test.cpp'], sessions=sessions,
                warm=dict(ready_seconds=1, cpu_seconds=1, page_faults=10,
                          complete_page_faults=100, modules_built=0))


class WarmAcceptanceTests(unittest.TestCase):
    def check_cli(self, image, accepted, platform='darwin-arm64', native=None, release=None, extra_args=(), identities=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = copy.deepcopy(native if native is not None else report())
            image = copy.deepcopy(image)
            if identities:
                for name in ('native-engine', 'runner', 'image.okb'):
                    (root / name).write_bytes(name.encode())
                native['engine'] = [str(root / 'native-engine')]
                image['engine'] = [str(root / 'runner'), str(root / 'image.okb')]
            (root / 'native.json').write_text(json.dumps(native))
            (root / 'image.json').write_text(json.dumps(image))
            options = list(extra_args)
            if release is not None:
                options += ['--release-version', release, '--source-commit', 'a' * 40]
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('warm_prime_accept.py')),
                                     '--platform', platform, '--native', str(root / 'native.json'),
                                     '--image', str(root / 'image.json'), '--out', str(root / 'result.json'), *options],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0 if accepted else 1, result.stdout + result.stderr)
            evidence = json.loads((root / 'result.json').read_text())
            self.assertEqual(evidence['accepted'], accepted)
            return evidence

    def cold_cpu(self, cpu):
        value = report()
        value['sessions'][0]['cpu_seconds'] = cpu
        value['sessions'][0]['cpu_sample']['cpu_seconds'] = cpu
        return value

    def test_exception_preserves_strict_failure_and_measured_artifact_identities(self):
        result = self.check_cli(self.cold_cpu(12), True, 'linux-x64', self.cold_cpu(10), '0.0.20')
        self.assertFalse(result['target_met'])
        self.assertEqual(len(result['target_failures']), 1)
        self.assertEqual(result['waived_failures'], result['target_failures'])
        self.assertEqual(result['failures'], [])
        policy = result['release_exception']
        self.assertTrue(policy['applied'])
        self.assertEqual(policy['extra_cpu_seconds'], 2)
        self.assertEqual(policy['artifact_sha256'], {
            'native': hashlib.sha256(b'native-engine').hexdigest(),
            'runner': hashlib.sha256(b'runner').hexdigest(),
            'image': hashlib.sha256(b'image.okb').hexdigest()})
        result = self.check_cli(self.cold_cpu(11.5), True, 'linux-x64', self.cold_cpu(10), '0.0.20')
        self.assertTrue(result['target_met'])
        self.assertFalse(result['release_exception']['applied'])

    def test_exception_has_both_exact_inclusive_ceilings(self):
        for native, image, accepted in ((12, 15, True), (12, 15.000001, False),
                                        (15, 18, True), (15, 18.000001, False),
                                        (10, 12.5, True), (10, 12.500001, False),
                                        (20, 23, True), (20, 23.000001, False),
                                        (20, 24, False)):
            with self.subTest(native=native, image=image):
                self.check_cli(self.cold_cpu(image), accepted, 'linux-x64', self.cold_cpu(native), '0.0.20')

    def test_exception_expires_and_does_not_apply_to_other_hosts_or_implicit_calls(self):
        for host, release in (('linux-x64', None), ('linux-x64', '0.0.21'),
                              ('linux-x64', '0.0.200'), ('linux-arm64', '0.0.20'),
                              ('darwin-arm64', '0.0.20')):
            with self.subTest(host=host, release=release):
                result = self.check_cli(self.cold_cpu(12), False, host, self.cold_cpu(10), release)
                self.assertIsNone(result['release_exception'])

    def test_exception_does_not_admit_other_failures(self):
        cases = []
        image = self.cold_cpu(12)
        image['sessions'][0]['ready_seconds'] = 1.15001
        cases.append(image)
        image = self.cold_cpu(12)
        for session in image['sessions'][1:]:
            session['cpu_seconds'] = session['cpu_sample']['cpu_seconds'] = 1.15001
        image['warm']['cpu_seconds'] = 1.15001
        cases.append(image)
        image = self.cold_cpu(12)
        image['warm']['ready_seconds'] = 1.16
        cases.append(image)
        image = self.cold_cpu(12)
        image['sessions'][0]['complete_page_faults'] = 201
        image['sessions'][0]['waited_usage']['minor_faults'] = 200
        cases.append(image)
        for field, value in (('ok', False), ('cache', 'copied'), ('cpu_sample', None)):
            image = self.cold_cpu(12)
            image['sessions'][0][field] = value
            cases.append(image)
        for field, value in (('measurement_version', 2), ('units', 303)):
            image = self.cold_cpu(12)
            image[field] = value
            cases.append(image)
        for image in cases:
            with self.subTest(image=image):
                result = self.check_cli(image, False, 'linux-x64', self.cold_cpu(10), '0.0.20')
                self.assertFalse(result['release_exception']['applied'])

    def test_exception_requires_identity_and_unchanged_other_limits(self):
        self.check_cli(self.cold_cpu(12), False, 'linux-x64', self.cold_cpu(10), '0.0.20', identities=False)
        for options in (('--limit', '1.25'), ('--fault-limit', '3')):
            self.check_cli(self.cold_cpu(12), False, 'linux-x64', self.cold_cpu(10), '0.0.20', options)
        self.check_cli(self.cold_cpu(12), False, 'linux-x64', self.cold_cpu(10),
                       extra_args=('--release-version', '0.0.20'))

    def test_invalid_values_and_rounding_cannot_bypass_the_target_or_exception(self):
        for value in (None, float('nan'), float('inf'), -1, True):
            with self.subTest(value=value):
                self.check_cli(self.cold_cpu(value), False, 'linux-x64', release='0.0.20')
        self.check_cli(self.cold_cpu(1.150001), False, 'linux-x64')

    def test_windows_path_comparison_remains_non_gating(self):
        native = report()
        native['sessions'][0].update(builds='in clangd', owned_cache='not used')
        result = self.check_cli(self.cold_cpu(2), True, 'win32-x64', native, '0.0.20')
        self.assertFalse(result['gated'])
        self.assertIsNone(result['release_exception'])

    def test_readiness_samples_do_not_substitute_for_complete_kernel_counters(self):
        image = report()
        image['sessions'][0]['page_faults'] = 1000
        result = self.check_cli(image, True)
        self.assertEqual(result['ratios']['cold']['page_faults'], 100)
        self.assertEqual(result['ratios']['cold']['complete_page_faults'], 1)
        image['sessions'][0]['page_faults'] = 1
        image['sessions'][0]['waited_usage']['minor_faults'] = 200
        image['sessions'][0]['complete_page_faults'] = 201
        self.check_cli(image, False)

    def test_rejects_legacy_or_unsupported_boundary(self):
        for field, value in [('measurement_version', 1), ('measurement_version', 2), ('fault_scope', 'readiness')]:
            with self.subTest(field=field):
                image = report()
                image[field] = value
                self.check_cli(image, False)

    def test_linux_requires_matching_valid_observations_and_original_limits(self):
        self.check_cli(report(), True, 'linux-x64')
        for field, value in [('valid', False), ('scope_id', 'sampled'), ('cpu_seconds', 0),
                             ('attempts', 0), ('processes', 0), ('observation_ns', -1)]:
            with self.subTest(field=field):
                image = report()
                image['sessions'][0]['cpu_sample'][field] = value
                self.check_cli(image, False, 'linux-x64')
        image = report()
        image['sessions'][0]['cpu_seconds'] = 1.16
        image['sessions'][0]['cpu_sample']['cpu_seconds'] = 1.16
        evidence = self.check_cli(image, False, 'linux-x64')
        self.assertTrue(any('over 1.15' in failure for failure in evidence['failures']))
        image = report()
        image['warm']['cpu_seconds'] = 0.5
        self.check_cli(image, False, 'linux-x64')

    def test_rejects_missing_wrong_scope_or_inconsistent_raw_kernel_counters(self):
        variants = [None, dict(scope_id='outer-includes-python', minor_faults=99, major_faults=1),
                    dict(scope_id=FAULT_SCOPE, minor_faults=-1, major_faults=101),
                    dict(scope_id=FAULT_SCOPE, minor_faults=True, major_faults=99),
                    dict(scope_id=FAULT_SCOPE, minor_faults=99, major_faults=2)]
        for value in variants:
            with self.subTest(value=value):
                image = report()
                image['sessions'][0]['waited_usage'] = value
                self.check_cli(image, False)

    def test_rejects_forged_warm_aggregate_and_shortened_workload(self):
        image = report()
        image['warm']['complete_page_faults'] = 1
        self.check_cli(image, False)
        image = report()
        image['sessions'].pop()
        self.check_cli(image, False)

    def test_ready_and_cpu_limits_still_apply(self):
        for field in ('ready_seconds', 'cpu_seconds'):
            with self.subTest(field=field):
                image = report()
                image['sessions'][0][field] = 1.16
                self.check_cli(image, False)


if __name__ == '__main__':
    unittest.main()
