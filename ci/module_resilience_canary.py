#!/usr/bin/env python3
"""One module that does not compile leaves the others, why a module is rebuilt is said, and
completion's waits for modules are bounded.

Self-contained, on the final package bytes (`clangd --check`, no client):

- partial-prerequisite-modules: `good` compiles, `bad` does not, `user` imports `bad`; `main.cpp`
  imports all three. `good` is built and used, the failure is reported with the compile's first
  error, and `main.cpp` has exactly one error, at the import of `bad` (the upstream engine gives
  the file no module at all).
- module-rebuild-reasons: the first build says there was no BMI, and after `good.cppm` changes the
  rebuild names the file that changed; the file's prerequisites say what they cost.
- bounded-module-wait: the engine takes the two waits as options (their behaviour is covered by
  the unit tests, TUSchedulerTests.StaleWithin*).

Exits 0 when all hold, 1 with the first that does not.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

GOOD = 'export module good;\nexport int answer() { return 42; }\n'
BAD = 'export module bad;\nexport int broken() { return undeclared_thing; }\n'
USER = 'export module user;\nimport bad;\nexport int use() { return broken(); }\n'
MAIN = 'import good;\nimport bad;\nimport user;\nint main() { return answer(); }\n'


def check(engine, root):
    run = subprocess.run([str(engine), '--experimental-modules-support', '--check=main.cpp'],
                         cwd=root, text=True, capture_output=True, timeout=300)
    return run.stdout + run.stderr


def fail(message, output=''):
    print(f'module resilience canary: FAIL {message}')
    if output:
        print(output[-4000:])
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    engine = parser.parse_args().engine.resolve()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        for name, text in (('good.cppm', GOOD), ('bad.cppm', BAD), ('user.cppm', USER), ('main.cpp', MAIN)):
            (root / name).write_text(text)
        (root / 'compile_commands.json').write_text(json.dumps([
            {'directory': str(root), 'file': str(root / name), 'arguments': ['clang++', '-std=c++20', '-c', name]}
            for name in ('good.cppm', 'bad.cppm', 'user.cppm', 'main.cpp')]))

        first = check(engine, root)
        if not re.search(r'Built module good to ', first):
            fail('the module that compiles was not built', first)
        failures = [line for line in first.splitlines() if 'Failed to build module prerequisites for' in line]
        if not any('undeclared_thing' in line for line in failures):
            fail("the failure does not carry the compile's first error", first)
        if not any('it imports bad, which could not be built' in line for line in failures):
            fail('the module importing the failed one is not reported', first)
        errors = re.findall(r'E\[[^\]]*\] \[([a-z_]+)\] Line (\d+): (.*)', first)
        if [(code, line) for code, line, _ in errors] != [('module_not_found', '2')]:
            fail(f'main.cpp should have one error, at the import of bad; it has {errors}', first)
        if 'Rebuilding module good: ' not in first or 'Prerequisites of ' not in first:
            fail('the first build does not say why it builds, or what it cost', first)

        (root / 'good.cppm').write_text(GOOD + 'export int more() { return 1; }\n')
        second = check(engine, root)
        changed = [line for line in second.splitlines() if 'Rebuilding module good: ' in line]
        if not changed or 'good.cppm' not in changed[0]:
            fail('the rebuild after an edit does not name the file that changed', second)

    options = subprocess.run([str(engine), '--help-hidden'], text=True, capture_output=True, timeout=60).stdout
    for option in ('--completion-first-preamble-wait-ms', '--completion-module-wait-ms'):
        if option not in options:
            fail(f'the engine has no {option}')
    print('module resilience canary: OK')


if __name__ == '__main__':
    main()
