#!/usr/bin/env python3
"""An unresolvable third-party import must not degrade resolvable modules.

When one direct import names a module whose unit source the project scanner
cannot resolve (a toolchain module seen through a foreign compiler profile),
the prerequisite builder used to discard every module it had already built and
return FailedPrerequisiteModules forever. Every request then re-ran the
dependency build and parsed without a preamble, so members of the resolvable
modules stopped completing semantically. The resolvable module's symbols must
complete, and later requests must reuse the prerequisites rather than rebuild
them per request.
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

PROBE = 'dep_va'


def completion_step(uri, text, version, position):
    return {'method': 'textDocument/completion',
            'params': {'textDocument': {'uri': uri}, 'position': position,
                       'context': {'triggerKind': 1}},
            'expected_symbols': ['dep_value']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    engine, clang = replay.executable(args.engine), replay.executable(args.clang)
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    dep = root / 'dep.cppm'
    dep.write_text('export module dep;\nexport int dep_value() { return 1; }\n')
    source = root / 'main.cpp'
    body = (f'import third_party_missing;\nimport dep;\n'
            f'int probe() {{\n    return {PROBE};\n}}\n')
    text_v1 = body
    source.write_text(text_v1)
    text_v2 = body.replace(PROBE, PROBE + 'l', 1)

    def position_of(text, needle):
        prefix = text[:text.index(needle) + len(needle)]
        return {'line': prefix.count('\n'),
                'character': len(prefix.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}

    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]}
        for p in (dep, source)]))

    uri = source.as_uri()
    document = {'textDocument': {'uri': uri}}
    sequence = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': uri, 'languageId': 'cpp', 'version': 1, 'text': text_v1}}},
        {'method': 'textDocument/documentSymbol', 'params': document,
         'expect': {'/result/0/name': 'probe'}},
        completion_step(uri, text_v1, 1, position_of(text_v1, PROBE)),
        {'method': 'textDocument/didChange', 'notify': True, 'params': {
            'textDocument': {'uri': uri, 'version': 2},
            'contentChanges': [{'text': text_v2}]}},
        completion_step(uri, text_v2, 2, position_of(text_v2, PROBE + 'l')),
        {'action': 'await-log', 'contains': 'Built module dep to '},
    ]
    manifest = root / 'case.json'
    manifest.write_text(json.dumps({
        'id': 'third-party-import-reuse', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 60,
        'flags': ['--experimental-modules-support', '--background-index=false', '-j=2'],
        'sequence': sequence}))
    result = replay.replay(engine, manifest)

    stderr = result.get('stderr', '')
    # Every preamble build rescans the unresolvable import once and logs it.
    # Completion requests reuse the validated prerequisites, so they must not
    # add further failures: the failure count has to track the preamble count.
    failures = stderr.count('third_party_missing')
    preambles = stderr.count('Built preamble of size')
    detail = result.get('detail', '')
    if result['outcome'] == 'pass' and failures > preambles:
        result['outcome'] = 'error'
        detail = (f'unresolved import re-built per request: {failures} failure logs '
                  f'for {preambles} preamble builds')
    report = {'schema': 1, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'result': result, 'failure_logs': failures, 'preamble_builds': preambles,
              'limits': ['Third-party imports stay textual; no toolchain-module mapping claim.']}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result['outcome'], detail, f"failures={failures} preambles={preambles}")
    if result['outcome'] != 'pass':
        return 1

    # A file whose only import is third-party keeps its preamble: the parse
    # never loads a named-module BMI, so the PCH+modules mixing upstream
    # guards against cannot arise. Once a buildable import appears on disk,
    # the verdict re-derives and the preamble collapses back before any BMI
    # is combined with a real PCH.
    fat = root / 'fat.h'
    fat_lines = ['#pragma once', '// deterministic declarations proving preamble content']
    fat_lines += [f'namespace fat {{ struct S{i} {{ int v{i}; int w{i}; }}; }}'
                  for i in range(20000)]
    fat.write_text('\n'.join(fat_lines) + '\n')
    source2 = root / 'main2.cpp'
    text2 = ('#include "fat.h"\nimport third_party_missing;\n'
             'int probe2() {\n    return fat::S399;\n}\n')
    source2.write_text(text2)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]}
        for p in (dep, source, source2)]))

    def position2(text, needle):
        prefix = text[:text.index(needle) + len(needle)]
        return {'line': prefix.count('\n'),
                'character': len(prefix.rsplit('\n', 1)[-1].encode('utf-16-le')) // 2}

    text2_flipped = text2.replace(
        'import third_party_missing;',
        'import third_party_missing;\nimport dep;', 1) + \
        'int use_dep() {\n    return dep_va;\n}\n'
    uri2 = source2.as_uri()
    document2 = {'textDocument': {'uri': uri2}}
    sequence2 = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': uri2, 'languageId': 'cpp', 'version': 1, 'text': text2}}},
        {'method': 'textDocument/documentSymbol', 'params': document2,
         'expect': {'/result/0/name': 'probe2'}},
        {'action': 'await-log', 'contains': f'{source2} version 1'},
        {'method': 'textDocument/completion',
         'params': {'textDocument': {'uri': uri2}, 'position': position2(text2, 'fat::S399'),
                    'context': {'triggerKind': 1}},
         'expected_symbols': ['S3999']},
        {'action': 'replace-file', 'file': 'main2.cpp',
         'from': 'import third_party_missing;',
         'with': 'import third_party_missing;\nimport dep;'},
        {'method': 'textDocument/didChange', 'notify': True, 'params': {
            'textDocument': {'uri': uri2, 'version': 2},
            'contentChanges': [{'text': text2_flipped}]}},
        {'action': 'await-log', 'contains': f'{source2} version 2'},
        # documentSymbol waits for the rebuilt AST, so the completions below
        # observe the re-derived prerequisites instead of racing the update.
        {'method': 'textDocument/documentSymbol', 'params': document2,
         'expect': {'/result/0/name': 'probe2'}},
        {'method': 'textDocument/completion',
         'params': {'textDocument': {'uri': uri2},
                    'position': position2(text2_flipped, 'fat::S399'),
                    'context': {'triggerKind': 1}},
         'expected_symbols': ['S3999']},
        {'method': 'textDocument/completion',
         'params': {'textDocument': {'uri': uri2},
                    'position': position2(text2_flipped, 'dep_va'),
                    'context': {'triggerKind': 1}},
         'expected_symbols': ['dep_value']},
    ]
    manifest.write_text(json.dumps({
        'id': 'third-party-import-preamble', 'project': '.', 'platform': replay.platform_name(),
        'baseline': 'pass', 'timeout_seconds': 240,
        'flags': ['--experimental-modules-support', '--background-index=false', '-j=2'],
        'sequence': sequence2}))
    retained = replay.replay(engine, manifest)
    sizes = {}
    for match in re.finditer(r'Built preamble of size (\d+) for file \S+main2\.cpp version (\d+)',
                             retained.get('stderr', '')):
        sizes.setdefault(int(match.group(2)), []).append(int(match.group(1)))
    detail2 = retained.get('detail', '')
    first = max(sizes.get(1, [0]))
    second = max(sizes.get(2, [10 ** 9]))
    if retained['outcome'] == 'pass' and first <= 600000:
        retained['outcome'] = 'error'
        detail2 = f'expected a real fat-header preamble, observed size {first}'
    if retained['outcome'] == 'pass' and second >= first // 2:
        retained['outcome'] = 'error'
        detail2 = (f'adding a buildable import must collapse the preamble: '
                   f'v1={first} v2={second}')
    report['preamble_case'] = retained
    report['preamble_sizes'] = {k: v for k, v in sizes.items()}
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(retained['outcome'], detail2, f"preamble sizes={sizes}")
    if retained['outcome'] != 'pass':
        return 1

    # A provider appearing through a compile-command change must reach files
    # whose prerequisite set resolved to nothing earlier: the reuse verdict
    # dies with the command generation instead of serving stale emptiness.
    # The whole sequence runs in one process so the change is genuinely
    # observed mid-session.
    dep2 = root / 'dep2.cppm'
    dep2.write_text('export module dep2;\nexport int dep2_value() { return 2; }\n')
    source3 = root / 'main3.cpp'
    text3 = ('import third_party_missing;\nimport dep2;\n'
             'int probe3() {\n    return dep2_va;\n}\n')
    text3b = text3.replace('dep2_va', 'dep2_val', 1)
    source3.write_text(text3)
    # dep2 has no compile command yet: its import stays textual.
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]}
        for p in (dep, source, source2, source3)]))
    with_dep2 = json.dumps([
        {'directory': str(root), 'file': str(p),
         'arguments': [str(clang), '-std=c++20', '-c', str(p)]}
        for p in (dep, dep2, source, source2, source3)])
    uri3 = source3.as_uri()
    document3 = {'textDocument': {'uri': uri3}}
    sequence3 = [
        {'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}},
        {'method': 'initialized', 'notify': True, 'params': {}},
        {'method': 'textDocument/didOpen', 'notify': True, 'params': {
            'textDocument': {'uri': uri3, 'languageId': 'cpp', 'version': 1, 'text': text3}}},
        {'method': 'textDocument/documentSymbol', 'params': document3,
         'expect': {'/result/0/name': 'probe3'}},
        {'method': 'textDocument/completion',
         'params': {'textDocument': {'uri': uri3},
                    'position': position_of(text3, 'dep2_va'),
                    'context': {'triggerKind': 1}},
         'forbidden_symbols': ['dep2_value']},
        # The provider appears: the compile database gains dep2's command.
        {'action': 'replace-file', 'file': 'compile_commands.json',
         'from': json.dumps({'directory': str(root), 'file': str(source3),
                             'arguments': [str(clang), '-std=c++20', '-c', str(source3)]}),
         'with': json.dumps({'directory': str(root), 'file': str(dep2),
                             'arguments': [str(clang), '-std=c++20', '-c', str(dep2)]}) +
                 ', ' +
                 json.dumps({'directory': str(root), 'file': str(source3),
                             'arguments': [str(clang), '-std=c++20', '-c', str(source3)]})},
        # The directory CDB revalidates on a five-second interval, so enough
        # request cycles must pass before the changed database reloads and
        # broadcasts; a later cycle's update then observes the new generation
        # and rebuilds the prerequisite set with the new provider.
        # The directory CDB revalidates on a five-second interval: wait past
        # it so the next request cycle reloads the database, broadcasts the
        # command change, and rebuilds prerequisites with the new provider.
        {'action': 'sleep', 'seconds': 6},
        {'method': 'textDocument/didChange', 'notify': True, 'params': {
            'textDocument': {'uri': uri3, 'version': 2},
            'contentChanges': [{'text': text3b}]}},
        {'method': 'textDocument/documentSymbol', 'params': document3,
         'expect': {'/result/0/name': 'probe3'}},
        {'action': 'await-log', 'contains': 'Built module dep2 to '},
    ]
    sequence3 += [
        {'method': 'textDocument/completion',
         'params': {'textDocument': {'uri': uri3},
                    'position': position_of(text3b, 'dep2_val'),
                    'context': {'triggerKind': 1}},
         'expected_symbols': ['dep2_value']},
    ]
    manifest.write_text(json.dumps({
        'id': 'third-party-import-provider-gain', 'project': '.',
        'platform': replay.platform_name(), 'baseline': 'pass', 'timeout_seconds': 240,
        'flags': ['--experimental-modules-support', '--background-index=false', '-j=2'],
        'sequence': sequence3}))
    provider_gain = replay.replay(engine, manifest)
    report['provider_case'] = provider_gain
    (root / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(provider_gain['outcome'], provider_gain.get('detail', '')[:150])
    return 0 if provider_gain['outcome'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
