#!/usr/bin/env python3
"""Run one clangd (a native program, or the ok image under okrun) through the
acceptance cases of clangd as an ok image and write what happened as JSON
(mcpp design 2026-10-30 part 2 §25.3, the acceptance).

usage: openkal_check.py --label L --out result.json [--repeat N] [--std] -- <clangd argv prefix...>

The argv prefix is how the clangd is started: `<clangd>` or `<okrun> <clangd.okb>`.
The cases are the four columns: `--version`; a file of templates with no library
header; `import m`; the system's C++ standard library. Each records the exit
status, the wall time, the peak resident set (the started process and its
children, sampled), and the tail of what it wrote. A --check case passes when
clangd reports `All checks completed, 0 errors`. `--version` runs as often as
each case: its median is the process's start (for the image, okrun admitting and
placing it), which the acceptance takes off each case's time to compare parsing.
`module-parallelism` builds twelve independent modules for one file and records
how many clangd builds at once (its `limit=` in the log): what the host's
processors allow it, which the image has to be told as the native clangd is.
"""
import argparse, json, os, platform, re, statistics, subprocess, sys, tempfile, time

import psutil

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--repeat", type=int, default=5)
ap.add_argument("--std", action="store_true", help="also the case over the system's C++ standard library")
ap.add_argument("--std-args", default="", help="extra compile arguments of the standard-library case")
ap.add_argument("--std-host", action="store_true",
                help="also the standard-library case naming no target and no SDK, which the engine completes "
                     "from the host as the system's own clangd does (macOS: the SDK xcrun names)")
ap.add_argument("--workers", action="store_true", help="also the module case under supervised workers (Linux)")
ap.add_argument("--clangd-arg", action="append", default=[], help="an argument added to every --check run")
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
prefix = [os.path.abspath(c) if os.path.exists(c) else c for c in a.cmd if c != "--"]
windows = os.name == "nt"


def run(argv, cwd=None, timeout=900, whole=False):
    t0 = time.perf_counter()
    # Output to a file, not a pipe: a pipe nobody reads while the process runs fills
    # (4 KiB on Windows) and the process blocks writing its log.
    log = tempfile.TemporaryFile()
    p = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    peak = 0
    try:
        ps = psutil.Process(p.pid)
        while p.poll() is None:
            try:
                rss = ps.memory_info().rss
                for c in ps.children(recursive=True):
                    rss += c.memory_info().rss
                peak = max(peak, rss)
            except psutil.Error:
                pass
            time.sleep(0.01)
            if time.perf_counter() - t0 > timeout:
                p.kill()
                break
    except psutil.Error:
        pass
    p.wait()
    log.seek(0)
    out = log.read().decode("utf-8", "replace")
    log.close()
    return {"rc": p.returncode, "seconds": round(time.perf_counter() - t0, 3),
            "peak_rss_mib": round(peak / 1048576, 1), "tail": out[-3000:]} | ({"log": out} if whole else {})


def cdb(d, entries):
    with open(os.path.join(d, "compile_commands.json"), "w") as f:
        json.dump([{"directory": d, "file": os.path.join(d, fn), "arguments": args + [os.path.join(d, fn)]}
                   for fn, args in entries], f, indent=1)


def heavy_free(n=4000):
    # Templates and overloads with no library header: parse and Sema work alike on every system.
    out = ["#include \"local.h\"", "#include <stdint.h>", "namespace probe {"]
    for i in range(n):
        out.append(f"template <class T, int N> struct S{i} {{ T v[N]; constexpr T sum() const {{ T s{{}}; for (int k = 0; k < N; ++k) s += v[k]; return s; }} }};")
        out.append(f"inline int64_t f{i}(int64_t x) {{ S{i}<int64_t, {i % 7 + 1}> s{{}}; s.v[0] = x; return s.sum() + probe_value(); }}")
    out.append("}")
    out.append("int main() { int64_t r = 0;")
    out += [f"  r += probe::f{i}(r);" for i in range(0, n, 5)]
    out.append("  return (int)r; }")
    return "\n".join(out) + "\n"


STD = """#include <algorithm>
#include <map>
#include <memory>
#include <optional>
#include <regex>
#include <string>
#include <unordered_map>
#include <variant>
#include <vector>
#include <functional>
#include <iostream>
#include <sstream>
struct Item { std::string name; int weight; };
int main() {
  std::vector<Item> items{{"a", 1}, {"b", 2}};
  std::sort(items.begin(), items.end(), [](const Item& x, const Item& y) { return x.weight < y.weight; });
  std::map<std::string, std::optional<int>> m; std::unordered_map<int, std::variant<int, std::string>> u;
  std::regex re("a+b*"); std::ostringstream os; os << std::regex_match("aab", re);
  std::function<int(int)> f = [](int x) { return x * 2; };
  std::cout << os.str() << f(items.size()) << std::endl;
}
"""

