#!/usr/bin/env python3
"""Readers of a shared BMI cache: in the owned cache a reader is given the published generation under a
lease of its own and no copy is made; on the portable path each reader's copy is protected while it lives
and reclaimed after its engine is killed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import sys
import signal
import subprocess
import threading
import time


class Engine:
    def __init__(self, binary, root, cache_mode="legacy", extra=()):
        self.root = root
        cache_flags = ['--modules-builder-owned-cache-payload-mib=0'] if cache_mode == 'legacy' else []
        self.proc = subprocess.Popen([str(binary), '--experimental-modules-support',
            '--background-index=false', '--modules-builder-versioned-gc-threshold-seconds=0', '-j=2', *cache_flags, *extra],
            cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=os.name != 'nt')
        self.replies = queue.Queue()
        self.logs = bytearray()
        self.raw = []
        self.rid = 0
        self.threads = [threading.Thread(target=self.read, daemon=True),
                        threading.Thread(target=self.stderr, daemon=True)]
        for thread in self.threads:
            thread.start()

    def stderr(self):
        while chunk := self.proc.stderr.read1(4096):
            if len(self.logs) < 1048576:
                self.logs.extend(chunk[:1048576-len(self.logs)])

    def read(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        raise EOFError('engine closed stdout')
                    if line in (b'\n', b'\r\n'):
                        break
                    key, value = line.decode().split(':', 1)
                    headers[key.lower()] = value.strip()
                self.replies.put(json.loads(self.proc.stdout.read(int(headers['content-length']))))
        except Exception as error:
            self.replies.put(error)

    def send(self, method, params=None, notify=False):
        self.rid += 1
        msg = {'jsonrpc': '2.0', 'method': method, 'params': params}
        if not notify:
            msg['id'] = self.rid
        data = json.dumps(msg).encode()
        self.proc.stdin.write(b'Content-Length: %d\r\n\r\n' % len(data) + data)
        self.proc.stdin.flush()
        if notify:
            return None
        deadline = time.monotonic() + 15
        while True:
            reply = self.replies.get(timeout=max(0.001, deadline-time.monotonic()))
            if isinstance(reply, Exception):
                raise reply
            if reply.get('id') == self.rid:
                self.raw.append({'method': method, 'reply': reply})
                if 'error' in reply:
                    raise RuntimeError(reply['error'])
                return reply['result']
            if time.monotonic() >= deadline:
                raise TimeoutError(method)

    def ready(self):
        self.send('initialize', {'rootUri': self.root.as_uri(), 'capabilities': {}})
        self.send('initialized', {}, notify=True)
        source = self.root / 'Use.cpp'
        doc = {'uri': source.as_uri()}
        self.send('textDocument/didOpen', {'textDocument': {**doc, 'languageId': 'cpp',
            'version': 1, 'text': source.read_text()}}, notify=True)
        symbols = self.send('textDocument/documentSymbol', {'textDocument': doc})
        if not any(s['name'] == 'marker' for s in symbols):
            raise RuntimeError('AST barrier lacks marker')
        items = self.send('textDocument/completion', {'textDocument': doc,
            'position': {'line': 1, 'character': 15}})
        if isinstance(items, dict):
            items = items.get('items', [])
        if not any(i.get('filterText') == 'fn1' and i.get('kind') == 3 for i in items):
            raise RuntimeError('missing semantic module function')

    def stop(self, kill=False):
        try:
            if not kill and self.proc.poll() is None:
                self.send('shutdown')
                self.send('exit', notify=True)
                self.proc.stdin.close()
                self.proc.wait(timeout=15)
                if self.proc.returncode != 0:
                    raise RuntimeError('unclean shutdown')
        finally:
            if os.name == 'nt':
                if self.proc.poll() is None:
                    subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'],
                                   capture_output=True, check=True, timeout=15)
            else:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.proc.wait(timeout=15)
            for thread in self.threads:
                thread.join(timeout=2)
            if any(t.is_alive() for t in self.threads):
                raise RuntimeError('engine left inherited pipes')
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                stream.close()


def lease_holders(lease, pids):
    """The engines among pids (and their workers) that hold the file lease open."""
    lease = os.path.realpath(lease)
    if sys.platform.startswith('linux'):
        family = set(pids)
        for entry in os.listdir('/proc'):
            if entry.isdigit():
                try:
                    if int(Path(f'/proc/{entry}/stat').read_text().rsplit(')', 1)[1].split()[1]) in family:
                        family.add(int(entry))
                except (OSError, IndexError, ValueError):
                    pass
        held = []
        for pid in sorted(family):
            try:
                if any(os.path.realpath(f'/proc/{pid}/fd/{fd}') == lease for fd in os.listdir(f'/proc/{pid}/fd')):
                    held.append(pid)
            except OSError:
                pass
        return held
    # macOS: the system's lsof names the processes that have the file open.
    found = subprocess.run(['lsof', '-t', lease], capture_output=True, text=True)
    return sorted(int(p) for p in found.stdout.split() if p.isdigit())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--clang', type=Path, required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    # auto: the cache the engine reports it uses for this directory ("Module cache <root>: owned"
    # or "...: a copy of each BMI for each reader"); legacy turns the owned cache off.
    parser.add_argument('--cache-mode', choices=['auto', 'legacy', 'owned'], default='auto')
    args = parser.parse_args()
    engine, clang = args.engine.resolve(), args.clang.resolve()
    if os.name == 'nt':
        engine, clang = engine.with_suffix('.exe'), clang.with_suffix('.exe')
    root = args.workdir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name, text in [('A.cppm', 'export module A;\nexport int fn1(){return 1;}\n'),
                       ('Use.cpp', 'import A;\nint marker = fn1();\n')]:
        (root / name).write_text(text)
    (root / 'compile_commands.json').write_text(json.dumps([
        {'directory': str(root), 'file': str(root/name),
         'arguments': [str(clang), '-std=c++20', '-c', str(root/name)]}
        for name in ('A.cppm', 'Use.cpp')]))
    cache = root / '.cache/clangd/modules'
    clients = []
    mode = args.cache_mode
    report = {'engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
              'passed': False, 'cache_mode': mode, 'checks': {}}
    try:
        seed = Engine(engine, root, mode); clients.append(seed); seed.ready(); seed.stop()
        logs = seed.logs.decode(errors='replace')
        if mode == 'auto':
            selected = re.search(r'Module cache .+: (owned|a copy of each BMI for each reader)', logs)
            mode = 'owned' if selected and selected[1] == 'owned' else 'legacy'
            report['cache_mode'] = mode
            report['cache_reported'] = selected[0] if selected else None
        if mode == 'owned':
            match = re.search(r'Built module A to (.+)', logs)
            if not match:
                raise RuntimeError('missing fresh owned publication event')
            published = Path(match[1].strip())
            if '.owned-payload-v1' not in published.parts or published.name != 'payload.pcm':
                raise RuntimeError('default owned admission did not publish its managed generation')
        else:
            found = list(cache.rglob('A.pcm'))
            if len(found) != 1:
                raise RuntimeError('expected one legacy A publication')
            published = found[0]
        report['published'] = str(published)

        # Deliberately ancient atime proves GC does not trust timestamps.
        before = published.stat()
        os.utime(published, ns=(0, before.st_mtime_ns))
        def unchanged():
            now = published.stat()
            return now.st_ino == before.st_ino and now.st_mtime_ns == before.st_mtime_ns

        if mode == 'owned':
            # A reader is given the stable generation where it was published, under a lease of its
            # own (`lease-<slot>`, an OFD lock beside the generations); no copy is made.
            slot = published.parent.name.split('-')[1]
            lease = published.parent.parent / f'lease-{slot}'
            payloads = lambda: sorted(cache.glob('.owned-payload-v1/generation-*/payload.pcm'))
            reader = Engine(engine, root, mode); clients.append(reader); reader.ready()
            report['checks']['published_identity_kept_on_reuse'] = unchanged()
            report['checks']['reused_where_published'] = (
                f'Reusing owned module A from {published}' in reader.logs.decode(errors='replace'))
            report['checks']['no_copy_made'] = payloads() == [published]
            report['checks']['reader_holds_lease'] = reader.proc.pid in lease_holders(lease, [reader.proc.pid])
            peer = Engine(engine, root, mode); clients.append(peer); peer.ready()
            report['checks']['peer_reads_the_same_generation'] = payloads() == [published]
            reader.stop(kill=True)
            collector = Engine(engine, root, mode, ['--log=verbose']); clients.append(collector); collector.ready()
            # Owned maintenance visits bounded slot batches independently of AST work; give it the
            # time it takes, never force it.
            time.sleep(6)
            report['engines'] = {'reader': reader.proc.pid, 'peer': peer.proc.pid, 'collector': collector.proc.pid}
            report['holders'] = lease_holders(lease, [peer.proc.pid, collector.proc.pid])
            report['checks']['live_readers_hold_lease'] = peer.proc.pid in report['holders']
            report['checks']['published_survives_collection'] = published.exists() and unchanged()
            report['checks']['still_no_copy'] = payloads() == [published]
        else:
            def live_copies():
                return {p: Path(str(p).removesuffix('.lease')) for p in cache.rglob('*.pcm.lease')}
            reader = Engine(engine, root, mode); clients.append(reader); reader.ready()
            report['checks']['published_identity_kept_on_reuse'] = unchanged()
            copies = live_copies()
            live = set(copies)
            if not live:
                raise RuntimeError('reused BMIs lack owner leases')
            for path in copies.values():
                stat = path.stat(); os.utime(path, ns=(0, stat.st_mtime_ns))
            peer = Engine(engine, root, mode); clients.append(peer); peer.ready()
            report['checks']['live_copy_kept'] = all(p.exists() for p in copies.values())
            report['checks']['published_identity_kept'] = unchanged()
            if not all(report['checks'].values()):
                raise RuntimeError('GC removed a live copy or rebuilt the published BMI')
            peer_copies = {p: value for p, value in live_copies().items() if p not in live}
            peer_live = set(peer_copies)
            reader.stop(kill=True)
            collector = Engine(engine, root, mode, ['--log=verbose']); clients.append(collector); collector.ready()
            report['engines'] = {'reader': reader.proc.pid, 'peer': peer.proc.pid, 'collector': collector.proc.pid}
            orphans = [p for p in live if p.exists() or copies[p].exists()]
            report['remaining'] = [str(copies[p]) for p in orphans]
            report['checks']['killed_reader_copies_reclaimed'] = not orphans
            report['checks']['other_live_reader_kept'] = bool(peer_live) and all(p.exists() and peer_copies[p].exists() for p in peer_live)
            report['checks']['published_survives_reclamation'] = published.exists() and published.stat().st_ino == before.st_ino
            report['copies'] = {'killed_reader': [str(p) for p in copies.values()], 'live_peer': [str(p) for p in peer_copies.values()]}
        report['passed'] = all(report['checks'].values())
    except Exception as error:
        report['error'] = str(error)
    finally:
        for client in reversed(clients):
            client.stop(kill=not report['passed'])
        report['raw'] = [{'responses': c.raw, 'stderr': c.logs.decode(errors='replace'),
                          'exit_code': c.proc.returncode} for c in clients]
        (root/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report['passed'], report.get('error', ''), report['checks'])
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
