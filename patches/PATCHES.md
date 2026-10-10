# Patch ledger

One entry per carried patch: the register rows it carries, its state, its test
map, and its drop condition. `ci/check_ledger.py` enforces this file against
`patches/series` (plan doc §3, layout principle 3; verification map:
fix-register doc §1).

States: `draft` → `stabilizing` → `steady` → `upstream-submitted` → `landed (dropped)`.
Only `steady` rides a release. Row ids never appear inside patch code or tests —
they live here and in patch *filenames* only; a filename carries the patch's
primary row, the `rows` column every row it serves.

A patch is **steady** when the series it belongs to, applied to the pinned
tarball, builds on every release platform (`build-test`), every test its row
maps passes in that run, the Ubuntu 20.04 floor package passes its runtime
controls, and no known negative remains open against it. A change to a steady
patch returns it to `stabilizing` until the same run passes again.

## The 0.0.12 series

The 0.0.12 series carries 25 topic patches. They were regrouped from 74
incremental patches without changing the patched tree (both apply to
`a2e92ba00e6666eaa5d1f975a4bd65b80537dbab`); each multi-change patch lists the
changes it combines in its message. Since then, running the product against the engine found these, each fixed in
the patch it belongs to: 0025's `ExternalUnqualifiedNamesPreserveScopesAndUsing`
compares, for an empty pattern, only the names its header declares (the
ordinary lookup an empty pattern uses lists target predeclarations and macros
differently for a preamble and a main file on x86_64-pc-windows-msvc); 0017's
module worker reports a command directory that does not exist yet and builds
on, as an in-process build does; 0025's completion inside the preamble region or
the module and import declarations (an import line being typed) no longer
rebuilds the prerequisites at every keystroke; 0019's owned cache skips a stable generation whose files
changed on disk instead of failing the module for good; and 0014's scan memo
replays a file's observations through one handle and does not read again a
header that is on disk with the identity, size and modification time it had,
last modified well before the scan (the metadata clang trusts for a module's
inputs), so a hit on `std.cppm` no longer reads and hashes every libc++ header.
The engine also proves `unresolved-import-recovery` on its package
(`ci/unresolved_import_canary.py`): a module unit importing a module nothing
provides leaves its importer answering. The tree is now
`982ccc039eaf43b47bfeb287064d9a477a97cb07`.
The incremental history and the raw evidence it produced are in the `archive/0.0.12-joint` branch and the `evidence-0.0.12`
release (`tests/evidence/README.md`).

