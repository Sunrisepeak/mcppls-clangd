"""Observe exact rebuild reasons and unchanged-source header selection."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine', type=lambda p: Path(p).resolve(), required=True)
parser.add_argument('--runner', type=lambda p: Path(p).resolve())
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--repeat', type=int, default=5)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
prefix = ([str(args.runner)] if args.runner else []) + [str(args.engine)]
results = []

def snapshot(project):
    result = []
    for path in sorted((project / '.cache').rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        info = path.stat()
        row = dict(path=str(path.relative_to(project)), bytes=info.st_size,
                   mtime_ns=info.st_mtime_ns, inode=info.st_ino)
        if path.name.endswith('.inputs'):
            row['contents'] = path.read_bytes().decode(errors='replace')
        if path.name == 'ledger-v1':
            data = path.read_bytes()
            row['sha256'] = hashlib.sha256(data).hexdigest()
            if len(data) >= 40:
                magic, width, slots, limit, pressure = struct.unpack_from('<5Q', data)
                row['header'] = dict(magic=magic, record_size=width, slots=slots, limit=limit, pressure=pressure)
                row['records'] = []
                if 1265 <= width <= 4096:
                    for bank in range(min(slots * 2, 32)):
                        record = data[40 + bank * width:40 + (bank + 1) * width]
                        if len(record) < width:
                            break
                        sequence, generation, size, kind = struct.unpack_from('<4Q', record)
                        if sequence:
                            row['records'].append(dict(bank=bank, sequence=sequence,
                                generation=generation, bytes=size, kind=kind,
                                key=record[176:241].split(b'\0')[0].decode(errors='replace'),
                                source=record[241:1265].split(b'\0')[0].decode(errors='replace')))
        result.append(row)
    return result

def check(project, logs, phase):
    command = [*prefix, '--experimental-modules-support', '--check=main.cpp',
               '--modules-builder-worker-policy=required']
    run = subprocess.run(command, cwd=project, text=True, capture_output=True, timeout=300)
    text = run.stdout + run.stderr
    (logs / (phase + '.log')).write_text(text)
    state = snapshot(project)
    (logs / (phase + '-cache.json')).write_text(json.dumps(state, indent=2) + '\n')
    return dict(exit=run.returncode, built=bool(re.search('Built module good to ', text)),
                reused=bool(re.search(r'Reusing (owned |persistent )?module good from ', text)),
                why=re.findall(r'Rebuilding module good: ([^\n]+)', text),
                strict_absent_reason=bool(re.search(r'Rebuilding module good: \S*first.lib\.h was absent when the module was built', text)),
                checks_ok='All checks completed, 0 errors' in text)

for mode in ('original', 'semantic'):
    for number in range(args.repeat):
        case = args.out / f'{mode}-{number}'
        project, logs = case / 'project', case / 'logs'
        (project / 'first').mkdir(parents=True)
        (project / 'second').mkdir()
        logs.mkdir()
        const = 'constexpr ' if mode == 'semantic' else ''
        (project / 'second/lib.h').write_text(f'inline {const}int lib_value = 42;\n')
        (project / 'good.cppm').write_text('module;\n#include "lib.h"\nexport module good;\n'
              + f'export {const}int answer() {{ return lib_value; }}\n')
        main = 'import good;\n'
        if mode == 'semantic':
            main += ('#if __has_include("first/lib.h")\nstatic_assert(answer() == 7);\n'
                     '#else\nstatic_assert(answer() == 42);\n#endif\n')
        main += 'int main() { return answer(); }\n'
        (project / 'main.cpp').write_text(main)
        (project / 'compile_commands.json').write_text(json.dumps([
            dict(directory=str(project.resolve()), file=str((project / name).resolve()),
                 arguments=['clang++', '-std=c++20', '-I' + str((project / 'first').resolve()),
                            '-I' + str((project / 'second').resolve()), '-c', name])
            for name in ['good.cppm', 'main.cpp']]))
        before = check(project, logs, 'before')
        again = check(project, logs, 'again')
        # Only this new header changes. Neither source nor compile command is rewritten.
        (project / 'first/lib.h').write_text(f'inline {const}int lib_value = 7;\n')
        after = check(project, logs, 'after')
        results.append(dict(mode=mode, number=number, before=before, again=again, after=after))
        (args.out / 'observations.json').write_text(json.dumps(results, indent=2) + '\n')
        print(json.dumps(results[-1]), flush=True)
        assert before['exit'] == 0 and before['built'] and again['exit'] == 0 and again['reused']
        if args.runner and mode == 'semantic':
            assert after['exit'] == 0 and after['checks_ok'] and after['built'], results[-1]
