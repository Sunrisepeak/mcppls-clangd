#!/usr/bin/env python3
"""warm-prime: how soon one clangd is ready in a large modules project, the first time and then with the cache it
left (mcpp design 2026-11-02 part 3 §9.4). The clangd is a native program or the ok image under okrun.

usage: warm_prime.py --label L --workdir D --out result.json [--sessions 3] [--std-args "..."] -- <clangd argv prefix...>

THE PROJECT is the module graph of the mcpp repository at the commit mcppls's ux-mcpp fixture pins
(ci/fixtures/ux-mcpp-modules.json: 304 translation units, 176 modules and the standard library), written as
sources of the same shape: each unit provides the module it provides there and imports the modules it imports
there, and calls a function of each; `import std` is `import corelib`, a module whose global module fragment holds
fourteen headers of the system's standard library, so that the module every unit imports is a large one, as the
standard library's is, and the run needs no standard library module of its own. The compile commands are
`clang++ -std=c++23 <std-args> -c <file>`, completed from the host by the engine as the system's clangd completes
them (`--std-args` states a target and an SDK, or the MSVC headers, where the host needs them).

A SESSION starts the engine in the project with the modules support on and the background index off, opens three
files (the program's main file, a module unit deep in the graph, and a test) and waits until the engine publishes
for each of them diagnostics with no error, which it does once the file's prerequisite modules are built or
reused and the file is parsed against them. Its time to READY is from the engine's start to the last of those.
The first session is COLD (no cache); `--sessions` more are WARM, each a new engine over the cache the earlier
ones left. Each records its ready time, the CPU time of the engine and every process it started (its module
workers) and their page faults --- on Linux from the kernel's record of the engine and of the programs it waited
for; elsewhere the engine's own sampled every 50 ms and each worker's processor time as the engine's log states
it, since a sample misses a worker that lives between two --- the modules built and reused, the workers' times
from the engine's log (`Module worker built ...`), and which cache the engine took (`Module cache <root>: owned` or `...: a copy of
each BMI for each reader`) and where it compiled (`Module builds: ...`). The engine's log of session N is
<workdir>/session-N-<cold|warm>.log.

Measurement version 3 brackets Linux tree reads with stable process identities, parentage and waited-child
counters. It includes reaped descendants of still-live intermediate processes and refuses an unstable sample.
`cpu_sample` records this boundary and its observation duration; version-2 CPU readings are not comparable.
`page_faults` remains a readiness diagnostic. `waited_usage` records POSIX kernel totals after the engine ends: its complete lifetime and
descendants it waited for, including shutdown. It excludes this Python harness and descendants reparented
elsewhere. Its minor plus major faults form `complete_page_faults`, the fault acceptance metric on POSIX.
This includes shutdown and has a different boundary from readiness; version 1 reports are not comparable.
"""
import argparse, json, os, re, statistics, subprocess, sys, threading, time

