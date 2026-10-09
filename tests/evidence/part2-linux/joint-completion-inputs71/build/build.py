from pathlib import Path
import json,subprocess,concurrent.futures,time,hashlib
root=Path(__file__).parent
source='/dev/shm/mcppls-part2-completion-inputs71'
base=Path('/tmp/mcppls-joint53-build/full-consumers66')
recipes=[]
for old in json.loads((base/'compile-args.json').read_text()):
 args=[x.replace('/tmp/mcppls-joint53',source) for x in old['argv']]
 obj=root/'objects'/old['original_object'];obj.parent.mkdir(parents=True,exist_ok=True)
 args[args.index('-o')+1]=str(obj)
 recipes.append({'name':old['name'],'original_object':old['original_object'],'argv':args,'object':str(obj)})
(root/'compile-args.json').write_text(json.dumps(recipes,indent=2)+'\n')
progress={'scope':'Private71: all141 prior clangd consumers rebuilt after ProjectModules virtual interface addition; unchanged LLVM/Sema70 objects reused. Full clean portable release build still required.','started_unix':time.time(),'objects':[]}
(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
def compile_one(r):
 log=root/'objects/logs'/(r['name'].replace('/','__')+'.log');log.parent.mkdir(exist_ok=True)
 began=time.monotonic()
 with log.open('w') as f:p=subprocess.run(r['argv'],cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=600)
 return {'name':r['name'],'exit_code':p.returncode,'seconds':round(time.monotonic()-began,3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 tasks=[pool.submit(compile_one,r) for r in recipes]
 for future in concurrent.futures.as_completed(tasks):
  result=future.result();progress['objects'].append(result)
  (root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
  print(len(progress['objects']),result,flush=True)
if any(x['exit_code'] for x in progress['objects']):raise SystemExit(1)
for target in ['clangd','ClangdTests']:
 args=json.loads((Path('/tmp/mcppls-part2-unqualified70-build')/(target+'-link-args.json')).read_text())
 replaced=[]
 for i,x in enumerate(args):
  if not x.endswith('.o'):continue
  for r in recipes:
   if x.endswith('/'+r['original_object']) or (r['name']=='unittests/CodeCompleteTests.cpp' and x=='/tmp/mcppls-part2-unqualified70-build/CodeCompleteTests.cpp.o'):
    args[i]=r['object'];replaced.append(r['name']);break
 args[args.index('-o')+1]=str(root/target)
 (root/(target+'-link-args.json')).write_text(json.dumps(args,indent=2)+'\n')
 (root/(target+'-replaced-consumers.json')).write_text(json.dumps(replaced,indent=2)+'\n')
 with (root/(target+'-link.log')).open('w') as f:p=subprocess.run(args,cwd='/home/speak/workspace/github/mcppls-clangd/build-linux-x64',stdout=f,stderr=subprocess.STDOUT,timeout=300)
 progress[target+'_link_exit_code']=p.returncode
 (root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n');print('link',target,p.returncode,flush=True)
 if p.returncode:raise SystemExit(p.returncode)
progress.update(status='complete',engine_sha256=hashlib.sha256((root/'clangd').read_bytes()).hexdigest(),finished_unix=time.time())
(root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
print('PRIVATE71_BUILD_COMPLETE',progress['engine_sha256'],flush=True)
