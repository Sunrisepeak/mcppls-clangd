#!/usr/bin/env python3
"""A header of the global module fragment is analysed whatever identity its path has.

A module unit that imports a module has no textual preamble: the headers of its
global module fragment are entered with the unit itself. The include analysis
then asks for the entry of each include's resolved path, and identifies the
header by that entry's identity. Where the resolved path is another spelling
than the one the header was entered by, a file system may answer with another
identity (Windows 11 24H2 under okrun did: an open file and its name were two
nodes), the include structure has no ID for the entry, and the engine
dereferenced the empty result: it ended on the first build of the unit, by an
illegal instruction where the standard library checks, silently elsewhere.

The unit here includes a header through a search path that is not its resolved
path, imports a module and uses the header's type. The engine must build it,
answer for it, and not offer the header in use for removal.
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--expect-two-identities', action='store_true',
                        help='fail unless the engine reports that an open file is not the node its name refers to')
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    (root / 'inc').mkdir(parents=True, exist_ok=True)
    (root / 'other').mkdir(exist_ok=True)

    (root / 'inc' / 'widget.h').write_text(
        '#ifndef WIDGET_H\n#define WIDGET_H\nstruct Widget { int size; };\n#define WIDGET_UNIT 1\n#endif\n')
    dep = root / 'dep.cppm'
    dep.write_text('export module dep;\nexport int dep_value() { return 1; }\n')
    unit = root / 'view.cppm'
    text = ('module;\n'
            '#include "widget.h"\n'
            'export module view;\n'
            'import dep;\n'
            'export int measure(const Widget &w) { return w.size * WIDGET_UNIT + dep_value(); }\n')
    unit.write_text(text)
    # The search path is spelled through a sibling directory, so the header is
    # entered by one path and resolved to another.
    include = '-I' + root.as_posix() + '/other/../inc'
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', include, '-c', str(p)]}
        for p in (dep, unit)]))

    uri = unit.as_uri()
    document = {'textDocument': {'uri': uri}}
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': uri, 'languageId': 'cpp', 'version': 1, 'text': text}}},
        {'method': 'textDocument/documentSymbol', 'params': document,
         'expect': {'/result/0/name': 'measure'}},
        # The unit's diagnostics, the include analysis among them, are published
        # when its build ends; the engine answers after it.
        {'action': 'await-log', 'contains': 'textDocument/publishDiagnostics'},
        {'method': 'textDocument/hover', 'params': {**document, 'position': {'line': 4, 'character': 12}},
         'expect': {'/result/contents/kind': 'plaintext'}},
    ]
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({
        'id': 'gmf-include-analysis', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 120,
        'flags': ['--experimental-modules-support', '--background-index=false', '-j=2', '--log=verbose'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)

    stderr = result.get('stderr', '')
    detail = result.get('detail', '')
    if result['outcome'] == 'pass' and 'Built module dep to ' not in stderr:
        result['outcome'], detail = 'error', 'the unit did not take the module path: dep was not built'
    if result['outcome'] == 'pass' and 'widget.h' in stderr and 'is not used directly' in stderr:
        result['outcome'], detail = 'error', 'the header in use was offered for removal'
    # The engine measures its cache directory at the first module it builds and says when the system gives an
    # open file another identity than its name: the condition under which this case met the defect.
    two_identities = 'an open file is not the node its name refers to' in stderr
    if result['outcome'] == 'pass' and args.expect_two_identities and not two_identities:
        result['outcome'], detail = 'error', 'this system gave a file one identity: the case did not meet the condition'
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'result': result, 'two_identities': two_identities,
              'limits': ['The identities a file system gives are its own: the case asserts the build on every '
                         'system and meets the two-identity condition only where the system has it.']}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result['outcome'], detail, f'two_identities={two_identities}')
    return 0 if result['outcome'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
