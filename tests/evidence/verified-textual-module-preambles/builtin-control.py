import importlib.util,json,pathlib,tempfile,hashlib
D=pathlib.Path('/tmp/mcppls-textual65-build');P=pathlib.Path(tempfile.mkdtemp(prefix='builtin-',dir=D))
spec=importlib.util.spec_from_file_location('replay','/home/speak/workspace/github/mcppls-clangd/tests/crash/replay.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
clang='/home/speak/workspace/github/mcppls-clangd/build-linux-x64/bin/clang++';E=D/'clangd'
(P/'M.cppm').write_text('module;\n#include <stddef.h>\nexport module M;\nexport struct BundleValue { size_t size; };\nexport int fn_bundle() { return sizeof(BundleValue); }\n')
U=P/'Use.cpp';text='import M;\nvoid probe() { fn; }\n';U.write_text(text)
(P/'compile_commands.json').write_text(json.dumps([{'directory':str(P),'file':str(f),'arguments':[clang,'-std=c++20','-fmodules','-c',str(f)]} for f in [P/'M.cppm',U]]))
seq=[{'method':'initialize','params':{'rootUri':P.as_uri(),'capabilities':{}}},{'method':'initialized','notify':True,'params':{}},{'method':'textDocument/didOpen','notify':True,'params':{'textDocument':{'uri':U.as_uri(),'languageId':'cpp','version':1,'text':text}}},{'method':'textDocument/completion','expected_symbols':['fn_bundle'],'params':{'textDocument':{'uri':U.as_uri()},'position':{'line':1,'character':17}}}]
case=P/'case.json';case.write_text(json.dumps({'id':'owned-implicit-bundle','project':'.','platform':r.platform_name(),'baseline':'pass','timeout_seconds':30,'flags':['--experimental-modules-support','--background-index=false','--log=verbose','-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23'],'sequence':seq}))
reports=[]
identities=[]
for i in range(2):
 q=r.replay(E,case); reports.append(q); (D/('builtin-'+str(i)+'.log')).write_text(q['stderr']);assert q['outcome']=='pass',q.get('detail'); assert q['exit_code']==0,q
 pcms=list(P.rglob('*.pcm')); assert any('/module-cache/' in str(x) for x in pcms),pcms
 identities.append({str(x):(x.stat().st_dev,x.stat().st_ino,x.stat().st_size,x.stat().st_mtime_ns) for x in pcms})
assert identities[0]==identities[1],identities
(D/'builtin-control.json').write_text(json.dumps({'project':str(P),'engine_sha256':hashlib.sha256(E.read_bytes()).hexdigest(),'reports':reports,'identities':identities,'pcms':[str(x) for x in P.rglob('*.pcm')]},indent=2))
print(P)
