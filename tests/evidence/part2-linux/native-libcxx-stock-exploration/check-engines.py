from pathlib import Path
import json,subprocess
root=Path(__file__).parent;repo=Path('/home/speak/workspace/github/mcppls-clangd');cdb=(root/'compile_commands.json').read_bytes()
summary={'scope':'Exploratory correctness only, compiler/build jobs overlap; latency is not qualification. Native Clang/libc++ source and actual insertion compiler inputs match between stock and candidate.','arms':{}}
for name,engine in [('stock','/home/speak/.local/share/mcppls/payload/clangd/bin/clangd'),('candidate','/tmp/mcppls-filtered-lookup-formal-build/clangd')]:
 p=root/name
 if p.exists():raise SystemExit('refusing overwrite '+name)
 p.mkdir();cache=p/'cdb';cache.mkdir();(cache/'compile_commands.json').write_bytes(cdb)
 args=['python3',str(repo/'tests/probes/project_completion.py'),'--engine',engine,'--project',str(root),'--source',str(root/'Use.cpp'),'--context-file',str(root/'context.json'),'--starts','1','--rounds','1','--phases','--compile-insertions','--output',str(p/'report.json'),'--engine-flag=-resource-dir=/home/speak/workspace/github/mcppls-clangd/build-linux-x64/lib/clang/23','--engine-flag=--compile-commands-dir='+str(cache)]
 (p/'command.json').write_text(json.dumps(args,indent=2)+'\n')
 with (p/'run.log').open('w') as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
 row={'exit_code':r.returncode}
 if (p/'report.json').exists():
  d=json.loads((p/'report.json').read_text());row.update(engine_sha256=d['engine_sha256'],semantic_pass=d['all_semantic_requests_passed'],insertion_pass=d['all_insertions_compiled'],semantic_counts=d['semantic_counts'])
 summary['arms'][name]=row;(root/'engine-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(name,row,flush=True)
raise SystemExit(any(x['exit_code'] or x.get('semantic_pass') is not True or x.get('insertion_pass') is not True for x in summary['arms'].values()))
