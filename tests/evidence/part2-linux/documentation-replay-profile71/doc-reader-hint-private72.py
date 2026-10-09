from pathlib import Path
import shutil
assert shutil.disk_usage(Path(__file__).parent).free >= 6*1024**3, 'insufficient staging space; no qualification process started'
import subprocess,json,sys,hashlib,re,threading,time
base=Path(__file__).parent;root=base/'doc-reader-hint-private72';root.mkdir(exist_ok=True)
repo=Path('/home/speak/workspace/github/mcppls-clangd');probes=repo/'tests/probes';sys.path.insert(0,str(probes))
from completion_insertion import apply,compile_insertion
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
context=probes/'contexts/qt/std-qualified.json';ctx=json.loads(context.read_text())
baseline='/tmp/mcppls-joint53-build/full-consumers66/clangd';candidate='/tmp/mcppls-part2-doc-detail71/clangd-reader-hint';reports={}
assert hashlib.sha256(Path(candidate).read_bytes()).hexdigest()=='373657d40ebbf718e6648524b2f9bae724c5f3fe6185a10772f9bc09a0776e60'
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:name=(proc/'comm').read_text().strip()
 except OSError:continue
 if name.startswith('clangd') or name in {'cc1','cc1plus','clang','clang++','gcc','g++','ninja'}:raise SystemExit('Other engine/compiler blocks serial four-arm measurement')
summary={'scope':'Private GCC72 ordered-comment insertion trace attribution only; not final floor bytes, no production qualification, headers/modules each1start3rounds, same original URI/CDB/drafts and stock headers. No latency distribution, source-exclusive speedup, resource regression or insertion qualification. All16 replies require real typed Sema; cold preserved and stable standard-library index gated.','arms':{}}
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

for label,engine,mode in [('headers',candidate,'headers'),('modules',candidate,'modules')]:
 p=root/label
 if p.exists():raise SystemExit('refusing overwrite '+str(p))
 p.mkdir();cache=p/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 draft='/tmp/mcppls-part2-textual-pair-valid/'+mode+'/main.cpp'
 args=['python3',str(probes/'project_completion.py'),'--engine',engine,'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--draft-source',draft,'--context-file',str(context),'--starts','1','--rounds','3','--phases','--settled-index-log','Indexed c++23 standard library:','--resources','--trace',str(p/'trace.json'),'--output',str(p/'report.json'),'--engine-flag=-resource-dir=/tmp/mcppls-part2-floor70/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
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
print('PRIVATE70_WARM_DETAIL_COMPLETE',flush=True)
