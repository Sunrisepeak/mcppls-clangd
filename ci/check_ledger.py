#!/usr/bin/env python3
"""check_ledger.py — enforce patches/PATCHES.md against patches/series and the
tree (plan doc §3 layout principle 3; §4.3 job verify-series).

Checks:
  1. every patch in `series` exists and every existing patch is in `series`;
  2. every patch has a ledger row with: register rows (UP-xx, comma separated,
     the filename's row first), state, tests, drop condition;
  3. states are from the lifecycle vocabulary;
  4. register row ids (UP-<n>) never appear in patch content or overlay code
     — the ledger (and patch filenames) are the only mapping (layout
     principle 1: a patch must read as an upstream contribution).
"""
import argparse
import re
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--release", action="store_true", help="reject patches without steady evidence")
parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
args = parser.parse_args()
REPO = args.repo.resolve()
STATES = {"draft", "stabilizing", "steady", "upstream-submitted", "landed (dropped)"}
ROW_ID = re.compile(r"\bUP-\d+\b")
REGISTER_ID = re.compile(r"(?:UP|FEATURE)-\d+")

def fail(msg):
    print(f"check_ledger: FAIL {msg}")
    sys.exit(1)

series_path = REPO / "patches" / "series"
ledger_path = REPO / "patches" / "PATCHES.md"

series = []
if series_path.exists():
    for line in series_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            series.append(line)

# 1. series <-> files
if len(series) != len(set(series)):
    fail("duplicate entries in series")
for entry in series:
    if not (REPO / "patches" / entry).exists():
        fail(f"series lists {entry} but the file does not exist")
on_disk = sorted(p.name for p in (REPO / "patches").glob("*.patch"))
in_series = sorted(Path(e).name for e in series)
if on_disk != in_series:
    fail(f"patch files on disk {on_disk} != series {in_series}")

# 2. ledger rows
ledger_rows = {}
if ledger_path.exists():
    for line in ledger_path.read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in ("patch", "") or set(cells[0]) <= {"-", " ", ":"}:
            continue
        if cells[0] in ledger_rows:
            fail(f"duplicate ledger row: {cells[0]}")
        ledger_rows[cells[0]] = cells

for entry in series:
    name = Path(entry).name
    if name not in ledger_rows:
        fail(f"{name}: no ledger row in PATCHES.md")
    cells = ledger_rows[name]
    row_id, state, tests, drop = cells[1], cells[2], cells[3], cells[4]
    row_ids = [part.strip() for part in row_id.split(",")]
    if not all(REGISTER_ID.fullmatch(part) for part in row_ids):
        fail(f"{name}: ledger rows {row_id!r} are not upstream defect or product feature ids")
    if not name[5:].startswith(row_ids[0] + "-"):
        fail(f"{name}: the filename names {name[5:].split('-')[0]}-..., the ledger's first row is {row_ids[0]}")
    if state not in STATES:
        fail(f"{name}: unknown state {state!r}")
    if state not in ("draft",) and not tests:
        fail(f"{name}: state {state} requires a test map")
    if args.release:
        if state != "steady":
            fail(f"{name}: release requires steady, found {state}")
        # Test paths in the ledger must name files carried by this patch or
        # repository. Prose about a benchmark is not an executable test map.
        paths = re.findall(r"[\w./-]+\.(?:cppm|cpp|test|py)", tests)
        patch = (REPO / "patches" / entry).read_text()
        if not paths:
            fail(f"{name}: release requires executable test paths")
        for path in paths:
            llvm_path = path
            for short, full in (("clangd/", "clang-tools-extra/clangd/"), ("clang-tidy/test/", "clang-tools-extra/test/clang-tidy/")):
                if llvm_path.startswith(short):
                    llvm_path = full + llvm_path[len(short):]
            if not (REPO / path).is_file() and f"+++ b/{llvm_path}" not in patch:
                fail(f"{name}: missing test {path}")
    if not drop:
        fail(f"{name}: missing drop condition")

# 4. row ids must not leak into patch content or overlay sources
for entry in series:
    text = (REPO / "patches" / entry).read_text(errors="replace")
    for i, line in enumerate(text.splitlines()):
        if line.startswith(("+", "-")) and ROW_ID.search(line):
            fail(f"{entry}: row id inside patch content (line {i+1}) — "
                 "the ledger is the only mapping")
for src in (REPO / "overlay").rglob("*"):
    if src.is_file() and src.suffix in (".cpp", ".h", ".test", ".ts", ".md") \
            and src.name != "PATCHES.md":
        if ROW_ID.search(src.read_text(errors="replace")):
            fail(f"overlay/{src.relative_to(REPO / 'overlay')}: row id inside source")

print(f"check_ledger: OK ({len(series)} patches, {len(ledger_rows)} ledger rows)")
