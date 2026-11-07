#!/usr/bin/env python3
"""The native jobs a build-test run carries (ci/performance-policy.md, "Comparison runs").

usage: comparison_matrix.py --event E [--platform P]   (writes GitHub step outputs to stdout)

The engine is distributed only as the ok image (clangd.okb); a native build is never released. A push or a pull
request therefore builds one native engine, linux-x64, for the series' unit and lit tests, and no native package.
A comparison run is a manual dispatch naming one platform or `all`: it builds the native engines of those
platforms, packages them like a release would (the Linux ones in the Ubuntu 20.04 floor job), and measures the
image against them (warm-prime and the shard exchange).

Outputs, each a JSON list for a matrix `include`: `build` (native build and test), `floor` (Linux floor package)
and `compare` (warm-prime); `compare` and `floor` are empty outside a comparison run.
"""
import argparse, json

PLATFORMS = {
    "linux-x64": {"os": "ubuntu-22.04"},
    "linux-arm64": {"os": "ubuntu-22.04-arm"},
    "darwin-arm64": {"os": "macos-15"},
    "win32-x64": {"os": "windows-2022"},
}
FLOOR = {
    "linux-x64": {"os": "ubuntu-24.04", "rootfs": "ci/linux-floor-rootfs.json", "cache": "", "minutes": 300},
    "linux-arm64": {"os": "ubuntu-24.04-arm", "rootfs": "ci/linux-floor-rootfs-arm64.json",
                    "cache": "-linux-arm64", "minutes": 300},
}
COMPARE = {
    "linux-x64": {"os": "ubuntu-24.04", "std": ""},
    "linux-arm64": {"os": "ubuntu-24.04-arm", "std": ""},
    "darwin-arm64": {"os": "macos-15", "std": "mac"},
    "win32-x64": {"os": "windows-2022", "std": "msvc"},
}


def matrices(event, platform):
    if event != "workflow_dispatch":
        return {"build": [{"platform": "linux-x64", **PLATFORMS["linux-x64"]}], "floor": [], "compare": []}
    if platform != "all" and platform not in PLATFORMS:
        raise SystemExit(f"comparison_matrix: unknown platform {platform!r}")
    chosen = list(PLATFORMS) if platform == "all" else [platform]
    return {
        "build": [{"platform": p, **PLATFORMS[p]} for p in chosen],
        "floor": [{"platform": p, **FLOOR[p]} for p in chosen if p in FLOOR],
        "compare": [{"platform": p, **COMPARE[p]} for p in chosen],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--event", required=True)
    ap.add_argument("--platform", default="all")
    a = ap.parse_args()
    for name, rows in matrices(a.event, a.platform).items():
        print(f"{name}={json.dumps(rows, separators=(',', ':'))}")
