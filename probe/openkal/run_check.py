#!/usr/bin/env python3
"""Run one clangd (a native program, or an ok image under okrun) through the
probe's cases and write what happened as JSON.

usage: run_check.py --label L --out result.json [--repeat N] [--std] -- <clangd argv prefix...>

The argv prefix is how the clangd is started: `<clangd>` or `<okrun> <clangd.oke>`.
Each case records the exit status, the wall time, the peak resident set (the
started process, sampled), and the tail of what it wrote. A --check case passes
when clangd reports `All checks completed, 0 errors`.
"""
import argparse, json, os, platform, re, statistics, subprocess, sys, tempfile, time

import psutil

ap = argparse.ArgumentParser()
ap.add_argument("--label", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--repeat", type=int, default=3)
ap.add_argument("--std", action="store_true", help="also the case over the system's C++ standard library")
ap.add_argument("--std-args", default="", help="extra compile arguments of the standard-library case")
ap.add_argument("--workers", action="store_true", help="also the module case under supervised workers (Linux)")
ap.add_argument("--clangd-arg", action="append", default=[], help="an argument added to every --check run")
ap.add_argument("cmd", nargs=argparse.REMAINDER)
a = ap.parse_args()
prefix = [os.path.abspath(c) if os.path.exists(c) else c for c in a.cmd if c != "--"]
windows = os.name == "nt"


def run(argv, cwd=None, timeout=900):
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
            "peak_rss_mib": round(peak / 1048576, 1), "tail": out[-3000:]}


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

results["cases"]["version"] = run(prefix + ["--version"])

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

with open(a.out, "w") as f:
    json.dump(results, f, indent=1)
for k, v in results["cases"].items():
    if k == "version":
        print(f"{a.label} version rc={v['rc']} {v['tail'].strip().splitlines()[:2]}")
    else:
        print(f"{a.label} {k}: ok={v['ok']} errors={v['errors']} rc={v['rc']} t={v['seconds_median']}s peak={v['peak_rss_mib_max']}MiB")
