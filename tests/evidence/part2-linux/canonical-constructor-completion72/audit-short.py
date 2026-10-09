from pathlib import Path
import json,gzip,sys
root=Path(sys.argv[1])
def read(p):
 return json.loads(p.read_text()) if p.exists() else json.loads(gzip.decompress(p.with_name(p.name+'.gz').read_bytes()))
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits','documentation']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
reports={};proof_count=0
for mode in ['headers','modules']:
 for side in ['baseline','candidate','after']:
  label=side+'-'+mode;p=root/label;d=read(p/'report.json');w=read(p/'workload.json');proofs=read(p/'selected-insertions.json')['proofs']
  assert d['starts']==1 and d['rounds']==3 and d['all_semantic_requests_passed']
  assert not w['compiler_overlap'] and not w['multiple_engine_overlap'] and not w['errors'] and w['watcher_stopped']
  answers=d['raw_results'][0]['context_answers'];assert len(answers)==8;selected=set()
  for phase,n in [('cold-open',1),('settled-warm',4),('edited',3)]:
   ids=[i for i,a in enumerate(answers) if a['phase']==phase];assert len(ids)==n
   selected.update([ids[0],ids[-1],max(ids,key=lambda i:answers[i]['elapsed_ms'])])
  assert {x['answer'] for x in proofs}==selected and all(x['exit_code']==0 for x in proofs)
  for a in answers:
   expected=23 if side=='candidate' or mode=='headers' else 65
   assert len(a['items'])==expected and len(set(map(key,a['items'])))==23
   assert sum(x['kind']==4 for x in a['items'])==expected-2
  reports[label]=d;proof_count+=len(proofs)
 for a,b,c in zip(*(reports[side+'-'+mode]['raw_results'][0]['context_answers'] for side in ['baseline','candidate','after'])):
  assert a['phase']==b['phase']==c['phase'] and a['draft']==b['draft']==c['draft']
  assert sorted(map(key,a['items']))==sorted(map(key,c['items']))
  assert set(map(key,a['items']))==set(map(key,b['items']))
  if mode=='headers':assert sorted(map(key,a['items']))==sorted(map(key,b['items']))
print(json.dumps({'scope':'Private constructor correctness/short controls only; no stable production latency gain claim. Canonical identity separately proven by profile and baseline-failing fixture.','typed_sema_checks':48,'selected_gcc_insertions':proof_count,'all_distinct_edit_fields_and_documentation_equal':True,'headers_multiplicity_unchanged':True,'modules_only_constructor_multiplicity_changed':True,'sampled_workload_pass':True}))
