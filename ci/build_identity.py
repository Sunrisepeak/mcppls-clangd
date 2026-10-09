#!/usr/bin/env python3
"""Record the input identity and unstripped engine bytes after a real build."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir', type=Path, required=True)
parser.add_argument('--llvm-dir', type=Path, required=True)
parser.add_argument('--platform', required=True)
args = parser.parse_args()
series = subprocess.check_output(['python3', str(ROOT / 'ci/series_identity.py')], text=True).strip()
if (args.llvm_dir / '.mcppls-clangd-patched').read_text().strip() != series:
    parser.error('build source marker does not match the ordered patch series')
subprocess.run(['git', '-C', str(args.llvm_dir), 'diff', '--quiet', 'HEAD'], check=True)
engine = args.build_dir / 'bin' / ('clangd.exe' if args.platform.startswith('win32-') else 'clangd')
digest = hashlib.sha256()
with engine.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1048576), b''):
        digest.update(chunk)
metadata = {'fork-commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
            'llvm-tree-commit': subprocess.check_output(['git', '-C', str(args.llvm_dir), 'rev-parse', 'HEAD'], text=True).strip(),
            'patch-series-sha256': series, 'platform': args.platform, 'build-binary-sha256': digest.hexdigest(),
            'cmake-cache-sha256': hashlib.sha256((args.build_dir / 'CMakeCache.txt').read_bytes()).hexdigest()}
(args.build_dir / 'engine-build.json').write_text(json.dumps(metadata, indent=2) + '\n')
