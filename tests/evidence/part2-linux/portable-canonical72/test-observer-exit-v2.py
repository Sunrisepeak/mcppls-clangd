from pathlib import Path
import sys,os,subprocess,time,json,importlib.util
q=Path(__file__).parent
spec=importlib.util.spec_from_file_location('tree_v2',q/'project-completion-tree-v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
report={'scope':'Actual Linux unreaped exited process and unexpected observer exception controls. Not engine semantics or latency.'}
p=subprocess.Popen([sys.executable,'-c','pass'])
try:
 os.waitid(os.P_PID,p.pid,os.WEXITED|os.WNOWAIT)
 sampler=m.TreeResources();sampler.proc=p;sampler.began=time.monotonic();sampler.tree=m.ProcessTree(p.pid)
 report['exited_process_state']=m.stat(p.pid)['state']
 assert report['exited_process_state']=='Z'
 try:sampler.read();raise AssertionError('exited process was accepted')
 except m.TreeChanged as e:report['exit_race']=str(e)
finally:p.wait(timeout=5)
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)'])
try:
 sampler=m.TreeResources()
 def injected_read():raise RuntimeError('injected unexpected observation failure')
 sampler.read=injected_read;sampler.started(p,time.monotonic()+2);sampler.thread.join(timeout=2)
 p.terminate();p.wait(timeout=5);result=sampler.finish()
 assert result['errors']==['RuntimeError: injected unexpected observation failure'] and result['sampler_stopped'] and not result['remaining_owned_processes']
 report['unexpected_exception_recorded']=result
finally:
 if p.poll() is None:p.kill();p.wait(timeout=5)
p=q/'observer-exit-control-v2.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n')
print('Actual exited-process race classified; unexpected observation exception recorded.')
