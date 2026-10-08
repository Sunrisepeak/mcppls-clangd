#!/usr/bin/env python3
"""Write engine provenance and checksums after final binary stripping."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {'linux-x64', 'win32-x64', 'darwin-arm64'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_build_source(llvm_dir, build_dir, stamp, series):
    """Bind capability inputs to the clean source actually configured and built."""
    source = llvm_dir.resolve()
    marker = source / '.mcppls-clangd-patched'
    if not marker.is_file() or marker.read_text().strip() != series:
        raise ValueError('package source marker does not match the ordered patch series')
    cache = (build_dir / 'CMakeCache.txt').read_text()
    home = re.search(r'^CMAKE_HOME_DIRECTORY:INTERNAL=(.*)$', cache, re.M)
    if not home or Path(home.group(1).strip()).resolve() != source / 'llvm':
        raise ValueError('package source is not the CMake build source')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if stamp.get('llvm-tree-commit') != head:
        raise ValueError('package source commit differs from the built source stamp')
    subprocess.run(['git', '-C', str(source), 'diff', '--quiet', 'HEAD'], check=True)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--llvm-dir', type=Path, required=True)
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
    base = pin['ref'][len('llvmorg-'):] if pin['ref'].startswith('llvmorg-') else pin['ref']
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
                    'UPSTREAM', 'patches', 'overlay', 'ci/scripts', 'ci/package_identity.py',
                    'tests/e2e/module_directive_diagnostics.py'], check=True,
                   stdout=subprocess.DEVNULL)
    fork = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    series = subprocess.check_output(['python3', str(ROOT / 'ci/series_identity.py')], text=True).strip()
    stamp = json.loads((args.build_dir / 'engine-build.json').read_text())
    original = args.build_dir / 'bin' / engine.name
    if (stamp.get('fork-commit') != fork or stamp.get('platform') != args.platform or
            stamp.get('patch-series-sha256') != series or
            stamp.get('build-binary-sha256') != sha(original) or
            stamp.get('cmake-cache-sha256') != sha(args.build_dir / 'CMakeCache.txt')):
        parser.error('build stamp does not identify this source, platform, configuration and binary')
    try:
        source = verify_build_source(args.llvm_dir, args.build_dir, stamp, series)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error(str(error))
    # Prove the declared capability against the final stripped package bytes.
    canary = source / 'clang-tools-extra/clangd/test/semantic-tokens-range.test'
    response = subprocess.run([str(engine.resolve()), '-lit-test'], input=canary.read_text(),
                              text=True, capture_output=True, timeout=20)
    data = re.search(r'"id":\s*1,.*?"data":\s*(\[.*?\])', response.stdout, re.S)
    if response.returncode != 0 or not data or json.loads(data.group(1)) != [1, 4, 1, 0, 131075, 1, 4, 1, 0, 131075]:
        parser.error('final package bytes failed semantic-tokens-range capability canary')
    format_canary = source / 'clang-tools-extra/clangd/test/mcpp-format-fallback.test'
    formatted = subprocess.run([str(engine.resolve()), '-lit-test', '-fallback-style=mcpp'],
                               input=format_canary.read_text(), text=True,
                               capture_output=True, timeout=20)
    if (formatted.returncode != 0 or not re.search(
            r'"id":\s*1,.*?"result":\s*\[\s*\]', formatted.stdout, re.S)):
        parser.error('final package bytes failed mcpp formatting fallback canary')
    directive_report = args.build_dir / 'module-directive-package-canary.json'
    directive = subprocess.run([
        'python3', str(ROOT / 'tests/e2e/module_directive_diagnostics.py'),
        '--engine', str(engine.resolve()), '--output', str(directive_report.resolve())],
        text=True, capture_output=True, timeout=30)
    if directive.returncode != 0:
        parser.error('final package bytes failed module directive diagnostic range canary: '
                     + directive.stderr.strip())
    verified_directive = json.loads(directive_report.read_text())
    if (verified_directive.get('outcome') != 'pass' or
            verified_directive.get('engine_sha256') != sha(engine)):
        parser.error('module directive canary does not identify the final package binary')
    metadata = {'engine-version': args.version, 'llvm-base-version': base,
                'llvm-commit': commit, 'fork-commit': fork, 'patch-series-sha256': series,
                'platform': args.platform, 'sha256': sha(engine),
                'features': ['semantic-tokens-range', 'format-style-mcpp',
                             'module-directive-diagnostic-ranges'],
                'build-binary-sha256': stamp['build-binary-sha256'],
                'llvm-tree-commit': stamp['llvm-tree-commit'],
                'cmake-cache-sha256': stamp['cmake-cache-sha256']}
    (args.directory / 'engine.json').write_text(json.dumps(metadata, indent=2) + '\n')
    # A sorted portable list; the output can never hash itself.
    entries = [f'{sha(path)}  ./{path.relative_to(args.checksums).as_posix()}'
               for path in sorted(args.checksums.rglob('*'))
               if path.is_file() and path != args.checksums / 'SHA256SUMS']
    (args.checksums / 'SHA256SUMS').write_text('\n'.join(entries) + '\n')


if __name__ == '__main__':
    main()
