#!/usr/bin/env python3
"""Whether clangd as an ok image keeps up with the native engine on one system in the warm-prime workspace
(warm_prime.py; mcpp design 2026-11-02 part 3, §9.4 and §11 L3).

usage: warm_prime_accept.py --platform P --native native.json --image image.json --out warm-prime-P.json

THE GATE, on every system where both engines build modules in supervised workers over the owned cache (Linux and
macOS): the image's time to ready and processor time are at most 1.15 times the native engine's, and its page
faults at most twice, in the cold session and in the median of the warm ones; every session of both is ready.
Faults use complete engine lifetimes, including shutdown and waited descendants, from POSIX kernel counters.
Readiness fault samples remain diagnostic. Version 3 requires a stable-reap Linux CPU observation;
earlier measurement versions cannot satisfy this gate. The one-release Linux x64 cold CPU
exception is explicit; the original target and its failures remain in the report (ci/performance-policy.md).

PATH PARITY, on every system: the image builds in supervised workers over the owned cache. The native engine does
so on Linux and macOS; on Windows it compiles in clangd and gives each reader a copy of each BMI (the portable
path), and the ratios there are recorded and are not the gate, since the two engines take different paths.
"""
import argparse, hashlib, json, math, re, statistics, sys
from decimal import Decimal
from warm_usage import FAULT_SCOPE, MEASUREMENT_VERSION, READY_CPU_SCOPE

ap = argparse.ArgumentParser()
ap.add_argument("--platform", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--image", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--limit", type=float, default=1.15)
ap.add_argument("--fault-limit", type=float, default=2.0)
ap.add_argument("--release-version", help="distribution version; only 0.0.20 has an approved exception")
ap.add_argument("--source-commit", help="exact producer source identity for a release exception")
a = ap.parse_args()

native = json.load(open(a.native))
image = json.load(open(a.image))
windows = a.platform.startswith("win32")
OWNED, WORKERS = "owned", "in supervised workers"


def number(x):
    return type(x) in (int, float) and math.isfinite(x) and x >= 0


def ratio(x, y):
    return round(x / y, 3) if number(x) and number(y) and y > 0 else None


def within(x, y, limit):
    # Rounded display ratios must not admit values just beyond either ceiling.
    return (number(x) and number(y) and y > 0 and
            Decimal(str(x)) <= Decimal(str(y)) * Decimal(str(limit)))


failures = []
exception = None
if a.release_version == '0.0.20' and a.platform == 'linux-x64':
    exception = dict(issue='https://github.com/Sunrisepeak/mcpp-language-server/issues/77',
                     release='0.0.20', platform='linux-x64', metric='cold.cpu_seconds',
                     ratio_limit=1.25, extra_cpu_seconds_limit=3.0,
                     source_commit=a.source_commit, applied=False)
    if a.limit != 1.15 or a.fault_limit != 2.0:
        failures.append('the release exception requires the unchanged 1.15 time/CPU and 2.0 fault targets')
    if not re.fullmatch(r'[0-9a-f]{40}', a.source_commit or ''):
        failures.append('the release exception requires an exact producer source commit')
    try:
        # Hash the actual command prefixes recorded by the measured lanes, not separately supplied files.
        if len(native['engine']) != 1 or len(image['engine']) != 2:
            raise ValueError('unexpected engine command prefix')
        identities = {}
        for name, path in (('native', native['engine'][0]), ('runner', image['engine'][0]),
                           ('image', image['engine'][1])):
            with open(path, 'rb') as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(1 << 20), b''):
                    digest.update(block)
            identities[name] = digest.hexdigest()
        exception['artifact_sha256'] = identities
    except (KeyError, TypeError, ValueError, OSError):
        failures.append('the release exception requires readable measured native, runner and image artifacts')
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
                failures.append(f"{name} {s['kind']} has no consistent stable-reap CPU observation")
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
    if a.platform.startswith('linux'):
        values = [s.get('cpu_seconds') for s in sessions if s.get('kind') == 'warm']
        if (len(values) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values) or
                run['warm'].get('cpu_seconds') != statistics.median(values)):
            failures.append(f"{name} warm CPU median does not match the three raw sessions")


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
target_failures = list(failures)
waived_failures = []
for when in ("cold", "warm"):
    n = native["sessions"][0] if when == "cold" else native["warm"]
    i = image["sessions"][0] if when == "cold" else image["warm"]
    ratios[when] = {k: ratio(i.get(k), n.get(k))
                    for k in ("ready_seconds", "cpu_seconds", "page_faults", "complete_page_faults")}
    if windows:
        continue
    for k, limit in (("ready_seconds", a.limit), ("cpu_seconds", a.limit), ("complete_page_faults", a.fault_limit)):
        r = ratios[when][k]
        if not within(i.get(k), n.get(k), limit):
            message = f"{when} {k}: the image {i.get(k)} against the native {n.get(k)} is {r}, over {limit} (unrounded comparison)"
            target_failures.append(message)
            allowed = False
            if exception and when == 'cold' and k == 'cpu_seconds' and r is not None:
                extra = Decimal(str(i[k])) - Decimal(str(n[k]))
                exception['extra_cpu_seconds'] = float(extra)
                allowed = within(i[k], n[k], 1.25) and extra <= Decimal('3.0')
            if allowed:
                waived_failures.append(message)
            else:
                failures.append(message)

if exception:
    exception['applied'] = bool(waived_failures) and not failures

result = {
    "measurement_version": MEASUREMENT_VERSION,
    "fault_scope": FAULT_SCOPE,
    "platform": a.platform,
    "gated": not windows,
    "release_version": a.release_version,
    "target_met": not target_failures,
    "target_failures": target_failures,
    "release_exception": exception,
    "waived_failures": waived_failures,
    "accepted": not failures,
    "failures": failures,
    "ratios": ratios,
    "parity": parity,
    "native": {"cold": native["sessions"][0], "warm": native["warm"]},
    "image": {"cold": image["sessions"][0], "warm": image["warm"]},
}
with open(a.out, "w") as f:
    json.dump(result, f, indent=1)
print(json.dumps({"platform": a.platform, "gated": not windows, "ratios": ratios, "parity": parity,
                  "target_met": result['target_met'], "accepted": result['accepted'],
                  "release_exception": exception}, indent=1))
for msg in target_failures:
    print("target not met:", msg)
for msg in failures:
    print("not accepted:", msg)
sys.exit(1 if failures else 0)
