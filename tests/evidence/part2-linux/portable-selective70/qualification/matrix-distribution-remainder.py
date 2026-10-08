from pathlib import Path
import shutil
assert shutil.disk_usage(Path(__file__).parent).free >= 6*1024**3, 'insufficient staging space; no qualification process started'
import json,subprocess,hashlib,sys,re,threading,time
probes=Path('/home/speak/workspace/github/mcppls-clangd/tests/probes');sys.path.insert(0,str(probes))
from completion_insertion import apply,compile_insertion
root=Path(__file__).parent/'matrix-distribution-remainder';root.mkdir(exist_ok=True)
contexts=probes/'contexts/qt';cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
summary={'scope':'Only remaining string context, each3starts x30rounds. All completion replies checked; GCC insertions selected per start/phase: first,last,slowest distinct replies, all expected symbols. Not every reply is compiled. Empty negative contexts have no selected insertion.','engine_sha256':hashlib.sha256((Path('/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd')).read_bytes()).hexdigest(),'results':{}}
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
assert json.loads((Path(__file__).parent.parent/'progress.json').read_text())['status']=='complete', 'portable build/package must pass first'
assert json.loads((Path(__file__).parent.parent/'portability.json').read_text())['problems']==[], 'actual floor portability must pass first'
metadata=json.loads((Path('/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/engine.json')).read_text())
assert metadata['sha256']==summary['engine_sha256'], 'final package binary SHA mismatch'
assert metadata['patch-series-sha256']=='710c2c8e380defe1be146a8a66f44d1c5e9216a6ebe4fde510372b516e22f424', 'whole70 series required'
for context in sorted(contexts.glob('string.json')):
 data=json.loads(context.read_text());p=root/context.stem;p.mkdir(exist_ok=True);cache=p/'cdb';cache.mkdir(exist_ok=True)
 if (cache/'.cache').exists() or (p/'report.json').exists():raise SystemExit('refusing to overwrite/reuse '+str(p))
 (cache/'compile_commands.json').write_bytes(cdb)
 args=['python3',str(probes/'project_completion.py'),'--engine',str(Path('/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd')),'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--context-file',str(context),'--starts','3','--rounds','30','--phases','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 if context.stem in {'std-qualified','first-column','ordinary'}:args.extend(['--settled-index-log','Indexed c++23 standard library:'])
 initial=compilers()
 if initial or last_engine_processes:
  (p/'preflight-blocked.json').write_text(json.dumps({'compilers':initial,'engines':last_engine_processes},indent=2)+'\n')
  raise SystemExit('compiler activity blocks timing; preserve incomplete arm')
 stop=threading.Event();samples=[];errors=[];began=time.monotonic()
 def monitor():
  while not stop.is_set():
   try:samples.append({'elapsed_ms':(time.monotonic()-began)*1000,'compilers':compilers(),'engines':list(last_engine_processes)})
   except OSError as e:errors.append(str(e))
   stop.wait(.2)
 thread=threading.Thread(target=monitor);thread.start()
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 try:
  with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=500)
 finally:
  stop.set();thread.join(timeout=2)
 compiler_overlap=any(x['compilers'] for x in samples)
 engine_overlap=any(len({e['pgid'] for e in x['engines']})>1 for x in samples)
 overlap=compiler_overlap or engine_overlap
 (p/'workload.json').write_text(json.dumps({'scope':'Compiler/ninja and clangd process sampling; two independent clangd process groups invalidate timing. Not proof of total system idleness.','interval_ms':200,'compiler_overlap':compiler_overlap,'multiple_engine_overlap':engine_overlap,'samples':samples,'errors':errors,'watcher_stopped':not thread.is_alive()},indent=2)+'\n')
 if overlap or errors or thread.is_alive():raise SystemExit('timing invalidated; preserve report and stop')
 row={'exit_code':r.returncode};proofs=[]
 if (p/'report.json').exists():
  report=json.load(open(p/'report.json'));row.update(semantic_pass=report['all_semantic_requests_passed'],phases=report['phases'],semantic_counts=report['semantic_counts'])
  if data.get('expected'):
   for start,raw in enumerate(report['raw_results']):
    answers=raw['context_answers'];selected=set()
    for phase in ['cold-open','settled-warm','edited']:
     indices=[i for i,a in enumerate(answers) if a['phase']==phase]
     if indices:selected.update([indices[0],indices[-1],max(indices,key=lambda i:answers[i]['elapsed_ms'])])
    for index in sorted(selected):
     answer=answers[index]
     for name in data['expected']:
      proof={'start':start,'answer':index,'phase':answer['phase'],'symbol':name}
      candidates=[i for i in answer['items'] if re.split(r'[(<]',i.get('filterText',i.get('label','')))[0].strip()==name]
      kind=data.get('kind',{}).get(name)
      if kind is not None:candidates=[i for i in candidates if i.get('kind')==kind]
      try:
       if not candidates:raise ValueError('no actual candidate of required symbol/kind')
       proof['item']=candidates[0];text=apply(answer['draft'],report['position'],candidates[0],data.get('bindings',{}).get(name,{}));proof.update(compile_insertion(Path('/home/speak/test/mcpp/qt-demo'),Path('/home/speak/test/mcpp/qt-demo/src/main.cpp'),text))
      except (ValueError,OSError) as e:proof['error']=str(e)
      proofs.append(proof)
   row['selected_insertions']=len(proofs);row['all_selected_insertions_compiled']=bool(proofs) and all(x.get('exit_code')==0 for x in proofs)
  else:row.update(selected_insertions=0,all_selected_insertions_compiled=None)
  limit=data.get('limit_ms');row['warm_edited_p95_pass']=None if limit is None else all(report['phases'][phase]['p95_ms']<=limit for phase in ['settled-warm','edited'])
 (p/'selected-insertions.json').write_text(json.dumps({'policy':'Per start/phase first,last,slowest distinct replies, all expected symbols; engine timing finished before compilation.','proofs':proofs},indent=2)+'\n')
 summary['results'][context.stem]=row;(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(context.stem,{'exit':r.returncode,'semantics':row.get('semantic_pass'),'insertions':row.get('all_selected_insertions_compiled'),'warm':row.get('phases',{}).get('settled-warm',{}).get('p95_ms'),'edited':row.get('phases',{}).get('edited',{}).get('p95_ms'),'budget_pass':row.get('warm_edited_p95_pass')},flush=True)
raise SystemExit(any(x['exit_code'] or x.get('semantic_pass') is False or x.get('all_selected_insertions_compiled') is False or x.get('warm_edited_p95_pass') is False for x in summary['results'].values()))