import psutil
from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION, LinuxTreeUsage, WaitedUsage, ready_cpu

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True)
ap.add_argument("--workdir", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--sessions", type=int, default=3, help="warm sessions after the cold one")
ap.add_argument("--std-args", default="", help="compile arguments the host needs for its standard library")
ap.add_argument("--timeout", type=int, default=1200, help="seconds a session may take to be ready")
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
prefix = [os.path.abspath(c) if os.path.exists(c) else c for c in a.cmd if c != "--"]
ROOT = os.path.dirname(os.path.abspath(__file__))
SHAPE = json.load(open(os.path.join(ROOT, "fixtures", "ux-mcpp-modules.json")))
HEADERS = ["algorithm", "array", "cstdint", "functional", "map", "memory", "optional", "set", "string",
           "string_view", "unordered_map", "utility", "variant", "vector"]


def ident(module):
    return re.sub(r"[^A-Za-z0-9_]", "_", module)


def module_of(name):
    return name.split(":")[0]


# ---- the project ------------------------------------------------------------------------------------------------

def write_project(at):
    os.makedirs(at, exist_ok=True)
    std_args = a.std_args.split()
    files = []

    def put(rel, text):
        path = os.path.join(at, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="\n") as f:
            f.write(text)
        files.append(rel)

    put("corelib/corelib.cppm", "module;\n" + "".join(f"#include <{h}>\n" for h in HEADERS) +
        "export module corelib;\nexport namespace corelib {\n"
        "using std::string; using std::string_view; using std::vector; using std::map; using std::set;\n"
        "using std::unordered_map; using std::optional; using std::variant; using std::unique_ptr;\n"
        "using std::shared_ptr; using std::function; using std::pair; using std::array;\n"
        "inline int value() { return static_cast<int>(string(\"corelib\").size()); }\n}\n")
    provided = {u["provides"] for u in SHAPE["units"] if u["provides"]}
    for u in SHAPE["units"]:
        name = u["provides"]
        if name == "std":
            continue
        rel = u["source"]
        if name and not rel.endswith((".cppm", ".ixx", ".mpp", ".cxxm")):
            rel = os.path.splitext(rel)[0] + ".cppm"
        if not name and not rel.endswith((".cpp", ".cc", ".cxx")):
            rel = os.path.splitext(rel)[0] + ".cpp"
        lines = []
        calls = []
        own = module_of(name) if name else None
        for r in u["requires"]:
            if r == "std":
                lines.append("import corelib;")
                calls.append("corelib::value()")
            elif ":" in r and own == module_of(r):
                # A partition of the unit's own module; the primary interface exports what it imports.
                lines.append(("export " if ":" not in name else "") + f"import :{r.split(':', 1)[1]};")
                calls.append(f"{ident(r)}_value()")
            elif r in provided:
                lines.append(f"import {r};")
                calls.append(f"{ident(r)}_value()")
        body = " + ".join(calls) if calls else "0"
        unit = ident(name) if name else ident(rel)
        decl = (f"struct {unit}_record {{ int a = 1; int b = 2; int sum() const {{ return a + b; }} }};\n"
                f"inline int {unit}_helper(int x) {{ return x * 2 + {unit}_record{{}}.sum(); }}\n")
        if name:
            text = f"export module {name};\n" + "".join(l + "\n" for l in lines) + \
                   f"export {decl}export int {unit}_value() {{ return {unit}_helper({body}); }}\n"
        else:
            text = "".join(l + "\n" for l in lines) + decl + f"int {unit}_use() {{ return {unit}_helper({body}); }}\n"
        put(rel, text)
    entries = [{"directory": at, "file": os.path.join(at, f),
                "arguments": ["clang++", "-std=c++23", *std_args, "-c", os.path.join(at, f)]} for f in files]
    with open(os.path.join(at, "compile_commands.json"), "w") as f:
        json.dump(entries, f, indent=1)
    return files


def probe_files(files):
    """The program's main file, a module unit four imports deep, and a test: what a person opens first."""
    units = {u["source"]: u for u in SHAPE["units"]}
    deep = sorted((f for f in files if f.endswith(".cppm") and units.get(f, {}).get("requires")),
                  key=lambda f: (-len(units[f]["requires"]), f))
    test = sorted(f for f in files if f.startswith("tests/") and f.endswith(".cpp"))
    picks = ["src/main.cpp" if "src/main.cpp" in files else files[-1], deep[len(deep) // 4], test[0] if test else files[0]]
    return list(dict.fromkeys(picks))


# ---- one session ------------------------------------------------------------------------------------------------

class Session:
    def __init__(self, at):
        self.at = at
        self.log = bytearray()
        self.replies = {}
        self.clean = {}  # uri -> when its diagnostics were last published with no error; absent while they have one
        self.cv = threading.Condition()
        self.id = 0
        self.waited_usage = WaitedUsage()
        self.t0 = time.perf_counter()
        self.p = subprocess.Popen(prefix + ["--experimental-modules-support", "--background-index=false", "-j=4",
                                            "--log=info", f"--compile-commands-dir={at}"],
                                  cwd=at, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.ps = psutil.Process(self.p.pid)
        self.linux_usage = LinuxTreeUsage(self.ps) if sys.platform.startswith('linux') else None
        self.cpu_sample = None
        self.seen = {}   # pid -> (cpu seconds, faults) last read: a worker is read while it lives
        self.own_cpu = 0.0   # the engine's own, at the last reading
        self.done_cpu = 0.0
        self.done_faults = 0
        self.readers = [threading.Thread(target=self.read, daemon=True), threading.Thread(target=self.err, daemon=True),
                        threading.Thread(target=self.sample, daemon=True)]
        self.stop_sampling = False
        for t in self.readers:
            t.start()

    def err(self):
        while chunk := self.p.stderr.read1(65536):
            if len(self.log) < 64 << 20:
                self.log.extend(chunk)

    def read(self):
        while True:
            n = 0
            while True:
                line = self.p.stdout.readline()
                if not line:
                    return
                if line in (b"\r\n", b"\n"):
                    break
                if line.lower().startswith(b"content-length:"):
                    n = int(line.split(b":")[1])
            m = json.loads(self.p.stdout.read(n))
            if m.get("method") == "textDocument/publishDiagnostics":
                errors = [d for d in m["params"].get("diagnostics", []) if d.get("severity", 1) == 1]
                with self.cv:
                    if errors:
                        self.clean.pop(m["params"]["uri"], None)
                    else:
                        self.clean[m["params"]["uri"]] = round(time.perf_counter() - self.t0, 3)
                    self.cv.notify_all()
            elif "id" in m and "method" in m:   # a request of the server's
                self.send({"jsonrpc": "2.0", "id": m["id"], "result": None})
            elif "id" in m:
                with self.cv:
                    self.replies[m["id"]] = m
                    self.cv.notify_all()

    @staticmethod
    def faults(proc):
        try:
            if sys.platform.startswith("linux"):
                fields = open(f"/proc/{proc.pid}/stat").read().rsplit(")", 1)[1].split()
                return int(fields[7]) + int(fields[9])   # minflt, majflt
            info = proc.memory_info()
            return int(getattr(info, "pfaults", getattr(info, "num_page_faults", 0)))
        except (OSError, psutil.Error, IndexError, ValueError):
            return 0

    def account(self):
        alive = {}
        try:
            procs = [self.ps] + self.ps.children(recursive=True)
        except psutil.Error:
            procs = []
        for proc in procs:
            try:
                t = proc.cpu_times()
                alive[proc.pid] = (t.user + t.system, self.faults(proc))
            except psutil.Error:
                pass
        for pid, last in list(self.seen.items()):
            if pid not in alive:   # ended since the last reading: its last reading is what it used
                self.done_cpu += last[0]
                self.done_faults += last[1]
                del self.seen[pid]
        self.seen.update(alive)

    def sample(self):
        while not self.stop_sampling and self.p.poll() is None:
            self.account()
            time.sleep(0.05)

    def usage(self):
        if self.linux_usage is not None:
            try:
                sample = self.linux_usage.read()
            finally:
                self.cpu_sample = self.linux_usage.last
            self.own_cpu = sample['own_cpu_seconds']
            return sample['cpu_seconds'], sample['page_faults']
        self.account()
        try:
            t = self.ps.cpu_times()
            self.own_cpu = t.user + t.system
        except psutil.Error:
            pass
        return (round(self.done_cpu + sum(v[0] for v in self.seen.values()), 3),
                self.done_faults + sum(v[1] for v in self.seen.values()))

    def send(self, m):
        b = json.dumps(m).encode()
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
        self.p.stdin.flush()

    def request(self, method, params, timeout):
        self.id += 1
        rid = self.id
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        with self.cv:
            if not self.cv.wait_for(lambda: rid in self.replies or self.p.poll() is not None, timeout):
                raise TimeoutError(method)
            if rid not in self.replies:
                raise RuntimeError("the engine ended")
            m = self.replies.pop(rid)
        if "error" in m:
            raise RuntimeError(m["error"])
        return m.get("result")

    def uri(self, rel):
        path = os.path.join(self.at, rel).replace("\\", "/")
        return "file:///" + path.lstrip("/")

    def run(self, probes):
        self.request("initialize", {"processId": None, "rootUri": self.uri(""), "capabilities": {}}, 120)
        self.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        for rel in probes:
            self.send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {
                "uri": self.uri(rel), "languageId": "cpp", "version": 1,
                "text": open(os.path.join(self.at, rel)).read()}}})
        uris = {self.uri(rel): rel for rel in probes}
        with self.cv:
            self.cv.wait_for(lambda: all(u in self.clean for u in uris) or self.p.poll() is not None, a.timeout)
            ready = {uris[u]: self.clean[u] for u in uris if u in self.clean}
        cpu, faults = self.usage()
        return ready, cpu, faults

    def stop(self):
        self.stop_sampling = True
        try:
            self.request("shutdown", None, 60)
            self.send({"jsonrpc": "2.0", "method": "exit"})
            self.p.wait(timeout=60)
        except Exception:
            self.p.kill()
            self.p.wait()
        for t in self.readers:
            t.join(timeout=5)
        return self.log.decode("utf-8", "replace")


def session(kind, at, probes, n):
    s = Session(at)
    error = None
    try:
        ready, cpu, faults = s.run(probes)
    except Exception as e:   # a session that fails is reported, not raised: the acceptance says what failed
        ready, cpu, faults, error = {}, None, None, str(e)
        try:
            cpu, faults = s.usage()
        except Exception as accounting_error:
            error += '; accounting: ' + str(accounting_error)
    log = s.stop()
    complete_usage = s.waited_usage.finish()
    with open(os.path.join(a.workdir, f"session-{n}-{kind}.log"), "w", encoding="utf-8") as f:
        f.write(log)
    workers = [(m, int(ms), int(c)) for m, ms, c in re.findall(r"Module worker built (\S+) in (\d+) ms: CPU (\d+) ms", log)]
    # Keep Linux's pre-shutdown kernel reading. /proc is gone after stop(),
    # which previously selected the sampled fallback even on Linux.
    cpu = ready_cpu(sys.platform, cpu, s.own_cpu, [w[2] for w in workers])
    cache = re.search(r"Module cache .+?: (owned|a copy of each BMI for each reader)[^\n]*", log)
    builds = re.search(r"Module builds: ([^;\n]+); owned module cache ([^;\n]+)", log)
    return {
        "kind": kind,
        "ok": error is None and len(ready) == len(probes),
        "error": error,
        "ready_seconds": max(ready.values()) if len(ready) == len(probes) else None,
        "files": ready,
        "cpu_seconds": cpu,
        "cpu_sample": getattr(s, 'cpu_sample', None),
        "page_faults": faults,
        "waited_usage": complete_usage,
        "complete_page_faults": (complete_usage["minor_faults"] + complete_usage["major_faults"]
                                 if complete_usage is not None else None),
        "modules_built": len(re.findall(r"Built module \S+ to ", log)),
        "modules_reused": len(re.findall(r"Reusing (?:owned |persistent )?module \S+ from ", log)),
        "workers": len(workers),
        "worker_ms_median": statistics.median(w[1] for w in workers) if workers else None,
        "worker_cpu_ms_median": statistics.median(w[2] for w in workers) if workers else None,
        "cache": cache.group(1) if cache else None,
        "cache_line": cache.group(0) if cache else None,
        "builds": builds.group(1) if builds else None,
        "owned_cache": builds.group(2) if builds else None,
        "failures": re.findall(r"E\[[^\]]*\] ([^\n]{0,300})", log)[:20],
    }


# ---- the run ----------------------------------------------------------------------------------------------------

at = os.path.abspath(os.path.join(a.workdir, "project"))
files = write_project(at)
probes = probe_files(files)
sessions = [session("cold" if n == 0 else "warm", at, probes, n) for n in range(a.sessions + 1)]
warm = [s for s in sessions if s["kind"] == "warm" and s["ok"]]
median = lambda key: statistics.median(s[key] for s in warm) if warm else None
result = {"measurement_version": MEASUREMENT_VERSION, "fault_scope": FAULT_SCOPE,
          "label": a.label, "engine": prefix, "probes": probes, "units": len(files), "sessions": sessions,
          "warm": {"ready_seconds": median("ready_seconds"), "cpu_seconds": median("cpu_seconds"),
                   "page_faults": median("page_faults"),
                   "complete_page_faults": (median("complete_page_faults")
                                             if warm and warm[0]["complete_page_faults"] is not None else None),
                   "modules_built": median("modules_built")}}
with open(a.out, "w") as f:
    json.dump(result, f, indent=1)
for s in sessions:
    print(f"{a.label} {s['kind']}: ok={s['ok']} ready={s['ready_seconds']}s cpu={s['cpu_seconds']}s faults={s['page_faults']} "
          f"built={s['modules_built']} reused={s['modules_reused']} workers={s['workers']} cache={s['cache']} builds={s['builds']}"
          + (f" error={s['error']}" if s["error"] else ""))
print(f"{a.label} warm median: {result['warm']}")
