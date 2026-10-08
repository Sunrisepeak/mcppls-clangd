from pathlib import Path
import json,subprocess,hashlib,os,time
out=Path(__file__).parent
base=Path('/tmp/mcppls-filtered-lookup-formal-build')
build='/home/speak/workspace/github/mcppls-clangd/build-linux-x64'
recipes=json.loads((base/'compile-args.json').read_text())
selected=[next(e for e in recipes if e['name']=='ASTReader.cpp'),next(e for e in recipes if e['name'].endswith('CodeCompleteTests.cpp'))]
env=dict(os.environ,TMPDIR='/dev/shm/mcppls-guide69-temp')
Path(env['TMPDIR']).mkdir(exist_ok=True)
for e in selected:
 args=e['argv'].copy();args[args.index('-o')+1]=str(out/(Path(args[args.index('-c')+1]).name+'.o'))
 (out/(e['name'].replace('/','_')+'-args.json')).write_text(json.dumps(args,indent=2)+'\n')
 with (out/(Path(args[args.index('-c')+1]).name+'-compile.log')).open('w') as f:r=subprocess.run(args,cwd=build,stdout=f,stderr=subprocess.STDOUT,env=env)
 print('compile',e['name'],r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
for target in ['clangd','ClangdTests']:
 args=json.loads((base/(target+'-link-args.json')).read_text())
 args=[str(out/'ASTReader.cpp.o') if a.endswith('/lib-objects/ASTReader.cpp.o') else str(out/'CodeCompleteTests.cpp.o') if a.endswith('/CodeCompleteTests.cpp.o') else a for a in args]
 args[args.index('-o')+1]=str(out/target)
 (out/(target+'-link-args.json')).write_text(json.dumps(args,indent=2)+'\n')
 with (out/(target+'-link.log')).open('w') as f:r=subprocess.run(args,cwd=build,stdout=f,stderr=subprocess.STDOUT,env=env)
 print('link',target,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
with (out/'guide-tests.log').open('w') as f:r=subprocess.run([str(out/'ClangdTests'),'--gtest_filter=CompletionTest.SelectedExternalNamesPreserveOrdinaryDeductionGuideLookup:CompletionTest.ExternalQualifiedDeductionGuidesPreserveAliasResults'],stdout=f,stderr=subprocess.STDOUT)
print('guide-tests',r.returncode,flush=True)
raise SystemExit(r.returncode)
