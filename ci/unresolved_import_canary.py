#!/usr/bin/env python3
"""An import that resolves to nothing is reported, and the file keeps answering.

Self-contained: a module unit imports a module no unit provides, and a file imports that unit and
another unknown module. Building such a module unit is what stalls clangd 23.1 (with it, every file
importing it). Exits 0 when the file's diagnostics arrive and a request on it is answered, 1 when
either times out (the upstream defect), 2 when clangd gives no usable answer.
"""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

UNIT = 'export module a;\nimport nowhere;\nexport int fa() { return 1; }\n'
MAIN = 'import a;\nimport missing;\nint main() { return fa(); }\n'


def send(proc, message):
    body = json.dumps(message).encode()
    proc.stdin.write(b'Content-Length: %d\r\n\r\n' % len(body) + body)
    proc.stdin.flush()


def reader(stream, out):
    while True:
        length = None
        while True:
            line = stream.readline()
            if not line:
                out.put(None)
                return
            line = line.strip()
            if not line:
                break
            if line.lower().startswith(b'content-length:'):
                length = int(line.split(b':', 1)[1])
        out.put(json.loads(stream.read(length)))


def answers(engine, timeout):
    """0, 1 or 2 as the module docstring says, and what happened."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        (root / 'a.cppm').write_text(UNIT)
        main = root / 'main.cpp'
        main.write_text(MAIN)
        (root / 'compile_commands.json').write_text(json.dumps([
            {'directory': str(root), 'file': str(root / name),
             'arguments': ['clang++', '-std=c++20', '-c', str(root / name)]}
            for name in ('a.cppm', 'main.cpp')]))
        proc = subprocess.Popen([str(engine), '--experimental-modules-support', '--background-index=false',
                                 '--log=error'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, cwd=tmp)
        messages = queue.Queue()
        threading.Thread(target=reader, args=(proc.stdout, messages), daemon=True).start()

        def wait_for(matches):
            while True:
                message = messages.get(timeout=timeout)
                if message is None:
                    return None
                if matches(message):
                    return message

        try:
            send(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                        'params': {'rootUri': root.as_uri(), 'capabilities': {}}})
            send(proc, {'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
            send(proc, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {
                'uri': main.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': MAIN}}})
            # By name: a URI's drive letter or /private prefix may be spelled differently.
            published = wait_for(lambda m: m.get('method') == 'textDocument/publishDiagnostics'
                                 and m['params'].get('uri', '').endswith('/main.cpp'))
            if published is None:
                return 2, 'clangd exited before publishing diagnostics'
            send(proc, {'jsonrpc': '2.0', 'id': 2, 'method': 'textDocument/documentSymbol',
                        'params': {'textDocument': {'uri': main.as_uri()}}})
            answered = wait_for(lambda m: m.get('id') == 2)
            if answered is None or 'result' not in answered:
                return 2, f'no answer to documentSymbol: {answered}'
            names = [d.get('message', '') for d in published['params']['diagnostics']]
            return 0, f'{len(names)} diagnostic(s), documentSymbol answered: {names}'
        except queue.Empty:
            return 1, f'no answer within {timeout} s'
        finally:
            proc.kill()
            proc.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    status, what = answers(args.engine.resolve(), args.timeout)
    print(f'unresolved import canary: {what}')
    return status


if __name__ == '__main__':
    sys.exit(main())
