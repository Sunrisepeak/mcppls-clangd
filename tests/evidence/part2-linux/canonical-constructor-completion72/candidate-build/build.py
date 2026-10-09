from pathlib import Path
import subprocess,json,concurrent.futures,hashlib
root=Path(__file__).parent
def compile_one(r):
 with (root/(r['name']+'.log')).open('w') as f:p=subprocess.run(r['argv'],cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 return {'name':r['name'],'exit_code':p.returncode}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compile_one,json.loads((root/'compile.json').read_text())))
(root/'compile-terminal.json').write_text(json.dumps(results,indent=2)+'\n');print(results,flush=True)
if any(x['exit_code'] for x in results):raise SystemExit(1)
for target in ['clangd','ClangdTests']:
 with (root/(target+'-link.log')).open('w') as f:p=subprocess.run(json.loads((root/(target+'-link.json')).read_text()),cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=300)
 (root/(target+'-link-terminal.json')).write_text(json.dumps({'exit_code':p.returncode})+'\n');print(target,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
print('engine_sha256',hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),flush=True)
