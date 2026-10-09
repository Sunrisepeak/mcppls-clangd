from pathlib import Path
import json,gzip,sys
root=Path(sys.argv[1])
def read(p):
 return json.loads(p.read_text()) if p.exists() else json.loads(gzip.decompress(p.with_name(p.name+'.gz').read_bytes()))
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits','documentation']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
reports={};counts={}
for label in ['baseline-headers','candidate-headers','after-headers','baseline-modules','candidate-modules','after-modules']:
 p=root/label;d=read(p/'report.json');w=read(p/'workload.json');proofs=read(p/'selected-insertions.json')['proofs']
 assert d['starts']==1 and d['rounds']==3 and d['all_semantic_requests_passed']
 assert not w['compiler_overlap'] and not w['multiple_engine_overlap'] and not w['errors'] and w['watcher_stopped']
 answers=d['raw_results'][0]['context_answers'];assert len(answers)==8
 selected=set()
 for phase,n in [('cold-open',1),('settled-warm',4),('edited',3)]:
  ids=[i for i,a in enumerate(answers) if a['phase']==phase];assert len(ids)==n
  selected.update([ids[0],ids[-1],max(ids,key=lambda i:answers[i]['elapsed_ms'])])
 assert {x['answer'] for x in proofs}==selected and all(x['exit_code']==0 for x in proofs)
 reports[label]=d;counts[label]=len(proofs)
for mode in ['headers','modules']:
 before=reports['baseline-'+mode]
 for label in ['candidate-'+mode,'after-'+mode]:
  other=reports[label];assert before['draft_source_sha256']==other['draft_source_sha256']
  for a,b in zip(before['raw_results'][0]['context_answers'],other['raw_results'][0]['context_answers']):
   assert a['phase']==b['phase'] and a['draft']==b['draft']
   assert sorted(map(key,a['items']))==sorted(map(key,b['items']))
print(json.dumps({'scope':'Private short controls only, not portable release qualification.','typed_sema_checks':48,'selected_gcc_insertions':sum(counts.values()),'all_returned_edit_fields_and_documentation_equal':True,'sampled_workload_pass':True}))
