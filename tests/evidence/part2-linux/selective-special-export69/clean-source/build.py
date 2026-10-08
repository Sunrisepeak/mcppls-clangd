from pathlib import Path
import subprocess,os,json,time,hashlib
root=Path(__file__).parent;repo=Path('/home/speak/workspace/github/mcppls-clangd')
evidence=repo/'tests/evidence/part2-linux/selective-special-export69/identity.json'
identity=json.loads(evidence.read_text())
series=subprocess.check_output(['python3','ci/series_identity.py'],cwd=repo,text=True).strip()
env=os.environ.copy();env.update(LLVM_DIR=str(root/'llvm-project'),BUILD_DIR=str(root/'build-linux-x64'),DIST_DIR=str(root/'dist'),TARBALL=str(repo/'llvm-src.tar.gz'),PLATFORM='linux-x64',JOBS='6',TEST='1',RUN_TESTS='lit-subset',CMAKE_EXTRA='-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',TMPDIR='/dev/shm/mcppls-clean-special69-compiler-temp')
Path(env['TMPDIR']).mkdir(exist_ok=True)
runtime=subprocess.check_output(['/home/speak/.xlings/subos/default/bin/c++','-print-file-name=libstdc++.so.6'],text=True).strip()
assert Path(runtime).is_file()
env['LD_LIBRARY_PATH']=str(Path(runtime).resolve().parent)+((':'+env['LD_LIBRARY_PATH']) if env.get('LD_LIBRARY_PATH') else '')
status={'series_sha256':series,'export_identity':identity,'source':env['LLVM_DIR'],'build':env['BUILD_DIR'],'runtime_library':runtime,'runtime_scope':'Local consumer execution only; does not prove payload relocation.','started_unix':time.time(),'stages':[]}
def save(): (root/'progress.json').write_text(json.dumps(status,indent=2)+'\n')
save()
for stage,args in [('fetch',['bash','ci/scripts/fetch.sh']),('apply',['bash','ci/scripts/apply.sh']),('configure',['bash','ci/scripts/configure.sh']),('build-test',['bash','ci/ci_build.sh'])]:
 status['current_stage']=stage;save()
 with (root/(stage+'.log')).open('w') as f:r=subprocess.run(args,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
 status['stages'].append({'stage':stage,'exit_code':r.returncode});save()
 print(stage,r.returncode,flush=True)
 if r.returncode:status['current_stage']='failed';status['finished_unix']=time.time();save();raise SystemExit(r.returncode)
 if stage=='apply':
  source=Path(env['LLVM_DIR']);hashes={f:hashlib.sha256((source/f).read_bytes()).hexdigest() for f in identity['source_hashes']}
  assert hashes==identity['source_hashes']
  status['changed_sources_byte_equal']=True;status['source_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip();save()
status['current_stage']='complete';status['finished_unix']=time.time();save()
