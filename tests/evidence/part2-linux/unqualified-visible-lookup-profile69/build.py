from pathlib import Path
import json,subprocess,time,hashlib
root=Path(__file__).parent
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:name=(proc/'comm').read_text().strip()
 except OSError:continue
 if name.startswith('clangd') or name in {'cc1','cc1plus','clang','clang++','ninja'}:raise SystemExit('Active compiler/clangd blocks attribution build')
progress={'started_unix':time.time(),'scope':'Private single-object profile build; not production.'}
for stage in ['compile','link']:
 args=json.loads((root/(stage+'-args.json')).read_text())
 with (root/(stage+'.log')).open('w') as log:r=subprocess.run(args,cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=log,stderr=subprocess.STDOUT,timeout=300)
 progress[stage+'_exit_code']=r.returncode;(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
 print(stage,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
progress.update(status='complete',engine_sha256=hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),finished_unix=time.time())
(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
