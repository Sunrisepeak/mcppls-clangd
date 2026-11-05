#!/usr/bin/env python3
"""Fixed native/image CPU phase and child-prefetch diagnostic, not admission."""
from pathlib import Path
import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import time
import psutil
import prefetch_probe as probe

HERE = Path(__file__).resolve().parent
ORIGINAL_ENVIRONMENT = probe.environment
CURRENT = {}
PHASE_ORDER = [('native', 'native'), ('baseline', 'default'), ('candidate', 'default'),
               ('candidate', 'touch'), ('native', 'native')]
MAIN_ORDER = ['native', 'baseline', 'candidate', 'candidate', 'baseline', 'native']


def environment(root, mode):
    env = ORIGINAL_ENVIRONMENT(root, mode)
    for key in ['MCPP_DIAG_PHASE_BINARY', 'MCPP_DIAG_PHASE_DIR']:
        env.pop(key, None)
    profile = CURRENT.get('profile')
    if profile:
        if CURRENT['label'] == 'native':
            env.update(LD_PRELOAD=CURRENT['meter'], MCPP_DIAG_PHASE_BINARY=CURRENT['native'],
                       MCPP_DIAG_PHASE_DIR=str(profile))
        else:
            env['OKRUN_PROF'] = 'phases:' + str(profile)
    return env


def meter_control(output, build):
    output.mkdir()
    executable = Path(build['meter_control']['path']).resolve()
    rows = []
    for mode in ['return', 'exit', 'quit']:
        folder = output/mode
        folder.mkdir()
        env = ORIGINAL_ENVIRONMENT(output/'loader', 'native')
        env.update(LD_PRELOAD=build['meter']['path'], MCPP_DIAG_PHASE_BINARY=str(executable),
                   MCPP_DIAG_PHASE_DIR=str(folder))
        done = subprocess.run([str(executable), mode], env=env, capture_output=True, text=True, timeout=15)
        (folder/'stderr.log').write_text(done.stderr)
        assert done.returncode == 0
        paths = list(folder.glob('native-*.json'))
        assert len(paths) == 1
        row = json.loads(paths[0].read_text())
        assert row['main_ns'] >= 10_000_000
        if mode == 'quit':
            assert row['cleanup_ns'] < 5_000_000
        else:
            assert row['cleanup_ns'] >= 30_000_000
        rows.append(dict(mode=mode, result=row))
    probe.save(output/'verified.json', dict(rows=rows, valid=True, qualification=False))


