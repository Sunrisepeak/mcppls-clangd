from pathlib import Path
import subprocess,json,concurrent.futures,hashlib
root=Path(__file__).parent;profile=Path('/tmp/mcppls-part2-doc-detail71')
def compile_one(pair):
 base,name=pair
 with (base/(name+'.log')).open('w') as f:p=subprocess.run(json.loads((base/(name+'.json')).read_text()),cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 (base/(name+'-terminal.json')).write_text(json.dumps({'exit_code':p.returncode})+'\n');return {'phase':str(base/name),'exit_code':p.returncode}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compile_one,[(root,'compile'),(profile,'hint-compile')]))
print(results,flush=True)
if any(x['exit_code'] for x in results):raise SystemExit(1)
for base,name in [(profile,'hint-link'),(root,'clangd-link'),(root,'ClangdTests-link')]:
 with (base/(name+'.log')).open('w') as f:p=subprocess.run(json.loads((base/(name+'.json')).read_text()),cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=300)
 (base/(name+'-terminal.json')).write_text(json.dumps({'exit_code':p.returncode})+'\n');print(name,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
print('production_private_sha256',hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),flush=True)
print('profile_sha256',hashlib.sha256((profile/'clangd-reader-hint').read_bytes()).hexdigest(),flush=True)
