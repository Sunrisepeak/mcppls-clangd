from pathlib import Path
import subprocess,json,time,hashlib
root=Path(__file__).parent
for phase in ['compile','link']:
 with (root/(phase+'.log')).open('w') as log:
  p=subprocess.run(json.loads((root/(phase+'.json')).read_text()),cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=log,stderr=subprocess.STDOUT,timeout=600)
 print(phase,p.returncode,flush=True)
 (root/(phase+'-terminal.json')).write_text(json.dumps({'exit_code':p.returncode,'unix':time.time()})+'\n')
 if p.returncode:raise SystemExit(p.returncode)
print('engine_sha256',hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),flush=True)
