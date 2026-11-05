#!/usr/bin/env python3
"""Frozen-image prefetch control; does not change producer acceptance."""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys

HERE = Path(__file__).resolve().parent
ORDER = ['native', 'touch', '0', '0', 'touch', 'native']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def environment(root, mode):
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(('KAL_', 'OKRUN_')) or key in (
                'LD_PRELOAD', 'LD_LIBRARY_PATH', 'CLANGD_TRACE', 'MCPPLS_DIAGNOSTIC_PERF_GATE'):
            env.pop(key)
    env.update(LANG='C.UTF-8', LC_ALL='C.UTF-8', TZ='UTC', KAL_RESOURCES='balanced')
    for key, name in [('XDG_CACHE_HOME','cache'), ('XDG_CONFIG_HOME','config'),
                      ('XDG_DATA_HOME','data'), ('XDG_STATE_HOME','state'),
                      ('XDG_RUNTIME_DIR','runtime'), ('TMPDIR','tmp'), ('OKRUN_CACHE','placed')]:
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        env[key] = str(folder)
    if mode in ('touch', '0'):
        env['OKRUN_PREFETCH'] = mode
    return env


def mappings(output, runner, bundle):
    output.mkdir(parents=True, exist_ok=False)
    tracer = shutil.which('strace')
    assert tracer, 'mapping control requires an existing strace'
    rows=[]
    for mode in ['default', 'touch', '0']:
        trace = output / (mode + '.trace')
        command = [tracer, '-f', '-qq', '-yy', '-s', '256',
                   '-e', 'trace=mmap,munmap,mprotect,openat,close,execve', '-o', str(trace),
                   str(runner), str(bundle), '--version']
        done = subprocess.run(command, env=environment(output/'loader', mode),
                              text=True, capture_output=True, timeout=30)
        (output/(mode+'.stdout')).write_text(done.stdout)
        (output/(mode+'.stderr')).write_text(done.stderr)
        assert done.returncode == 0 and 'clangd version 23.1.0-mcppls.9' in done.stdout
        mapped=[]
        for line in trace.read_text().splitlines():
            if 'MAP_POPULATE' not in line:
                continue
            match=re.search(r'mmap\(([^,]+), (\d+), ([^,]+), ([^,]+), (.+), (0x[0-9a-f]+|\d+)\)\s*= (.+)',line)
            assert match, line
            address,size,prot,flags,backing,offset,result=match.groups()
            assert not result.startswith('-1')
            mapped.append(dict(bytes=int(size),prot=prot,flags=flags,backing=backing,
                               offset=int(offset,0)))
        rows.append(dict(mode=mode,mappings=mapped,populate_bytes=sum(x['bytes'] for x in mapped),
                         trace_sha256=sha(trace),exit=done.returncode))
        save(output/'progress.json',rows)
    assert rows[0]['mappings'] == rows[1]['mappings']
    assert rows[0]['populate_bytes'] == 20025344
    assert rows[2]['populate_bytes'] == 0 and not rows[2]['mappings']
    save(output/'verified.json',dict(rows=rows,valid=True,qualification=False))
    return rows


