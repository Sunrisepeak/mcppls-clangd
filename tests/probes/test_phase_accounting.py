"""An AST readiness barrier is explicit; failed cold replies stay failures."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PhaseAccountingTest(unittest.TestCase):
    def run_probe(self, settled_only):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / 'engine.py'
            engine.write_text('''#!/usr/bin/env python3
import json,sys
ready=False
while True:
    headers={}
    while True:
        line=sys.stdin.buffer.readline()
        if not line:sys.exit(0)
        if line in (b'\\r\\n',b'\\n'):break
        key,value=line.decode().split(':',1);headers[key.lower()]=value.strip()
    message=json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    method=message['method']
    if method=='exit':break
    if 'id' not in message:continue
    result=None
    if method=='initialize':result={'capabilities':{}}
    if method=='textDocument/documentSymbol':ready=True;result=[]
    if method=='textDocument/completion':
        items=[{'label':'vector<class T>','kind':7}] if ready else []
        result={'items':items,'isIncomplete':False}
        print('Code complete: %d results from Sema, 0 from Index, 0 matched, 0 from identifiers, %d returned.'%(len(items),len(items)),file=sys.stderr,flush=True)
    body=json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}).encode()
    sys.stdout.buffer.write(('Content-Length: %d\\r\\n\\r\\n'%len(body)).encode()+body)
    sys.stdout.buffer.flush()
''')
            engine.chmod(0o755)
            source = root / 'Use.cpp'
            source.write_text('void f() {\n  anchor;\n}\n')
            context = root / 'context.json'
            context.write_text(json.dumps({'name': 'readiness', 'before': '  anchor;',
                                          'prefix': '  std::ve', 'suffix': 'ctor;\n',
                                          'replace_anchor': True, 'expected': ['vector'],
                                          'kind': {'vector': 7}, 'require_sema': True}))
            output = root / 'report.json'
            command = [sys.executable, str(Path(__file__).with_name('project_completion.py')),
                       '--engine', str(engine), '--source', str(source), '--project', str(root),
                       '--context-file', str(context), '--output', str(output),
                       '--starts', '1', '--rounds', '2', '--phases']
            if settled_only:
                command.append('--settled-only')
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            return result.returncode, json.loads(output.read_text())

    def test_default_records_the_failed_cold_completion(self):
        code, report = self.run_probe(False)
        self.assertEqual(code, 1)
        self.assertTrue(report['cold_completion_requested'])
        self.assertFalse(report['all_semantic_requests_passed'])
        cold = report['raw_results'][0]['context_answers'][0]
        self.assertEqual(cold['phase'], 'cold-open')
        self.assertEqual(cold['missing'], ['vector'])
        self.assertFalse(cold['semantic_pass'])

    def test_ast_ready_mode_requests_no_cold_completion_and_keeps_edit_drafts(self):
        code, report = self.run_probe(True)
        self.assertEqual(code, 0)
        self.assertFalse(report['cold_completion_requested'])
        self.assertEqual(report['measurement_mode'], 'ast-ready-only')
        self.assertNotIn('cold-open', report['phases'])
        self.assertTrue(report['all_semantic_requests_passed'])
        answers = report['raw_results'][0]['context_answers']
        self.assertEqual([a['phase'] for a in answers],
                         ['settled-warm', 'edited', 'settled-warm', 'edited', 'settled-warm'])
        self.assertEqual(answers[1]['draft'], answers[2]['draft'])
        self.assertEqual(answers[3]['draft'], answers[4]['draft'])
        self.assertTrue(answers[1]['draft'].endswith('// probe 0\n'))
        self.assertTrue(answers[3]['draft'].endswith('// probe 1\n'))


if __name__ == '__main__':
    unittest.main()
