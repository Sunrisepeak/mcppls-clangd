from pathlib import Path
import json,subprocess,time,hashlib,concurrent.futures
root=Path(__file__).parent
progress={'scope':'Private Scope/TU candidate. Two changed Sema objects and completion tests rebuilt, unchanged 0069 ABI consumers reused. No class layout/virtual ABI changes; full clean release rebuild still required.','started_unix':time.time(),'objects':[]}
recipes=json.loads((root/'compile-args.json').read_text())
def compile_one(r):
 with (root/(Path(r['name']).name+'.log')).open('w') as log:p=subprocess.run(r['argv'],cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=log,stderr=subprocess.STDOUT,timeout=500)
 return {'name':r['name'],'exit_code':p.returncode}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for r in pool.map(compile_one,recipes):
  progress['objects'].append(r);(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n');print(r,flush=True)
if any(r['exit_code'] for r in progress['objects']):raise SystemExit(1)
for target in ['clangd','ClangdTests']:
 args=json.loads((root/(target+'-link-args.json')).read_text())
 with (root/(target+'-link.log')).open('w') as log:p=subprocess.run(args,cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=log,stderr=subprocess.STDOUT,timeout=300)
 progress[target+'_link_exit_code']=p.returncode;(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n');print('link',target,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
progress.update(status='complete',engine_sha256=hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),finished_unix=time.time())
(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
