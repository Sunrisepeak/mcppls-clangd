from pathlib import Path
import shutil
assert shutil.disk_usage(Path(__file__).parent).free >= 6*1024**3, 'insufficient staging space; no qualification process started'
import subprocess,json,hashlib,os,signal,time
root=Path(__file__).parent
if (root/'identity.json').exists():raise SystemExit('refusing to overwrite prior product evidence')
args=json.loads((root/'command.json').read_text())
build_root=root.parent.parent
assert json.loads((build_root/'progress.json').read_text())['status']=='complete', 'final clean build/package must finish successfully'
assert json.loads((build_root/'portability.json').read_text())['problems']==[], 'actual floor dependency check must pass'
engine=Path(args[args.index('--clangd')+1])
metadata=json.loads((engine.parent.parent/'engine.json').read_text())
assert metadata['patch-series-sha256']=='710c2c8e380defe1be146a8a66f44d1c5e9216a6ebe4fde510372b516e22f424', 'whole70 required'
assert metadata['sha256']==hashlib.sha256(engine.read_bytes()).hexdigest(), 'final binary identity mismatch'
files={'server':Path(args[args.index('--server')+1]),'runner':Path(args[0]),'engine':Path(args[args.index('--clangd')+1]),'kit_manifest':Path(args[args.index('--kit')+1])/'kit.json'}
identity={'scope':'Final portable engine with fixed product binary and installed stock kit; inferred semantic integration and controlled direct-engine/product latency only; no immutable same-source kit/payload or answer-cache claim.','sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},'started_unix':time.time()}
compilers=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  name=(p/'comm').read_text().strip()
  if name in {'cc1','cc1plus','clang','clang++','g++','gcc','ninja'} or name.startswith(('clang-', 'clang++-', 'gcc-', 'g++-', 'cc1', 'mcxx-x-mcxx')):compilers.append({'pid':int(p.name),'name':name})
 except (OSError,ProcessLookupError):pass
identity['observed_compilers_at_start']=compilers
if compilers:raise SystemExit('compiler activity blocks final product qualification')
identity['engine_metadata']=metadata
(root/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
with (root/'run.log').open('w') as log:
 p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=p.wait(timeout=600)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);p.wait();code=124
 finally:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
identity.update(exit_code=code,finished_unix=time.time())
(root/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
print('Final-byte inferred product completion control:',code,flush=True)
raise SystemExit(code)