results = {"label": a.label, "system": platform.system(), "machine": platform.machine(), "argv": prefix, "cases": {}}
work = tempfile.mkdtemp(prefix="okprobe-")
d = os.path.realpath(work)

versions = [run(prefix + ["--version"]) for _ in range(a.repeat)]
results["cases"]["version"] = versions[-1] | {"seconds_median": statistics.median(r["seconds"] for r in versions),
                                             "rc": [r["rc"] for r in versions]}

with open(os.path.join(d, "local.h"), "w") as f:
    f.write("#pragma once\ninline int probe_value() { return 42; }\n")
with open(os.path.join(d, "test.cpp"), "w") as f:
    f.write(heavy_free())
with open(os.path.join(d, "m.cppm"), "w") as f:
    f.write("export module m;\nexport int m_value() { return 7; }\n")
with open(os.path.join(d, "use.cpp"), "w") as f:
    f.write("import m;\nint main() { return m_value(); }\n")
base = ["clang++", "-std=c++20", "-ffreestanding", "-c"]
entries = [("test.cpp", base), ("m.cppm", ["clang++", "-std=c++20", "-ffreestanding", "-c"]),
           ("use.cpp", ["clang++", "-std=c++20", "-ffreestanding", "-c"])]
if a.std:
    with open(os.path.join(d, "std.cpp"), "w") as f:
        f.write(STD)
    entries.append(("std.cpp", ["clang++", "-std=c++20"] + a.std_args.split() + ["-c"]))
if a.std_host:
    with open(os.path.join(d, "std-host.cpp"), "w") as f:
        f.write(STD)
    entries.append(("std-host.cpp", ["clang++", "-std=c++20", "-c"]))
cdb(d, entries)


def check(name, path, extra=()):
    runs = [run(prefix + [f"--check={path}", f"--compile-commands-dir={d}", "--check-locations=false"] + a.clangd_arg + list(extra), cwd=d)
            for _ in range(a.repeat)]
    last = runs[-1]
    m = re.search(r"All checks completed, (\d+) errors", last["tail"])
    results["cases"][name] = {
        "ok": all(r["rc"] == 0 for r in runs) and bool(m) and m.group(1) == "0",
        "errors": int(m.group(1)) if m else None,
        "rc": [r["rc"] for r in runs],
        "seconds_median": statistics.median(r["seconds"] for r in runs),
        "peak_rss_mib_max": max(r["peak_rss_mib"] for r in runs),
        "tail": last["tail"],
    }


check("check-freestanding", os.path.join(d, "test.cpp"))
if windows:
    # The same file spelled with forward slashes: what a file:/// URI turns into.
    check("check-freestanding-forward-slashes", os.path.join(d, "test.cpp").replace("\\", "/"))
    # A relative name from the directory: resolved against the current directory.
    check("check-freestanding-relative", "test.cpp")
check("check-module-import", os.path.join(d, "use.cpp"), ["--experimental-modules-support"])
if a.workers:
    check("check-module-workers", os.path.join(d, "use.cpp"),
          ["--experimental-modules-support", "--modules-builder-worker-policy=required"])
if a.std:
    check("check-std-headers", os.path.join(d, "std.cpp"))
if a.std_host:
    check("check-std-host", os.path.join(d, "std-host.cpp"))

# HOW MANY MODULES CLANGD BUILDS AT ONCE, which it takes from the host's
# processors: twelve modules no other imports, and one file importing them all.
p = os.path.join(d, "parallel")
os.makedirs(p, exist_ok=True)
pentries = []
for i in range(12):
    with open(os.path.join(p, f"p{i}.cppm"), "w") as f:
        f.write(f"export module p{i};\nexport int p{i}_value() {{ return {i}; }}\n")
    pentries.append((f"p{i}.cppm", ["clang++", "-std=c++20", "-ffreestanding", "-c"]))
with open(os.path.join(p, "all.cpp"), "w") as f:
    f.write("".join(f"import p{i};\n" for i in range(12)) + "int main() { return p11_value(); }\n")
