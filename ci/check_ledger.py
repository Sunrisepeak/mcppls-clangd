#!/usr/bin/env python3
"""check_ledger.py — enforce patches/PATCHES.md against patches/series and the
tree (plan doc §3 layout principle 3; §4.3 job verify-series).

Checks:
  1. every patch in `series` exists and every existing patch is in `series`;
  2. every patch has a ledger row with: register row (UP-xx), state, tests,
     drop condition;
  3. states are from the lifecycle vocabulary;
  4. register row ids (UP-<n>) never appear in patch content or overlay code
     — the ledger (and patch filenames) are the only mapping (layout
     principle 1: a patch must read as an upstream contribution).
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATES = {"draft", "stabilizing", "steady", "upstream-submitted", "landed (dropped)"}
ROW_ID = re.compile(r"\bUP-\d+\b")

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
        ledger_rows[cells[0]] = cells

for entry in series:
    name = Path(entry).name
    if name not in ledger_rows:
        fail(f"{name}: no ledger row in PATCHES.md")
    cells = ledger_rows[name]
    row_id, state, tests, drop = cells[1], cells[2], cells[3], cells[4]
    if not ROW_ID.fullmatch(row_id):
        fail(f"{name}: ledger row id {row_id!r} is not a UP-xx id")
    if state not in STATES:
        fail(f"{name}: unknown state {state!r}")
    if state not in ("draft",) and not tests:
        fail(f"{name}: state {state} requires a test map")
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
