from pathlib import Path
import json,subprocess,time,shutil,os,signal
root=Path(__file__).parent
if (root/'progress.json').exists():raise SystemExit('refuse to overwrite a prior floor attempt')
if shutil.disk_usage(root).free < 6*1024**3:raise SystemExit('insufficient root space for retained floor build; no build started')
args=json.loads((root/'command.json').read_text())
status={'status':'running','started_unix':time.time(),'scope':'Same-source floor build/package; not performance measurement.','command':args}
(root/'progress.json').write_text(json.dumps(status,indent=2)+'\n')
with (root/'run.log').open('w') as log:
 p=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 status['docker_cli_pid']=p.pid;(root/'progress.json').write_text(json.dumps(status,indent=2)+'\n')
 try:result=p.wait(timeout=10800)
 except subprocess.TimeoutExpired:
  cid=root/'container.id'
  if cid.exists():subprocess.run(['docker','rm','-f',cid.read_text().strip()],stdout=log,stderr=subprocess.STDOUT,timeout=30)
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  p.wait();result=124
status.update(status='complete' if result==0 else 'failed',exit_code=result,finished_unix=time.time())
(root/'progress.json').write_text(json.dumps(status,indent=2)+'\n')
print('Floor build/package:',result,flush=True)
raise SystemExit(result)
