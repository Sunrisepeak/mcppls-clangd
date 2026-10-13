#!/usr/bin/env python3
"""Module inputs are checked by where they come from, the module memos are kept across sessions, and
the number of retained ASTs is an option.

Self-contained, on the final package bytes (`clangd --check`, no client):

- managed-input-roots: a package store given with --managed-input-root is taken (the engine says how
  many stores it checks by their markers); a module unit including a header of a package in it builds
  and is used. How the checks skip a package version whose markers held is covered by the unit tests
  (PrerequisiteModulesTests.PackageInputsAreCheckedByTheirMarkers, ...CheckPackagesByTheirMarkers).
- persistent-module-memos: a run with --module-memo-dir writes the memos there; the next run reads
  them back and says how many it kept (each is checked again before it is used; covered by
  PrerequisiteModulesTests.MemosKeptForTheNextSession). Dependency scans are memoized only for a
  command whose driver inputs can be observed (a Linux target here; a Windows host's default target
  is not one without its tool roots), so the scans are required on Linux only; the BMI validation
  verdicts are required everywhere.
- retained-asts-option: the engine takes --max-retained-asts.
- module-input-recheck: the engine takes --module-input-recheck and says how long a check holds; how
  a check holds and a reported change ends it is covered by the unit tests
  (PrerequisiteModulesTests.ValidationVerdictsHoldWithinTheRecheckInterval, ...ScansHold...).
- interactive-actions: the engine takes --interactive-actions (covered by
  TUSchedulerTests.InteractiveActionsDoNotQueueBehindOthers).
- With module support, a file that imports no module completes as without it: Sema does not load the
  preamble's declarations, which the index has (as many results from Sema either way).

Exits 0 when all hold, 1 with the first that does not.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

GOOD = 'module;\n#include "lib.h"\nexport module good;\nexport int answer() { return lib_value; }\n'
MAIN = 'import good;\nint main() { return answer(); }\n'


def check(engine, root, *flags):
    run = subprocess.run([str(engine), '--experimental-modules-support', '--check=main.cpp', *flags],
                         cwd=root, text=True, capture_output=True, timeout=300)
    return run.returncode, run.stdout + run.stderr


def fail(message, output=''):
    print(f'module inputs canary: FAIL {message}')
    if output:
        print(output[-4000:])
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    engine = parser.parse_args().engine.resolve()

    options = subprocess.run([str(engine), '--help-hidden'], text=True, capture_output=True, timeout=60).stdout
    for option in ('--managed-input-root', '--module-memo-dir', '--max-retained-asts', '--module-input-recheck',
                   '--interactive-actions'):
        if option not in options:
            fail(f'the engine has no {option}')

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve() / 'project'
        store = Path(tmp).resolve() / 'store'
        memos = Path(tmp).resolve() / 'memos'
        package = store / 'lib' / '1.0'
        (package / 'include').mkdir(parents=True)
        (package / 'include' / 'lib.h').write_text('inline int lib_value = 42;\n')
        (package / '.mcpp_ok').write_text('1\n')
        (package / '.xpkg-install.json').write_text('{}\n')
        root.mkdir()
        (root / 'good.cppm').write_text(GOOD)
        (root / 'main.cpp').write_text(MAIN)
        include = f'-I{package / "include"}'
        (root / 'compile_commands.json').write_text(json.dumps([
            {'directory': str(root), 'file': str(root / name),
             'arguments': ['clang++', '-std=c++20', include, '-c', name]}
            for name in ('good.cppm', 'main.cpp')]))
        flags = (f'--managed-input-root={store}', f'--module-memo-dir={memos}', '--max-retained-asts=6',
                 '--module-input-recheck=60', '--interactive-actions=2')

        code, first = check(engine, root, *flags)
        if code != 0:
            fail('the first run did not check main.cpp', first)
        if not re.search(r'Module inputs: 1 managed package store', first):
            fail('the engine does not say it checks the package store by its markers', first)
        if not re.search(r'Built module good to ', first):
            fail('the module including a package header was not built', first)
        if not re.search(r'Module inputs: a check holds for 60 s', first):
            fail('the engine does not say how long a check of module inputs holds', first)
        written = memos / 'module-memos.json'
        scans = sys.platform.startswith('linux')
        if scans and (not written.is_file() or not json.loads(written.read_text()).get('scans')):
            fail('the first run kept none of its dependency scans', first)

        # The second run reads the scans back, and reuses the BMI: its validation is a verdict to keep.
        code, second = check(engine, root, *flags)
        if code != 0:
            fail('the second run did not check main.cpp', second)
        found = re.search(r'Module memos: (\d+) BMI verdicts and (\d+) scans kept', second)
        if scans and (not found or int(found.group(2)) == 0):
            fail('the second run kept no scan from the first', second)
        if not written.is_file() or not json.loads(written.read_text()).get('verdicts'):
            fail('the second run kept no BMI validation verdict', second)

        code, third = check(engine, root, *flags)
        found = re.search(r'Module memos: (\d+) BMI verdicts and (\d+) scans kept', third)
        if code != 0 or not found or int(found.group(1)) == 0:
            fail('the third run kept no BMI validation verdict from the second', third)
        # A file that imports no module: Sema gives as many results with module support as without.
        headers = Path(tmp).resolve() / 'headers'
        headers.mkdir()
        (headers / 'lib.h').write_text('int canary_alpha();\nint canary_beta();\n')
        (headers / 'main.cpp').write_text('#include "lib.h"\nint main() {\n  can\n}\n')
        (headers / 'compile_commands.json').write_text(json.dumps([
            {'directory': str(headers), 'file': str(headers / 'main.cpp'),
             'arguments': ['clang++', '-std=c++20', '-c', 'main.cpp']}]))
        sema = {}
        for modules in (True, False):
            run = subprocess.run([str(engine), *(['--experimental-modules-support'] if modules else []),
                                  '--check=main.cpp', '--check-completion', '--check-lines=3'],
                                 cwd=headers, text=True, capture_output=True, timeout=300)
            found = re.search(r'Code complete: (\d+) results from Sema', run.stdout + run.stderr)
            if not found:   # the half-typed word is an error: the check's own exit status says so
                fail('the header-only file was not completed', run.stdout + run.stderr)
            sema[modules] = int(found.group(1))
        if sema[True] != sema[False]:
            fail(f'with module support, Sema loaded the preamble of a file that imports no module '
                 f'({sema[True]} results from Sema, {sema[False]} without module support)')
    print('module inputs canary: OK')


if __name__ == '__main__':
    main()
