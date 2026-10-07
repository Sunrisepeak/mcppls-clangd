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
| 0004-UP-09-semantic-tokens-range.patch | UP-09 | stabilizing | clangd/test/semantic-tokens-range.test (in-patch) | drop when upstream implements textDocument/semanticTokens/range |
| 0005-UP-22-const-correctness-ranges-pipeline.patch | UP-22 | draft | clang-tidy/test/clang-tidy/checkers/misc/const-correctness-cxx20-ranges.cpp (in-patch); verified on the issue #37 shape (piped filter_view no longer flagged); follow-up: teach ExprMutationAnalyzer the by-value range-for case (transform_view still flagged) | drop when upstream stops suggesting const for ranges forwarded into pipes |
| 0006-UP-25-completion-index-fast-path.patch | UP-25 | draft | clangd/test/modules*.test (fallback when no index); bench: qt-demo identifier/qualified completion p95 (measured 81 ms, was ~1000 ms; gate < 200 ms); item-set verified against the Sema path (nlohmann::j → 12 correct members) | drop when upstream serves module completion without re-deserializing BMIs per request (S2-B tables or equivalent) |
| 0007-UP-13-windows-crash-dumps.patch | UP-13 | draft | win-crash-corpus job (save-loop scenario; per-row entries land with C0 corpus); gives every Windows crash a symbolized dump, unblocking UP-12/13/20 stacks | drop when upstream gains native crash-dump diagnostics for the LSP server |
| 0008-UP-25-semantic-module-completion-default.patch | UP-25 | draft | tests/e2e/completion_quality.py | drop when module completion preserves scope and unindexed exports without the parser |
| 0009-UP-25-precise-validation-input-identity.patch | UP-25 | draft | tests/e2e/completion_quality.py | drop when upstream validation memo tracks precise input identity |
| 0010-UP-13-crash-dump-declaration.patch | UP-13 | draft | ci/ci_build.sh | drop together with the Windows crash capture implementation |
| 0011-UP-25-validation-memo-respects-drafts.patch | UP-25 | stabilizing | clangd/test/modules-validation-overlay.test (in-patch); tests/e2e/completion_quality.py --unsaved-update; product inferred/C7 | drop when upstream memo verifies the request VFS identities before accepting a disk verdict |

| 0012-mcpp-fallback-style.patch | FEATURE-43 | stabilizing | clang-tools-extra/clangd/test/mcpp-format-style.test; clang-tools-extra/clangd/test/mcpp-format-fallback.test; clang/unittests/Format/ConfigParseTest.cpp | Upstream supports the pinned mcpp preset or an equivalent explicit fallback configuration |
