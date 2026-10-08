from pathlib import Path
import json,subprocess,time
root=Path(__file__).parent
assert json.loads((root/'progress.json').read_text())['status']=='complete'
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:name=(proc/'comm').read_text().strip()
 except OSError:continue
 if name.startswith('clangd') or name in {'cc1','cc1plus','clang','clang++','ninja'}:raise SystemExit('Active compiler/clangd blocks isolated profile')
probes=Path('/home/speak/workspace/github/mcppls-clangd/tests/probes')
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
results={}
for context in ['first-column','ordinary']:
 out=root/context
 if out.exists():raise SystemExit('Refusing reused profile case')
 out.mkdir();cache=out/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 args=['python3',str(probes/'project_completion.py'),'--engine',str(root/'clangd'),'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--context-file',str(probes/'contexts/qt'/f'{context}.json'),'--starts','1','--rounds','3','--phases','--trace',str(out/'trace.json'),'--output',str(out/'report.json'),'--engine-flag=-resource-dir=/tmp/mcppls-part2-floor69/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (out/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 with (out/'run.log').open('w') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 results[context]={'exit_code':r.returncode,'scope':'Private batch CPU/work attribution, not latency qualification.'};(root/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 print(context,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
