import json,pathlib,shlex,subprocess,concurrent.futures,time
out=pathlib.Path(__file__).parent
source='/tmp/mcppls-filtered-special-names'
original='/home/speak/workspace/github/mcppls-clangd/llvm-project'
build='/home/speak/workspace/github/mcppls-clangd/build-linux-x64'
entries=json.load(open(build+'/compile_commands.json'))
recipes=[]
for name in ['ExternalASTSource.cpp','SemaLookup.cpp','SemaCodeComplete.cpp','CodeCompleteConsumer.cpp','ASTReader.cpp','ASTUnit.cpp','CompilerInstance.cpp']:
 e=next(e for e in entries if e['file'].endswith('/'+name));args=shlex.split(e['command']);args=[a.replace(original,source) for a in args];obj=out/'lib-objects'/(name+'.o');obj.parent.mkdir(exist_ok=True);args[args.index('-o')+1]=str(obj)
 recipes.append({'name':name,'argv':args,'object':str(obj)})
for e in json.load(open('/tmp/mcppls-joint53-build/full-consumers66/compile-args.json')):
 args=[a.replace('/tmp/mcppls-joint53',source) for a in e['argv']]
 # The source-prefix substitution also affects the old output path: override it.
 obj=out/e['original_object'];obj.parent.mkdir(parents=True,exist_ok=True);args[args.index('-o')+1]=str(obj)
 recipes.append({'name':'clangd/'+e['name'],'argv':args,'object':str(obj)})
(out/'compile-args.json').write_text(json.dumps(recipes,indent=2)+'\n')
def compile_one(e):
 began=time.monotonic();log=out/'logs'/ (e['name'].replace('/','__')+'.log');log.parent.mkdir(exist_ok=True)
 with log.open('w') as f:r=subprocess.run(e['argv'],cwd=build,stdout=f,stderr=subprocess.STDOUT)
 return {'name':e['name'],'exit_code':r.returncode,'seconds':round(time.monotonic()-began,3)}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 tasks={pool.submit(compile_one,e):e for e in recipes}
 for f in concurrent.futures.as_completed(tasks):
  result=f.result();results.append(result)
  (out/'progress.json').write_text(json.dumps(results,indent=2)+'\n')
  print(result,flush=True)
  if result['exit_code']:
   for pending in tasks:pending.cancel()
   raise SystemExit(result['exit_code'])
print('COMPILED_ALL',len(results),flush=True)
for target in ['clangd','ClangdTests']:
 args=json.load(open('/tmp/mcppls-joint53-build/full-consumers66/'+target+'-link-args.json'))
 args=[a.replace('/tmp/mcppls-joint53-build/full-consumers66',str(out)) for a in args]
 for name,lib in [('ExternalASTSource.cpp','lib/libclangAST.a'),('SemaLookup.cpp','lib/libclangSema.a'),('SemaCodeComplete.cpp','lib/libclangSema.a'),('CodeCompleteConsumer.cpp','lib/libclangSema.a'),('ASTReader.cpp','lib/libclangSerialization.a'),('ASTUnit.cpp','lib/libclangFrontend.a'),('CompilerInstance.cpp','lib/libclangFrontend.a')]:
  replacement = str(out/'lib-objects'/(name+'.o'))
  explicit = [i for i,a in enumerate(args) if a.endswith('/'+name+'.o')]
  if explicit:
   assert len(explicit) == 1
   args[explicit[0]] = replacement
  else:
   args.insert(args.index(lib),replacement)
 (out/(target+'-link-args.json')).write_text(json.dumps(args,indent=2)+'\n')
 with (out/(target+'-link.log')).open('w') as f:r=subprocess.run(args,cwd=build,stdout=f,stderr=subprocess.STDOUT)
 print('LINK',target,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
