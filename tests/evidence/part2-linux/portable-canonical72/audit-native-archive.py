from pathlib import Path
import json,hashlib,collections,math,gzip
q=Path(__file__).parent;root=q/'native-settled-distribution'
summary=json.loads((root/'summary.json').read_text());assert summary['all_explicit_performance_checks_pass']
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
reports={};count=proof_count=0;cdb=set();detail={}
for arm in ['baseline-before','candidate','baseline-after']:
 folder=root/arm;data=gzip.decompress((folder/'report.json.gz').read_bytes());d=json.loads(data);reports[arm]=d
 expected='696e8caa5246525669583eb0f999f23cb21a87191f3b1be59a0c3952a5d1a0b1' if arm=='candidate' else 'c52547480ebac0f2887bb70e34bdfb54a0841d6bc84881c21e66de81c1bf2b0b'
 assert d['engine_sha256']==expected and d['starts']==3 and d['rounds']==30 and d['all_semantic_requests_passed']
 wanted=set()
 for start,raw in enumerate(d['raw_results']):
  assert raw['outcome']=='pass' and raw['exit_code']==0 and raw['readers_stopped']
  answers=raw['context_answers'];assert len(answers)==61
  assert collections.Counter(a['phase'] for a in answers)=={'settled-warm':31,'edited':30}
  for answer in answers:
   assert answer['semantic_pass'] and not answer['semantic_origin_failed'] and not answer['index_origin_failed'] and not answer['missing'] and not answer['untyped_expected']
   assert answer['origin']['sema']>0
  for phase in ['settled-warm','edited']:
   ids=[i for i,a in enumerate(answers) if a['phase']==phase]
   chosen={ids[0],ids[-1],max(ids,key=lambda i:answers[i]['elapsed_ms'])}
   wanted.update((start,index,symbol) for index in chosen for symbol in d['context']['expected'])
  count+=len(answers)
 for phase,n in [('settled-warm',93),('edited',90)]:
  p=d['phases'][phase];assert p['requested']==p['answered']==len(p['samples_ms'])==n and p['missing']==0
  assert p['p95_ms']==sorted(p['samples_ms'])[math.ceil(.95*n)-1]
 workload=json.loads(gzip.decompress((folder/'workload.json.gz').read_bytes()))
 assert not workload['compiler_overlap'] and not workload['multiple_engine_overlap'] and not workload['errors'] and workload['watcher_stopped']
 assert workload['samples'] and all(not x['compilers'] and len({e['pgid'] for e in x['engines']})<=1 for x in workload['samples'])
 proofs=json.loads((folder/'insertions.json').read_text())
 assert {(p['start'],p['answer'],p['symbol']) for p in proofs}==wanted and len(proofs)==len(wanted)==summary['arms'][arm]['selected_native_insertions']
 assert all(p['exit_code']==0 for p in proofs);cdb.update(p['cdb_sha256'] for p in proofs);proof_count+=len(proofs)
 detail[arm]={'report_sha256':hashlib.sha256(data).hexdigest(),'typed_sema_checks':183,'selected_native_insertions':len(proofs),'warm_p95_ms':d['phases']['settled-warm']['p95_ms'],'edited_p95_ms':d['phases']['edited']['p95_ms']}
for start in range(3):
 rows=[reports[a]['raw_results'][start]['context_answers'] for a in ['baseline-before','candidate','baseline-after']]
 for before,candidate,after in zip(*rows):
  assert before['phase']==candidate['phase']==after['phase'] and before['draft']==candidate['draft']==after['draft']
  assert sorted(map(key,before['items']))==sorted(map(key,candidate['items']))==sorted(map(key,after['items']))
assert count==549 and len(cdb)==1
report={'scope':'Final72 AST-ready native three-arm qualification only; cold baseline not requested, old failures retained. Selected replies compiled, not every reply. Main resources do not qualify descendants or physical cache.','arms':detail,'typed_sema_checks':count,'selected_native_insertions':proof_count,'proof_cdb_hashes':sorted(cdb),'all_actual_edit_fields_equal':True,'explicit_performance_checks':summary['explicit_performance_checks'],'comparisons':summary['comparisons'],'all_checked_requirements_passed':True}
assert report==json.loads((q/'native-distribution-audit.json').read_text())
print(json.dumps({'typed_sema_checks':count,'selected_native_insertions':proof_count,'all_checked_requirements_passed':True}))
