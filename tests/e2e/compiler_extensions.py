#!/usr/bin/env python3
"""Focused semantic compiler-extension checks; not crash or release-soak evidence."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    project = args.workdir.resolve()
    project.mkdir(parents=True, exist_ok=True)
    linux = ['-std=c++20', '--target=x86_64-unknown-linux-gnu']
    windows = ['-std=c++20', '--target=x86_64-pc-windows-msvc', '-fms-extensions']
    cases = [
        ('gnu-introducer', '__attr', '__attr\nint marker;\n', linux, ['__attribute__'], []),
        ('gnu-cleanup', 'cle', 'void release(int*);\nvoid f() { int value __attribute__((cle)); }\n', linux, ['cleanup'], ['__try']),
        ('gnu-cleanup-function', 'rel', 'void release(int*);\nvoid releaseWrong();\nvoid releaseValue(int);\nvoid releasePair(int*, int);\nint releaseData;\nvoid f() { int value __attribute__((cleanup(rel))); }\n', linux, ['release'], ['cleanup', '__try', '__attribute__', 'releaseWrong', 'releaseValue', 'releasePair', 'releaseData']),
        ('windows-seh', '__tr', 'void f() {\n  __tr\n}\n', windows, ['__try'], []),
        ('visible-gnu-macro', '__tr', '#define __try 1\nvoid f() { int value = __tr; }\n', linux, ['__try'], []),
        ('linux-no-seh', '__tr', 'void f() {\n  __tr\n}\n', linux + ['-fms-extensions'], [], ['__try']),
        ('windows-mode-off', '__tr', 'void f() {\n  __tr\n}\n', windows[:-1] + ['-fno-ms-extensions'], [], ['__try']),
        ('expression-not-attribute', '__attr', 'void f() { int value = __attr; }\n', linux, [], ['__attribute__', 'cleanup', '__try']),
        ('ordinary-cleanup', 'cle', 'void f() { cle; }\n', linux, [], ['cleanup']),
        ('comment', '__attr', 'void f() { // __attr\n}\n', linux, [], ['__attribute__', 'cleanup', '__try']),
        ('string', '__attr', 'const char* value = "__attr";\n', linux, [], ['__attribute__', 'cleanup', '__try']),
    ]
    results = []
    inserted_compilation = []
    for name, prefix, text, flags, expected, forbidden in cases:
        root = project / name
        root.mkdir(exist_ok=True)
        source = root / 'test.cpp'
        source.write_text(text)
        offset = text.rindex(prefix) + len(prefix)
        before = text[:offset]
        line = before.count('\n')
        character = len(before.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2
        (root / 'compile_commands.json').write_text(json.dumps([{
            'directory': str(root), 'file': str(source),
            'arguments': [str(clang), *flags, '-c', str(source)]}]))
        case = {'id': name, 'platform': replay.platform_name(), 'baseline': 'pass',
                'project': '.', 'timeout_seconds': 20,
                'flags': ['--sync', '--background-index=false', '--header-insertion=never'],
                'sequence': [
                    {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {
                        'textDocument': {'completion': {'completionItem': {'snippetSupport': True}}}}}},
                    {'method': 'initialized', 'notify': True, 'params': {}},
                    {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {
                        'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}},
                    {'method': 'textDocument/completion', 'params': {'textDocument': {'uri': source.as_uri()},
                        'position': {'line': line, 'character': character}},
                     'expected_symbols': expected, 'forbidden_symbols': forbidden}]}
        fragments = {
            'gnu-introducer': {'__attribute__': ['__attribute__((', '))']},
            'gnu-cleanup': {'cleanup': ['cleanup(', ')']},
            'windows-seh': {'__try': ['__try {', '__except(', 'filter-expression', '$0']},
        }.get(name)
        if fragments:
            case['sequence'][-1]['expected_snippet_fragments'] = fragments
        manifest = root / 'case.json'
        manifest.write_text(json.dumps(case, indent=2))
        result = replay.replay(engine, manifest)
        results.append(result)
        print(name, result['outcome'], result.get('detail', ''))
        # Apply the actual returned edit, filling the caller-selected snippet
        # fields, then ask the declared target compiler to accept the result.
        if result['outcome'] == 'pass' and expected:
            item = result['responses'][-1]['completion_items'][expected[0]][0]
            edit = item['textEdit']
            lines = text.splitlines(keepends=True)
            def at(position):
                return sum(len(part) for part in lines[:position['line']]) + position['character']
            fields = {'statements': 'int value = 0; (void)value;', 'filter-expression': '1'}
            insertion = re.sub(r'\$\{\d+:([^}]*)\}', lambda match: fields.get(match[1], ''), edit['newText'])
            final_field = {'gnu-introducer': 'used', 'gnu-cleanup': 'release'}.get(name, '')
            insertion = re.sub(r'\$\d+', lambda match: final_field if match[0] == '$0' else '', insertion)
            applied = text[:at(edit['range']['start'])] + insertion + text[at(edit['range']['end']):]
            inserted = root / 'inserted.cpp'
            inserted.write_text(applied)
            command = [str(clang), *flags, '-fsyntax-only', str(inserted)]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
            inserted_compilation.append({'id': name, 'actual_edit': edit, 'expanded_source': applied,
                                         'command': command, 'exit_code': completed.returncode,
                                         'stderr': completed.stderr, 'ok': completed.returncode == 0})
    sources = {
        'gnu': ('void release(int*) {}\n__attribute__((noinline)) void f() { int value __attribute__((cleanup(release))) = 0; }\n', linux, 0),
        'windows': ('void f() { __try { int value = 0; (void)value; } __except (1) {} }\n', windows, 0),
        'linux-rejects-seh': ('void f() { __try {} __except (1) {} }\n', linux + ['-fms-extensions'], 1),
    }
    compilation = []
    for name, (text, flags, expected_code) in sources.items():
        source = project / (name + '.cpp')
        source.write_text(text)
        command = [str(clang), *flags, '-fsyntax-only', str(source)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
        valid = completed.returncode == expected_code
        if name == 'linux-rejects-seh':
            valid = valid and "SEH '__try' is not supported on this target" in completed.stderr
        compilation.append({'id': name, 'command': command, 'exit_code': completed.returncode,
                            'stderr': completed.stderr, 'ok': valid})
    report = {'schema': 1, 'scope': 'compiler extensions, self-contained semantic and syntax checks',
              'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'results': results, 'compilation': compilation, 'inserted_compilation': inserted_compilation}
    (project / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if all(r['outcome'] == 'pass' for r in results) and all(r['ok'] for r in compilation + inserted_compilation) else 1


if __name__ == '__main__':
    raise SystemExit(main())
