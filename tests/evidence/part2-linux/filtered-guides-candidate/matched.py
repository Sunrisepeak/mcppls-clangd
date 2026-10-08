import pathlib,subprocess,json,hashlib
root=pathlib.Path(__file__).parent/'matched';root.mkdir(exist_ok=True)
cdb=pathlib.Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
probe='/home/speak/workspace/github/mcppls-clangd/tests/probes/project_completion.py'
baseline='/tmp/mcppls-filtered-lookup-formal-build/clangd';candidate=str(root.parent/'clangd')
for arm,engine in [('baseline-before',baseline),('candidate',candidate),('baseline-after',baseline)]:
 p=root/arm;p.mkdir(exist_ok=True);d=p/'cdb';d.mkdir(exist_ok=True)
 if (d/'.cache').exists():raise SystemExit('refusing to reuse cache for '+arm)
 (d/'compile_commands.json').write_bytes(cdb)
 args=['python3',probe,'--engine',engine,'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--context-file','/home/speak/workspace/github/mcppls-clangd/tests/probes/contexts/qt/std-qualified.json','--starts','1','--rounds','5','--phases','--compile-insertions','--resources','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23','--engine-flag=--compile-commands-dir='+str(d)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
 print(arm,'exit',r.returncode,flush=True)
 if (p/'report.json').exists():
  report=json.load(open(p/'report.json'));print({k:v for k,v in report['phases'].items() if k!='cold-open'},flush=True)
 if r.returncode:raise SystemExit(r.returncode)
