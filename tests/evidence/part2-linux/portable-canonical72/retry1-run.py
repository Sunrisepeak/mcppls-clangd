from pathlib import Path
import json,subprocess,time,shutil,os,signal
root=Path(__file__).parent
if (root/'retry1-progress.json').exists():raise SystemExit('refuse to overwrite a prior floor attempt')
if shutil.disk_usage(root).free < 1024**3:raise SystemExit('insufficient root space for final package/evidence; no build started')
if shutil.disk_usage('/dev/shm').free < 8*1024**3:raise SystemExit('insufficient shared memory for retained build/source; no build started')
assert json.loads((root/'source-progress.json').read_text())['status']=='complete'
args=json.loads((root/'retry1-command.json').read_text())
status={'status':'running','started_unix':time.time(),'scope':'Whole72 clean floor build/test/package with source/build in shared memory to preserve root storage. Not performance measurement; old builds/sources/binaries/negative evidence retained, final package/logs on data disk.','command':args}
(root/'retry1-progress.json').write_text(json.dumps(status,indent=2)+'\n')
with (root/'retry1-run.log').open('w') as log:
 p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 status['docker_cli_pid']=p.pid;(root/'retry1-progress.json').write_text(json.dumps(status,indent=2)+'\n')
 try:result=p.wait(timeout=10800)
 except subprocess.TimeoutExpired:
  cid=root/'retry1-container.id'
  if cid.exists():subprocess.run(['docker','rm','-f',cid.read_text().strip()],stdout=log,stderr=subprocess.STDOUT,timeout=30)
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  p.wait();result=124
status.update(status='complete' if result==0 else 'failed',exit_code=result,finished_unix=time.time())
(root/'retry1-progress.json').write_text(json.dumps(status,indent=2)+'\n')
print('Floor build/package:',result,flush=True)
raise SystemExit(result)
