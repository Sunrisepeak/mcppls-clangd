import copy
import unittest

from resource_window import stable_window


def boundary(time, cpu, rss):
    return {'sample_started_monotonic_ns': time, 'monotonic_ns': time + 1,
            'cpu_ms': cpu, 'rss_kib': rss}


def answer(phase, start, end, cpu_start, cpu_end, rss):
    return {'phase': phase, 'semantic_pass': True,
            'started_monotonic_ns': start + 2, 'completed_monotonic_ns': end - 1,
            'resource_snapshots': {'start': boundary(start, cpu_start, rss),
                                   'end': boundary(end, cpu_end, rss)}}


class ResourceWindowTest(unittest.TestCase):
    def setUp(self):
        self.raw = {'outcome': 'pass', 'readers_stopped': True,
                    'resources': {'errors': [], 'sampler_stopped': True, 'cpu_tick_ms': 10,
                                  'samples': [boundary(5, 3000, 90000), boundary(150, 9100, 500)]},
                    'context_answers': [answer('cold-open', 0, 10, 0, 9000, 90000),
                                        answer('settled-warm', 100, 200, 9000, 9100, 400),
                                        answer('edited', 300, 400, 9200, 9400, 450)]}

    def test_boundaries_exclude_cold_and_include_intervening_work(self):
        result = stable_window(self.raw)
        self.assertEqual(result['stable_requests'], 2)
        self.assertEqual(result['cpu_ms'], 400)
        self.assertEqual((result['cpu_lower_ms'], result['cpu_upper_ms']), (380, 420))
        self.assertEqual(result['rss_observed_max_kib'], 500)
        self.assertEqual(result['rss_observations'], 5)

    def test_weak_or_failed_evidence_is_rejected(self):
        variants = []
        weak = copy.deepcopy(self.raw)
        del weak['context_answers'][1]['resource_snapshots']
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        weak['context_answers'][0]['semantic_pass'] = False
        variants.append(weak)  # Cold failures cannot silently gain qualification.
        weak = copy.deepcopy(self.raw)
        weak['resources']['errors'] = ['read failed']
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        weak['resources']['sampler_stopped'] = False
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        del weak['resources']['cpu_tick_ms']
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        weak['context_answers'][2]['resource_snapshots']['end']['cpu_ms'] = 9000
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        weak['context_answers'][2]['resource_snapshots']['start']['monotonic_ns'] = 500
        variants.append(weak)
        weak = copy.deepcopy(self.raw)
        weak['resources']['samples'][1]['rss_kib'] = float('nan')
        variants.append(weak)
        for raw in variants:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    stable_window(raw)


if __name__ == '__main__':
    unittest.main()
