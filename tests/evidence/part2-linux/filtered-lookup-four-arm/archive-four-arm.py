from pathlib import Path
import json,hashlib,gzip,math,shutil
b=Path(__file__).parent;root=b/'four-arm';out=Path('/home/speak/workspace/github/mcppls-clangd/tests/evidence/part2-linux/filtered-lookup-four-arm');out.mkdir(exist_ok=True)
summary=json.loads((root/'summary.json').read_text());reports={};audit={'scope':summary['scope'],'arms':{},'artifact_sha256':{}}
sha=lambda x:hashlib.sha256(x).hexdigest()
for label in summary['arms']:
 p=root/label;d=json.loads((p/'report.json').read_text()); reports[label]=d; aa=[a for r in d['raw_results'] for a in r['context_answers']]
 assert len(aa)==186 and d['all_semantic_requests_passed']
 assert len(d['raw_results'])==3 and d['source_sha256']=='bac3d5a798671ba51db0640ccfd63a7b7a72750b9561503565697c420f61a871'
 for r in d['raw_results']:assert r['readers_stopped'] and r['exit_code']==0 and r['resources']['sampler_stopped'] and not r['resources']['errors']
 for a in aa:assert a['semantic_pass'] and not any(a[k] for k in ['missing','polluted','unexpected_nonempty','semantic_origin_failed','untyped_expected']) and a['origin']['sema']>0
 for ph,n in [('cold-open',3),('settled-warm',93),('edited',90)]:
  vals=sorted(a['elapsed_ms'] for a in aa if a['phase']==ph);assert len(vals)==n and vals[math.ceil(.95*n)-1]==d['phases'][ph]['p95_ms'] and d['phases'][ph]['missing']==0
 proofs=json.loads((p/'selected-insertions.json').read_text())['proofs'];assert proofs and all(x['exit_code']==0 for x in proofs)
 for x in proofs:assert x['item'] in d['raw_results'][x['start']]['context_answers'][x['answer']]['items'] and x['cdb_sha256']=='8e4b828dc81b40d56ddc476a399019ca30e0daf6ea2929d8231d309da53c4291'
 audit['arms'][label]={'replies':len(aa),'selected_gcc_insertions':len(proofs),'max_edited_ms':max(a['elapsed_ms'] for a in aa if a['phase']=='edited'),'edited_above200_count':sum(a['elapsed_ms']>200 for a in aa if a['phase']=='edited')}
 for f in [p/'report.json',p/'report.case.json',p/'command.json',p/'run.log',p/'selected-insertions.json',p/'cdb/compile_commands.json']:
  data=f.read_bytes();rel=label+'/'+('cdb--compile_commands.json' if f.parent.name=='cdb' else f.name);dest=out/(rel+'.gz');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.compress(data,mtime=0));audit['artifact_sha256'][rel]=sha(data)
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
audit['returned_item_parity']={}
for mode in ['headers','modules']:
 a=reports['baseline-'+mode];z=reports['candidate-'+mode];counts=[];different=[]
 for start,(ra,rz) in enumerate(zip(a['raw_results'],z['raw_results'])):
  for i,(x,y) in enumerate(zip(ra['context_answers'],rz['context_answers'])):
   assert x['phase']==y['phase'];counts.append([len(x['items']),len(y['items'])])
   if sorted(map(key,x['items']))!=sorted(map(key,y['items'])):different.append({'start':start,'answer':i,'phase':x['phase'],'baseline':sorted(map(key,x['items'])),'candidate':sorted(map(key,y['items']))})
 audit['returned_item_parity'][mode]={'replies':len(counts),'all_items_equal':not different,'item_count_ranges':[min(x[0] for x in counts),max(x[0] for x in counts),min(x[1] for x in counts),max(x[1] for x in counts)],'differences':different}
# Compare only genuinely matched p95 values from this single four-arm run.
vals={k:v['phases']['edited']['p95_ms'] for k,v in summary['arms'].items()}
audit['edited_p95_comparison']={'ms':vals,'baseline_modules_minus_headers_ms':vals['baseline-modules']-vals['baseline-headers'],'candidate_modules_minus_headers_ms':vals['candidate-modules']-vals['candidate-headers'],'modules_improvement_percent':100*(1-vals['candidate-modules']/vals['baseline-modules']),'headers_improvement_percent':100*(1-vals['candidate-headers']/vals['baseline-headers']),'candidate_modules_over_headers_percent':100*(vals['candidate-modules']/vals['candidate-headers']-1)}
for f in [b/'four-arm.py',b/'four-arm.log',Path(__file__)]:shutil.copyfile(f,out/f.name)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps({'comparison':audit['edited_p95_comparison'],'parity':{m:{k:v for k,v in row.items() if k!='differences'} for m,row in audit['returned_item_parity'].items()},'gcc_total':sum(x['selected_gcc_insertions'] for x in audit['arms'].values())},indent=2))
