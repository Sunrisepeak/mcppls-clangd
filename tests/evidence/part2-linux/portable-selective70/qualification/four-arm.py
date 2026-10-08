from pathlib import Path
import shutil
assert shutil.disk_usage(Path(__file__).parent).free >= 6*1024**3, 'insufficient staging space; no qualification process started'
import subprocess,json,sys,hashlib,re,threading,time
base=Path(__file__).parent;root=base/'four-arm';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd');probes=repo/'tests/probes';sys.path.insert(0,str(probes))
from completion_insertion import apply,compile_insertion
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
context=probes/'contexts/qt/std-qualified.json';ctx=json.loads(context.read_text())
baseline='/tmp/mcppls-joint53-build/full-consumers66/clangd';candidate='/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd';reports={}
package=Path(candidate).parent.parent
assert json.loads((base.parent/'progress.json').read_text())['status']=='complete'
assert json.loads((base.parent/'portability.json').read_text())['problems']==[]
metadata=json.loads((package/'engine.json').read_text())
assert metadata['patch-series-sha256']=='710c2c8e380defe1be146a8a66f44d1c5e9216a6ebe4fde510372b516e22f424'
assert metadata['sha256']==hashlib.sha256(Path(candidate).read_bytes()).hexdigest()
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:name=(proc/'comm').read_text().strip()
 except OSError:continue
 if name.startswith('clangd') or name in {'cc1','cc1plus','clang','clang++','gcc','g++','ninja'}:raise SystemExit('Other engine/compiler blocks serial four-arm measurement')
summary={'scope':'Matched headers/modules x baseline/candidate, each3starts x30rounds, original URI/CDB, no added trace instrumentation. GCC first,last,slowest per phase/start compiled after all four arms; not every reply compiled. Header macros/declaration exposure differs from module exports. Final70 Clang12 floor package versus baseline67 GCC development artifact, same upstream pin/producer inputs; compiler build recipes differ, so do not attribute every gain exclusively to source code. Same-compiler private controls are separate evidence.','arms':{}}
watched={'cc1','cc1plus','clang','clang++','g++','gcc','rustc','ninja'}
last_engine_processes=[]
def compilers():
 global last_engine_processes
 last_engine_processes=[]
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   name=(p/'comm').read_text().strip()
   if name in watched or name.startswith(('clang-', 'clang++-', 'gcc-', 'g++-', 'cc1', 'mcxx-x-mcxx')):rows.append({'pid':int(p.name),'name':name})
   if name.startswith('clangd'):
    stat=(p/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
    last_engine_processes.append({'pid':int(p.name),'name':name,'ppid':int(fields[1]),'pgid':int(fields[2]),'start_ticks':int(fields[19])})
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return rows

for label,engine,mode in [('baseline-headers',baseline,'headers'),('candidate-modules',candidate,'modules'),('baseline-modules',baseline,'modules'),('candidate-headers',candidate,'headers')]:
 p=root/label
 if p.exists():raise SystemExit('refusing overwrite '+str(p))
 p.mkdir();cache=p/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 draft='/tmp/mcppls-part2-textual-pair-valid/'+mode+'/main.cpp'
 args=['python3',str(probes/'project_completion.py'),'--engine',engine,'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--draft-source',draft,'--context-file',str(context),'--starts','3','--rounds','30','--phases','--settled-index-log','Indexed c++23 standard library:','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 initial=compilers()
 if initial or last_engine_processes:
  (p/'preflight-blocked.json').write_text(json.dumps({'compilers':initial,'engines':last_engine_processes},indent=2)+'\n')
  raise SystemExit('compiler workload active; retain incomplete arm and stop')
 stop=threading.Event();samples=[];errors=[];began=time.monotonic()
 def watch():
  while not stop.is_set():
   try:samples.append({'elapsed_ms':(time.monotonic()-began)*1000,'compilers':compilers(),'engines':list(last_engine_processes)})
   except OSError as e:errors.append(str(e))
   stop.wait(0.2)
 thread=threading.Thread(target=watch);thread.start()
 try:
  with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=500)
 finally:
  stop.set();thread.join(timeout=2)
 compiler_overlap=any(x['compilers'] for x in samples)
 engine_overlap=any(len({e['pgid'] for e in x['engines']})>1 for x in samples)
 overlap=compiler_overlap or engine_overlap
 (p/'workload.json').write_text(json.dumps({'sampling_interval_ms':200,'scope':'Observed compiler/ninja and clangd processes; more than one clangd process group invalidates timing, not proof of total system idleness.','samples':samples,'errors':errors,'compiler_overlap':compiler_overlap,'multiple_engine_overlap':engine_overlap,'watcher_stopped':not thread.is_alive()},indent=2)+'\n')
 if overlap or errors or thread.is_alive():raise SystemExit('compiler overlap invalidates four-arm timing; preserve reports')
 if r.returncode:raise SystemExit(f'{label} failed {r.returncode}')
 d=json.loads((p/'report.json').read_text());assert d['all_semantic_requests_passed']
 reports[label]=d;summary['arms'][label]={'engine_sha256':d['engine_sha256'],'draft_source_sha256':d['draft_source_sha256'],'semantic_counts':d['semantic_counts'],'phases':d['phases']}
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(label,{phase:round(x['p95_ms'],2) for phase,x in d['phases'].items()},flush=True)
fields=['label','kind','textEdit','insertText','insertTextFormat','additionalTextEdits']
key=lambda item:json.dumps({f:item.get(f) for f in fields},sort_keys=True)
for mode in ['headers','modules']:
 b=reports['baseline-'+mode];c=reports['candidate-'+mode]
 assert b['draft_source_sha256']==c['draft_source_sha256']
 assert len(b['raw_results'])==len(c['raw_results'])==3
 for br,cr in zip(b['raw_results'],c['raw_results']):
  assert len(br['context_answers'])==len(cr['context_answers'])==62
  for ba,ca in zip(br['context_answers'],cr['context_answers']):
   assert ba['phase']==ca['phase'] and ba['draft']==ca['draft']
   assert sorted(map(key,ba['items']))==sorted(map(key,ca['items']))
summary['within_mode_all_returned_fields_equal']=True
from resource_window import stable_window
for label,d in reports.items():
 windows=[stable_window(raw) for raw in d['raw_results']]
 summary['arms'][label]['stable_main_process_resources']={'windows':windows,'cpu_lower_ms':sum(w['cpu_lower_ms'] for w in windows),'cpu_upper_ms':sum(w['cpu_upper_ms'] for w in windows),'rss_p95_max_kib':max(w['rss_p95_kib'] for w in windows),'scope':'Main process only; no descendants or hard memory ceiling.'}
for mode in ['headers','modules']:
 b=summary['arms']['baseline-'+mode];c=summary['arms']['candidate-'+mode]
 br=b['stable_main_process_resources'];cr=c['stable_main_process_resources']
 summary.setdefault('resource_comparisons',{})[mode]={'cpu_ratio_conservative':cr['cpu_upper_ms']/br['cpu_lower_ms'] if br['cpu_lower_ms'] else None,'rss_observed_p95_max_ratio':cr['rss_p95_max_kib']/br['rss_p95_max_kib']}
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

(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('FINAL_FOUR_ARM_PASS',flush=True)