| patch | rows | state | tests | drop condition |
|-------|------|-------|-------|----------------|
| 0001-UP-05-backport-std-predefined-decl-merge.patch | UP-05 | steady | clang/test/Modules/pr218152.cppm | upstream landed it in 23.1.1 (52774473867e); drop when the base is bumped past 23.1.0 |
| 0002-UP-25-module-validation-memo.patch | UP-25 | steady | clangd/test/modules-validation-cache.test; clangd/test/modules-validation-overlay.test; tests/e2e/completion_quality.py | upstream memoizes BMI validation for preamble reuse, keyed by precise input identity and verified against the request filesystem |
| 0003-UP-18-module-cache-locks.patch | UP-18, UP-21 | steady | clangd/test/modules-stale-lock.test; tests/e2e/module_lock_close.py | upstream breaks dead-owner module locks (Windows included) and cancels lock waits when the document closes |
| 0004-UP-09-semantic-tokens-range.patch | UP-09 | steady | clangd/test/semantic-tokens-range.test | upstream implements textDocument/semanticTokens/range |
| 0005-UP-22-const-correctness-ranges.patch | UP-22 | steady | clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-ranges.cpp; clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-range-constraints.cpp; tests/e2e/const_correctness.py | upstream validates const range consumption with instantiated constraints |
| 0006-UP-25-module-index-completion.patch | UP-25 | steady | tests/e2e/completion_quality.py (the opt-in index path stays off; the semantic default is asserted) | upstream serves module completion without re-deserializing BMIs per request; the opt-in flag goes with it |
| 0007-UP-13-windows-crash-dumps.patch | UP-13 | steady | ci/test_windows_crash_capture.py; .github/workflows/win-crash-corpus.yml | upstream gains native crash-dump diagnostics for the LSP server |
| 0008-UP-25-module-importer-semantic-completion.patch | UP-25 | steady | tests/e2e/completion_quality.py; tests/e2e/module_cold_completion.py; clangd/unittests/PreambleTests.cpp | upstream completion keeps semantic results on module importers, refreshes stale BMI views and waits for the resolved command |
| 0009-FEATURE-43-mcpp-format-style.patch | FEATURE-43 | steady | clangd/test/mcpp-format-style.test; clangd/test/mcpp-format-fallback.test | upstream supports the pinned mcpp preset or an equivalent explicit fallback configuration |
| 0010-FEATURE-44-compiler-extension-completion.patch | FEATURE-44 | steady | tests/e2e/compiler_extensions.py | upstream offers attribute introducers, cleanup references and target-aware SEH without index-only keyword pollution |
| 0011-UP-01-module-directive-recovery.patch | UP-01, UP-12, UP-15 | steady | clangd/test/module-directive-recovery.test; clangd/test/missing-bmi-token-recovery.test; clang/test/Modules/missing-module-semicolon-location.cpp; tests/e2e/module_directive_recovery.py; tests/e2e/module_directive_diagnostics.py | upstream token collection, missing-BMI keyword handling and separator diagnostics recover in place |
| 0012-UP-03-module-prerequisite-dag.patch | UP-03, UP-24, UP-25 | steady | clangd/test/modules-bounded-dag.test; ci/unresolved_import_canary.py; tests/e2e/module_dag.py; tests/e2e/module_cycle.py; tests/e2e/third_party_import.py; tests/e2e/module_cache_lease.py | upstream schedules prerequisite builds as a bounded cancellable DAG with cycle rejection, third-party import fallback and reader leases |
| 0013-UP-03-module-provider-command-cache.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_provider_cache.py | upstream reuses provider command facts across equivalent CDB generations |
| 0014-UP-03-module-dependency-scan-memo.patch | UP-03, UP-23 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_scan_memo.py; tests/e2e/module_scan_builtins.py; tests/e2e/module_request_inputs.py | upstream reuses dependency scans only after replaying every observed input |
| 0015-UP-03-module-compile-command-inputs.patch | UP-03, UP-23, UP-27 | steady | clangd/unittests/GlobalCompilationDatabaseTests.cpp; clangd/unittests/CompileCommandsTests.cpp; tests/e2e/module_response_inputs.py | upstream reloads response-file generations, resolves external module commands per project and preserves the GCC mapper dialect |
| 0016-UP-24-module-cache-gc-ownership-test.patch | UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp | the owned cache divergence (0017, 0019) is dropped |
| 0017-UP-03-module-compiler-workers.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_worker_default.py; tests/e2e/module_worker_failure.py; tests/e2e/module_worker_diagnostics.py | upstream isolates module compilation in supervised, budgeted workers |
| 0018-UP-24-module-read-copy-maintenance.patch | UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_cache_lease.py | upstream maintains copy-on-read orphans outside requests with bounded traversal |
| 0019-UP-03-owned-module-payloads.patch | UP-03, UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_worker_default.py | upstream owns module payloads through admission and kernel leases with cancellable bounded waits |
| 0020-UP-23-module-preamble-policy.patch | UP-23, UP-26 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_preamble_mode.py | upstream resolves the module preamble policy from the attached prerequisites |
| 0021-UP-20-published-prerequisite-generations.patch | UP-20, UP-03, UP-23 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_cycle.py; tests/e2e/module_dag.py | upstream binds consumers to published dependency generations and limits producer snapshots to their closure |
| 0022-UP-03-module-scan-exact-queries.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_scan_memo.py | upstream scan recording preserves relative query spelling |
| 0023-UP-28-verified-textual-module-preambles.patch | UP-28 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/completion_quality.py | upstream proves textual-prefix reuse with complete PCH input and import audits |
| 0024-UP-29-gnu-standard-module-producers.patch | UP-29 | steady | clangd/unittests/CompileCommandsTests.cpp; tests/e2e/module_request_inputs.py | upstream dependency scanning recognizes installed GNU standard module producers |
| 0025-UP-25-selective-completion-loading.patch | UP-25 | steady | clangd/unittests/CodeCompleteTests.cpp; clang/unittests/Serialization/NamespaceLookupTest.cpp; tests/e2e/frontend_completion_consumers.py | upstream completion loads only names that can match the typed prefix and emits each constructor overload once |
