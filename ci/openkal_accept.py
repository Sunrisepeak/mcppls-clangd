#!/usr/bin/env python3
"""Whether clangd as an ok image is accepted on one system: its run of the
acceptance cases (openkal_check.py) against the native clangd's on the same
machine (mcpp design 2026-10-30 part 2 §25.3).

usage: openkal_accept.py --platform P --native native.json --image image.json --image-file clangd.oke --out acceptance.json

Accepted when every case of the image passes, its parse time is at most 1.3
times the native one's for the cases that parse, and its peak resident set
exceeds the native one's by no more than the image's own size (the segments it
loads, which an ok image holds beside the program it runs). The report says
which criterion failed; a system that is not accepted keeps the native clangd
in mcppls's payload, and the report states the gap.

A case's parse time is its median wall time less the median of `--version`,
the process's start: for the image, okrun admitting the image (its SHA-256)
and placing it, which a language server pays once per start rather than per
file. The start of each is reported beside the parse times.
"""
import argparse, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--platform", required=True)
ap.add_argument("--native", required=True)
ap.add_argument("--image", required=True)
ap.add_argument("--image-file", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

native = json.load(open(a.native))["cases"]
image = json.load(open(a.image))["cases"] if os.path.exists(a.image) else {}
segments_mib = os.path.getsize(a.image_file) / 1048576 if os.path.exists(a.image_file) else 0.0
COLUMNS = ["version", "check-freestanding", "check-module-import", "check-std-headers"]
TIMED = ["check-freestanding", "check-std-headers"]

failures, measured = [], {}
for name in COLUMNS:
    case = image.get(name)
    if case is None:
        failures.append(f"{name}: not run")
        continue
    rc = case.get("rc")
    ok = (all(r == 0 for r in rc) if isinstance(rc, list) else rc == 0) if name == "version" else case.get("ok", False)
    if not ok:
        failures.append(f"{name}: failed ({case.get('errors')} errors, rc {case.get('rc')})")
def start(cases):
    v = cases.get("version") or {}
    return v.get("seconds_median", v.get("seconds", 0.0))


native_start, image_start = start(native), start(image)
for name in TIMED:
    n, i = native.get(name), image.get(name)
    if not n or not i:
        continue
    native_parse = max(n["seconds_median"] - native_start, 1e-3)
    image_parse = max(i["seconds_median"] - image_start, 1e-3)
    ratio = image_parse / native_parse
    rss_gap = i["peak_rss_mib_max"] - n["peak_rss_mib_max"]
    measured[name] = {"time_ratio": round(ratio, 3), "rss_gap_mib": round(rss_gap, 1),
                      "native_seconds": n["seconds_median"], "image_seconds": i["seconds_median"],
                      "native_parse_seconds": round(native_parse, 3), "image_parse_seconds": round(image_parse, 3),
                      "native_rss_mib": n["peak_rss_mib_max"], "image_rss_mib": i["peak_rss_mib_max"]}
    if ratio > 1.3:
        failures.append(f"{name}: parse time {ratio:.2f}x the native clangd's (at most 1.3x)")
    if rss_gap > segments_mib:
        failures.append(f"{name}: resident set {rss_gap:.1f} MiB above the native clangd's (at most the image's {segments_mib:.1f} MiB)")

report = {"platform": a.platform, "accepted": not failures, "failures": failures,
          "image_mib": round(segments_mib, 1),
          "start_seconds": {"native": native_start, "image": image_start}, "measured": measured}
json.dump(report, open(a.out, "w"), indent=1)
print(json.dumps(report, indent=1))
