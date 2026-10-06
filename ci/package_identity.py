#!/usr/bin/env python3
"""Write engine provenance and checksums after final binary stripping."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {'linux-x64', 'win32-x64', 'darwin-x64', 'darwin-arm64', 'linux-arm64'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--platform', choices=sorted(PLATFORMS), required=True)
    parser.add_argument('--checksums', type=Path, required=True)
    args = parser.parse_args()
    pin = dict(line.split(':', 1) for line in (ROOT / 'UPSTREAM').read_text().splitlines()
               if ':' in line and not line.startswith('#'))
    pin = {key.strip(): value.strip() for key, value in pin.items()}
    commit = pin.get('commit', '')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        parser.error('UPSTREAM must pin the resolved LLVM commit')
    base = pin['ref'].removeprefix('llvmorg-')
    if not re.fullmatch(re.escape(base) + r'-mcppls\.[0-9]+', args.version):
        parser.error('engine version must retain its maintained-engine identity')
    engine = args.directory / 'bin' / ('clangd.exe' if args.platform.startswith('win32-') else 'clangd')
    for path in (engine, args.directory / 'LICENSE.TXT', args.directory / 'NOTICE.txt',
                 args.directory / 'lib/clang' / base.split('.')[0] / 'include/stddef.h'):
        if not path.is_file():
            parser.error(f'missing required package file: {path}')
    version = subprocess.check_output([str(engine.resolve()), '--version'], text=True, timeout=20)
    if not re.search(r'clangd version ' + re.escape(args.version) + r'(?:\s|$)', version):
        parser.error(f'binary does not report expected identity: {version.strip()}')
    subprocess.run(['git', '-C', str(ROOT), 'diff', '--exit-code', 'HEAD', '--',
                    'UPSTREAM', 'patches', 'overlay', 'ci/scripts', 'ci/package_identity.py'], check=True,
                   stdout=subprocess.DEVNULL)
    fork = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    series = subprocess.check_output(['python3', str(ROOT / 'ci/series_identity.py')], text=True).strip()
    metadata = {'engine-version': args.version, 'llvm-base-version': base,
                'llvm-commit': commit, 'fork-commit': fork, 'patch-series-sha256': series,
                'platform': args.platform, 'sha256': sha(engine),
                'features': ['semantic-tokens-range']}
    (args.directory / 'engine.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # A sorted portable list; the output can never hash itself.
    entries = [f'{sha(path)}  ./{path.relative_to(args.checksums).as_posix()}'
               for path in sorted(args.checksums.rglob('*'))
               if path.is_file() and path != args.checksums / 'SHA256SUMS']
    (args.checksums / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')


if __name__ == '__main__':
    main()
