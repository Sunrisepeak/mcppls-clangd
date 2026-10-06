#!/usr/bin/env python3
"""Semantic regression probe for module members at non-final completion lines.

Uses a small self-contained module (no SDK or standard library dependency).
Produces asserted LSP manifests and preserves response names/timings and engine
SHA. This is a focused correctness canary, not the full W1 performance gate.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

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
    project = args.workdir.resolve()
    project.mkdir(parents=True, exist_ok=True)
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    module = project / 'Api.cppm'
    module.write_text('export module Api;\nexport struct Cli {\n'
                      '  void addHelpOption();\n  void addOption();\n};\n')
    source = project / 'Use.cpp'
    cdb = [{'directory': str(project), 'file': str(p),
            'arguments': [str(clang), '-std=c++20', '-c', str(p), '-o', str(p)+'.o']}
           for p in (module, source)]
    (project / 'compile_commands.json').write_text(json.dumps(cdb, indent=2))
    results = []
    for name, prefix in [('member', 'cli.'), ('member-prefix', 'cli.ad'), ('pointer', 'ptr->')]:
        text = ('import Api;\nvoid qVersion();\nvoid Counter();\nvoid AdlTester();\n'
                'void f() {\n  Cli cli;\n  Cli* ptr = &cli;\n  '+prefix+'\n}\n'
                '// This final line is unrelated to the completion context.\n')
        source.write_text(text)
        uri = source.as_uri()
        case = {'id': name, 'platform': replay.platform_name(), 'baseline': 'pass',
                'project': '.', 'timeout_seconds': 30,
                'flags': ['--experimental-modules-support', '--background-index=false',
                          '--header-insertion=never', '--log=verbose', '-j=2'],
                'sequence': [
                    {'method': 'initialize', 'params': {'rootUri': project.as_uri(), 'capabilities': {}}},
                    {'method': 'initialized', 'params': {}, 'notify': True},
                    {'method': 'textDocument/didOpen', 'notify': True,
                     'params': {'textDocument': {'uri': uri, 'languageId': 'cpp', 'version': 1, 'text': text}}},
                    {'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': uri}}},
                    {'method': 'textDocument/completion',
                     'params': {'textDocument': {'uri': uri}, 'position': {'line': 7, 'character': 2+len(prefix)}},
                     'expected_symbols': ['addHelpOption', 'addOption'],
                     'forbidden_symbols': ['qVersion', 'Counter', 'AdlTester']} ]}
        if name == 'member':
            updated = text.replace('cli.', 'cli.new')
            case['sequence'] += [
                {'action': 'replace-file', 'file': 'Api.cppm', 'from': 'addOption', 'with': 'newOption', 'same-second': True},
                {'method': 'workspace/didChangeWatchedFiles', 'notify': True,
                 'params': {'changes': [{'uri': module.as_uri(), 'type': 2}]}},
                {'method': 'textDocument/didChange', 'notify': True,
                 'params': {'textDocument': {'uri': uri, 'version': 2}, 'contentChanges': [{'text': updated}]}},
                {'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': uri}}},
                {'method': 'textDocument/completion',
                 'params': {'textDocument': {'uri': uri}, 'position': {'line': 7, 'character': 9}},
                 'expected_symbols': ['newOption'], 'forbidden_symbols': ['addOption']}]
        manifest = project / f'{name}.json'
        manifest.write_text(json.dumps(case, indent=2))
        results.append(replay.replay(engine, manifest))
    report = {'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'platform': replay.platform_name(), 'results': results}
    (project / 'quality-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({r['id']: {'outcome': r['outcome'], 'detail': r.get('detail'),
                             'responses': r['responses']} for r in results}, indent=2))
    return int(any(r['outcome'] != 'pass' for r in results))


if __name__ == '__main__':
    sys.exit(main())
