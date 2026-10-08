from pathlib import Path
import os,json,subprocess,time
root=Path(__file__).parent;repo=Path('/home/speak/workspace/github/mcppls-clangd');status=json.loads((root/'progress.json').read_text())
assert status['stages'][-1]=={'stage':'build-test','exit_code':1}
log=(root/'build-test.log').read_text(errors='replace');assert 'No space left on device' in log
scratch=Path('/dev/shm/mcppls-clean-selective68-compiler-temp');scratch.mkdir(exist_ok=True)
env=os.environ.copy();env.update(LLVM_DIR=str(root/'llvm-project'),BUILD_DIR=str(root/'build-linux-x64'),DIST_DIR=str(root/'dist'),PLATFORM='linux-x64',JOBS='6',TEST='1',RUN_TESTS='lit-subset',CMAKE_EXTRA='-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',TMPDIR=str(scratch))
status['current_stage']='build-test-resume';status['resume_reason']='Confirmed terminal compiler temporary/output writes hit root filesystem exhaustion. Keep partial clean build, use dedicated tmpfs compiler temporary directory; no source/flags/series change.';status['compiler_temp']=str(scratch);(root/'progress.json').write_text(json.dumps(status,indent=2)+'\n')
with (root/'build-test-resume.log').open('w') as f:r=subprocess.run(['bash','ci/ci_build.sh'],cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
status['stages'].append({'stage':'build-test-resume','exit_code':r.returncode});status['current_stage']='complete' if r.returncode==0 else 'failed';status['finished_unix']=time.time();(root/'progress.json').write_text(json.dumps(status,indent=2)+'\n');print('resume',r.returncode,flush=True)
raise SystemExit(r.returncode)
