#!/usr/bin/env python3
"""Whether clangd as an ok image keeps up with the native engine on one system in the warm-prime workspace
(warm_prime.py; mcpp design 2026-11-02 part 3, §9.4 and §11 L3; sampling rule: ci/performance-policy.md).

usage: warm_prime_accept.py --platform P --pair native-1.json image-1.json ... --out warm-prime-P.json

THE SAMPLE is a pair: the native engine's report and then the image's, measured one after the other on one
runner, each a cold session over an empty cache followed by three warm ones. A measurement is at least eight
pairs, alternating native and image, so that a drift of the runner reaches both engines alike.

THE GATE, on every system where both engines build modules in supervised workers over the owned cache (Linux and
macOS): for the cold session and for the median of the warm ones, the median over the pairs of the image/native
ratio of time to ready and of processor time is at most 1.15, and of page faults at most 2; every session of both
engines is ready. Faults use complete engine lifetimes, including shutdown and waited descendants, from POSIX kernel
counters. Readiness fault samples remain diagnostic. Version 3 requires a stable-reap Linux CPU observation.

A MEASUREMENT IS INVALID, and only then may it be repeated, in full: fewer than eight pairs; a report that is
not the version-3 measurement of the 304-unit, three-probe, one-cold/three-warm workload; a missing or
inconsistent counter or aggregate; or, on a gated system, more than a quarter of the pairs (at least one) whose
cold processor-time ratio lies further than 0.03 from the median (O4, the spread measured on one runner, mcpp
design 2026-11-07, A.2), or whose cold readiness ratio lies further than 0.10 from the median (O5,
ci/performance-policy.md). An invalid measurement exits 2; a valid one that misses the gate exits 1.

PATH PARITY, on every system: the image builds in supervised workers over the owned cache. The native engine does
so on Linux and macOS; on Windows it compiles in clangd and gives each reader a copy of each BMI (the portable
path), and the ratios there are recorded and are not the gate, since the two engines take different paths.
"""
import argparse, json, math, statistics, sys
from decimal import Decimal
from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION, READY_CPU_SCOPE

ap = argparse.ArgumentParser()
ap.add_argument("--platform", required=True)
ap.add_argument("--pair", nargs=2, action="append", required=True, metavar=("NATIVE", "IMAGE"))
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=float, default=1.15)
ap.add_argument("--fault-limit", type=float, default=2.0)
ap.add_argument("--min-pairs", type=int, default=8)
ap.add_argument("--spread", type=float, default=0.03)
ap.add_argument("--ready-spread", type=float, default=0.10)
a = ap.parse_args()

windows = a.platform.startswith("win32")
OWNED, WORKERS = "owned", "in supervised workers"
METRICS = ("ready_seconds", "cpu_seconds", "page_faults", "complete_page_faults")


def number(x):
    return type(x) in (int, float) and math.isfinite(x) and x >= 0


def exact(x, y):
    # The ratio as a decimal of the recorded values, so that display rounding admits nothing.
    return Decimal(str(x)) / Decimal(str(y)) if number(x) and number(y) and y > 0 else None


def malformed(name, run):
    """The reasons `run` is not a valid measurement of the workload."""
    out = []
    if run.get("measurement_version") != MEASUREMENT_VERSION or run.get("fault_scope") != FAULT_SCOPE:
        out.append(f"{name} has no supported measurement version and complete-lifetime fault scope")
    sessions = run.get("sessions") or []
    if (run.get("units") != 304 or len(run.get("probes", [])) != 3 or
            [s.get("kind") for s in sessions] != ["cold", "warm", "warm", "warm"]):
        out.append(f"{name} does not contain the 304-unit, three-file, one-cold/three-warm workload")
        return out
    for s in sessions:
        if a.platform.startswith('linux'):
            sample = s.get('cpu_sample')
            if (not isinstance(sample, dict) or sample.get('valid') is not True or
                    sample.get('scope_id') != READY_CPU_SCOPE or
                    type(sample.get('cpu_seconds')) not in (int, float) or
                    not math.isfinite(sample['cpu_seconds']) or sample['cpu_seconds'] < 0 or
                    type(sample.get('page_faults')) is not int or sample['page_faults'] < 0 or
                    type(sample.get('attempts')) is not int or not 1 <= sample['attempts'] <= 8 or
                    type(sample.get('processes')) is not int or sample['processes'] < 1 or
                    type(sample.get('observation_ns')) is not int or sample['observation_ns'] < 0 or
                    sample.get('cpu_seconds') != s.get('cpu_seconds') or
                    sample.get('page_faults') != s.get('page_faults')):
                out.append(f"{name} {s['kind']} has no consistent stable-reap CPU observation")
        if not windows:
            usage = s.get("waited_usage")
            valid = (isinstance(usage, dict) and usage.get("scope_id") == FAULT_SCOPE and
                     all(type(usage.get(k)) is int and usage[k] >= 0
                         for k in ("minor_faults", "major_faults")))
            total = s.get("complete_page_faults")
            if not valid or type(total) is not int or total != usage["minor_faults"] + usage["major_faults"]:
                out.append(f"{name} {s['kind']} has missing or inconsistent complete-lifetime kernel faults")
    warm = run.get("warm") or {}
    if not all(s.get("ok") for s in sessions):
        return out  # a session that was not ready fails the gate; warm_prime.py aggregates the ready ones
    if not windows:
        values = [s.get("complete_page_faults") for s in sessions if s.get("kind") == "warm"]
        if (any(type(v) is not int or v < 0 for v in values) or
                warm.get("complete_page_faults") != statistics.median(values)):
            out.append(f"{name} warm complete-lifetime fault median does not match the three raw sessions")
    if a.platform.startswith('linux'):
        values = [s.get('cpu_seconds') for s in sessions if s.get('kind') == 'warm']
        if (any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values) or
                warm.get('cpu_seconds') != statistics.median(values)):
            out.append(f"{name} warm CPU median does not match the three raw sessions")
    return out


