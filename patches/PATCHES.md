# Patch ledger

One entry per carried patch: the register row it carries, its state, its test
map, and its drop condition. `ci/check_ledger.py` enforces this file against
`patches/series` (plan doc §3, layout principle 3; verification map:
fix-register doc §1).

States: `draft` → `stabilizing` → `steady` → `upstream-submitted` → `landed (dropped)`.
Only `steady` rides a release. Row ids never appear inside patch code or tests —
they live here and in patch *filenames* only.

| patch | row | state | tests | drop condition |
|-------|-----|-------|-------|----------------|
| 0001-UP-05-backport-handling-merging-predefined-decls-from-std.patch | UP-05 | stabilizing | clang/test/Modules/pr218152.cppm (in-patch, upstream's own) | upstream landed it in 23.1.1 (52774473867e); drop when the bundled base is bumped past 23.1.0 |
| 0002-UP-25-memoize-module-file-validation-across-requests.patch | UP-25 | stabilizing | clangd/test/modules-validation-cache.test (in-patch); bench gate: warm completion p95 (tests/probes) | drop when upstream memoizes BMI validation for the preamble-reuse path |
| 0003-UP-18-break-module-cache-locks-whose-owner-died.patch | UP-18 | stabilizing | clangd/test/modules-stale-lock.test (in-patch); soak covers kill -9 cycles | drop when upstream breaks dead-owner module locks on Windows |
