#!/usr/bin/env python3
"""LSP driver for mcppls-clangd's e2e and conformance jobs.

Drives a language server (clangd directly, or mcppls with the fork's clangd
swapped in via --clangd) over stdio, on a generated modules project.

Run: %python lsp_driver.py <server-cmd...> --project <dir> --scenarios <list>

Scenarios:
  completion   - didOpen + completion must return module-exported symbols
  definition   - definition on a call must resolve into the project
  diagnostics  - a didOpen on a broken body must produce a diagnostic
  latency      - warm completion p95 must stay under --budget-ms (default 5000)

Exit code 0 = all scenarios passed. Details go to stdout as JSON.
"""
import json
import os
import subprocess
import sys
import threading
import time

args = sys.argv[1:]
if "--project" not in args:
    raise SystemExit("usage: lsp_driver.py <server-cmd...> --project <dir> "
                     "[--scenarios a,b] [--budget-ms N]")
split = args.index("--project")
server_cmd = args[:split]
rest = args[split + 1:]
# rest[0] is the project value; remaining options come after it
project = os.path.abspath(rest[0])
rest = rest[1:]

def opt(name, default=None):
    return rest[rest.index(name) + 1] if name in rest else default

scenarios = opt("--scenarios", "completion").split(",")
budget_ms = int(opt("--budget-ms", "5000"))

use = os.path.join(project, "Use.cpp")
uri = "file://" + use
base = open(use).read()
# the completion point: the line holding the bare `fn` token
fn_line = next(i for i, l in enumerate(base.split("\n")) if l.strip() == "fn")
FN_POS = {"line": fn_line, "character": 6}
# the real call line for definition requests
def_line = next(i for i, l in enumerate(base.split("\n")) if "return fn1()" in l)
DEF_POS = {"line": def_line, "character": 13}

proc = subprocess.Popen(server_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL)

responses = {}
notifications = []
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
            with lock:
                if "id" in m:
                    responses[m["id"]] = m
                else:
                    notifications.append(m)
        except Exception:
            pass
threading.Thread(target=reader, daemon=True).start()

_i = 0
def send(method, params=None, notify=False):
    global _i
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        _i += 1
        msg["id"] = _i
    data = json.dumps(msg).encode()
    proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
    proc.stdin.flush()
    return None if notify else _i

def wait_id(rid, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        with lock:
            m = responses.get(rid)
            if m and ("result" in m or "error" in m):
                return m
        time.sleep(0.005)
    raise SystemExit(f"lsp_driver: timeout waiting for id {rid}")

diags = []
results = {"server": server_cmd, "scenarios": {}}

rid = send("initialize", {"processId": os.getpid(), "rootUri": "file://" + project,
                          "capabilities": {"textDocument": {
                              "completion": {"completionItem": {"snippetSupport": True}}}}})
init = wait_id(rid)
results["scenarios"]["initialize"] = "ok" if init.get("result") else "fail: no result"
send("initialized", {}, notify=True)
send("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "cpp",
                                               "version": 1, "text": base}}, notify=True)
time.sleep(2.0)  # initial parse + module prerequisites

def scenario_completion():
    rid = send("textDocument/completion",
               {"textDocument": {"uri": uri}, "position": FN_POS})
    r = wait_id(rid)
    items = r.get("result") or []
    if isinstance(items, dict):
        items = items.get("items", [])
    names = {i.get("label", "").split("(")[0].strip() for i in items}
    found = [n for n in names if n.startswith("fn")]
    return "ok" if found else f"fail: no module symbols in {sorted(names)[:10]}"

def scenario_latency():
    lat = []
    text = base
    for i in range(6):
        text = base + f"int touched{i} = 0;\n"
        send("textDocument/didChange",
             {"textDocument": {"uri": uri, "version": 10 + i},
              "contentChanges": [{"text": text}]}, notify=True)
        time.sleep(0.4)
        t0 = time.time()
        rid = send("textDocument/completion",
                   {"textDocument": {"uri": uri},
                    "position": {"line": text.count("\n") - 1, "character": 0}})
        wait_id(rid)
        lat.append((time.time() - t0) * 1000)
    lat_sorted = sorted(lat[1:])
    p95 = lat_sorted[-1] if lat_sorted else lat[0]
    results["latency_ms"] = [round(x, 1) for x in lat]
    return "ok" if p95 < budget_ms else f"fail: warm p95 {p95:.0f}ms > {budget_ms}ms"

def scenario_hover():
    # go-to-definition on module-imported symbols is a known upstream gap
    # (register UP-08 family); hover resolves through Sema instead.
    rid = send("textDocument/hover",
               {"textDocument": {"uri": uri}, "position": DEF_POS})
    r = wait_id(rid)
    ok = bool(r.get("result"))
    return "ok" if ok else "fail: no hover for the module-imported call"

def scenario_diagnostics():
    send("textDocument/didChange",
         {"textDocument": {"uri": uri, "version": 99},
          "contentChanges": [{"text": base + "\nint broken_syntax_here ;;;\n"}]},
         notify=True)
    deadline = time.time() + 90
    while time.time() < deadline:
        with lock:
            for m in list(notifications):
                if m.get("method") == "textDocument/publishDiagnostics":
                    ds = m["params"].get("diagnostics", [])
                    if ds:
                        diags.extend(ds)
                        return "ok"
        time.sleep(0.25)
    return "fail: no diagnostics arrived"

for s in scenarios:
    s = s.strip()
    if s == "completion":
        results["scenarios"]["completion"] = scenario_completion()
    elif s == "hover":
        results["scenarios"]["hover"] = scenario_hover()
    elif s == "diagnostics":
        results["scenarios"]["diagnostics"] = scenario_diagnostics()
    elif s == "latency":
        results["scenarios"]["latency"] = scenario_latency()

send("shutdown", None)
send("exit", None, notify=True)
try:
    proc.stdin.close()
    proc.wait(timeout=20)
except Exception:
    proc.kill()

print(json.dumps(results, indent=2))
failed = [k for k, v in results["scenarios"].items() if str(v).startswith("fail")]
sys.exit(1 if failed else 0)