pentries.append(("all.cpp", ["clang++", "-std=c++20", "-ffreestanding", "-c"]))
cdb(p, pentries)
r = run(prefix + [f"--check={os.path.join(p, 'all.cpp')}", f"--compile-commands-dir={p}", "--check-locations=false",
                  "--experimental-modules-support", "--log=verbose"] + a.clangd_arg, cwd=p, whole=True)
limits = [int(x) for x in re.findall(r"Module build task \S+ started \(active=\d+, limit=(\d+)\)", r["log"])]
results["cases"]["module-parallelism"] = {"rc": r["rc"], "limit": max(limits) if limits else None, "seconds": r["seconds"]}

# THE INDEX OF A DOZEN FILES ON FOUR WORKERS AT ONCE, which every case above
# misses: each parses one file on one thread, while a language server's workers
# and its background index allocate and compare strings together. An ok image's
# C library once served every allocation under one lock, and clangd.okb then used
# less than one of four processors in mcppls's warm start while passing every
# case above. Timed from `initialized' to the end of `backgroundIndexProgress',
# over a fresh copy each time, the median of three.
def lsp_index(prefix, root, files, timeout=600):
    log = tempfile.TemporaryFile()
    p = subprocess.Popen(prefix + [f"--compile-commands-dir={root}", "-j=4", "--background-index", "--log=error"],
                         cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
    def send(m):
        b = json.dumps(m).encode()
        p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
        p.stdin.flush()
    def recv():
        n = 0
        while True:
            line = p.stdout.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                n = int(line.split(b":")[1])
        return json.loads(p.stdout.read(n))
    uri = lambda f: "file:///" + os.path.join(root, f).replace("\\", "/").lstrip("/")
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "processId": None, "rootUri": uri(""), "capabilities": {"window": {"workDoneProgress": True}}}})
    while True:
        m = recv()
        if m is None or m.get("id") == 1:
            break
    send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    t0 = time.perf_counter()
    text = open(os.path.join(root, files[0])).read()
    send({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {"textDocument": {
        "uri": uri(files[0]), "languageId": "cpp", "version": 1, "text": text}}})
    ended = False
    while time.perf_counter() - t0 < timeout:
        m = recv()
        if m is None:
            break
        if m.get("method") == "window/workDoneProgress/create":
            send({"jsonrpc": "2.0", "id": m["id"], "result": None})
        if (m.get("method") == "$/progress" and m["params"].get("token") == "backgroundIndexProgress"
                and m["params"].get("value", {}).get("kind") == "end"):
            ended = True
            break
    seconds = round(time.perf_counter() - t0, 3)
    try:
        send({"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
        send({"jsonrpc": "2.0", "method": "exit"})
        p.wait(timeout=30)
    except Exception:
        p.kill()
    log.close()
    return {"ok": ended, "seconds": seconds, "rc": p.returncode}


def index_tree(at):
    os.makedirs(at, exist_ok=True)
    with open(os.path.join(at, "local.h"), "w") as f:
        f.write("#pragma once\ninline int probe_value() { return 42; }\n")
    names = []
    for i in range(12):
        with open(os.path.join(at, f"i{i}.cpp"), "w") as f:
            f.write(heavy_free(1200).replace("namespace probe", f"namespace probe{i}").replace("probe::", f"probe{i}::"))
        names.append(f"i{i}.cpp")
    cdb(at, [(n, ["clang++", "-std=c++20", "-ffreestanding", "-c"]) for n in names])
    return names


runs = []
for k in range(3):
    at = os.path.join(d, f"index{k}")
    runs.append(lsp_index(prefix + a.clangd_arg, at, index_tree(at)))
results["cases"]["parallel-index"] = {"ok": all(r["ok"] for r in runs), "seconds": [r["seconds"] for r in runs],
                                      "seconds_median": statistics.median(r["seconds"] for r in runs)}

with open(a.out, "w") as f:
    json.dump(results, f, indent=1)
for k, v in results["cases"].items():
    if k == "module-parallelism":
        print(f"{a.label} module-parallelism: rc={v['rc']} limit={v['limit']}")
    elif k == "parallel-index":
        print(f"{a.label} parallel-index: ok={v['ok']} t={v['seconds_median']}s {v['seconds']}")
    elif k == "version":
        print(f"{a.label} version rc={v['rc']} t={v['seconds_median']}s {v['tail'].strip().splitlines()[:2]}")
    else:
        print(f"{a.label} {k}: ok={v['ok']} errors={v['errors']} rc={v['rc']} t={v['seconds_median']}s peak={v['peak_rss_mib_max']}MiB")
