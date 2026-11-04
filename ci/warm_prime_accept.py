#!/usr/bin/env python3
"""Whether clangd as an ok image keeps up with the native engine on one system in the warm-prime workspace
(warm_prime.py; mcpp design 2026-11-02 part 3, §9.4 and §11 L3).

usage: warm_prime_accept.py --platform P --native native.json --image image.json --out warm-prime-P.json

THE GATE, on every system where both engines build modules in supervised workers over the owned cache (Linux and
macOS): the image's time to ready and processor time are at most 1.15 times the native engine's, and its page
faults at most twice, in the cold session and in the median of the warm ones; every session of both is ready.
Faults use complete engine lifetimes, including shutdown and waited descendants, from POSIX kernel counters.
Readiness fault samples remain diagnostic; measurement version 1 reports cannot satisfy this gate.

PATH PARITY, on every system: the image builds in supervised workers over the owned cache. The native engine does
so on Linux and macOS; on Windows it compiles in clangd and gives each reader a copy of each BMI (the portable
path), and the ratios there are recorded and are not the gate, since the two engines take different paths.
"""
import argparse, json, statistics, sys
from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION

ap = argparse.ArgumentParser()
ap.add_argument("--platform", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--image", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=float, default=1.15)
ap.add_argument("--fault-limit", type=float, default=2.0)
a = ap.parse_args()

native = json.load(open(a.native))
image = json.load(open(a.image))
windows = a.platform.startswith("win32")
OWNED, WORKERS = "owned", "in supervised workers"


def ratio(x, y):
    return round(x / y, 3) if x is not None and y else None


failures = []
for name, run in (("native", native), ("image", image)):
    if run.get("measurement_version") != MEASUREMENT_VERSION or run.get("fault_scope") != FAULT_SCOPE:
        failures.append(f"{name} has no supported measurement version and complete-lifetime fault scope")
    sessions = run["sessions"]
    if (run.get("units") != 304 or len(run.get("probes", [])) != 3 or
            [s.get("kind") for s in sessions] != ["cold", "warm", "warm", "warm"]):
        failures.append(f"{name} does not contain the 304-unit, three-file, one-cold/three-warm workload")
    for s in run["sessions"]:
        if not s["ok"]:
            failures.append(f"{name} {s['kind']} session was not ready: {s.get('error') or s.get('files')}")
        if not windows:
            usage = s.get("waited_usage")
            valid = (isinstance(usage, dict) and usage.get("scope_id") == FAULT_SCOPE and
                     all(type(usage.get(k)) is int and usage[k] >= 0
                         for k in ("minor_faults", "major_faults")))
            total = s.get("complete_page_faults")
            if not valid or type(total) is not int or total != usage["minor_faults"] + usage["major_faults"]:
                failures.append(f"{name} {s['kind']} has missing or inconsistent complete-lifetime kernel faults")
    if not windows:
        values = [s.get("complete_page_faults") for s in sessions if s.get("kind") == "warm"]
        if (len(values) != 3 or any(type(v) is not int or v < 0 for v in values) or
                run["warm"].get("complete_page_faults") != statistics.median(values)):
            failures.append(f"{name} warm complete-lifetime fault median does not match the three raw sessions")


def path(run):
    s = run["sessions"][0]
    return {"builds": s.get("builds"), "owned_cache": s.get("owned_cache"), "cache": s.get("cache")}


def owned_workers(p):
    return p["builds"] == WORKERS and p["owned_cache"] not in (None, "not used") and p["cache"] == OWNED


parity = {"image": path(image), "native": path(native)}
if not owned_workers(parity["image"]):
    failures.append(f"the image does not build in supervised workers over the owned cache: {parity['image']}")
native_ok = (parity["native"]["builds"] == "in clangd" and parity["native"]["owned_cache"] == "not used") \
    if windows else owned_workers(parity["native"])
if not native_ok:
    failures.append(f"the native engine took another path than this system's: {parity['native']}")

ratios = {}
for when in ("cold", "warm"):
    n = native["sessions"][0] if when == "cold" else native["warm"]
    i = image["sessions"][0] if when == "cold" else image["warm"]
    ratios[when] = {k: ratio(i.get(k), n.get(k))
                    for k in ("ready_seconds", "cpu_seconds", "page_faults", "complete_page_faults")}
    if windows:
        continue
    for k, limit in (("ready_seconds", a.limit), ("cpu_seconds", a.limit), ("complete_page_faults", a.fault_limit)):
        r = ratios[when][k]
        if r is None or r > limit:
            failures.append(f"{when} {k}: the image {i.get(k)} against the native {n.get(k)} is {r}, over {limit}")

result = {
    "measurement_version": MEASUREMENT_VERSION,
    "fault_scope": FAULT_SCOPE,
    "platform": a.platform,
    "gated": not windows,
    "accepted": not failures,
    "failures": failures,
    "ratios": ratios,
    "parity": parity,
    "native": {"cold": native["sessions"][0], "warm": native["warm"]},
    "image": {"cold": image["sessions"][0], "warm": image["warm"]},
}
with open(a.out, "w") as f:
    json.dump(result, f, indent=1)
print(json.dumps({"platform": a.platform, "gated": not windows, "ratios": ratios, "parity": parity}, indent=1))
for msg in failures:
    print("not accepted:", msg)
sys.exit(1 if failures else 0)
