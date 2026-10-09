#!/usr/bin/env python3
"""A view whose const begin() is not viable is not suggested 'const' (misc-const-correctness).

Self-contained: the view is declared in the source, so no standard library is needed. `Plain` is
the positive control; the check holds when it alone is reported. Exits 0 when it holds, 1 when the
view is reported too (the upstream defect), 2 when clangd gives no usable answer.
"""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

SOURCE = '''template <class T> struct Filter {
  T *First, *Last;
  T *begin() { return First; }
  T *end() { return Last; }
  T *begin() const requires(sizeof(T) == 0) { return First; }
  T *end() const requires(sizeof(T) == 0) { return Last; }
};
int sum(int *First, int *Last) {
  Filter<int> View{First, Last};
  int Total = 0;
  for (int Value : View)
    Total += Value;
  int Plain = 1;
  return Total + Plain;
}
'''


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


def flagged(engine, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # misc-const-correctness is a slow check, which clangd runs only without a fast-check filter.
        (root / '.clangd').write_text('Diagnostics:\n  ClangTidy:\n    Add: [misc-const-correctness]\n'
                                      '    FastCheckFilter: None\n')
        (root / 'compile_flags.txt').write_text('-std=c++20\n')
        source = root / 'views.cpp'
        source.write_text(SOURCE)
        proc = subprocess.Popen([str(engine), '--sync', '--background-index=false', '--enable-config',
                                 '--clang-tidy', '--log=error'], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=tmp)
        messages = queue.Queue()
        threading.Thread(target=reader, args=(proc.stdout, messages), daemon=True).start()
        try:
            send(proc, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                        'params': {'rootUri': root.as_uri(), 'capabilities': {}}})
            send(proc, {'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
            send(proc, {'jsonrpc': '2.0', 'method': 'textDocument/didOpen', 'params': {'textDocument': {
                'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': SOURCE}}})
            while True:
                message = messages.get(timeout=timeout)
                if message is None:
                    return None
                # The configuration's own warnings are published for .clangd first.
                # (by name: a URI's drive letter or /private prefix may be spelled differently).
                if (message.get('method') == 'textDocument/publishDiagnostics'
                        and message['params'].get('uri', '').endswith('/views.cpp')):
                    names = set()
                    for diagnostic in message['params']['diagnostics']:
                        if diagnostic.get('code') == 'misc-const-correctness':
                            for name in ('View', 'Plain'):
                                if f"'{name}'" in diagnostic.get('message', ''):
                                    names.add(name)
                    return names
        except queue.Empty:
            return None
        finally:
            proc.kill()
            proc.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    names = flagged(args.engine.resolve(), args.timeout)
    if names is None or 'Plain' not in names:
        print(f'const views canary: no usable answer ({names})')
        return 2
    print(f'const views canary: reported {sorted(names)}')
    return 1 if 'View' in names else 0


if __name__ == '__main__':
    sys.exit(main())
