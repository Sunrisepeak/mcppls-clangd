#!/usr/bin/env python3
"""The engine offers its refactorings.

clangd's refactorings (its tweaks: "Define constructor", "Extract to function",
"Expand macro" and the rest) are an object library whose every unit registers
itself when the program starts; nothing refers to them, so clangd's link names
their objects one by one. The ok image is linked from the libraries of that
line, and through 0.0.22 from the libraries alone: it carried no refactoring,
and answered every request for code actions that no diagnostic's fix answers
with an empty list (mcpp-language-server issue 89).

The engine is asked for the actions on a class's name, on an expression and on a
deduced type, and must offer the refactoring of each.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

TEXT = ('namespace render {\n'
        'class FinalPass {\n'
        'public:\n'
        '  static int create(int a);\n'
        'private:\n'
        '  int width_;\n'
        '  int height_;\n'
        '};\n'
        '}\n'
        'int area(int w, int h) {\n'
        '  auto doubled = w * 2;\n'
        '  return doubled * h;\n'
        '}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    unit = root / 'pass.cpp'
    unit.write_text(TEXT)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(unit), 'arguments': [str(clang), '-std=c++20', '-c', str(unit)]}]))

    uri = unit.as_uri()

    def actions(line, start, end):
        return {'textDocument': {'uri': uri},
                'range': {'start': {'line': line, 'character': start}, 'end': {'line': line, 'character': end}},
                'context': {'diagnostics': []}}

    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': uri, 'languageId': 'cpp', 'version': 1, 'text': TEXT}}},
        # The file is read: its first symbol is the namespace.
        {'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': uri}},
         'expect': {'/result/0/name': 'render'}},
        {'method': 'textDocument/codeAction', 'params': actions(1, 8, 8)},      # the class's name
        {'method': 'textDocument/codeAction', 'params': actions(10, 17, 22)},   # an expression
        {'method': 'textDocument/codeAction', 'params': actions(10, 3, 3)},     # `auto`
    ]
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({
        'id': 'code-actions', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 120,
        'flags': ['--background-index=false', '-j=2', '--log=verbose'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)
    # What each request was answered with, by the refactoring's identifier: the order they are offered in is the
    # order their units registered in, which a link decides.
    offered = [{(action.get('arguments') or [{}])[0].get('tweakID'): action
                for action in answer['reply'].get('result') or [] if action.get('command') == 'clangd.applyTweak'}
               for answer in result.get('raw_responses', []) if answer['method'] == 'textDocument/codeAction']
    expected = [{'MemberwiseConstructor': 'Define constructor', 'SpecialMembers': 'Declare implicit copy/move members'},
                {'ExtractVariable': None}, {'ExpandDeducedType': None}]
    if result['outcome'] == 'pass':
        problems = []
        if len(offered) != len(expected):
            problems.append(f'{len(offered)} answers to {len(expected)} requests')
        for got, wanted in zip(offered, expected):
            for tweak, title in wanted.items():
                if tweak not in got:
                    problems.append(f'the engine offered no {tweak} where one was asked for')
                elif title is not None and got[tweak].get('title') != title:
                    problems.append(f"{tweak} is titled {got[tweak].get('title')!r}, expected {title!r}")
        if problems:
            result['outcome'], result['detail'] = 'error', '; '.join(problems)
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(), 'result': result,
              'limits': ['Three of the refactorings are asked for; that every one is registered follows from their '
                         'being one object library, linked whole or not at all.']}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result['outcome'], result.get('detail', ''))
    return 0 if result['outcome'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
