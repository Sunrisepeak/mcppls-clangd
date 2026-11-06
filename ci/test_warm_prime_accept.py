"""Exercise the actual acceptance CLI with complete and deliberately incomplete reports."""
import copy
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
    def check_cli(self, image, accepted, platform='darwin-arm64'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'native.json').write_text(json.dumps(report()))
            (root / 'image.json').write_text(json.dumps(image))
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('warm_prime_accept.py')),
                                     '--platform', platform, '--native', str(root / 'native.json'),
                                     '--image', str(root / 'image.json'), '--out', str(root / 'result.json')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0 if accepted else 1, result.stdout + result.stderr)
            evidence = json.loads((root / 'result.json').read_text())
            self.assertEqual(evidence['accepted'], accepted)
            return evidence

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
