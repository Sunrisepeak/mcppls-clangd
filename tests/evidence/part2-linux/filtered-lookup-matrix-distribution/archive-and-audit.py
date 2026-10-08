from pathlib import Path
import gzip,hashlib,json,math,sys,shutil
root=Path('/tmp/mcppls-filtered-lookup-formal-build/matrix-distribution')
repo=Path('/home/speak/workspace/github/mcppls-clangd')
out=repo/'tests/evidence/part2-linux/filtered-lookup-matrix-distribution'
sys.path.insert(0,str(repo/'tests/probes'))
from completion_insertion import apply
sha=lambda b:hashlib.sha256(b).hexdigest()
summary=json.loads((root/'summary.json').read_text())
audit={'scope':summary['scope'],'engine_sha256':summary['engine_sha256'],'production_source_commit':'7db2e70abf4e6e760ceef25a142f55085fe52a8c','contexts':{},'raw_context_replies':0,'required_typed_sema_replies':0,'selected_gcc_insertions':0,'artifact_sha256':{}}
for name,row in summary['results'].items():
 p=root/name; d=json.loads((p/'report.json').read_text());ctx=d['context']
 assert row['exit_code']==0 and row['semantic_pass'] is True
 assert d['engine_sha256']==summary['engine_sha256']
 assert d['source_sha256']=='bac3d5a798671ba51db0640ccfd63a7b7a72750b9561503565697c420f61a871'
 assert d['starts']==3 and d['rounds']==30 and len(d['raw_results'])==3
 answers=[];per_start=[]
 for start,raw in enumerate(d['raw_results']):
  assert raw['outcome']=='pass' and raw['exit_code']==0 and raw['readers_stopped']
  assert raw['resources']['sampler_stopped'] and not raw['resources']['errors']
  aa=raw['context_answers']; assert len(aa)==62
  phases={}
  for phase,n in [('cold-open',1),('settled-warm',31),('edited',30)]:
   rows=[a for a in aa if a['phase']==phase]; assert len(rows)==n
   ss=sorted(a['elapsed_ms'] for a in rows)
   phases[phase]={'answered':n,'p95_ms':ss[math.ceil(.95*n)-1],'max_ms':ss[-1]}
  per_start.append({'start':start,'phases':phases})
  for a in aa:
   assert a['semantic_pass'] and not any(a[k] for k in ['missing','polluted','unexpected_nonempty','semantic_origin_failed','untyped_expected'])
   if ctx.get('require_sema'):assert a['origin']['sema']>0
   if name in ['comment','string']:assert not a['items']
  answers.extend(aa)
 for phase,n in [('cold-open',3),('settled-warm',93),('edited',90)]:
  rows=[a for a in answers if a['phase']==phase]; ss=sorted(a['elapsed_ms'] for a in rows)
  assert d['phases'][phase]['answered']==n and d['phases'][phase]['missing']==0
  assert len(rows)==n and ss[math.ceil(.95*n)-1]==d['phases'][phase]['p95_ms']
 proofs=json.loads((p/'selected-insertions.json').read_text())['proofs']
 assert len(proofs)==row['selected_insertions']
 expected=set()
 for start,raw in enumerate(d['raw_results']):
  aa=raw['context_answers']; selected=set()
  for phase in ['cold-open','settled-warm','edited']:
   ids=[i for i,a in enumerate(aa) if a['phase']==phase]
   selected.update([ids[0],ids[-1],max(ids,key=lambda i:aa[i]['elapsed_ms'])])
  expected.update((start,i,sym) for i in selected for sym in ctx.get('expected',[]))
 assert {(x['start'],x['answer'],x['symbol']) for x in proofs}==expected
 for x in proofs:
  a=d['raw_results'][x['start']]['context_answers'][x['answer']]
  assert x['exit_code']==0 and x['phase']==a['phase'] and x['item'] in a['items']
  assert x['cdb_sha256']=='8e4b828dc81b40d56ddc476a399019ca30e0daf6ea2929d8231d309da53c4291'
  text=apply(a['draft'],d['position'],x['item'],ctx.get('bindings',{}).get(x['symbol'],{}))
  assert sha(text.encode())==x['applied_tu_sha256']
 audit['raw_context_replies']+=len(answers)
 audit['required_typed_sema_replies']+=len(answers) if ctx.get('require_sema') else 0
 audit['selected_gcc_insertions']+=len(proofs)
 audit['contexts'][name]={'replies':len(answers),'required_typed_sema':bool(ctx.get('require_sema')),'selected_gcc_insertions':len(proofs),'warm_edited_p95_pass':row['warm_edited_p95_pass'],'per_start':per_start,'edited_above200_count':sum(a['elapsed_ms']>200 for a in answers if a['phase']=='edited')}
 for f in [p/'report.json',p/'report.case.json',p/'command.json',p/'run.log',p/'selected-insertions.json',p/'cdb/compile_commands.json']:
  data=f.read_bytes(); rel=name+'/'+('cdb--compile_commands.json' if f.parent.name=='cdb' else f.name)
  dest=out/(rel+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_bytes(gzip.compress(data,mtime=0));audit['artifact_sha256'][rel]=sha(data)
 for f in sorted((p/'cdb').glob('compile_commands.json')): assert sha(f.read_bytes())=='8e4b828dc81b40d56ddc476a399019ca30e0daf6ea2929d8231d309da53c4291'
std=json.loads((repo/'tests/evidence/part2-linux/filtered-lookup-std-3x30/summary.json').read_text())
assert std['engine_sha256']==audit['engine_sha256'] and std['semantic_pass'] and std['insertion_pass'] and std['insertions']==186
assert audit['raw_context_replies']==2046 and audit['required_typed_sema_replies']==1488 and audit['selected_gcc_insertions']==246
audit['combined12']={'context_replies':2232,'required_typed_sema_replies':1674,'include_replies':186,'empty_negative_replies':372,'gcc_insertions':432,'std_all_replies_compiled':186,'other11_sampled_insertions':246,'std_evidence':'../filtered-lookup-std-3x30/summary.json','remaining':'Matched four-arm distribution, stock comparison, snippet/resolve/module table boundaries, clean build, final product/native/long-term release qualification remain open.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
(out/'scope.json').write_text(json.dumps({'status':'complete: all11 measured distributions and selected GCC insertions passed','scope':summary['scope'],'remaining':audit['combined12']['remaining']},indent=2)+'\n')
(out/'archive-and-audit.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps(audit['combined12'],indent=2))
