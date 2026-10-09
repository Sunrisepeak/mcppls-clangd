from pathlib import Path
import json,hashlib,collections,math,gzip
q=Path(__file__).parent;root=q/'four-arm'
summary=json.loads((root/'summary.json').read_text());assert summary['all_explicit_performance_checks_pass']
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits','documentation']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
reports={};count=proof_count=0;cdb=set();detail={}
for arm in ['baseline-headers','candidate-modules','baseline-modules','candidate-headers']:
 folder=root/arm;data=gzip.decompress((folder/'report.json.gz').read_bytes());d=json.loads(data);reports[arm]=d
 expected='696e8caa5246525669583eb0f999f23cb21a87191f3b1be59a0c3952a5d1a0b1' if arm.startswith('candidate-') else '5213fa91c24f93f9d3a6f625f4a0699f4ea93892063a7032b2b9ef34b13a179e'
 assert d['engine_sha256']==expected and d['starts']==3 and d['rounds']==30 and d['all_semantic_requests_passed']
 wanted=set()
 for start,raw in enumerate(d['raw_results']):
  assert raw['outcome']=='pass' and raw['exit_code']==0 and raw['readers_stopped']
  answers=raw['context_answers'];assert len(answers)==62
  assert collections.Counter(a['phase'] for a in answers)=={'cold-open':1,'settled-warm':31,'edited':30}
  for answer in answers:
   assert answer['semantic_pass'] and not answer['semantic_origin_failed'] and not answer['index_origin_failed'] and not answer['missing'] and not answer['untyped_expected']
   assert answer['origin']['sema']>0
  for phase in ['cold-open','settled-warm','edited']:
   ids=[i for i,a in enumerate(answers) if a['phase']==phase]
   chosen={ids[0],ids[-1],max(ids,key=lambda i:answers[i]['elapsed_ms'])}
   wanted.update((start,index,symbol) for index in chosen for symbol in d['context']['expected'])
  count+=len(answers)
 for phase,n in [('cold-open',3),('settled-warm',93),('edited',90)]:
  p=d['phases'][phase];assert p['requested']==p['answered']==len(p['samples_ms'])==n and p['missing']==0
  assert p['p95_ms']==sorted(p['samples_ms'])[math.ceil(.95*n)-1]
 workload=json.loads(gzip.decompress((folder/'workload.json.gz').read_bytes()))
 assert not workload['compiler_overlap'] and not workload['multiple_engine_overlap'] and not workload['errors'] and workload['watcher_stopped']
 assert workload['samples'] and all(not x['compilers'] and len({e['pgid'] for e in x['engines']})<=1 for x in workload['samples'])
 proofs=json.loads((folder/'selected-insertions.json').read_text())['proofs']
 assert {(p['start'],p['answer'],p['symbol']) for p in proofs}==wanted and len(proofs)==len(wanted)==summary['arms'][arm]['gcc_insertions']
 assert all(p['exit_code']==0 for p in proofs);cdb.update(p['cdb_sha256'] for p in proofs);proof_count+=len(proofs)
 detail[arm]={'report_sha256':hashlib.sha256(data).hexdigest(),'typed_sema_checks':186,'selected_gcc_insertions':len(proofs),'warm_p95_ms':d['phases']['settled-warm']['p95_ms'],'edited_p95_ms':d['phases']['edited']['p95_ms']}
for mode in ['headers','modules']:
 before=reports['baseline-'+mode];after=reports['candidate-'+mode]
 assert before['draft_source_sha256']==after['draft_source_sha256']
 for br,cr in zip(before['raw_results'],after['raw_results']):
  for ba,ca in zip(br['context_answers'],cr['context_answers']):
   assert ba['phase']==ca['phase'] and ba['draft']==ca['draft']
   old=collections.Counter(map(key,ba['items']));new=collections.Counter(map(key,ca['items']))
   assert set(old)==set(new)
   if mode=='headers':assert old==new
   else:
    for item,n in old.items():assert new[item]==(1 if json.loads(item)['kind']==4 else n)
assert count==744 and proof_count==82 and len(cdb)==1
report={'scope':'Final72 versus portable70 same Clang12 recipe, four arms3x30. Distinct edits/documentation preserved; only known module constructor multiplicity removed. Selected replies compiled. Main resources only; not full release or header parity.','arms':detail,'typed_sema_checks':count,'selected_gcc_insertions':proof_count,'proof_cdb_hashes':sorted(cdb),'all_actual_edit_fields_equal':True,'explicit_performance_checks':summary['explicit_performance_checks'],'resource_comparisons':summary['resource_comparisons'],'all_checked_requirements_passed':True}
assert report==json.loads((q/'four-arm-audit.json').read_text())
print(json.dumps({'typed_sema_checks':count,'selected_gcc_insertions':proof_count,'all_checked_requirements_passed':True}))
