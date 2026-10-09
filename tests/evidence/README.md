# Evidence

Raw evidence is not kept in this repository. Reports, traces, logs and
replay inputs are produced by the scripts under `ci/`, `tests/e2e/` and
`tests/probes/`, and a release's evidence is published as one archive.

| Release | Archive | sha256 | Files |
|---|---|---|---|
| 0.0.12 | [`mcppls-clangd-0.0.12-evidence.tar.zst`](https://github.com/Sunrisepeak/mcppls-clangd/releases/tag/evidence-0.0.12) | `a50e884595447178c7aa750c579f69b9eb204f0f5bfde2b0e1812a59830c1ea1` | 3212 evidence files and the 74 incremental patches |

Paths of the form `tests/evidence/...` in `ci/*.md` and in older plans name
files inside that archive (`mcppls-clangd-0.0.12-evidence/tests/evidence/...`).
Patch numbers in them are the incremental series; `patches/HISTORY.md` maps
them to the topic patches. CI keeps its own run evidence as workflow artifacts.

`ci/check_tree.py` keeps it this way: it refuses tracked files above 1 MiB,
generated module and object files, and absolute home-directory paths.
