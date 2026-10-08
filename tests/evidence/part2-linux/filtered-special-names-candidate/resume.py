from pathlib import Path
import json,subprocess,concurrent.futures,os,time,hashlib
root=Path(__file__).parent
build='/home/speak/workspace/github/mcppls-clangd/build-linux-x64'
recipes=json.loads((root/'compile-args.json').read_text())
progress=json.loads((root/'progress.json').read_text())
assert all(x['exit_code']==0 for x in progress)
done={x['name'] for x in progress};assert len(done)==len(progress)
assert all(Path(e['object']).is_file() for e in recipes if e['name'] in done)
env=dict(os.environ,TMPDIR='/dev/shm/mcppls-guide69-temp')
remaining=[e for e in recipes if e['name'] not in done]
(root/'resume-identity.json').write_text(json.dumps({'reason':'Original tool session missing and process independently confirmed absent after sandbox environment change; retain 75 confirmed completed objects and compile only remaining recipes. Corrected ASTReader uses separately compiled object.','retained':len(done),'remaining':len(remaining)},indent=2)+'\n')
def compile_one(e):
 began=time.monotonic();log=root/'logs'/(e['name'].replace('/','__')+'-resume.log');log.parent.mkdir(exist_ok=True)
 with log.open('w') as f:r=subprocess.run(e['argv'],cwd=build,env=env,stdout=f,stderr=subprocess.STDOUT)
 return {'name':e['name'],'exit_code':r.returncode,'seconds':round(time.monotonic()-began,3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(compile_one,remaining):
  progress.append(result);(root/'progress-resume.json').write_text(json.dumps(progress,indent=2)+'\n');print(result,flush=True)
  if result['exit_code']:raise SystemExit(result['exit_code'])
base=Path('/tmp/mcppls-filtered-lookup-formal-build')
for target in ['clangd','ClangdTests']:
 args=json.loads((base/(target+'-link-args.json')).read_text())
 args=[a.replace(str(base),str(root)) for a in args]
 args=[str(root/'lib-objects/ASTReader-completion-spelling.cpp.o') if a==str(root/'lib-objects/ASTReader.cpp.o') else a for a in args]
 args[args.index('-o')+1]=str(root/target)
 (root/(target+'-link-args.json')).write_text(json.dumps(args,indent=2)+'\n')
 with (root/(target+'-link.log')).open('w') as f:r=subprocess.run(args,cwd=build,env=env,stdout=f,stderr=subprocess.STDOUT)
 print('link',target,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
with (root/'completion-tests.log').open('w') as f:r=subprocess.run([str(root/'ClangdTests'),'--gtest_filter=CompletionTest.*'],stdout=f,stderr=subprocess.STDOUT,timeout=120)
print('completion-tests',r.returncode,flush=True)
raise SystemExit(r.returncode)
