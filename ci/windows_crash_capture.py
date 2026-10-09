#!/usr/bin/env python3
"""Capture an actual historical Windows crash with the matching upstream PDB."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
import zipfile

import windows_symbols

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('crash_replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

RELEASE = 'https://github.com/clangd/clangd/releases/download/23.1.0/'
ENGINE_ARCHIVE = 'clangd-windows-23.1.0.zip'
ENGINE_ARCHIVE_SHA = '23412a240756a162e7b98a282f36aa2a23a88db5ce16a0cbc4fef7253768c810'
ENGINE_SHA = 'dbd52c13d21ef9d284f4f0627efe76c81adf2fe0998f230127f554a54fc9dde7'
PDB_ARCHIVE = 'clangd-debug-symbols-windows-23.1.0.7z'
PDB_ARCHIVE_SHA = '63ed86924ee2300448555319c32cd0dbb75f223dc91441351f58f688f32ecfd4'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(directory, name, expected):
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / name
    if not archive.exists():
        partial = archive.with_suffix(archive.suffix + '.partial')
        try:
            with urllib.request.urlopen(RELEASE + name, timeout=120) as source, partial.open('wb') as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
            if digest(partial) != expected:
                raise ValueError(f'{name}: upstream archive digest mismatch')
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    if digest(archive) != expected:
        raise ValueError(f'{name}: cached upstream archive digest mismatch')
    return archive


def stock_pair(directory, sevenzip):
    archive = download(directory, ENGINE_ARCHIVE, ENGINE_ARCHIVE_SHA)
    with zipfile.ZipFile(archive) as files:
        files.extractall(directory / 'engine')
    symbols = download(directory, PDB_ARCHIVE, PDB_ARCHIVE_SHA)
    subprocess.run([str(sevenzip), 'x', str(symbols), '-o' + str(directory / 'pdb'), '-y'],
                   check=True, timeout=120, stdout=subprocess.DEVNULL)
    engines = list((directory / 'engine').rglob('clangd.exe'))
    pdbs = list((directory / 'pdb').rglob('clangd.pdb'))
    if len(engines) != 1 or len(pdbs) != 1:
        raise ValueError('upstream assets must supply exactly one clangd executable and linked PDB')
    if digest(engines[0]) != ENGINE_SHA:
        raise ValueError('upstream executable digest differs from the qualified historical baseline')
    return engines[0].resolve(), pdbs[0].resolve()


def debugger_script(dump):
    # Nested exception-command quoting cannot accept arbitrary debugger syntax.
    # The fast workflow uses a workspace path without whitespace; fail before
    # attaching if a caller supplies an incompatible path.
    # CDB unescapes backslashes inside the quoted exception command. Forward
    # slashes preserve the absolute Windows path through that extra parsing.
    path = dump.resolve().as_posix()
    if re.search(r'[\s;"\r\n]', path):
        raise ValueError('the debugger dump path must contain no whitespace, quotes or semicolons')
    capture = ('.echo MCPPLS_SECOND_CHANCE; .lastevent; .exr -1; .ecxr; '
               f'kv; ~* kb; .dump /m /o {path}; gn')
    return ('!sym noisy\n.lines -e\n.reload /f clangd.exe\n'
            # The attach breakpoint is handled explicitly by gh below. Later
            # breakpoint exceptions are not handled and reach second chance.
            'sxd -h bpe\n'
            f'sxd -c2 "{capture}" bpe\n'
            f'sxd -c2 "{capture}" av\n'
            'sx\n.echo MCPPLS_CDB_ATTACHED\ngh\n')


def evidence(result, log, dump, debugger_forced):
    second = bool(re.search(r'^\s*MCPPLS_SECOND_CHANCE\s*$', log, re.M))
    codes = re.findall(r'ExceptionCode:\s*([0-9a-fA-F]{8})\b', log)
    code = int(result.get('exit_code') or 0) & 0xffffffff
    # Only executed stack rows count. Echoed debugger commands and symbol
    # lookup text elsewhere in the log cannot stand in for a crash frame.
    symbols = re.findall(r'^\s*[0-9a-fA-F`]+(?:\s+[0-9a-fA-F`]+)?\s+:\s+'
                         r'(?:[0-9a-fA-F`]+\s+){4}:\s+clangd!([^\r\n]+)', log, re.M)
    source_lines = [list(match) for frame in symbols for match in re.findall(
        r'\[([^\]\r\n]+\.(?:cpp|cc|cxx|h|hpp))\s+@\s+(\d+)\]', frame)]
    dump_ok = dump.is_file() and dump.stat().st_size > 4
    if dump_ok:
        with dump.open('rb') as stream:
            dump_ok = stream.read(4) == b'MDMP'
    captured = (result['outcome'] == 'crash' and code == 0x80000003
                and '80000003' in [value.lower() for value in codes]
                and second and bool(symbols) and bool(source_lines) and dump_ok and not debugger_forced
                and result.get('readers_stopped') is True)
    return {'captured': captured, 'natural_exit_hex': f'0x{code:08x}',
            'second_chance_handler_executed': second, 'exception_codes': codes,
            'symbolized_frames': sorted(set(symbols)), 'minidump_valid': dump_ok,
            'source_lines': source_lines,
            'debugger_forced_termination': debugger_forced}


def capture(args, engine, pdb):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    symbols = windows_symbols.identity(engine, pdb, args.readobj, args.pdbutil)
    symbols['files'] = {engine.name: digest(engine), pdb.name: digest(pdb)}
    lookup = windows_symbols.run([str(args.cdb), '-y', str(pdb.parent), '-c',
        '.reload /f clangd.exe; x clangd!*clangdMain*; q', str(engine), '--version'])
    (output / 'symbol-lookup.log').write_text(lookup)
    if not re.search(r'^[0-9a-fA-F`]+\s+clangd!.*clangdMain', lookup, re.M):
        raise ValueError('CDB cannot resolve clangdMain from the GUID/age matched upstream PDB')
    symbols['symbol_lookup'] = 'clangdMain'
    symbols['upstream_assets'] = {ENGINE_ARCHIVE: ENGINE_ARCHIVE_SHA,
                                 PDB_ARCHIVE: PDB_ARCHIVE_SHA}
    (output / 'symbols.json').write_text(json.dumps(symbols, indent=2) + '\n')

    dump, log = output / 'second-chance.dmp', output / 'cdb.log'
    for path in (dump, log):
        path.unlink(missing_ok=True)
    commands = output / 'attach.cdb'
    commands.write_text(debugger_script(dump))
    debugger = None
    forced = False
    with (output / 'debugger-console.log').open('wb') as console:
        def attach(proc, deadline):
            nonlocal debugger
            debugger = subprocess.Popen([str(args.cdb), '-p', str(proc.pid), '-G',
                '-y', str(pdb.parent), '-logo', str(log), '-cf', str(commands)],
                stdin=subprocess.DEVNULL, stdout=console, stderr=subprocess.STDOUT)
            while time.monotonic() < deadline:
                text = log.read_text(errors='replace') if log.exists() else ''
                if re.search(r'^\s*MCPPLS_CDB_ATTACHED\s*$', text, re.M):
                    return
                if debugger.poll() is not None:
                    raise RuntimeError(f'CDB exited before attach readiness: {debugger.returncode}')
                time.sleep(0.05)
            raise subprocess.TimeoutExpired('debugger attach', 0)

        try:
            result = replay.replay(engine, args.case.resolve(), process_started=attach)
        finally:
            if debugger is not None:
                try:
                    debugger.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    forced = True
                    debugger.kill()
                    debugger.wait(timeout=5)
    text = log.read_text(errors='replace') if log.exists() else ''
    status = evidence(result, text, dump, forced)
    status.update(actual_host=replay.platform_name(),
                  scope='historical stock Windows baseline; no fork/native-fixed claim',
                  engine_sha256=digest(engine), replay=result,
                  debugger_exit_code=debugger.returncode if debugger else None)
    (output / 'capture.json').write_text(json.dumps(status, indent=2) + '\n')
    return status['captured']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-directory', type=Path, required=True)
    for name in ('sevenzip', 'cdb', 'readobj', 'pdbutil', 'case', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('historical Windows debugger capture must execute on Windows')
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        engine, pdb = stock_pair(args.stock_directory.resolve(), args.sevenzip)
        return 0 if capture(args, engine, pdb) else 1
    except Exception as error:
        (args.output / 'capture-error.json').write_text(json.dumps({'captured': False,
            'detail': str(error), 'scope': 'setup failed; no crash evidence'}) + '\n')
        raise


if __name__ == '__main__':
    sys.exit(main())
