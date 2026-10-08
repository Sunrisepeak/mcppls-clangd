from pathlib import Path
import subprocess,json,hashlib,os,signal,time
root=Path(__file__).parent
if (root/'identity.json').exists():raise SystemExit('refusing to overwrite prior product evidence')
args=json.loads((root/'command.json').read_text())
files={'server':Path(args[args.index('--server')+1]),'runner':Path(args[0]),'engine':Path(args[args.index('--clangd')+1]),'kit_manifest':Path(args[args.index('--kit')+1])/'kit.json'}
identity={'scope':'Final portable engine with fixed product binary and installed stock kit; inferred semantic integration only, no product performance or immutable same-source kit/payload claim.','sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},'started_unix':time.time()}
compilers=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  name=(p/'comm').read_text().strip()
  if name in {'cc1','cc1plus','clang','clang++','g++','gcc','ninja'}:compilers.append({'pid':int(p.name),'name':name})
 except (OSError,ProcessLookupError):pass
identity['observed_compilers_at_start']=compilers
(root/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
with (root/'run.log').open('w') as log:
 p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=p.wait(timeout=240)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);p.wait();code=124
 finally:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
identity.update(exit_code=code,finished_unix=time.time())
(root/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
print('Final-byte inferred product semantic smoke:',code,flush=True)
raise SystemExit(code)
