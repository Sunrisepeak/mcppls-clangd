#!/usr/bin/env python3
"""check_tree.py — the repository carries sources, not generated output.

Fails on a tracked file above 1 MiB, a generated module/precompiled/object file,
or an absolute home-directory path (a machine's local layout) in a text file.
Raw evidence belongs in a release's evidence archive (tests/evidence/README.md).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 1 << 20
GENERATED = re.compile(r"\.(pcm|pch|o|obj|gch)(\.gz|\.zst)?$")
# CI runner accounts are not a person's machine; a recorded runner path is fine.
HOME = re.compile(rb"(?<![\w$])(?:/home/|/Users/|[A-Za-z]:\\\\?Users\\\\?)(?!runner(?:admin)?\b)[A-Za-z0-9._-]+[/\\]")
SELF = {"ci/check_tree.py"}

files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout.split(b"\0")
problems = []
for raw in filter(None, files):
    name = raw.decode()
    path = ROOT / name
    if not path.is_file():
        continue
    if GENERATED.search(name):
        problems.append(f"{name}: generated file")
    size = path.stat().st_size
    if size > LIMIT and not name.startswith("patches/"):
        problems.append(f"{name}: {size} bytes, above {LIMIT}")
    if name in SELF:
        continue
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        continue
    match = HOME.search(data)
    if match:
        problems.append(f"{name}: absolute home path {match.group(0).decode(errors='replace')!r}")
for problem in problems:
    print(f"check_tree: FAIL {problem}")
if problems:
    sys.exit(1)
print(f"check_tree: OK ({sum(1 for f in files if f)} tracked files)")
