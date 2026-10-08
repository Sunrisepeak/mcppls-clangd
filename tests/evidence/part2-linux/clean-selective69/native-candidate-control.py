from pathlib import Path
import json,subprocess,time,threading,gzip,sys
assert json.loads((Path(__file__).parent/'progress.json').read_text())['current_stage']=='complete', 'final clean build/test must pass before measurement'
root=Path(__file__).parent/'native-candidate-control';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd')
cdb=Path('/tmp/mcppls-part2-native-libcxx-std/compile_commands.json').read_bytes()
summary={'scope':'Candidate independent correctness; no baseline speedup proof. Original stock cold failure retained separately. Same-URI/CDB, same explicit completion-parse=always on both engines, real typed Sema required; no index gate for this prebuilt native std fixture. Compiler overlap invalidates timing; actual selected edits compile only after all engine measurements.','arms':{}}
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
for arm,engine in [('candidate','/tmp/mcppls-part2-clean-special69/build-linux-x64/bin/clangd')]:
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
 args=['python3',str(repo/'tests/probes/project_completion.py'),'--engine',engine,'--project','/tmp/mcppls-part2-native-libcxx-std','--source','/tmp/mcppls-part2-native-libcxx-std/Use.cpp','--context-file',str(Path(__file__).parent/'native-context.json'),'--starts','1','--rounds','1','--phases','--engine-flag=--completion-parse=always','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
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
sys.path.insert(0,str(repo/'tests/probes'))
from completion_insertion import apply,compile_insertion
ctx=json.loads((Path(__file__).parent/'native-context.json').read_text())
import re
for arm,d in reports.items():
 proofs=[]
 for i,a in enumerate(d['raw_results'][0]['context_answers']):
  for sym in ctx['expected']:
   item=next(x for x in a['items'] if re.split(r'[(<]',x.get('filterText',x.get('label','')))[0].strip()==sym and x.get('kind')==ctx['kind'][sym])
   text=apply(a['draft'],d['position'],item,ctx.get('bindings',{}).get(sym,{}))
   row={'answer':i,'phase':a['phase'],'symbol':sym,'item':item};row.update(compile_insertion(Path('/tmp/mcppls-part2-native-libcxx-std'),Path('/tmp/mcppls-part2-native-libcxx-std/Use.cpp'),text));proofs.append(row)
 (root/arm/'insertions.json').write_text(json.dumps(proofs,indent=2)+'\n')
 assert all(x['exit_code']==0 for x in proofs)
 summary['arms'][arm]['selected_native_insertions']=len(proofs)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('CANDIDATE_CONTROL_PASS',flush=True)