def run_case(output, shared, number, mode, inputs, sessions, resource):
    output.mkdir(exist_ok=False)
    prefix=[inputs['native']['path']] if mode=='native' else [inputs['runner']['path'],inputs['bundle']['path']]
    explicit_resource = resource is not None
    resource = resource or (Path(inputs['native' if mode=='native' else 'bundle']['path']).parent.parent/'lib/clang/23')
    if explicit_resource:
        prefix.append('--resource-dir='+str(resource))
    command=[sys.executable,str(HERE/'ready_role_observer.py'),'observe',
             '--output',str(output/'roles'),'--','--label',f'prefetch-{number}-{mode}',
             '--workdir',str(output/'work'),'--out',str(output/'result.json'),
             '--sessions',str(sessions),'--']+prefix
    with (output/'harness.log').open('w') as log:
        done=subprocess.run(command,env=environment(shared,mode),stdout=log,stderr=subprocess.STDOUT,timeout=1500)
    assert done.returncode == 0, ('full workload failed',number,mode)
    result=json.loads((output/'result.json').read_text())
    observation=json.loads((output/'roles/observation.json').read_text())
    assert result['units']==304 and len(result['probes'])==3
    assert len(result['sessions'])==sessions+1
    assert result['sessions'][0]['workers']==176 and result['sessions'][0]['modules_built']==176
    assert all(s['ok'] and s['cache']=='owned' and s['builds']=='in supervised workers' for s in result['sessions'])
    assert all(not o['errors'] and not o['resource_stop'] for o in observation['observers'])
    assert all(c['exit']==0 for c in observation['adopted'])
    phases=[]
    for index,session in enumerate(result['sessions']):
        kind=session['kind']
        log=(output/f'work/session-{index}-{kind}.log').read_text()
        stdlib=re.findall(r'Indexed c\+\+23 standard library: ([^\n]+)',log)
        assert len(stdlib)==1 and 'incomplete' not in stdlib[0]
        actual=[line for line in log.splitlines() if ' -resource-dir=' in line]
        assert len(actual)==3 and all('-resource-dir='+str(resource) in line for line in actual)
        if not explicit_resource:
            assert 'Failed to auto-detect resource directory' not in log
        assert 'falling back' not in log.lower()
        parts=json.loads((output/f'roles/session-{index}/readiness-components.json').read_text())
        assert len(parts['reaped'])==1 and len(parts['usage'])==1
        root=parts['reaped'][0]['root']
        hz=observation['observers'][index]['hz']
        complete=session['waited_usage']
        worker_cpu=[int(value) for value in re.findall(r'Module worker built .+ in \d+ ms: CPU (\d+) ms, peak \d+ MiB',log)]
        assert len(worker_cpu)==session['workers']
        phases.append(dict(kind=kind,stdlib=stdlib,ready_cpu=session['cpu_seconds'],
             ready_seconds=session['ready_seconds'],page_faults=session['page_faults'],
             complete_cpu=complete['user_seconds']+complete['system_seconds'],
             complete_page_faults=session['complete_page_faults'],
             ready_components={key:root[key]/hz for key in ('utime','stime','cutime','cstime')},
             bracket=parts['usage'][0].get('bracket_after_original_measurement'),
             workers=session['workers'],worker_log_cpu_lower_ms=sum(worker_cpu),
             observed_worker_cpu_records=len(worker_cpu)))
    report=dict(number=number,mode=mode,phases=phases,command=command,
                env_override={'KAL_RESOURCES':'balanced','OKRUN_PREFETCH':mode if mode!='native' else None},
                original=result,adopted=observation['adopted'],valid=True,qualification=False)
    save(output/'verified.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--runner',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--resource-dir',type=Path)
    parser.add_argument('--transport-control',action='store_true',help='One non-qualifying cold image session only')
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    inputs={name:dict(path=str(value.resolve()),sha256=sha(value)) for name,value in
            [('native',args.native),('runner',args.runner),('bundle',args.bundle)]}
    assert inputs['native']['sha256']=='176b8da15867a90edf3059ba4ad384920953839477df49f8e2249cce825f3c72'
    assert inputs['bundle']['sha256']=='72fe2ebb7558ff2bdd5dae2f1bccf65ae2357dff6bcf21d73258a2991bde0e25'
    assert sha(HERE/'warm_prime.py')=='0fa91c57969ad090f0e5dbb4d6ab7d2950724993c93a492225e62803da1963d1'
    trees={}
    for lane in ['native','bundle']:
        directory=(args.resource_dir or (Path(inputs[lane]['path']).parent.parent/'lib/clang/23')).resolve()
        trees[lane]={str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    assert trees['native']==trees['bundle'] and len(trees['native'])==303
    order=['0'] if args.transport_control else ORDER
    sessions=0 if args.transport_control else 3
    save(output/'plan.json',dict(inputs=inputs,order=order,warm_sessions=sessions,
         source_sha256=sha(HERE/'warm_prime.py'),script_sha256=sha(__file__),
         resource_tree=trees['native'],workload='original304units/3probes/176workers',
         scope='cold means new module cache; OS page cache is untouched; loader cache shared within batch',
         treatment='existing prefetch policy only; mapping segmentation can also change',
         stopping='stop at first validity failure; no additional samples or retries',qualification=False))
    mappings(output/'mapping-control',args.runner.resolve(),args.bundle.resolve())
    rows=[]
    for index,mode in enumerate(order):
        row=run_case(output/f'case{index}-{mode}',output/'loader',index,mode,inputs,sessions,
                     args.resource_dir.resolve() if args.resource_dir else None)
        rows.append(row);save(output/'progress.json',rows)
        print(json.dumps({k:row[k] for k in ('number','mode','valid')} |
                         {'cold':{k:v for k,v in row['phases'][0].items() if k not in ('bracket','stdlib')}}),flush=True)
    assert len({tuple(phase['stdlib']) for row in rows for phase in row['phases']})==1
    assert all(sha(item['path'])==item['sha256'] for item in inputs.values())
    for lane in ['native','bundle']:
        directory=(args.resource_dir or (Path(inputs[lane]['path']).parent.parent/'lib/clang/23')).resolve()
        assert all(sha(directory/name)==expected for name,expected in trees[lane].items())
    save(output/'verified.json',dict(inputs=inputs,rows=rows,inputs_unchanged=True,
         resources_unchanged=True,valid=True,qualification=False))
