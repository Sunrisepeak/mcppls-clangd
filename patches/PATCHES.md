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
| 0005-UP-22-const-correctness-ranges-pipeline.patch | UP-22 | stabilizing | clang-tidy/test/clang-tidy/checkers/misc/const-correctness-cxx20-ranges.cpp (in-patch); broad heuristic superseded by patch 0021, retained as series history | drop together with patch 0021 when upstream semantically validates const range consumption |
| 0006-UP-25-completion-index-fast-path.patch | UP-25 | draft | clangd/test/modules*.test (fallback when no index); bench: qt-demo identifier/qualified completion p95 (measured 81 ms, was ~1000 ms; gate < 200 ms); item-set verified against the Sema path (nlohmann::j → 12 correct members) | drop when upstream serves module completion without re-deserializing BMIs per request (S2-B tables or equivalent) |
| 0007-UP-13-windows-crash-dumps.patch | UP-13 | draft | win-crash-corpus job (save-loop scenario; per-row entries land with C0 corpus); gives every Windows crash a symbolized dump, unblocking UP-12/13/20 stacks | drop when upstream gains native crash-dump diagnostics for the LSP server |
| 0008-UP-25-semantic-module-completion-default.patch | UP-25 | draft | tests/e2e/completion_quality.py | drop when module completion preserves scope and unindexed exports without the parser |
| 0009-UP-25-precise-validation-input-identity.patch | UP-25 | draft | tests/e2e/completion_quality.py | drop when upstream validation memo tracks precise input identity |
| 0010-UP-13-crash-dump-declaration.patch | UP-13 | draft | ci/ci_build.sh | drop together with the Windows crash capture implementation |
| 0011-UP-25-validation-memo-respects-drafts.patch | UP-25 | stabilizing | clangd/test/modules-validation-overlay.test (in-patch); tests/e2e/completion_quality.py --unsaved-update; product inferred/C7 | drop when upstream memo verifies the request VFS identities before accepting a disk verdict |

| 0012-mcpp-fallback-style.patch | FEATURE-43 | stabilizing | clang-tools-extra/clangd/test/mcpp-format-style.test; clang-tools-extra/clangd/test/mcpp-format-fallback.test; clang/unittests/Format/ConfigParseTest.cpp | Upstream supports the pinned mcpp preset or an equivalent explicit fallback configuration |

| 0013-UP-25-completion-refreshes-module-dependencies.patch | UP-25 | stabilizing | tests/e2e/completion_quality.py | Upstream completion validates module dependencies against the request filesystem and refreshes stale BMI views |

| 0014-compiler-extension-semantic-completion.patch | FEATURE-44 | stabilizing | tests/e2e/compiler_extensions.py | Upstream offers declaration attribute introducers, cleanup function references and target/context-aware SEH without index-only keyword pollution |

| 0015-UP-01-module-directive-token-recovery.patch | UP-01 | stabilizing | clang-tools-extra/clangd/test/module-directive-recovery.test; tests/e2e/module_directive_recovery.py; clang/unittests/Tooling/Syntax/TokensTest.cpp | Upstream token collection ignores logical end-of-directive tokens and raw malformed module directives recover without hanging |

| 0016-module-lock-wait-cancellation.patch | UP-21 | stabilizing | tests/e2e/module_lock_close.py | Upstream document close cancels active preamble module-lock waits without deleting live-owner locks |

| 0017-module-dependency-cycle-rejection.patch | UP-03 | stabilizing | tests/e2e/module_cycle.py | Upstream prerequisite graph traversal distinguishes active cycles from completed diamond dependencies and propagates a cycle error before BMI construction |

| 0018-completion-stage-tracing.patch | UP-25 | stabilizing | tests/probes/project_completion.py --trace; ci/project-completion-performance.md | Upstream completion tracing independently reports module validation and semantic execution for real project optimization |

| 0019-third-party-imports-keep-resolvable-modules.patch | UP-25 | stabilizing | tests/e2e/third_party_import.py | Upstream keeps resolvable module BMIs and the textual-import file preamble when a direct import has no buildable unit in the project; the skip verdict re-derives on file or command changes |

| 0020-prerequisite-reuse-dies-with-command-generation.patch | UP-25 | stabilizing | tests/e2e/third_party_import.py | Upstream reusable prerequisite sets record the compile-command generation and stop being reused after a command-change broadcast, so a provider appearing later reaches files that resolved to nothing |

| 0021-UP-22-semantic-const-range-constraints.patch | UP-22 | stabilizing | clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-range-constraints.cpp; tests/e2e/const_correctness.py; ci/const-correctness.md | Upstream checks const iterator/adaptor overload viability with instantiated constraints while preserving valid ordinary pipe and const-capable range suggestions |

