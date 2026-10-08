from pathlib import Path
import json,subprocess,time,threading,gzip,sys
root=Path(__file__).parent/'matched';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd')
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
summary={'scope':'Short same-URI/CDB A/B/A, explicit standard-library index wait and positive index match verification. Compiler overlap invalidates timing; actual selected edits compile only after all engine measurements.','arms':{}}
reports={}
watched={'cc1','cc1plus','clang','clang++','g++','gcc','rustc','ninja'}
def compilers():
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   name=(p/'comm').read_text().strip()
   if name in watched:rows.append({'pid':int(p.name),'name':name})
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return rows
for arm,engine in [('baseline-before','/tmp/mcppls-filtered-guide69-build/clangd'),('candidate','/tmp/mcppls-filtered-special-names-build/clangd'),('baseline-after','/tmp/mcppls-filtered-guide69-build/clangd')]:
 p=root/arm
 if p.exists():raise SystemExit('refusing overwrite '+str(p))
 p.mkdir();cache=p/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 initial=compilers()
 if initial:
  (p/'preflight-blocked.json').write_text(json.dumps(initial,indent=2)+'\n')
  raise SystemExit('compiler workload still active; no timing run started')
 stop=threading.Event();samples=[];errors=[];began=time.monotonic()
 def watch():
  while not stop.is_set():
   try:samples.append({'elapsed_ms':(time.monotonic()-began)*1000,'compilers':compilers()})
   except OSError as e:errors.append(str(e))
   stop.wait(0.2)
 thread=threading.Thread(target=watch);thread.start()
 args=['python3',str(repo/'tests/probes/project_completion.py'),'--engine',engine,'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--context-file',str(repo/'tests/probes/contexts/qt/std-qualified.json'),'--starts','1','--rounds','5','--phases','--settled-index-log','Indexed c++23 standard library:','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 try:
  with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=150)
 finally:
  stop.set();thread.join(timeout=2)
 overlap=any(x['compilers'] for x in samples)
 (p/'workload.json').write_text(json.dumps({'sampling_interval_ms':200,'scope':'Observed compiler/ninja processes only; not proof of system idleness or descendant resource accounting.','samples':samples,'errors':errors,'watcher_stopped':not thread.is_alive(),'compiler_overlap':overlap},indent=2)+'\n')
 if r.returncode:raise SystemExit(f'{arm} failed {r.returncode}')
 d=json.loads((p/'report.json').read_text());assert d['all_semantic_requests_passed'];reports[arm]=d
 summary['arms'][arm]={'engine_sha256':d['engine_sha256'],'phases':d['phases'],'compiler_overlap':overlap,'sampler_errors':errors,'watcher_stopped':not thread.is_alive()}
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(arm,summary['arms'][arm],flush=True)
 if overlap or errors or thread.is_alive():raise SystemExit('workload invalidates timing qualification; preserve semantic results and stop scheduling')
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits']
key=lambda i:json.dumps({f:i.get(f) for f in fields},sort_keys=True)
for before,after,final in zip(*(reports[a]['raw_results'][0]['context_answers'] for a in ['baseline-before','candidate','baseline-after'])):
 assert sorted(map(key,before['items']))==sorted(map(key,after['items']))==sorted(map(key,final['items']))
summary['all_item_edit_fields_equal']=True
sys.path.insert(0,str(repo/'tests/probes'))
from completion_insertion import apply,compile_insertion
ctx=json.loads((repo/'tests/probes/contexts/qt/std-qualified.json').read_text())
import re
for arm,d in reports.items():
 proofs=[]
 for i,a in enumerate(d['raw_results'][0]['context_answers']):
  for sym in ctx['expected']:
   item=next(x for x in a['items'] if re.split(r'[(<]',x.get('filterText',x.get('label','')))[0].strip()==sym and x.get('kind')==ctx['kind'][sym])
   text=apply(a['draft'],d['position'],item,ctx.get('bindings',{}).get(sym,{}))
   row={'answer':i,'phase':a['phase'],'symbol':sym,'item':item};row.update(compile_insertion(Path('/home/speak/test/mcpp/qt-demo'),Path('/home/speak/test/mcpp/qt-demo/src/main.cpp'),text));proofs.append(row)
 (root/arm/'insertions.json').write_text(json.dumps(proofs,indent=2)+'\n')
 assert all(x['exit_code']==0 for x in proofs)
 summary['arms'][arm]['selected_gcc_insertions']=len(proofs)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('MATCHED_PASS',flush=True)
