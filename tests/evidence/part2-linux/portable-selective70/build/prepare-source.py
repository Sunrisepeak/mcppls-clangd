from pathlib import Path
import subprocess,json,os,time,hashlib
root=Path(__file__).parent;repo=Path('/home/speak/workspace/github/mcppls-clangd')
identity=json.loads((repo/'tests/evidence/part2-linux/selective-unqualified-export70/identity.json').read_text())
env=os.environ.copy();env.update(LLVM_DIR='/dev/shm/mcppls-part2-floor70-source',BUILD_DIR='/dev/shm/mcppls-part2-floor70-build',DIST_DIR=str(root/'dist'),TARBALL=str(repo/'llvm-src.tar.gz'),PLATFORM='linux-x64')
assert Path(env['TARBALL']).is_file(), 'Require cached verified tarball; no download intended'
status={'scope':'Fresh cached pinned tarball and whole70 series preparation; no build or performance qualification.','status':'running','stages':[],'started_unix':time.time(),'series_sha256':identity['series_sha256']}
for stage in ['fetch','apply']:
 with (root/(stage+'.log')).open('w') as log:r=subprocess.run(['bash','ci/scripts/'+stage+'.sh'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=500)
 status['stages'].append({'stage':stage,'exit_code':r.returncode});(root/'source-progress.json').write_text(json.dumps(status,indent=2)+'\n');print(stage,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
source=Path(env['LLVM_DIR'])
assert {f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in identity['source_hashes']}==identity['source_hashes']
def tree(path,rev):
 return {line.split('\t',1)[1]:line.split('\t',1)[0] for line in subprocess.check_output(['git','-C',str(path),'ls-tree','-r',rev],text=True).splitlines()}
a=tree(source,'HEAD');b=tree('/dev/shm/mcppls-part2-unqualified70','HEAD')
differences=sorted(n for n in a.keys()|b.keys() if a.get(n)!=b.get(n))
assert differences==['.mcppls-clangd-fetched-'],differences[:20]
status.update(status='complete',source=str(source),source_head=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),tracked_tree_differences= differences,changed_sources_byte_equal=True,finished_unix=time.time())
(root/'source-progress.json').write_text(json.dumps(status,indent=2)+'\n');print('WHOLE70_SOURCE_PREP_PASS',flush=True)
