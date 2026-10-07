#!/usr/bin/env python3
"""Replay exact-input scan invalidation and warm semantic reuse on Linux."""
import argparse, hashlib, importlib.util, json
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--engine', type=Path, required=True)
p.add_argument('--clang', type=Path, required=True)
p.add_argument('--workdir', type=Path, required=True)
a = p.parse_args()
s = importlib.util.spec_from_file_location('replay', Path(__file__).resolve().parents[2] / 'tests/crash/replay.py')
r = importlib.util.module_from_spec(s)
s.loader.exec_module(r)
root = a.workdir.resolve()
root.mkdir(parents=True, exist_ok=True)
use = root / 'Use.cpp'
header = root / 'enable.h'
if header.exists():
    header.unlink()
text = '#if __has_include("enable.h")\n#include "enable.h"\n#endif\nint probe() { return fn; }\n'
use.write_text(text)
cmd = []
for m, sym in [('M', 'fn_m'), ('N', 'fn_n')]:
    f = root / (m + '.cppm')
    f.write_text(f'export module {m};\nexport int {sym}() {{ return 1; }}\n')
    cmd.append({'directory': str(root), 'file': str(f), 'arguments': [str(a.clang.resolve()), '-std=c++20', '-c', str(f)]})
cmd.append({'directory': str(root), 'file': str(use), 'arguments': [str(a.clang.resolve()), '-std=c++20', '-c', str(use)]})
(root / 'compile_commands.json').write_text(json.dumps(cmd))
seq = [{'method': 'initialize', 'params': {'rootUri': root.as_uri(), 'capabilities': {}}}, {'method': 'initialized', 'notify': True, 'params': {}}, {'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {'uri': use.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}}]

def probe(v, sym=None):
    if v > 1:
        seq.append({'method': 'textDocument/didChange', 'notify': True, 'params': {'textDocument': {'uri': use.as_uri(), 'version': v}, 'contentChanges': [{'text': text}]}})
    seq.append({'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': use.as_uri()}}, 'expect': {'/result/0/name': 'probe'}})
    if sym:
        seq.append({'method': 'textDocument/completion', 'params': {'textDocument': {'uri': use.as_uri()}, 'position': {'line': 3, 'character': 23}}, 'expected_symbols': [sym]})
probe(1)
probe(2)
seq.append({'action': 'write-file', 'file': 'enable.h', 'contents': 'import M;\n'})
probe(3, 'fn_m')
probe(4, 'fn_m')
seq.append({'action': 'replace-file', 'file': 'enable.h', 'from': 'import M;', 'with': 'import N;', 'preserve-mtime': True})
probe(5, 'fn_n')
seq.append({'method': 'textDocument/didOpen', 'notify': True, 'params': {'textDocument': {'uri': header.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': 'import M;\n'}}})
probe(6, 'fn_m')
probe(7, 'fn_m')
seq.append({'method': 'textDocument/didChange', 'notify': True, 'params': {'textDocument': {'uri': header.as_uri(), 'version': 2}, 'contentChanges': [{'text': 'import N;\n'}]}})
probe(8, 'fn_n')
case = root / 'case.json'
case.write_text(json.dumps({'id': 'verified-module-scan-memo', 'project': '.', 'platform': r.platform_name(), 'baseline': 'pass', 'timeout_seconds': 35, 'flags': ['--experimental-modules-support', '--background-index=false', '--log=verbose', '--use-dirty-headers'], 'sequence': seq}))
result = r.replay(r.executable(a.engine), case)
result['engine_sha256'] = hashlib.sha256(a.engine.read_bytes()).hexdigest()
result['main_contents_unchanged'] = use.read_text() == text
result['memo_hits'] = result['stderr'].count('Module dependency scan memo hit:')
result['memo_invalidations'] = result['stderr'].count('Module dependency scan memo invalidated:')
(root / 'result.json').write_text(json.dumps(result, indent=2))
print(json.dumps({k: result.get(k) for k in ['outcome', 'detail', 'memo_hits', 'memo_invalidations', 'main_contents_unchanged']}))
if result['outcome'] != 'pass' or result['memo_hits'] < 1 or result['memo_invalidations'] < 1:
    raise SystemExit(1)