def snapshot_seed(output, runner, bundle):
    done = subprocess.run([runner, bundle, '--version'], env=environment(output, 'default'),
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0 and 'clangd version 23.1.0-mcppls.9' in done.stdout
    deadline = time.monotonic() + 30
    while True:
        markers = list((output/'placed').rglob('*.sealing'))
        snapshots = list((output/'placed').rglob('*.oksnap'))
        if len(markers) == 1 and markers[0].read_text().strip() == 'made' and len(snapshots) == 1:
            return dict(path=str(snapshots[0]), sha256=probe.sha(snapshots[0]), bytes=snapshots[0].stat().st_size)
        assert time.monotonic() < deadline, 'snapshot was not actually created'
        time.sleep(.02)


def aggregate_role(records, role):
    selected = [record for record in records if record['role'] == role]
    assert selected
    return {key: sum(record['stages'][key] for record in selected) for key in selected[0]['stages']}


def phase_report(folder, label, mode, workload):
    root_ids = {p['bracket']['before']['pid']: p['kind'] + '-parent' for p in workload['phases']}
    assert len(root_ids) == 2
    profiles = [json.loads(p.read_text()) for p in sorted(folder.glob('*.json'))]
    assert len(profiles) == 178, (label, len(profiles))
    records = []
    for profile in profiles:
        pid = profile['pid'] if label == 'native' else profile['id']
        role = root_ids.get(pid, 'worker')
        if label == 'native':
            assert profile['result'] == 0 and profile['after_main_ns'] >= profile['before_main_ns'] > 0
            assert profile['after_exit_callbacks_ns'] >= profile['after_main_ns']
            stages = dict(startup_ns=profile['before_main_ns'], body_ns=profile['main_ns'],
                          cleanup_ns=profile['cleanup_ns'], accounted_ns=profile['after_exit_callbacks_ns'])
            assert stages['startup_ns'] + stages['body_ns'] + stages['cleanup_ns'] == stages['accounted_ns']
            boundary = profile['boundary']
        else:
            moments = profile['moments']
            named = {moment['name']: moment for moment in moments}
            assert all((moment['present'] & 4) and (moment['present'] & 32) for moment in moments)
            assert all(moments[i]['cpu_ns'] <= moments[i + 1]['cpu_ns'] for i in range(len(moments) - 1))
            assert all(name in named for name in ['admitted', 'loaded', 'initialised', 'main'])
            stages = dict(startup_ns=named['initialised']['cpu_ns'],
                          body_ns=named['main']['cpu_ns'] - named['initialised']['cpu_ns'],
                          accounted_ns=named['main']['cpu_ns'],
                          before_admitted_ns=named['admitted']['cpu_ns'],
                          load_ns=named['loaded']['cpu_ns'] - named['admitted']['cpu_ns'],
                          initialise_ns=named['initialised']['cpu_ns'] - named['loaded']['cpu_ns'])
            assert stages['startup_ns'] == sum(stages[key] for key in ['before_admitted_ns', 'load_ns', 'initialise_ns'])
            expected = 'nothing' if label == 'candidate' and mode == 'default' and role == 'worker' else 'the touched pages'
            assert any(note['point'] == 'prefetch' and note['outcome'] == expected for note in profile['runner'])
            assert any(note['point'] == 'snapshot' and note['outcome'] == 'used' for note in profile['runner'])
            boundary = 'image entry including libc guard, C++main, exit callbacks and stdio'
        records.append(dict(pid=pid, role=role, boundary=boundary, stages=stages))
    assert len({record['pid'] for record in records}) == 178
    assert sum(record['role'] == 'worker' for record in records) == 176
    aggregate = {role: aggregate_role(records, role) for role in ['cold-parent', 'worker', 'warm-parent']}
    cold_accounted = (aggregate['cold-parent']['accounted_ns'] + aggregate['worker']['accounted_ns']) / 1e9
    assert cold_accounted <= workload['phases'][0]['complete_cpu'] + .025
    return dict(records=records, aggregate=aggregate,
                cold_complete_minus_accounted_cpu=workload['phases'][0]['complete_cpu'] - cold_accounted,
                valid=True, qualification=False)


def validate_original(row):
    for phase, original in zip(row['phases'], row['original']['sessions'], strict=True):
        assert phase['ready_cpu'] == original['cpu_seconds']
        assert abs(sum(phase['ready_components'].values()) - phase['ready_cpu']) < 1e-8
        assert phase['bracket']['waited_fields_stable'] and len(phase['bracket']['processes']) == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variants', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true', help='one complete candidate cold/warm transport check; not the fixed comparison')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build = json.loads((args.variants/'verified.json').read_text())
    assert build['baseline_reproduced_exactly'] and build['originals_unchanged']
    runners = {row['label']: {key: row[key] for key in ['path', 'sha256']} for row in build['results']}
    native = dict(path=str(args.native.resolve()), sha256=probe.sha(args.native))
    bundle = dict(path=str(args.bundle.resolve()), sha256=probe.sha(args.bundle))
    assert native['sha256'] == '176b8da15867a90edf3059ba4ad384920953839477df49f8e2249cce825f3c72'
    assert bundle['sha256'] == '72fe2ebb7558ff2bdd5dae2f1bccf65ae2357dff6bcf21d73258a2991bde0e25'
    assert probe.sha(HERE/'warm_prime.py') == '0fa91c57969ad090f0e5dbb4d6ab7d2950724993c93a492225e62803da1963d1'
    identities = [native, bundle, build['meter'], build['meter_control'], *runners.values()]
    assert all(probe.sha(item['path']) == item['sha256'] for item in identities)
    resource = args.native.resolve().parent.parent/'lib/clang/23'
    resources = {str(p.relative_to(resource)): probe.sha(p) for p in sorted(resource.rglob('*')) if p.is_file()}
    assert len(resources) == 303
    phase_order = [('candidate', 'default')] if args.preflight_only else PHASE_ORDER
    main_order = [] if args.preflight_only else MAIN_ORDER
    probe.save(output/'plan.json', dict(native=native, bundle=bundle, runners=runners,
        native_meter=build['meter'], resource_tree=resources, phase_order=phase_order, main_order=main_order,
        workload='Original 304units/3probes/176coldworkers. Phase cases onecoldonewarm; main cases onecoldthreewarm.',
        cache='Shared warmed loader cache; independent module cache per case; OS page cache untouched.',
        boundaries='Native main and exitcallbacks separate; image entry includes runtime guard and exitcallbacks/stdio. Different instrumentation costs remain. No phase ratios are admission results.',
        stopping='First input/semantic/observer validity failure; fixed cases only, no favorable-data reruns.',
        platform=platform.platform(), affinity=sorted(os.sched_getaffinity(0)),
        cpu_models=sorted({line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')}),
        tools={name: str(Path(shutil.which(name)).resolve()) for name in ['clang++', 'mcpp']},
        script_sha256=probe.sha(__file__), observer_sha256=probe.sha(HERE/'ready_role_observer.py'),
        qualification=False))
    CURRENT.update(native=native['path'], meter=build['meter']['path'])
    probe.environment = environment
    meter_control(output/'native-meter-control', build)
    snapshot = snapshot_seed(output/'loader', runners['baseline']['path'], bundle['path'])
    probe.save(output/'snapshot-seed.json', snapshot)
    phase_results = []
    for number, (label, mode) in enumerate(phase_order):
        folder = output/f'phase{number}-{label}-{mode}'
        folder.mkdir()
        profiles = folder/'profiles'
        profiles.mkdir()
        CURRENT.update(label=label, profile=profiles)
        inputs = dict(native=native, bundle=bundle, runner=runners['baseline-phases' if label == 'native' else label + '-phases'])
        row = probe.run_case(folder/'workload', output/'loader', number, mode, inputs, 1, resource)
        validate_original(row)
        report = phase_report(profiles, label, mode, row)
        report.update(label=label, mode=mode, workload=row)
        probe.save(folder/'verified.json', report)
        phase_results.append(report)
        probe.save(output/'phase-progress.json', phase_results)
        print(json.dumps(dict(phase=number, label=label, mode=mode, valid=True,
                              worker_cpu_ms={key: round(value/1e6, 3) for key, value in report['aggregate']['worker'].items()})), flush=True)
    CURRENT['profile'] = None
    results = []
    for number, label in enumerate(main_order):
        assert shutil.disk_usage(output).free > 3_000_000_000 and psutil.virtual_memory().available > 3_000_000_000
        inputs = dict(native=native, bundle=bundle, runner=runners['baseline' if label == 'native' else label])
        row = probe.run_case(output/f'case{number}-{label}', output/'loader', number,
                             'native' if label == 'native' else 'default', inputs, 3, resource)
        validate_original(row)
        row['label'] = label
        probe.save(output/f'case{number}-{label}'/'verified.json', row)
        results.append(row)
        probe.save(output/'progress.json', results)
        cold, warm = row['phases'][0], row['phases'][1:]
        print(json.dumps(dict(case=number, label=label, cold_cpu=cold['ready_cpu'], cold_ready=cold['ready_seconds'],
                              parts=cold['ready_components'], worker_ms=cold['worker_log_cpu_lower_ms'],
                              warm_cpu=statistics.median(p['ready_cpu'] for p in warm), valid=True)), flush=True)
    assert all(probe.sha(item['path']) == item['sha256'] for item in identities)
    assert probe.sha(snapshot['path']) == snapshot['sha256']
    assert all(probe.sha(resource/name) == digest for name, digest in resources.items())
    workloads = [row['workload'] for row in phase_results] + results
    assert len({tuple(p['stdlib']) for row in workloads for p in row['phases']}) == 1
    probe.save(output/'verified.json', dict(phase_results=phase_results, rows=results,
        input_bytes_unchanged=True, resource_bytes_unchanged=True, snapshot_bytes_unchanged=True,
        baseline_reproduced_exactly=True, preflight_only=args.preflight_only, valid=True, qualification=False))


if __name__ == '__main__':
    main()
