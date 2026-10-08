from pathlib import Path
import json,subprocess,time,threading,gzip,sys
assert json.loads((Path(__file__).parent.parent/'progress.json').read_text())['status']=='complete', 'portable build/package must pass first'
p=Path(__file__).parent
package=Path('/tmp/mcppls-part2-floor69/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd')
assert json.loads((p.parent/'progress.json').read_text())['status']=='complete'
assert json.loads((p.parent/'portability.json').read_text())['problems']==[]
import hashlib
assert hashlib.sha256((package/'bin/clangd').read_bytes()).hexdigest()==json.loads((package/'engine.json').read_text())['sha256']
root=Path(__file__).parent/'native-settled-distribution';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd')
cdb=Path('/tmp/mcppls-part2-native-libcxx-std/compile_commands.json').read_bytes()
summary={'scope':'3starts x30rounds AST-ready same-URI/CDB A/B/A; cold completion explicitly not requested. Original stock auto/always cold failures retained separately and not reclassified. Candidate independent cold correctness passes. No cold baseline or full release claim; selected first,last,slowest edits per phase/start compile after all timings, same explicit completion-parse=always on both engines, real typed Sema required; no index gate for this prebuilt native std fixture. Compiler overlap invalidates timing; actual selected edits compile only after all engine measurements.','arms':{}}
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
for arm,engine in [('baseline-before','/home/speak/.local/share/mcppls/payload/clangd/bin/clangd'),('candidate','/tmp/mcppls-part2-floor69/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd'),('baseline-after','/home/speak/.local/share/mcppls/payload/clangd/bin/clangd')]:
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
 args=['python3',str(repo/'tests/probes/project_completion.py'),'--engine',engine,'--project','/tmp/mcppls-part2-native-libcxx-std','--source','/tmp/mcppls-part2-native-libcxx-std/Use.cpp','--context-file',str(Path(__file__).parent/'native-context.json'),'--starts','3','--rounds','30','--phases','--settled-only','--engine-flag=--completion-parse=always','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/tmp/mcppls-part2-floor69/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 try:
  with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=500)
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
arms=['baseline-before','candidate','baseline-after']
assert all(len(reports[a]['raw_results'])==3 for a in arms)
for start in range(3):
 answers=[reports[a]['raw_results'][start]['context_answers'] for a in arms]
 assert all(len(x)==61 for x in answers)
 for before,after,final in zip(*answers):
  assert before['phase']==after['phase']==final['phase']
  assert before['draft']==after['draft']==final['draft']
  assert sorted(map(key,before['items']))==sorted(map(key,after['items']))==sorted(map(key,final['items']))
summary['all_item_edit_fields_equal']=True
sys.path.insert(0,str(repo/'tests/probes'))
from completion_insertion import apply,compile_insertion
ctx=json.loads((Path(__file__).parent/'native-context.json').read_text())
import re
for arm,d in reports.items():
 proofs=[]
 for start,raw in enumerate(d['raw_results']):
  answers=raw['context_answers'];selected=set()
  for phase in ['settled-warm','edited']:
   indices=[i for i,a in enumerate(answers) if a['phase']==phase]
   if indices:selected.update([indices[0],indices[-1],max(indices,key=lambda i:answers[i]['elapsed_ms'])])
  for i in sorted(selected):
   a=answers[i]
   for sym in ctx['expected']:
    item=next(x for x in a['items'] if re.split(r'[(<]',x.get('filterText',x.get('label','')))[0].strip()==sym and x.get('kind')==ctx['kind'][sym])
    text=apply(a['draft'],d['position'],item,ctx.get('bindings',{}).get(sym,{}))
    row={'start':start,'answer':i,'phase':a['phase'],'symbol':sym,'item':item};row.update(compile_insertion(Path('/tmp/mcppls-part2-native-libcxx-std'),Path('/tmp/mcppls-part2-native-libcxx-std/Use.cpp'),text));proofs.append(row)
 (root/arm/'insertions.json').write_text(json.dumps(proofs,indent=2)+'\n')
 assert all(x['exit_code']==0 for x in proofs)
 summary['arms'][arm]['selected_native_insertions']=len(proofs)
from resource_window import stable_window
for arm,d in reports.items():
 windows=[stable_window(raw) for raw in d['raw_results']]
 summary['arms'][arm]['stable_main_process_resources']={'windows':windows,'cpu_lower_ms':sum(w['cpu_lower_ms'] for w in windows),'cpu_upper_ms':sum(w['cpu_upper_ms'] for w in windows),'rss_p95_max_kib':max(w['rss_p95_kib'] for w in windows),'scope':'Main process only; no descendants or hard memory ceiling.'}
for arm in ['baseline-before','baseline-after']:
 b=summary['arms'][arm];c=summary['arms']['candidate']
 bres=b['stable_main_process_resources'];cres=c['stable_main_process_resources']
 summary.setdefault('comparisons',{})[arm]={'edited_p95_improvement_fraction':1-c['phases']['edited']['p95_ms']/b['phases']['edited']['p95_ms'],'cpu_ratio_conservative':cres['cpu_upper_ms']/bres['cpu_lower_ms'] if bres['cpu_lower_ms'] else None,'rss_observed_p95_max_ratio':cres['rss_p95_max_kib']/bres['rss_p95_max_kib']}
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('MATCHED_PASS',flush=True)