| 0022-UP-24-copy-on-read-owner-leases.patch | UP-24 | stabilizing | tests/e2e/module_cache_lease.py; ci/module-read-leases.md | Upstream copy-on-read lifetime has kernel-backed owner leases, immediate crash-orphan reclamation, and protection of live readers and published BMIs |

| 0023-UP-03-bounded-module-dag-compilation.patch | UP-03 | stabilizing | clang-tools-extra/clangd/test/modules-bounded-dag.test; tests/e2e/module_dag.py; tests/e2e/module_cycle.py; tests/e2e/module_lock_close.py; tests/e2e/third_party_import.py; ci/module-dag-compilation.md | Upstream schedules ready nodes in a shared bounded pool, preserves prebuilt dependencies and textual direct imports, and drains failed/cancelled jobs before releasing request state |

| 0024-UP-12-missing-bmi-directive-replay.patch | UP-12 | stabilizing | clang-tools-extra/clangd/test/missing-bmi-token-recovery.test; clang/unittests/Tooling/Syntax/TokensTest.cpp; tests/crash/candidates/up12-galtranslpp.json; ci/missing-bmi-directive-recovery.md | Upstream contextual module keyword handling consumes a successfully queued directive even after an earlier missing BMI sets the fatal-loader flag; native historical Windows crash qualification remains required |
| 0025-UP-03-provider-command-generation-cache.patch | UP-03 | stabilizing | clangd/unittests/PrerequisiteModulesTest.cpp Provider* and GlobalCompilationDatabaseTests.cpp ProviderIndexFollowsDatabaseGeneration (in-patch); tests/e2e/module_provider_cache.py; tests/evidence/module-provider-cache.json | drop when upstream reuses provider command facts with equivalent CDB generation, adjusted-command, response-file and source-validation guarantees |

| 0026-UP-23-request-buffer-module-scans.patch | UP-23 | stabilizing | clangd/unittests/PrerequisiteModulesTest.cpp UnsavedImportUsesExactRequestBuffer (in-patch); tests/e2e/module_request_inputs.py; tests/e2e/module_dag.py; ci/request-module-inputs.md | Upstream propagates exact request inputs through module scans and reuse checks with request-owned overlay bytes outliving scanner caches and drained jobs |

| 0027-UP-15-module-separator-diagnostic-locations.patch | UP-15 | stabilizing | clangd/unittests/DiagnosticsTests.cpp MissingModuleSeparatorsStayOnDirective and DiagnosticRanges (in-patch); clang/test/Modules/missing-module-semicolon-location.cpp; tests/e2e/module_directive_diagnostics.py; ci/module-separator-diagnostics.md | Upstream keeps missing separator diagnostics and insertions on the original directive while preserving real-token diagnostic ranges; verified package capability required before retiring product compatibility |

| 0028-UP-03-verified-module-dependency-scan-memo.patch | UP-03 | stabilizing | clangd/unittests/PrerequisiteModulesTest.cpp PositiveScanMemo* (in-patch); tests/e2e/module_scan_memo.py; ci/module-scan-memo.md | Upstream verifies every observed scan input, command/CDB/environment and alias relation with bounded retained ownership, while unsupported target/discovery inputs decline reuse; compiler/deadline/RSS admission remains separate |

| 0029-UP-03-observe-module-scan-builtin-expansions.patch | UP-03 | stabilizing | tests/e2e/module_scan_builtins.py; ci/module-scan-builtins.md | Upstream observes actual time-dependent builtin expansions before positive scan reuse, while keeping the driver and filesystem observation contract |

| 0031-UP-03-module-build-cancellation-boundaries.patch | UP-03 | stabilizing | PrerequisiteModulesTests.CancellationAtCompilerBoundaries; ci/module-build-cancellation.md | Upstream discards observed cancellation at compiler boundaries and cleans temporary PCMs before publication |

| 0032-UP-25-first-module-completion-commands.patch | UP-25 | stabilizing | tests/e2e/module_cold_completion.py; ci/module-cold-completion.md | Upstream first module completion waits for initial inputs and uses the resolved compile command while preserving explicit fallback |

| 0033-UP-24-owner-lease-gc-fixture.patch | UP-24 | stabilizing | PrerequisiteModulesTests.PersistentModuleCacheGCReclaimsOnlyUnownedReadCopies; ci/module-build-cancellation.md | Upstream GC fixture asserts actual orphan kernel-lease ownership while retaining stable and active-reader PCMs |
