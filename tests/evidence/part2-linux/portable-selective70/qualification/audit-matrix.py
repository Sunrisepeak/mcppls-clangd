from pathlib import Path
import json,hashlib,collections,time,gc
q=Path(__file__).parent
pkg=Path('/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd')
m=json.loads((pkg/'engine.json').read_text())
original=json.loads((q/'matrix-distribution/summary.json').read_text())
remainder=json.loads((q/'matrix-distribution-remainder/summary.json').read_text())
assert len(original['results'])==11 and set(remainder['results'])=={'string'}
assert not (set(original['results']) & set(remainder['results']))
assert original['engine_sha256']==remainder['engine_sha256']==m['sha256']
audit={'scope':'Final70 per-context qualification: original eleven completed controls plus separately run previously unstarted string. Original invocation exit1/preflight compiler block remains; no passed timing replaced. Sampled workload only, no full release or descendant resource claim.', 'engine_metadata':m,'original_invocation_exit_code':1,'remainder_invocation_exit_code':0,'contexts':{},'request_checks':0,'typed_sema_required':0,'include_checks':0,'empty_negative_checks':0,'selected_gcc_insertions':0,'recorded_unix':time.time()}
cdb_hashes=set()
for source,summary in [('matrix-distribution',original),('matrix-distribution-remainder',remainder)]:
 for name,row in summary['results'].items():
  folder=q/source/name
  data=(folder/'report.json').read_bytes();d=json.loads(data)
  assert d['engine_sha256']==m['sha256'] and d['starts']==3 and d['rounds']==30
  assert d['all_semantic_requests_passed'] and row['exit_code']==0 and row['semantic_pass']
  assert row['warm_edited_p95_pass'] is not False and row['all_selected_insertions_compiled'] is not False
  assert len(d['raw_results'])==3
  context=d['context'];n=0;wanted=set();base=None
  for start,raw in enumerate(d['raw_results']):
   assert raw['outcome']=='pass' and raw['readers_stopped'] and raw['exit_code']==0
   answers=raw['context_answers'];assert len(answers)==62
   assert collections.Counter(a['phase'] for a in answers)=={'cold-open':1,'settled-warm':31,'edited':30}
   if base is None:base=answers[0]['draft']
   assert answers[0]['draft']==answers[1]['draft']==base
   for round_index in range(30):
    expected=base+f'\n// probe {round_index}\n'
    assert answers[2+2*round_index]['draft']==answers[3+2*round_index]['draft']==expected
   for a in answers:
    assert a['semantic_pass'] and not a['semantic_origin_failed'] and not a['index_origin_failed'] and not a['missing'] and not a['untyped_expected']
    if context.get('require_sema'):assert a['origin']['sema']>0
    if context.get('expect_empty'):assert not a['items']
    if name in {'std-qualified','first-column','ordinary'} and a['phase']!='cold-open':assert a['origin']['index']>0 and a['origin']['matched']>0
   selected=set()
   for phase in ['cold-open','settled-warm','edited']:
    indices=[i for i,a in enumerate(answers) if a['phase']==phase]
    selected.update([indices[0],indices[-1],max(indices,key=lambda i:answers[i]['elapsed_ms'])])
   wanted.update((start,index,symbol) for index in selected for symbol in context['expected'])
   n+=len(answers)
  assert n==186
  for phase,count in [('cold-open',3),('settled-warm',93),('edited',90)]:
   x=d['phases'][phase]
   assert x['requested']==x['answered']==count and x['missing']==0 and len(x['samples_ms'])==count
  workload=json.loads((folder/'workload.json').read_text())
  assert not workload['compiler_overlap'] and not workload['multiple_engine_overlap'] and not workload['errors'] and workload['watcher_stopped']
  assert workload['samples'] and all(not s['compilers'] and len({e['pgid'] for e in s['engines']})<=1 for s in workload['samples'])
  proofs=json.loads((folder/'selected-insertions.json').read_text())['proofs']
  actual={(p['start'],p['answer'],p['symbol']) for p in proofs}
  assert actual==wanted and len(proofs)==len(wanted)==row['selected_insertions']
  assert all(p['exit_code']==0 for p in proofs)
  cdb_hashes.update(p['cdb_sha256'] for p in proofs)
  audit['request_checks']+=n;audit['selected_gcc_insertions']+=len(proofs)
  bucket='typed_sema_required' if context.get('require_sema') else 'empty_negative_checks' if context.get('expect_empty') else 'include_checks'
  audit[bucket]+=n
  audit['contexts'][name]={'source':source,'report_sha256':hashlib.sha256(data).hexdigest(),'checks':n,'selected_insertions':len(proofs),'warm_p95_ms':d['phases']['settled-warm']['p95_ms'],'edited_p95_ms':d['phases']['edited']['p95_ms'],'budget_pass':row['warm_edited_p95_pass'],'semantic_pass':True,'draft_inputs_checked':True,'exact_selected_reply_set_checked':True,'sampled_workload_pass':True}
  del d,data;gc.collect()
assert len(audit['contexts'])==12 and audit['request_checks']==2232
assert audit['typed_sema_required']==1674 and audit['include_checks']==186 and audit['empty_negative_checks']==372
assert len(cdb_hashes)==1
assert audit['selected_gcc_insertions']==sum(row['selected_insertions'] for summary in [original,remainder] for row in summary['results'].values())
audit['proof_cdb_hashes']=sorted(cdb_hashes);audit['all_per_context_requirements_passed']=True
(q/'matrix-distribution-combined-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps({k:audit[k] for k in ['request_checks','typed_sema_required','include_checks','empty_negative_checks','selected_gcc_insertions','all_per_context_requirements_passed']}))
