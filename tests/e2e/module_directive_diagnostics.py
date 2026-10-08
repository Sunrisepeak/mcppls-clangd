#!/usr/bin/env python3
"""Verify actual missing-separator diagnostics on the directive's own line."""
import argparse
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("replay", ROOT / "tests/crash/replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


CASES = [
    ('import', 'import A\nimport B;\n', 'expected_semi_after_module_or_import', 0, 8),
    ('continued-import', 'import \\\n  A\nimport B;\n', 'expected_semi_after_module_or_import', 1, 3),
    ('module', 'export module M // pending\nint marker;\n', 'pp_unexpected_tok_after_module_name', 0, 15),
    ('continued-module', 'export module \\\n  M\nint marker;\n', 'pp_unexpected_tok_after_module_name', 1, 3),
]


def probe(engine):
    engine = replay.executable(engine)
    messages = [{'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {
        'rootUri': 'test:///', 'capabilities': {},
        'initializationOptions': {'fallbackFlags': ['-std=c++20']}}}]
    for name, code, _, _, _ in CASES:
        messages.append({'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {
            'textDocument': {'uri': f'test:///{name}.cpp', 'languageId': 'cpp',
                             'version': 1, 'text': code}}})
    messages.extend([{'jsonrpc': '2.0', 'id': 1, 'method': 'shutdown', 'params': None},
                     {'jsonrpc': '2.0', 'method': 'exit'}])
    frames = '\n---\n'.join(json.dumps(m) for m in messages).encode() + b'\n'
    result = subprocess.run([str(engine), '-lit-test', '--background-index=false'],
                            input=frames, capture_output=True, timeout=20)
    stream = io.BytesIO(result.stdout)
    replies = []
    while line := stream.readline():
        if not line.startswith(b'Content-Length: '):
            raise ValueError('engine emitted invalid LSP framing')
        size = int(line.split(b':', 1)[1])
        if stream.readline().strip():
            raise ValueError('missing LSP header separator')
        replies.append(json.loads(stream.read(size)))
    cases = []
    for name, code, diagnostic, line, character in CASES:
        diagnostics = [d for reply in replies
            if reply.get('method') == 'textDocument/publishDiagnostics'
            # lit-test resolves test:/// into its platform's clangd-test root.
            and reply['params']['uri'].endswith(f'/{name}.cpp')
            for d in reply['params']['diagnostics'] if d.get('code') == diagnostic]
        position = {'line': line, 'character': character}
        expected = {'start': position, 'end': position}
        cases.append({'id': name, 'text': code, 'expected_range': expected,
                      'diagnostics': diagnostics,
                      'pass': len(diagnostics) == 1 and diagnostics[0]['range'] == expected})
    shutdown = any(r.get('id') == 1 and r.get('result', 'missing') is None for r in replies)
    digest = hashlib.sha256()
    with engine.open('rb') as binary:
        for chunk in iter(lambda: binary.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'outcome': 'pass' if result.returncode == 0 and shutdown
            and all(c['pass'] for c in cases) else 'error',
            'engine_sha256': digest.hexdigest(),
            'exit_code': result.returncode, 'shutdown_reply': shutdown,
            'cases': cases, 'raw_replies': replies,
            'stderr': result.stderr.decode(errors='replace')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = probe(args.engine)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'outcome': result['outcome'], 'cases':
                     {c['id']: c['pass'] for c in result['cases']}}))
    return int(result['outcome'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
