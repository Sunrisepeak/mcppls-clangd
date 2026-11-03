#!/usr/bin/env python3
"""Diagnostic first-chance capture; results do not qualify release acceptance."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run_case(args, image, mode, replay):
    output = args.output.resolve() / (image.suffix[1:] + '-' + mode + '-lsp')
    output.mkdir(parents=True)
    environment = os.environ.copy()
    for key in tuple(os.environ):
        if key.startswith('OKRUN_') or key in ('GH_TOKEN', 'GITHUB_TOKEN'):
            os.environ.pop(key)
    for key in ('LOCALAPPDATA', 'XDG_RUNTIME_DIR', 'OKRUN_CACHE', 'TEMP', 'TMP'):
        directory = output / key.lower()
        directory.mkdir()
        os.environ[key] = str(directory)
    if mode != 'default':
        os.environ['OKRUN_SNAPSHOT'] = '0'
    if mode == 'no-placement':
        os.environ['OKRUN_PLACE'] = '0'
    project = output / 'project'
    project.mkdir()
    (project / 'probe.cpp').write_text('int probe() { return 42; }\n')
    manifest = output / 'case.json'
    manifest.write_text(json.dumps(dict(id=output.name, platform='win32-x64', project='project',
        baseline='pass', timeout_seconds=90, flags=[str(image), '--background-index=false', '-j=2'],
        sequence=[dict(method='initialize', params=dict(rootUri='${PROJECT_URI}', capabilities={})),
                  dict(method='initialized', notify=True, params={}),
                  dict(method='textDocument/didOpen', notify=True, params=dict(textDocument=dict(
                      uri='${PROJECT_URI}/probe.cpp', languageId='cpp', version=1,
                      text='int probe() { return 42; }\n'))),
                  dict(method='textDocument/documentSymbol', params=dict(textDocument=dict(
                      uri='${PROJECT_URI}/probe.cpp')), expect={'/result/0/name': 'probe'})]), indent=2))
    dump, log = output / 'first-chance.dmp', output / 'cdb.log'
    commands = output / 'attach.cdb'
    capture = ('.echo MCPPLS_OPENKAL_FIRST_CHANCE; .lastevent; .exr -1; .ecxr; r; kv; '
               '!address @rip; .dump /m /o ' + dump.as_posix() + '; gn')
    commands.write_text('sxe -c "' + capture + '" av\n.echo MCPPLS_CDB_ATTACHED\ngh\n')
    debugger = None
    forced = False
    with (output / 'debugger-console.log').open('wb') as console:
        def attach(proc, deadline):
            nonlocal debugger
            debugger = subprocess.Popen([str(args.cdb), '-p', str(proc.pid), '-G',
                '-logo', str(log), '-cf', str(commands)], stdin=subprocess.DEVNULL,
                stdout=console, stderr=subprocess.STDOUT)
            while time.monotonic() < deadline:
                text = log.read_text(errors='replace') if log.exists() else ''
                if re.search(r'^\s*MCPPLS_CDB_ATTACHED\s*$', text, re.M):
                    return
                if debugger.poll() is not None:
                    raise RuntimeError('CDB exited before attach: ' + str(debugger.returncode))
                time.sleep(0.05)
            raise subprocess.TimeoutExpired('debugger attach', 90)
        try:
            result = replay.replay(args.runner.resolve(), manifest, process_started=attach)
        except Exception as error:
            result = {'outcome': 'error', 'detail': repr(error)}
        finally:
            if debugger is not None:
                try:
                    debugger.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    forced = True
                    debugger.kill()
                    debugger.wait(timeout=10)
            os.environ.clear()
            os.environ.update(environment)
    text = log.read_text(errors='replace') if log.exists() else ''
    result.update(diagnostic_only=True, image_sha256=digest(image),
                  runner_sha256=digest(args.runner), debugger_forced_termination=forced,
                  first_chance_captured=bool(re.search(r'^\s*MCPPLS_OPENKAL_FIRST_CHANCE\s*$', text, re.M)),
                  minidump_bytes=dump.stat().st_size if dump.exists() else 0,
                  version_reported=bool(re.search(r'^clangd version 23\.1\.0-mcppls\.9\s*$',
                      (output / 'debugger-console.log').read_text(errors='replace'), re.M)))
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('stderr', 'raw_responses')}))
    return result


def launch_capture(args, image, mode):
    """Start under the debugger: attachment cannot observe this early crash."""
    output = args.output.resolve() / (image.suffix[1:] + '-' + mode)
    output.mkdir(parents=True)
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith('OKRUN_') or key in ('GH_TOKEN', 'GITHUB_TOKEN'):
            environment.pop(key)
    for key in ('LOCALAPPDATA', 'XDG_RUNTIME_DIR', 'OKRUN_CACHE', 'TEMP', 'TMP'):
        directory = output / key.lower()
        directory.mkdir()
        environment[key] = str(directory)
    if mode != 'default':
        environment['OKRUN_SNAPSHOT'] = '0'
    if mode == 'no-placement':
        environment['OKRUN_PLACE'] = '0'
    dump, log = output / 'first-chance.dmp', output / 'cdb.log'
    commands = output / 'launch.cdb'
    capture = ('.echo MCPPLS_OPENKAL_FIRST_CHANCE; .lastevent; .exr -1; .ecxr; r; '
               'kv; u @rip-20 L30; !address @rip; !address @rdi; !address @rsi; '
               '!address @rdx; .dump /m /o ' + dump.as_posix() + '; gn')
    commands.write_text('sxe -c "' + capture + '" av\n.echo MCPPLS_CDB_LAUNCHED\ng\n')
    started = time.monotonic()
    forced = False
    with (output / 'debugger-console.log').open('wb') as console:
        debugger = subprocess.Popen([str(args.cdb), '-G', '-logo', str(log),
            '-cf', str(commands), str(args.runner.resolve()), str(image), '--version'],
            env=environment, stdin=subprocess.DEVNULL, stdout=console, stderr=subprocess.STDOUT)
        try:
            debugger.wait(timeout=90)
        except subprocess.TimeoutExpired:
            forced = True
            subprocess.run(['taskkill', '/PID', str(debugger.pid), '/T', '/F'],
                           capture_output=True, timeout=15)
            debugger.wait(timeout=15)
    text = log.read_text(errors='replace') if log.exists() else ''
    result = dict(id=output.name, diagnostic_only=True, protocol='--version under CDB from creation',
                  elapsed_seconds=time.monotonic()-started, debugger_exit_code=debugger.returncode,
                  image_sha256=digest(image), runner_sha256=digest(args.runner),
                  debugger_forced_termination=forced,
                  first_chance_captured=bool(re.search(r'^\s*MCPPLS_OPENKAL_FIRST_CHANCE\s*$', text, re.M)),
                  minidump_bytes=dump.stat().st_size if dump.exists() else 0,
                  version_reported=bool(re.search(r'^clangd version 23\.1\.0-mcppls\.9\s*$',
                      (output / 'debugger-console.log').read_text(errors='replace'), re.M)))
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runner', 'cdb', 'raw', 'bundle', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('requires native Windows')
    args.output.mkdir(parents=True)
    shutil.copy2(args.runner, args.output / 'okrun.exe')
    for pdb in args.runner.parent.glob('*.pdb'):
        shutil.copy2(pdb, args.output / pdb.name)
    spec = importlib.util.spec_from_file_location('replay', Path(__file__).resolve().parents[1] / 'tests/crash/replay.py')
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    results = [launch_capture(args, image.resolve(), mode)
               for image in (args.raw, args.bundle)
               for mode in ('default', 'no-snapshot', 'no-placement')]
    versions_pass = all(r['debugger_exit_code'] == 0 and r.get('version_reported')
                        and not r['first_chance_captured'] for r in results)
    semantic = [run_case(args, image.resolve(), mode, replay)
                for image in (args.raw, args.bundle)
                for mode in ('default', 'no-snapshot', 'no-placement')]
    status = dict(candidate_runner_source=os.environ.get('RUNNER_SOURCE_HEAD'),
                  versions=results, semantic=semantic,
                  accepted=versions_pass and all(r['outcome'] == 'pass' for r in semantic),
                  scope='Candidate loader correction against unchanged old engine artifacts; final published qualification pending')
    (args.output / 'summary.json').write_text(json.dumps(status, indent=2) + '\n')
    return 0 if status['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
