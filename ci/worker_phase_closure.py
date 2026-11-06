#!/usr/bin/env python3
"""Close frozen native/image worker CPU stages against waited-child totals."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from prefetch_probe import environment, save, sha
from frozen_phase_probe import detailed_stages, meter_control


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--native', required=True, type=Path)
    ap.add_argument('--bundle', required=True, type=Path)
    ap.add_argument('--variants', required=True, type=Path)
    ap.add_argument('--backend-variants', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    a.output = a.output.resolve()
    a.output.mkdir(exist_ok=False)
    build = json.loads((a.variants/'verified.json').read_text())
    backend = json.loads((a.backend_variants/'verified.json').read_text())
    assert build['baseline_reproduced_exactly'] and build['originals_unchanged']
    assert backend['valid'] and backend['original_backend_object_reproduced']
    assert backend['original_objects_unchanged']
    assert backend['variants_sha256'] == sha(a.variants/'verified.json')
    runners = {r['label']: r for r in backend['results']}
    native, bundle = a.native.resolve(), a.bundle.resolve()
    assert sha(native) == '176b8da15867a90edf3059ba4ad384920953839477df49f8e2249cce825f3c72'
    assert sha(bundle) == '72fe2ebb7558ff2bdd5dae2f1bccf65ae2357dff6bcf21d73258a2991bde0e25'
    inputs = {str(p): sha(p) for p in [native, bundle, Path(build['meter']['path']),
              Path(build['meter_control']['path']), Path(runners['filtered']['path']),
              Path(runners['filtered-phases']['path'])]}
    for item in [build['meter'], build['meter_control'], *runners.values()]:
        assert sha(item['path']) == item['sha256']
    resource = native.parent.parent/'lib/clang/23'
    resources = {str(p.relative_to(resource)): sha(p) for p in resource.rglob('*') if p.is_file()}
    assert len(resources) == 303
    order = ['native', 'image', 'image', 'native']
    save(a.output/'plan.json', dict(order=order, inputs=inputs, resources=resources,
        purpose='Identify dominant child kernel stage after the published supervisor fix. Preserve the unaccounted reporting/exit remainder rather than attributing it to main.',
        cases='Four fixed cases, each one cold and one warm;304units/3probes/176coldworkers.',
        boundaries='Native C++main and exit callbacks separate; image entry includes libc guard/main/exitcallbacks. Final phase precedes report writing and process teardown.',
        scope='Stage profiles are diagnostic. No per-import clocks. Stable-reap readiness v3 and actual waited-child user/system counters retained.',
        stopping='Stop on invalid identities, semantic results, missing profiles or inconsistent arithmetic. No extra cases based on pass/fail.',
        affinity=sorted(os.sched_getaffinity(0)), cpu_models=sorted({line.split(':',1)[1].strip()
            for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')}),
        qualification=False))
    meter_control(a.output/'meter-control', build)
    env = environment(a.output/'loader', 'default')
    seed = subprocess.run([runners['filtered']['path'],str(bundle),'--version'],env=env,
                          capture_output=True,text=True,timeout=30)
    assert seed.returncode == 0
    deadline = time.monotonic()+30
    while True:
        markers=list((a.output/'loader/placed').rglob('*.sealing'))
        snapshots=list((a.output/'loader/placed').rglob('*.oksnap'))
        if len(markers)==len(snapshots)==1 and markers[0].read_text().strip()=='made': break
        assert time.monotonic()<deadline
        time.sleep(.02)
    snapshot = sha(snapshots[0])
    rows=[]; drivers=set(); stdlib=set()
    for index,lane in enumerate(order):
        case=a.output/f'case{index}-{lane}'; case.mkdir()
        profiles=case/'profiles'; profiles.mkdir()
        current=dict(env)
        if lane=='native':
            prefix=[str(native)]
            current.update(LD_PRELOAD=build['meter']['path'],MCPP_DIAG_PHASE_BINARY=str(native),
                           MCPP_DIAG_PHASE_DIR=str(profiles))
        else:
            prefix=[runners['filtered-phases']['path'],str(bundle)]
            current['OKRUN_PROF']='phases:'+str(profiles)
        prefix.append('--resource-dir='+str(resource))
        here=Path(__file__).resolve().parent
        command=[sys.executable,str(here/'ready_role_observer.py'),'observe','--source',str(here/'warm_prime.py'),
            '--output',str(case/'roles'),'--','--label',lane,'--workdir',str(case/'work'),
            '--out',str(case/'result.json'),'--sessions','1','--']+prefix
        with (case/'harness.log').open('w') as log:
            done=subprocess.run(command,env=current,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        assert done.returncode==0, (index,lane,'workload failed')
        result=json.loads((case/'result.json').read_text())
        assert result['measurement_version']==3 and result['units']==304 and len(result['probes'])==3
        assert len(result['sessions'])==2
        assert result['sessions'][0]['workers']==176 and result['sessions'][1]['workers']==0
        roots={}; actual=[]
        for j,session in enumerate(result['sessions']):
            assert session['ok'] and session['cpu_sample']['valid'] and session['cpu_sample']['processes']==1
            raw=json.loads((case/f'roles/session-{j}/readiness-components.json').read_text())['usage'][0]['bracket_after_original_measurement']
            assert raw['waited_fields_stable'] and len(raw['processes'])==1
            roots[raw['before']['pid']]=session['kind']+'-parent'
            hz=json.loads((case/f'roles/session-{j}/observer.json').read_text())['hz']
            parts={k:raw['before'][k]/hz for k in ['utime','stime','cutime','cstime']}
            assert abs(sum(parts.values())-session['cpu_seconds'])<.000001
            actual.append(dict(kind=session['kind'],parts=parts,ready_cpu=session['cpu_seconds'],
                               complete=session['waited_usage']))
            text=(case/f'work/session-{j}-{session["kind"]}.log').read_text()
            commands=[line for line in text.splitlines() if ' -resource-dir=' in line]
            assert len(commands)==3 and all('-resource-dir='+str(resource) in line for line in commands)
            drivers.update(line.split(' ',1)[0] for line in commands)
            import re
            standard=re.findall(r'Indexed c\+\+23 standard library: ([^\n]+)',text)
            assert len(standard)==1 and 'incomplete' not in standard[0]
            stdlib.add(standard[0])
        docs=[json.loads(p.read_text()) for p in profiles.glob('*.json')]
        assert len(docs)==178
        aggregates={r:Counter() for r in ['cold-parent','warm-parent','worker']}
        ids=set(); counts=Counter()
        for d in docs:
            pid=d['pid'] if lane=='native' else d['id']
            assert pid not in ids; ids.add(pid)
            role=roots.get(pid,'worker'); counts[role]+=1
            if lane=='native': assert d['result']==0
            else:
                assert not d['calls']
                assert any(n['point']=='snapshot' and n['outcome']=='used' for n in d['runner'])
                assert any(n['point']=='prefetch' and n['outcome']=='the touched pages' for n in d['runner'])
            aggregates[role].update(detailed_stages(d,lane=='native'))
        assert counts=={'cold-parent':1,'warm-parent':1,'worker':176}
        stages={role:dict(c) for role,c in aggregates.items()}
        w=stages['worker']; p=actual[0]['parts']
        residual={part:p[field]-w['accounted_'+part+'_ns']/1e9 for part,field in [('user','cutime'),('system','cstime')]}
        # Tick-quantized parent usage and child microsecond observations need not
        # have identical rounding; retain the signed remainder.
        assert all(v>=-.03 for v in residual.values())
        row=dict(index=index,lane=lane,stages=stages,actual=actual,
            worker_waited_minus_accounted_seconds=residual,profiles=178)
        rows.append(row); save(a.output/'progress.json',rows)
        print(json.dumps(dict(index=index,lane=lane,worker_ms={k:round(w[k]/1e6,3) for k in [
            'startup_user_ns','startup_system_ns','body_user_ns','body_system_ns','body_other_system_ns']},
            residual_ms={k:round(v*1000,3) for k,v in residual.items()})),flush=True)
    assert len(drivers)==len(stdlib)==1
    assert all(sha(p)==h for p,h in inputs.items())
    assert sha(snapshots[0])==snapshot and all(sha(resource/p)==h for p,h in resources.items())
    save(a.output/'verified.json',dict(valid=True,qualification=False,rows=rows,drivers=list(drivers),
        stdlib=list(stdlib),inputs_unchanged=True,resources_unchanged=True,snapshot_unchanged=True))


if __name__=='__main__':
    main()
