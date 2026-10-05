#!/usr/bin/env python3
"""Acceptance probe: drives a language server on a real project with an
injected completion point. Generalizes the qt probe for the acceptance
matrix (qt-demo / mcppls / mcpp / ...).

Usage:
  %python accept.py <server-cmd...> -- --project <dir> --file <rel> \
      --marker <line-prefix> --pa <prefix> [--pb <prefix>] \
      [--rounds N] [--out file.json]

didOpen carries the file content with `<marker>\n\n<pa>` injected after the
marker line; each round alternates the injected prefix pa/pb via didChange
(body-only edits; the preamble stays valid) and times a completion request
at the end of the injected prefix.
"""
import json
import os
import subprocess
import sys
import threading
import time

args = sys.argv[1:]
split = args.index("--")
SERVER = args[:split]
rest = args[split + 1:]

def opt(name, default=None):
    return rest[rest.index(name) + 1] if name in rest else default

project = os.path.abspath(opt("--project"))
relfile = opt("--file")
marker = opt("--marker")
pa = opt("--pa")
pb = opt("--pb", pa)
rounds = int(opt("--rounds", "12"))
out = opt("--out")

path = os.path.join(project, relfile)
raw = open(path, encoding="utf-8").read()
assert marker in raw, f"marker {marker!r} not in {path}"
inj_a = raw.replace(marker, marker + "\n\n" + pa, 1)
inj_b = raw.replace(marker, marker + "\n\n" + pb, 1)
assert inj_a != raw

uri = "file://" + path
proc = subprocess.Popen(SERVER, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL)

responses = {}
lock = threading.Lock()
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
                with lock:
                    responses[m["id"]] = m
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

def wait_id(rid, t=180):
    end = time.time() + t
    while time.time() < end:
        with lock:
            m = responses.get(rid)
            if m and ("result" in m or "error" in m):
                return m
        time.sleep(0.005)
    raise SystemExit(f"accept: timeout on id {rid}")

rid = send("initialize", {"processId": os.getpid(),
                          "rootUri": "file://" + project, "capabilities": {}})
wait_id(rid)
send("initialized", {}, notify=True)

version = 0
lat = []
for i in range(rounds):
    version += 1
    text = inj_a if i % 2 == 0 else inj_b
    params = {"textDocument": {"uri": uri, "languageId": "cpp",
                               "version": version, "text": text}}
    if i > 0:
        params = {"textDocument": {"uri": uri, "version": version},
                  "contentChanges": [{"text": text}]}
    send("textDocument/didOpen" if i == 0 else "textDocument/didChange",
         params, notify=True)
    time.sleep(0.35)
    t0 = time.time()
    prefix = pa if i % 2 == 0 else pb
    line_no = text[:text.index(prefix)].count("\n")
    rid = send("textDocument/completion",
               {"textDocument": {"uri": uri},
                "position": {"line": line_no, "character": len(prefix)}})
    wait_id(rid)
    lat.append((time.time() - t0) * 1000)

send("shutdown", None)
send("exit", None, notify=True)
proc.stdin.close()
try:
    proc.wait(timeout=20)
except subprocess.TimeoutExpired:
    proc.kill()

def pct(xs, p):
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return round(xs[k], 1)

res = {"server": SERVER, "project": project, "file": relfile, "rounds": rounds,
       "cold_ms": round(lat[0], 1), "p50_ms": pct(lat[1:], 50),
       "p95_ms": pct(lat[1:], 95), "max_ms": round(max(lat), 1),
       "all_ms": [round(x, 1) for x in lat]}
print(json.dumps(res, indent=2))
if out:
    open(out, "w").write(json.dumps(res, indent=2))
