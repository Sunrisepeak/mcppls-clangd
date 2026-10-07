#!/usr/bin/env python3
"""Verify warm module scans and actual wall-clock builtin admission."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
parser = argparse.ArgumentParser(description='Verify warm module scans with actual preprocessing inputs.')
parser.add_argument('--engine', type=Path, required=True)
parser.add_argument('--clang', type=Path, required=True)
parser.add_argument('--workdir', type=Path, required=True)
parser.add_argument('--resource-dir', type=Path, help='Resource headers for an isolated development link')
parser.add_argument('--allow-no-hits', action='store_true', help='Baseline or unsupported native target: require semantics but permit declined reuse')
a = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
s = importlib.util.spec_from_file_location('replay', repo / 'tests/crash/replay.py')
r = importlib.util.module_from_spec(s)
s.loader.exec_module(r)
root = a.workdir.resolve()
root.mkdir(parents=True, exist_ok=True)
compiler = r.executable(a.clang)
engine = r.executable(a.engine)
cases = {'macro': '#define JOIN_(a,b) a ## b\n#define JOIN(a,b) JOIN_(a,b)\n#define FLAG_ON 1\n#if JOIN(FLAG_,ON)\nimport M;\n#endif\n', 'std-header': '#include <vector>\nimport M;\n', 'inactive-and-literal': '#if 0\n__DATE__ __TIME__ __TIMESTAMP__\n#endif\nconst char *literal = "__DATE__";\nimport M;\n', 'pasted-builtin': '#define JOIN_(a,b) a ## b\n#define JOIN(a,b) JOIN_(a,b)\n#if __has_include(JOIN(__DA,TE__))\nimport N;\n#endif\nimport M;\n', 'direct-builtin': '#if __has_include(__TIME__)\nimport N;\n#endif\nimport M;\n'}
summary = []
for name, prefix in cases.items():
    work = root / ('case-' + name)
    work.mkdir(exist_ok=True)
    source = work / 'Use.cpp'
    text = prefix + 'void probe() {\n  fn\n}\n'
    source.write_text(text)
    commands = []
    for m in ['M', 'N']:
        f = work / (m + '.cppm')
        f.write_text(f'export module {m};\nexport int fn_{m.lower()}() {{ return 1; }}\n')
        commands.append({'directory': str(work), 'file': str(f), 'arguments': [str(compiler), '-std=c++20', '-c', str(f)]})
    commands.append({'directory': str(work), 'file': str(source), 'arguments': [str(compiler), '-std=c++20', '-c', str(source)]})
    (work / 'compile_commands.json').write_text(json.dumps(commands))
    sequence = [{'method': 'initialize', 'params': {'rootUri': work.as_uri(), 'capabilities': {}}}, {'method': 'initialized', 'notify': True, 'params': {}}, {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}}]
    for version in range(1, 4):
        if version > 1:
            sequence.append({'method': 'textDocument/didChange', 'notify': True, 'params': {'textDocument': {'uri': source.as_uri(), 'version': version}, 'contentChanges': [{'text': text}]}})
        sequence.append({'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': source.as_uri()}}})
        sequence.append({'method': 'textDocument/completion', 'params': {'textDocument': {'uri': source.as_uri()}, 'position': {'line': len(prefix.splitlines()) + 1, 'character': 4}}, 'expected_symbols': ['fn_m']})
    manifest = work / 'case.json'
    manifest.write_text(json.dumps({'id': name, 'project': '.', 'platform': r.platform_name(), 'baseline': 'pass', 'timeout_seconds': 30, 'flags': ['--experimental-modules-support', '--background-index=false', '--log=verbose'] + (['--resource-dir=' + str(a.resource_dir.resolve())] if a.resource_dir else []), 'sequence': sequence}))
    result = r.replay(engine, manifest)
    result['use_hits'] = result['stderr'].count('Module dependency scan memo hit: ' + str(source))
    result['use_stores'] = result['stderr'].count('Module dependency scan memo stored: ' + str(source))
    result['use_declines'] = result['stderr'].count('Module dependency scan memo declined: ' + str(source))
    (work / 'result.json').write_text(json.dumps(result, indent=2))
    print(name, result['outcome'], result['use_hits'], result['use_stores'], result['use_declines'], flush=True)
    summary.append({k: result.get(k) for k in ['id', 'outcome', 'exit_code', 'readers_stopped', 'use_hits', 'use_stores', 'use_declines']})
ok = all((x['outcome'] == 'pass' and x['exit_code'] == 0 and x['readers_stopped'] for x in summary))
if not a.allow_no_hits and sys.platform.startswith('linux'):
    for x in summary:
        if x['id'] in ('direct-builtin', 'pasted-builtin'):
            ok &= x['use_hits'] == 0 and x['use_stores'] == 0 and (x['use_declines'] > 0)
        else:
            ok &= x['use_hits'] > 0 and x['use_stores'] > 0
report = {'ok': ok, 'scope': 'Warm scans only: documentSymbol waits for AST before completion. No cold completion, native registry, deadline or RSS claim.', 'results': summary}
(root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
raise SystemExit(0 if ok else 1)
