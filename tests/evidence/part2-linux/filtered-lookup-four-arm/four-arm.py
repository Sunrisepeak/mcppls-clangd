from pathlib import Path
import subprocess,json,sys,hashlib,re
base=Path(__file__).parent;root=base/'four-arm';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd');probes=repo/'tests/probes';sys.path.insert(0,str(probes))
from completion_insertion import apply,compile_insertion
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
context=probes/'contexts/qt/std-qualified.json';ctx=json.loads(context.read_text())
baseline='/tmp/mcppls-joint53-build/full-consumers66/clangd';candidate=str(base/'clangd');reports={}
summary={'scope':'Matched headers/modules x baseline/candidate, each3starts x30rounds, original URI/CDB, no added trace instrumentation. GCC first,last,slowest per phase/start compiled after all four arms; not every reply compiled. Header macros/declaration exposure differs from module exports.','arms':{}}
for label,engine,mode in [('baseline-headers',baseline,'headers'),('candidate-modules',candidate,'modules'),('baseline-modules',baseline,'modules'),('candidate-headers',candidate,'headers')]:
 p=root/label
 if p.exists():raise SystemExit('refusing overwrite '+str(p))
 p.mkdir();cache=p/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 draft='/tmp/mcppls-part2-textual-pair-valid/'+mode+'/main.cpp'
 args=['python3',str(probes/'project_completion.py'),'--engine',engine,'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--draft-source',draft,'--context-file',str(context),'--starts','3','--rounds','30','--phases','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit(f'{label} failed {r.returncode}')
 d=json.loads((p/'report.json').read_text());assert d['all_semantic_requests_passed']
 reports[label]=d;summary['arms'][label]={'engine_sha256':d['engine_sha256'],'draft_source_sha256':d['draft_source_sha256'],'semantic_counts':d['semantic_counts'],'phases':d['phases']}
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(label,{phase:round(x['p95_ms'],2) for phase,x in d['phases'].items()},flush=True)
for label,d in reports.items():
 proofs=[]
 for start,raw in enumerate(d['raw_results']):
  aa=raw['context_answers'];selected=set()
  for phase in ['cold-open','settled-warm','edited']:
   ids=[i for i,a in enumerate(aa) if a['phase']==phase]
   selected.update([ids[0],ids[-1],max(ids,key=lambda i:aa[i]['elapsed_ms'])])
  for i in sorted(selected):
   a=aa[i]
   for sym in ctx['expected']:
    items=[x for x in a['items'] if re.split(r'[(<]',x.get('filterText',x.get('label','')))[0].strip()==sym and x.get('kind')==ctx.get('kind',{}).get(sym,x.get('kind'))]
    assert items;item=items[0];text=apply(a['draft'],d['position'],item,ctx.get('bindings',{}).get(sym,{}))
    proof={'start':start,'answer':i,'phase':a['phase'],'symbol':sym,'item':item};proof.update(compile_insertion(Path('/home/speak/test/mcpp/qt-demo'),Path('/home/speak/test/mcpp/qt-demo/src/main.cpp'),text));proofs.append(proof)
 (root/label/'selected-insertions.json').write_text(json.dumps({'policy':'All engine timing complete before compilation. Per start/phase first,last,slowest distinct replies.','proofs':proofs},indent=2)+'\n')
 summary['arms'][label]['gcc_insertions']=len(proofs);summary['arms'][label]['selected_insertions_pass']=all(x['exit_code']==0 for x in proofs)
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(label,'GCC',len(proofs),summary['arms'][label]['selected_insertions_pass'],flush=True)
 if not summary['arms'][label]['selected_insertions_pass']:raise SystemExit(1)
