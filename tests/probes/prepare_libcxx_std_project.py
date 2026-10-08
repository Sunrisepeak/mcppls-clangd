#!/usr/bin/env python3
"""Prepare a native Clang/libc++ std project with actual compiler insertion inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    compiler, kit, out = args.compiler.resolve(), args.kit.resolve(), args.output.resolve()
    if out.exists():
        parser.error('output must be new; prior evidence is never overwritten')
    manifest = json.loads((kit / 'kit.json').read_text())
    metadata_path = kit / manifest['stdlib']['module-metadata']
    metadata = json.loads(metadata_path.read_text())
    std = next(m for m in metadata['modules'] if m['logical-name'] == 'std')
    provider = (metadata_path.parent / std['source-path']).resolve()
    if not provider.is_file() or not compiler.is_file():
        parser.error('compiler and std producer must exist')
    out.mkdir(parents=True)
    native = out / 'native'; native.mkdir()
    source = out / 'Use.cpp'
    source.write_text('import std;\nvoid probe() {\n    std::vector<int> stable;\n}\n')
    common = ['--no-default-config', '-std=c++23', '-stdlib=libc++', '-nostdinc++',
              '--sysroot=' + str(kit / 'sysroot')]
    for path in manifest['system-include-directories']:
        common += ['-isystem', str(kit / path)]
    for path in std.get('local-arguments', {}).get('system-include-directories', []):
        common += ['-isystem', str((metadata_path.parent / path).resolve())]
    pcm = native / 'std.pcm'
    producer_args = [str(compiler), *common, '--precompile', str(provider), '-o', str(pcm)]
    importer_args = [str(compiler), *common, '-fmodule-file=std=' + str(pcm),
                     '-c', str(source), '-o', str(native / 'Use.o')]
    entries = [{'directory': str(out), 'file': str(provider), 'arguments': producer_args},
               {'directory': str(out), 'file': str(source), 'arguments': importer_args}]
    cdb = out / 'compile_commands.json'; cdb.write_text(json.dumps(entries, indent=2) + '\n')
    context = {'name': 'native-libcxx-std-qualified', 'before': '    std::vector<int> stable;',
               'prefix': '    std::ve', 'suffix': ' probe_vector;\n', 'expected': ['vector'],
               'kind': {'vector': 7}, 'bindings': {'vector': {'1': 'int', '2': 'std::allocator<int>'}},
               'require_sema': True, 'limit_ms': 200}
    (out / 'context.json').write_text(json.dumps(context, indent=2) + '\n')
    report = {'scope': 'Separate native Clang/libc++ project; not a replacement for GNU Qt '
              'qualification. The native producer/importer are actually compiled; engine '
              'semantics and matched performance still require separate runs.',
              'compiler_sha256': digest(compiler), 'provider_sha256': digest(provider),
              'source_sha256': digest(source), 'cdb_sha256': digest(cdb), 'stages': {}}
    for name, command in [('producer', producer_args), ('importer', importer_args)]:
        with (out / (name + '.log')).open('w') as log:
            result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=90)
        report['stages'][name] = {'command': command, 'exit_code': result.returncode}
        (out / 'identity.json').write_text(json.dumps(report, indent=2) + '\n')
        print(name, result.returncode, flush=True)
        if result.returncode:
            return result.returncode
    report['native_std_pcm_sha256'] = digest(pcm)
    (out / 'identity.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