def path(run):
    s = run["sessions"][0]
    return {"builds": s.get("builds"), "owned_cache": s.get("owned_cache"), "cache": s.get("cache")}


def owned_workers(p):
    return p["builds"] == WORKERS and p["owned_cache"] not in (None, "not used") and p["cache"] == OWNED


invalid, failures, pairs = [], [], []
if len(a.pair) < a.min_pairs:
    invalid.append(f"{len(a.pair)} pairs, fewer than {a.min_pairs}")
for k, (native_file, image_file) in enumerate(a.pair, 1):
    native, image = json.load(open(native_file)), json.load(open(image_file))
    for name, run in (("native", native), ("image", image)):
        for s in run.get("sessions") or []:
            if not s.get("ok"):
                failures.append(f"pair {k} {name} {s.get('kind')} session was not ready: {s.get('error') or s.get('files')}")
    reasons = malformed(f"pair {k} native", native) + malformed(f"pair {k} image", image)
    invalid += reasons
    if reasons:
        pairs.append({"pair": k, "valid": False})
        continue
    parity = {"image": path(image), "native": path(native)}
    if not owned_workers(parity["image"]):
        failures.append(f"pair {k}: the image does not build in supervised workers over the owned cache: {parity['image']}")
    native_ok = (parity["native"]["builds"] == "in clangd" and parity["native"]["owned_cache"] == "not used") \
        if windows else owned_workers(parity["native"])
    if not native_ok:
        failures.append(f"pair {k}: the native engine took another path than this system's: {parity['native']}")
    entry = {"pair": k, "valid": True, "parity": parity, "ratios": {}, "native": {}, "image": {}}
    for when in ("cold", "warm"):
        n = native["sessions"][0] if when == "cold" else native["warm"]
        i = image["sessions"][0] if when == "cold" else image["warm"]
        entry["native"][when], entry["image"][when] = n, i
        entry["ratios"][when] = {m: exact(i.get(m), n.get(m)) for m in METRICS}
    pairs.append(entry)

measured = [p for p in pairs if p["valid"]]
medians, spread, ready_spread = {}, {}, {}
if not invalid:
    for when in ("cold", "warm"):
        medians[when] = {}
        for m in METRICS:
            values = [p["ratios"][when][m] for p in measured]
            medians[when][m] = statistics.median(values) if all(v is not None for v in values) else None
    # O4 and O5: the pairs a quarter of the measurement (at least one) may leave outside each bound.
    allowed = max(1, len(measured) // 4)

    def outside_of(metric, bound):
        centre = medians["cold"][metric]
        ratios = [p["ratios"]["cold"][metric] for p in measured]
        out = [p["pair"] for p, r in zip(measured, ratios)
               if r is None or centre is None or abs(r - centre) > Decimal(str(bound))]
        return {"metric": f"cold.{metric}", "bound": bound, "median": centre, "pairs_outside": out,
                "allowed": allowed}

    spread = outside_of("cpu_seconds", a.spread)
    ready_spread = outside_of("ready_seconds", a.ready_spread)
    for s, what in ((spread, "cold CPU"), (ready_spread, "cold readiness")):
        if not windows and len(s["pairs_outside"]) > allowed:
            invalid.append(f"{what} ratios of pairs {s['pairs_outside']} lie further than {s['bound']} from the "
                           f"median {s['median']} (at most {allowed} may)")
    if not windows and not invalid:
        for when in ("cold", "warm"):
            for m, limit in (("ready_seconds", a.limit), ("cpu_seconds", a.limit),
                             ("complete_page_faults", a.fault_limit)):
                r = medians[when][m]
                if r is None or r > Decimal(str(limit)):
                    failures.append(f"{when} {m}: the median image/native ratio over {len(measured)} pairs is "
                                    f"{r}, over {limit} (unrounded comparison)")


def shown(r):
    return None if r is None else round(float(r), 3)


result = {
    "measurement_version": MEASUREMENT_VERSION,
    "fault_scope": FAULT_SCOPE,
    "platform": a.platform,
    "gated": not windows,
    "valid": not invalid,
    "invalid": invalid,
    "accepted": not invalid and not failures,
    "failures": failures,
    "pairs": len(a.pair),
    "ratios": {w: {m: shown(r) for m, r in ms.items()} for w, ms in medians.items()},
    "spread": {**spread, "median": shown(spread.get("median"))} if spread else {},
    "ready_spread": {**ready_spread, "median": shown(ready_spread.get("median"))} if ready_spread else {},
    "samples": [{**p, "ratios": {w: {m: shown(r) for m, r in ms.items()} for w, ms in p["ratios"].items()}}
                if p["valid"] else p for p in pairs],
}
with open(a.out, "w") as f:
    json.dump(result, f, indent=1)
print(json.dumps({k: result[k] for k in ("platform", "gated", "valid", "accepted", "pairs", "ratios", "spread",
                                         "ready_spread")},
                 indent=1))
for msg in invalid:
    print("invalid measurement:", msg)
for msg in failures:
    print("not accepted:", msg)
sys.exit(2 if invalid else 1 if failures else 0)
