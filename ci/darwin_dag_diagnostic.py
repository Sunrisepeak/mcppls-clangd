#!/usr/bin/env python3
"""Immutable native DAG shutdown A/B; no engine builds and no deadline changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True, timeout=10).strip()


def native_identity():
    sdk = Path(command('xcrun', '--show-sdk-path'))
    return {'machine': platform.machine(), 'sdk_path': str(sdk),
            'sdk_version': command('xcrun', '--show-sdk-version'),
            'sdk_settings_sha256': digest(sdk / 'SDKSettings.json'),
            'xcode': command('xcodebuild', '-version'), 'os': command('sw_vers'),
            'runner_image': os.environ.get('ImageVersion'),
            'runner_image_os': os.environ.get('ImageOS')}


def bundle(build, output):
    if sys.platform != 'darwin' or platform.machine() != 'x86_64':
        raise ValueError('requires native Intel Darwin')
    package = output / 'payload'
    (package / 'bin').mkdir(parents=True)
    for name in ('clangd', 'clang'):
        shutil.copy2(build / 'bin' / name, package / 'bin' / name)
    (package / 'bin/clang++').symlink_to('clang')
    shutil.copytree(build / 'lib/clang', package / 'lib/clang')
    shutil.copy2(build / 'engine-build.json', package / 'engine-build.json')
    stamp = json.loads((package / 'engine-build.json').read_text())
    built_checkout = command('git', '-C', str(ROOT), 'rev-parse', 'HEAD')
    if (stamp['platform'] != 'darwin-x64' or
            stamp['fork-commit'] != built_checkout or
            stamp['build-binary-sha256'] != digest(package / 'bin/clangd')):
        raise ValueError('same-build engine marker does not match uploaded bytes/source')
    hashes = {str(p.relative_to(package)): digest(p) for p in package.rglob('*') if p.is_file()}
    identity = {'run_id': os.environ['GITHUB_RUN_ID'], 'built_checkout_sha': built_checkout,
                'workflow_head_sha': os.environ['WORKFLOW_HEAD_SHA'],
                'repository': os.environ['GITHUB_REPOSITORY'], 'native': native_identity(),
                'engine_version': command(str(package / 'bin/clangd'), '--version'),
                'compiler_version': command(str(package / 'bin/clang'), '--version'),
                'compiler_source_path': str((build / 'bin/clang').resolve()),
                'file_sha256': hashes,
                'scope': 'Same-build engine/driver at built_checkout_sha; PR workflow head can differ. Not the earlier failed-run payload.'}
    (package / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    with tarfile.open(output / 'darwin-dag-payload.tar.gz', 'w:gz', dereference=False) as archive:
        archive.add(package, arcname='payload')


def run_ab(package, output, run_id, workflow_head_sha):
    output.mkdir(parents=True)
    identity = json.loads((package / 'identity.json').read_text())
    if identity['run_id'] != run_id or identity['workflow_head_sha'] != workflow_head_sha:
        raise ValueError('artifact run/workflow-head identity mismatch')
    if identity['repository'] != os.environ['GITHUB_REPOSITORY']:
        raise ValueError('artifact repository mismatch')
    current = native_identity()
    (output / 'identity.json').write_text(json.dumps({'artifact': identity, 'current': current}, indent=2) + '\n')
    for key in ('machine', 'sdk_path', 'sdk_version', 'sdk_settings_sha256', 'xcode'):
        if current[key] != identity['native'][key]:
            raise ValueError('native compiler/SDK context mismatch: ' + key)
    for name, expected in identity['file_sha256'].items():
        if digest(package / name) != expected:
            raise ValueError('artifact byte mismatch: ' + name)
    stamp = json.loads((package / 'engine-build.json').read_text())
    if (stamp['fork-commit'] != identity['built_checkout_sha'] or
            stamp['build-binary-sha256'] != digest(package / 'bin/clangd') or
            stamp['platform'] != 'darwin-x64'):
        raise ValueError('built-checkout/engine marker mismatch')
    if (package / 'bin/clang++').readlink() != Path('clang'):
        raise ValueError('compiler alias mismatch')
    results = []
    inputs = []
    for policy in ('default', 'stdlib-disabled'):
        work = output / 'work'
        args = [sys.executable, str(ROOT / 'tests/e2e/module_dag.py'),
                '--engine', str(package / 'bin/clangd'), '--clang', str(package / 'bin/clang'),
                '--workdir', str(work), '--case', 'wide-1', '--darwin-timeout-sample']
        if policy == 'stdlib-disabled':
            args.append('--disable-standard-library')
        with (output / (policy + '.log')).open('wb') as log:
            completed = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT, timeout=60)
        case = work / 'wide-1'
        facts = {p.name: digest(p) for p in case.iterdir() if p.suffix in ('.cpp', '.cppm') or p.name == 'compile_commands.json'}
        inputs.append(facts)
        manifest = json.loads((case / 'case.json').read_text())
        result = json.loads((case / 'replay-result.json').read_text())
        results.append({'policy': policy, 'runner_exit_code': completed.returncode,
                        'outcome': result['outcome'], 'inputs': facts,
                        'flags': manifest['flags'], 'timeout_seconds': manifest['timeout_seconds'],
                        'project_config': (case / '.clangd').read_text() if (case / '.clangd').exists() else None})
        work.rename(output / policy)
    same = inputs[0] == inputs[1] and results[0]['flags'] == results[1]['flags']
    report = {'same_input_bytes_and_flags': same, 'results': results,
              'limits': ['One cold wide/1 per policy; diagnostic only, not a performance distribution.',
                         'Original 30s timeout, semantic/worker assertions and forced-kill failure retained.',
                         'Matching compiler bytes and SDK/Xcode; recorded OS/runner image fields are not equality requirements.',
                         'Only control .clangd Index.StandardLibrary differs; SDK equality checked above.']}
    (output / 'ab-result.json').write_text(json.dumps(report, indent=2) + '\n')
    if not same or any(r['runner_exit_code'] != 0 for r in results):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['bundle', 'ab'])
    parser.add_argument('--build', type=Path)
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--workflow-head-sha')
    args = parser.parse_args()
    if args.action == 'bundle':
        bundle(args.build.resolve(), args.output.resolve())
    else:
        run_ab(args.payload.resolve(), args.output.resolve(), args.run_id, args.workflow_head_sha)


if __name__ == '__main__':
    main()
