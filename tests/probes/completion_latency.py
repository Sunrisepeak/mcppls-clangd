#!/usr/bin/env python3
"""Measures completion latency against a clangd binary over LSP.

Run: %python completion_latency.py <clangd> <project-dir> <rounds> [out.json]

Scenario: open Use.cpp (which imports the project's modules), then repeat
`rounds` times: a body-only didChange (preamble stays valid) followed by a
blocking completion request. Reports cold (first) and warm percentiles in
milliseconds as JSON on stdout, and exits 0.

This is the probe behind the UP-25 gate: the module prerequisite validation
runs on every preamble-compatibility check, so warm completion latency is
what the validation memo buys.
"""
import atexit
import json
from pathlib import Path
import os
import statistics
import subprocess
import sys
import threading
import time

clangd = os.path.abspath(sys.argv[1])
project = os.path.abspath(sys.argv[2])
rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 30
if rounds < 2:
    raise SystemExit("need cold and at least one warm request")
out_path = sys.argv[4] if len(sys.argv) > 4 else None
stderr_log = sys.argv[5] if len(sys.argv) > 5 else os.devnull

use = os.path.join(project, "Use.cpp")
uri = Path(use).as_uri()
base = open(use).read()
# a body-only marker edit; the import block stays untouched
edited = base.replace("int main() {", "int touched = 0;\nint main() {", 1)
assert edited != base, "marker line not found in Use.cpp"

proc = subprocess.Popen(
    [clangd, "--experimental-modules-support", f"--compile-commands-dir={project}",
     "--background-index=false", "--header-insertion=never", "--pretty=false",
     "-j=4"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(stderr_log, "w"))

def cleanup():
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)
atexit.register(cleanup)

response_q = []
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
        body = f.read(n)
        try:
            response_q.append(json.loads(body))
        except Exception:
            pass
threading.Thread(target=reader, daemon=True).start()

_id = 0
def send(method, params=None, notify=False):
    global _id
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

def wait_id(rid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        for m in list(response_q):
            if m.get("id") == rid and ("result" in m or "error" in m):
                return m
        time.sleep(0.005)
    raise SystemExit(f"completion_latency: timeout waiting for id {rid}")

rid = send("initialize", {"processId": os.getpid(), "rootUri": Path(project).as_uri(),
                          "capabilities": {}})
wait_id(rid)
send("initialized", {}, notify=True)
send("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "cpp",
                                               "version": 1, "text": base}}, notify=True)

latencies = []
version = 1
for i in range(rounds):
    version += 1
    text = base if i % 2 == 0 else edited
    send("textDocument/didChange", {"textDocument": {"uri": uri, "version": version},
                                    "contentChanges": [{"text": text}]}, notify=True)
    time.sleep(0.35)  # let the didChange settle, like a typing cadence
    t0 = time.time()
    rid = send("textDocument/completion",
               {"textDocument": {"uri": uri},
                "position": {"line": next(n for n, line in enumerate(text.splitlines()) if line.strip() == "fn"), "character": 6}})
    response = wait_id(rid)
    items = response.get("result") or []
    if isinstance(items, dict):
        items = items.get("items", [])
    if not any(item.get("filterText", item.get("label", "")).split("(")[0].strip() == "fn1" for item in items):
        raise SystemExit(f"round {i}: completion lacks required module symbol fn1")
    latencies.append((time.time() - t0) * 1000.0)

proc.stdin.close()
proc.wait(timeout=30)

def pct(xs, p):
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return round(xs[k], 1)

result = {
    "clangd": clangd,
    "project": project,
    "rounds": rounds,
    "cold_ms": round(latencies[0], 1),
    "p50_ms": pct(latencies[1:], 50) if len(latencies) > 1 else latencies[0],
    "p95_ms": pct(latencies[1:], 95) if len(latencies) > 1 else latencies[0],
    "max_ms": round(max(latencies), 1),
    "all_ms": [round(x, 1) for x in latencies],
}
print(json.dumps(result, indent=2))
if out_path:
    with open(out_path, "w") as F:
        json.dump(result, F, indent=2)
