#!/usr/bin/env python3
"""Verify Linux x64 engine bytes on the promised glibc 2.31 floor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('engine', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
engine = args.engine.resolve()
problems = []
abi = subprocess.check_output(['readelf', '--version-info', str(engine)], text=True)
headers = subprocess.check_output(['readelf', '-l', str(engine)], text=True)
loader = re.search(r'Requesting program interpreter: (.*?)\]', headers)
if not loader or not loader.group(1).startswith('/lib') or not Path(loader.group(1)).is_file():
    problems.append('ELF interpreter is not a system loader available on the floor')
versions = [tuple(map(int, v.split('.'))) for v in re.findall(r'\bGLIBC_([0-9.]+)', abi)]
if versions and max(versions) > (2, 31):
    problems.append('GLIBC requirement exceeds 2.31')
if 'GLIBCXX_' in abi:
    problems.append('engine still depends on dynamic libstdc++')
runtime = os.confstr('CS_GNU_LIBC_VERSION')
if runtime != 'glibc 2.31':
    problems.append(f'runtime is {runtime}, not the actual glibc 2.31 floor')
linked = subprocess.run(['ldd', str(engine)], capture_output=True, text=True, timeout=20)
if linked.returncode or 'not found' in linked.stdout or '/home/' in linked.stdout:
    problems.append('runtime dependencies are unresolved or reference a development home')
started = subprocess.run([str(engine), '--version'], capture_output=True, text=True, timeout=20)
if started.returncode or 'clangd version' not in started.stdout:
    problems.append('engine does not start on the floor')
args.output.write_text(json.dumps({'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
                                  'runtime': runtime, 'interpreter': loader.group(1) if loader else None,
                                  'max_glibc': list(max(versions)) if versions else None,
                                  'dependencies': linked.stdout, 'version': started.stdout,
                                  'problems': problems}, indent=2) + '\n')
if problems:
    parser.error('; '.join(problems))
