from pathlib import Path
import json,subprocess,hashlib
base=Path(__file__).parent
assert json.loads((base/'matrix-distribution/terminal.json').read_text())['terminal'] is True, 'Require observed matrix process termination before tracing'
assert len(json.loads((base/'matrix-distribution/summary.json').read_text())['results'])==12, 'Complete final matrix before attribution'
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:name=(proc/'comm').read_text().strip()
 except OSError:continue
 if name.startswith('clangd') or name in {'clang','clang++','cc1','cc1plus','g++','gcc','ninja'}:raise SystemExit('Other clangd/compiler activity blocks isolated attribution: '+proc.name+' '+name)
root=base/'unqualified-attribution'
if root.exists():raise SystemExit('Refusing to overwrite attribution evidence')
root.mkdir()
probes=Path('/home/speak/workspace/github/mcppls-clangd/tests/probes')
engine=base.parent/'dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd'
resource=engine.parent.parent/'lib/clang/23'
cdb=Path('/tmp/mcppls-pch-scan68-build/integrated/qt-cdb/compile_commands.json').read_bytes()
summary={'scope':'Final-byte native trace attribution only, 1start x3rounds; trace timings cannot qualify distribution. First-column/ordinary failed or near-budget paths, no optimization claim from source inspection alone.','engine_sha256':hashlib.sha256(engine.read_bytes()).hexdigest(),'results':{}}
for context in ['first-column','ordinary']:
 out=root/context;out.mkdir();cache=out/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 args=['python3',str(probes/'project_completion.py'),'--engine',str(engine),'--project','/home/speak/test/mcpp/qt-demo','--source','/home/speak/test/mcpp/qt-demo/src/main.cpp','--context-file',str(probes/'contexts/qt'/f'{context}.json'),'--starts','1','--rounds','3','--phases','--resources','--trace',str(out/'trace.json'),'--output',str(out/'report.json'),'--engine-flag=-resource-dir='+str(resource),'--engine-flag=--compile-commands-dir='+str(cache)]
 (out/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 with (out/'run.log').open('w') as log:result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 summary['results'][context]={'exit_code':result.returncode}
 (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 if result.returncode:raise SystemExit(result.returncode)
 print(context,'trace complete',flush=True)
