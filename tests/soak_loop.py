#!/usr/bin/env python3
"""Kill/restart lifecycle loop over a modules project (soak job).

Run: %python soak_loop.py <clangd> <project> [--cycles N]

Each cycle: start clangd, open Use.cpp, request a completion, then either let
it finish or SIGKILL it mid-flight (before the reply). A killed clangd may
leave module-cache locks or copy-on-read temporaries behind — the next cycle
must still answer, which is what the stale-lock and temp-cleanup patches
guarantee. Exits non-zero if any cycle fails to produce a completion.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time

args = sys.argv[1:]
clangd = os.path.abspath(args[0])
project = os.path.abspath(args[1])
cycles = int(args[args.index("--cycles") + 1]) if "--cycles" in args else 10

use = os.path.join(project, "Use.cpp")
uri = "file://" + use
base = open(use).read()

def one_cycle(i, kill_mid):
    proc = subprocess.Popen(
        [clangd, "--experimental-modules-support",
         f"--compile-commands-dir={project}", "--background-index=false",
         "--pretty=false", "-j=2"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    resp = {}
    def reader():
        f = proc.stdout
        while True:
            headers = {}
            line = f.readline()
            if not line:
                break
            while line not in (b"\r\n", b"\n"):
                k, _, v = line.decode().partition(":")
                headers[k.strip().lower()] = v.strip()
                line = f.readline()
            n = int(headers.get("content-length", 0))
            try:
                m = json.loads(f.read(n))
                if "id" in m:
                    resp[m["id"]] = m
            except Exception:
                pass
    threading.Thread(target=reader, daemon=True).start()

    _id = 0
    def send(method, params=None, notify=False):
        nonlocal _id
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            _id += 1
            msg["id"] = _id
        data = json.dumps(msg).encode()
        proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        proc.stdin.flush()
        return None if notify else _id

    send("initialize", {"processId": os.getpid(), "rootUri": "file://" + project,
                        "capabilities": {}})
    end = time.time() + 120
    while time.time() < end and 1 not in resp:
        time.sleep(0.02)
    send("initialized", {}, notify=True)
    send("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "cpp",
                                                   "version": 1, "text": base}}, notify=True)
    rid = send("textDocument/completion",
               {"textDocument": {"uri": uri},
                "position": {"line": base.count("\n") - 2, "character": 4}})
    if kill_mid:
        time.sleep(0.05)
        proc.send_signal(signal.SIGKILL)
        return True, "killed"
    end = time.time() + 120
    while time.time() < end and rid not in resp:
        time.sleep(0.02)
    ok = rid in resp
    try:
        proc.stdin.close()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    return ok, "replied" if ok else "timeout"

failures = 0
for i in range(cycles):
    kill = (i % 3 == 2)  # every third cycle dies mid-flight
    ok, how = one_cycle(i, kill)
    print(f"soak_loop: cycle {i+1}/{cycles} {'kill' if kill else 'clean'} -> {how}")
    if not ok:
        failures += 1

print(f"soak_loop: {cycles - failures}/{cycles} cycles answered")
sys.exit(1 if failures else 0)
