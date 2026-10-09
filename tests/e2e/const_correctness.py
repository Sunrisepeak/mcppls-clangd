#!/usr/bin/env python3
"""Check raw clangd and clang-tidy const suggestions against compilable fixes."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import time

SOURCE = r'''#include <array>
#include <ranges>
struct Number { int value; };
int operator|(const Number &n, int mask) { return n.value | mask; }
void check(const std::array<int, 4> &source) {
  auto filtered = source | std::views::filter([](int v) { return v > 0; });
  auto transformed = filtered | std::views::transform([](int v) { return v * 2; });
  for (const int value : transformed) (void)value;
  auto safe = source | std::views::transform([](int v) { return v * 2; });
  auto safeAgain = safe | std::views::transform([](int v) { return v + 1; });
  for (const int value : safeAgain) (void)value;
  auto reference = std::ranges::ref_view(filtered);
  for (const int value : reference) (void)value;
  std::array<int, 4> mutableBase{};
  for (int &value : mutableBase) value = 1;
  Number input{3};
  (void)(input | 1);
  int answer = 42;
  (void)answer;
}
'''
EXPECTED = {'safe', 'safeAgain', 'reference', 'input', 'answer'}
WARNING = re.compile(r"variable '([^']+)' .*can be declared 'const'", re.IGNORECASE)


def raw_diagnostics(engine, root, source, text):
    proc = subprocess.Popen([str(engine), '--sync', '--background-index=false',
                             '--enable-config', '--clang-tidy'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    messages = queue.Queue()
    logs = []

    def read():
        try:
            while True:
                length = 0
                while True:
                    line = proc.stdout.readline()
                    if not line:
                        raise EOFError('clangd closed stdout')
                    if line in (b'\n', b'\r\n'):
                        break
                    if line.lower().startswith(b'content-length:'):
                        length = int(line.split(b':', 1)[1])
                messages.put(json.loads(proc.stdout.read(length)))
        except Exception as exc:
            messages.put(exc)

    def stderr():
        for line in proc.stderr:
            logs.append(line.decode(errors='replace'))

    readers = [threading.Thread(target=read, daemon=True),
               threading.Thread(target=stderr, daemon=True)]
    for thread in readers:
        thread.start()
    deadline = time.monotonic() + 20
    sequence = 0

    def send(method, params=None, notify=False):
        nonlocal sequence
        sequence += 1
        message = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if not notify:
            message['id'] = sequence
        payload = json.dumps(message).encode()
        proc.stdin.write(b'Content-Length: %d\r\n\r\n' % len(payload) + payload)
        proc.stdin.flush()
        return sequence

    def wait(predicate):
        while True:
            message = messages.get(timeout=max(.001, deadline-time.monotonic()))
            if isinstance(message, Exception):
                raise message
            if predicate(message):
                return message

    try:
        request = send('initialize', {'rootUri': root.as_uri(), 'capabilities': {}})
        wait(lambda message: message.get('id') == request)
        send('initialized', {}, True)
        send('textDocument/didOpen', {'textDocument': {
            'uri': source.as_uri(), 'languageId': 'cpp', 'version': 1, 'text': text}}, True)
        diagnostics = wait(lambda message: message.get('method') == 'textDocument/publishDiagnostics'
                           and message['params'].get('uri') == source.as_uri())['params']['diagnostics']
        request = send('shutdown')
        wait(lambda message: message.get('id') == request)
        send('exit', None, True)
        proc.stdin.close()
        proc.wait(timeout=max(.001, deadline-time.monotonic()))
        if proc.returncode:
            raise RuntimeError('clangd failed: ' + ''.join(logs))
        return diagnostics
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        for thread in readers:
            thread.join(timeout=1)
        proc.stdout.close()
        proc.stderr.close()
        (root / 'clangd.log').write_text(''.join(logs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang-tidy', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    args = parser.parse_args()
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'range.cpp'
    source.write_text(SOURCE)
    engine, tidy, clang = args.engine.resolve(), args.clang_tidy.resolve(), args.clang.resolve()
    (root / '.clang-tidy').write_text("Checks: '-*,misc-const-correctness'\n")
    (root / '.clangd').write_text('Diagnostics:\n  ClangTidy:\n    FastCheckFilter: None\n')
    (root / 'compile_commands.json').write_text(json.dumps([{
        'directory': str(root), 'file': str(source),
        'arguments': [str(clang), '-std=c++20', '-c', str(source)]}]))
    diagnostics = raw_diagnostics(engine, root, source, SOURCE)
    observed = {match[1] for diag in diagnostics
                if (match := WARNING.search(diag['message']))}
    if observed != EXPECTED or any(diag.get('severity') == 1 for diag in diagnostics):
        raise RuntimeError(f'raw clangd suggestions {observed}; expected {EXPECTED}; {diagnostics}')
    completed = subprocess.run([str(tidy), str(source), '-fix', '--', '-std=c++20'],
                               text=True, capture_output=True, timeout=20)
    suggestions = set(WARNING.findall(completed.stdout + completed.stderr))
    if completed.returncode or suggestions != EXPECTED:
        raise RuntimeError('clang-tidy disagreement: ' + completed.stdout + completed.stderr)
    compilation = subprocess.run([str(clang), '-std=c++20', '-fsyntax-only', str(source)],
                                 text=True, capture_output=True, timeout=20)
    if compilation.returncode:
        raise RuntimeError('const fixes do not compile: ' + compilation.stderr)
    report = {'ok': True, 'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'tidy_sha256': hashlib.sha256(tidy.read_bytes()).hexdigest(),
              'raw_clangd_diagnostics': diagnostics, 'suggested_variables': sorted(observed),
              'all_const_fixes_compile': True}
    (root / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'ok': True, 'suggested_variables': sorted(observed),
                      'all_const_fixes_compile': True}))


if __name__ == '__main__':
    main()
