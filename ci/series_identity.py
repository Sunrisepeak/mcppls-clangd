#!/usr/bin/env python3
"""Digest ordered patch bytes and overlay paths/content for applied-tree identity."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent.parent
digest = hashlib.sha256()


def add(name, data):
    encoded = name.encode()
    digest.update(len(encoded).to_bytes(8, 'big'))
    digest.update(encoded)
    digest.update(len(data).to_bytes(8, 'big'))
    digest.update(data)


for line in (root / 'patches/series').read_text().splitlines():
    entry = line.split('#', 1)[0].strip()
    if entry:
        add(entry, (root / 'patches' / entry).read_bytes())
for path in sorted((root / 'overlay').rglob('*')):
    if path.is_file():
        add('overlay/' + path.relative_to(root / 'overlay').as_posix(), path.read_bytes())
print(digest.hexdigest())
