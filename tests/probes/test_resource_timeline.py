"""Exercise request/resource correlation through a real framed subprocess."""
import json
from pathlib import Path
import platform
import tempfile
import time
import unittest

from project_completion import Resources, replay


@unittest.skipUnless(platform.system() == 'Linux', 'resource sampler uses /proc')
class ResourceTimelineTest(unittest.TestCase):
    def test_normal_and_deferred_spans_share_the_resource_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / 'engine.py'
            engine.write_text('''#!/usr/bin/env python3
import json,sys,time
while True:
    headers={}
    while True:
        line=sys.stdin.buffer.readline()
        if not line:sys.exit(0)
        if line in (b'\\r\\n',b'\\n'):break
        key,value=line.decode().split(':',1);headers[key.lower()]=value.strip()
    message=json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    if message['method']=='exit':break
    if 'id' not in message:continue
    result=None
    if message['method']=='initialize':result={'capabilities':{}}
    if message['method']=='textDocument/completion':
        until=time.process_time()+0.2
        while time.process_time()<until:pass
        result={'items':[{'label':'vector','kind':7}],'isIncomplete':False}
    body=json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}).encode()
    sys.stdout.buffer.write(('Content-Length: %d\\r\\n\\r\\n'%len(body)).encode()+body)
    sys.stdout.buffer.flush()
''')
            engine.chmod(0o755)
            case = root / 'case.json'
            case.write_text(json.dumps({
                'id': 'resource-timeline', 'platform': replay.platform_name(),
                'baseline': 'pass', 'project': '.', 'timeout_seconds': 10,
                'sequence': [
                    {'method': 'initialize', 'params': {}},
                    {'method': 'textDocument/completion', 'params': {},
                     'expected_symbols': ['vector']},
                    {'method': 'textDocument/completion', 'params': {},
                     'defer': 'pending'},
                    {'action': 'await', 'request': 'pending',
                     'expect': {'/result/items/0/kind': 7}},
                ],
            }))
            resources = Resources()
            def snapshot(proc, method):
                result = resources.snapshot(proc, method)
                if result is not None:
                    time.sleep(0.06)  # A slow observer must not inflate reply latency.
                return result
            try:
                result = replay.replay(engine, case, process_started=resources.started,
                                       request_snapshot=snapshot)
            finally:
                sampled = resources.finish()
            self.assertEqual(result['outcome'], 'pass', result)
            self.assertTrue(result['readers_stopped'])
            self.assertTrue(sampled['sampler_stopped'])
            self.assertFalse(sampled['errors'])
            replies = result['raw_responses']
            self.assertEqual([r['method'] for r in replies],
                             ['initialize', 'textDocument/completion', 'textDocument/completion'])
            for reply in replies:
                start, end = reply['started_monotonic_ns'], reply['completed_monotonic_ns']
                self.assertLess(start, end)
                self.assertLessEqual((end-start)/1e6, reply['elapsed_ms'] + 0.001)
                if reply['method'] == 'textDocument/completion':
                    samples = reply['resource_snapshots']
                    self.assertLessEqual(samples['start']['monotonic_ns'], start)
                    self.assertGreaterEqual(samples['end']['sample_started_monotonic_ns'], end)
                    self.assertGreater(samples['end']['cpu_ms'], samples['start']['cpu_ms'])
                    self.assertEqual((end-start)/1e6, reply['elapsed_ms'])
            self.assertLessEqual(replies[1]['completed_monotonic_ns'],
                                 replies[2]['started_monotonic_ns'])
            stable = [s for s in sampled['samples']
                      if replies[1]['started_monotonic_ns'] <= s['sample_started_monotonic_ns']
                      <= replies[2]['completed_monotonic_ns']]
            stable = [s for s in stable if s['monotonic_ns'] <= replies[2]['completed_monotonic_ns']]
            self.assertGreaterEqual(len(stable), 2)
            self.assertGreater(stable[-1]['cpu_ms'], stable[0]['cpu_ms'])


if __name__ == '__main__':
    unittest.main()
