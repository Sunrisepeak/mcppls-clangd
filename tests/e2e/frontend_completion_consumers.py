#!/usr/bin/env python3
"""Exercise default completion consumers with textual and serialized names."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile


def executable(path):
    path = path.resolve()
    if os.name == 'nt' and not path.suffix:
        path = path.with_suffix('.exe')
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def run(work, name, argv, stdin=None):
    stdout, stderr = work / (name + '.stdout'), work / (name + '.stderr')
    timed_out = False
    with stdout.open('wb') as out, stderr.open('wb') as err:
        process = subprocess.Popen(argv, cwd=work, stdin=subprocess.PIPE,
                                   stdout=out, stderr=err,
                                   start_new_session=os.name != 'nt')
        try:
            process.communicate(stdin, timeout=45)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, timeout=15, check=True)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=15)
    if stdout.stat().st_size > 2 * 1048576 or stderr.stat().st_size > 2 * 1048576:
        raise RuntimeError('unexpectedly large consumer output')
    row = {'argv': list(map(str, argv)), 'exit_code': process.returncode,
           'timed_out': timed_out, 'stdout_sha256': digest(stdout),
           'stderr_sha256': digest(stderr)}
    return row, stdout.read_text(errors='replace'), stderr.read_text(errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--c-index-test', type=Path, required=True)
    parser.add_argument('--clang-repl', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    clang, index, repl = map(executable, [args.clang, args.c_index_test, args.clang_repl])
    work = args.workdir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix='consumers-', dir=work))
    header, source = project / 'API.h', project / 'Use.cpp'
    header.write_text('namespace api {\nint vector(int count);\n'
                      'int vector(double amount);\nint version();\nint ordinary;\n}\n')
    text = 'void probe() { api::ve; }\n'
    source.write_text(text)
    location = str(source) + ':1:' + str(text.index('ve') + len('ve') + 1)
    report = {'passed': False, 'scope': 'CLI/CIndex default completion consumer parity '
              'for text/PCH, two overloads and a second name; interpreter declaration '
              'execution smoke, not interactive completion or performance qualification.',
              'tool_sha256': {str(p): digest(p) for p in [clang, index, repl]},
              'project': str(project), 'stages': {}, 'parity': {}}
    try:
        pch = project / 'API.pch'
        row, out, err = run(project, 'clang-build-pch', [str(clang), '-x', 'c++-header',
                         '-std=c++20', str(header), '-o', str(pch)])
        report['stages']['clang-build-pch'] = row
        if row['exit_code'] or row['timed_out'] or not pch.is_file():
            raise RuntimeError('CLI failed to produce PCH')
        outputs = {}
        for mode, include in [('text', ['-include', str(header)]),
                              ('pch', ['-include-pch', str(pch)])]:
            row, out, err = run(project, 'clang-' + mode, [str(clang), '-std=c++20',
                '-fsyntax-only', *include, '-Xclang', '-code-completion-at=' + location,
                str(source)])
            report['stages']['clang-' + mode] = row
            if row['exit_code'] or row['timed_out']:
                raise RuntimeError('CLI completion failed')
            outputs[mode] = sorted(x for x in out.splitlines() if x.startswith('COMPLETION:'))
            if sum(x.startswith('COMPLETION: vector :') for x in outputs[mode]) != 2:
                raise RuntimeError('CLI lost vector overloads')
            if not any(x.startswith('COMPLETION: version :') for x in outputs[mode]):
                raise RuntimeError('CLI lost version')
        report['parity']['clang'] = outputs
        if outputs['text'] != outputs['pch']:
            raise RuntimeError('CLI text/PCH completion differs')
        index_pch = project / 'API-index.pch'
        row, out, err = run(project, 'index-build-pch', [str(index), '-write-pch',
                           str(index_pch), '-x', 'c++-header', '-std=c++20', str(header)])
        report['stages']['index-build-pch'] = row
        if row['exit_code'] or row['timed_out'] or not index_pch.is_file():
            raise RuntimeError('CIndex failed to produce PCH')
        outputs = {}
        for mode, include in [('text', ['-include', str(header)]),
                              ('pch', ['-include-pch', str(index_pch)])]:
            row, out, err = run(project, 'index-' + mode, [str(index),
                '-code-completion-at=' + location, '-std=c++20', *include, str(source)])
            report['stages']['index-' + mode] = row
            if row['exit_code'] or row['timed_out']:
                raise RuntimeError('CIndex completion failed')
            outputs[mode] = sorted(x for x in out.splitlines() if x.startswith('FunctionDecl:'))
            if sum('{TypedText vector}' in x for x in outputs[mode]) != 2:
                raise RuntimeError('CIndex lost vector overloads')
            if not any('{TypedText version}' in x for x in outputs[mode]):
                raise RuntimeError('CIndex lost version')
        report['parity']['c-index-test'] = outputs
        if outputs['text'] != outputs['pch']:
            raise RuntimeError('CIndex text/PCH completion differs')
        row, out, err = run(project, 'interpreter', [str(repl)],
                           b'int value = 41;\nint next = value + 1;\n%quit\n')
        report['stages']['interpreter'] = row
        if row['exit_code'] or row['timed_out'] or 'error:' in out + err:
            raise RuntimeError('interpreter declaration execution failed')
        report['pch_sha256'] = {'clang': digest(pch), 'c-index-test': digest(index_pch)}
        report['source_unchanged'] = source.read_text() == text
        if not report['source_unchanged']:
            raise RuntimeError('consumer probe changed source')
        report['passed'] = True
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
    (work / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'error': report.get('error'),
                      'stages': {k: v['exit_code'] for k, v in report['stages'].items()}}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
