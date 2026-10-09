from pathlib import Path
import json,subprocess,time,hashlib
root=Path(__file__).parent
build=json.loads((root/'progress.json').read_text())
assert build.get('status')=='complete'
identity=json.loads((root/'candidate-identity.json').read_text())
source=Path(identity['source'])
assert all(hashlib.sha256((source/p).read_bytes()).hexdigest()==v for p,v in identity['source_sha256'].items())
args=[str(root/'ClangdTests'),'--gtest_filter=PrerequisiteModulesTests.*Textual*:PrerequisiteModulesTests.CompletionInputs*:CompletionTest.*']
(root/'controls-command.json').write_text(json.dumps(args,indent=2)+'\n')
with (root/'controls.log').open('w') as f:
 p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=300)
result={'scope':'Private71 semantic regression controls only; timings/resources excluded. New joint draft-role-prefix test and existing textual fallback/fresh-byte controls plus whole completion suite.','exit_code':p.returncode,'observed_terminal_unix':time.time(),'test_binary_sha256':hashlib.sha256((root/'ClangdTests').read_bytes()).hexdigest(),'source_commit':identity['source_commit']}
(root/'controls-terminal.json').write_text(json.dumps(result,indent=2)+'\n')
print(result,flush=True)
raise SystemExit(p.returncode)
