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

| 0030-UP-03-response-input-CDB-generation-reload.patch | UP-03 | stabilizing | GlobalCompilationDatabaseTest.Response*; ci/response-file-generations.md | Upstream generations own immutable nested response inputs and reload on exact input changes, including forced provider inventory freshness |

| 0031-UP-03-module-build-cancellation-boundaries.patch | UP-03 | stabilizing | PrerequisiteModulesTests.CancellationAtCompilerBoundaries; ci/module-build-cancellation.md | Upstream discards observed cancellation at compiler boundaries and cleans temporary PCMs before publication |

| 0032-UP-25-first-module-completion-commands.patch | UP-25 | stabilizing | tests/e2e/module_cold_completion.py; ci/module-cold-completion.md | Upstream first module completion waits for initial inputs and uses the resolved compile command while preserving explicit fallback |

| 0033-UP-24-owner-lease-gc-fixture.patch | UP-24 | stabilizing | PrerequisiteModulesTests.PersistentModuleCacheGCReclaimsOnlyUnownedReadCopies; ci/module-build-cancellation.md | Upstream GC fixture asserts actual orphan kernel-lease ownership while retaining stable and active-reader PCMs |

| 0034-UP-03-module-compiler-worker-protocol.patch | UP-03 | stabilizing | PrerequisiteModulesTests.ModuleWorkerPreservesCapturedInputs; ci/module-worker-isolation.md | Upstream provides a module worker input protocol with captured VFS semantics and explicit output ownership; parent supervision remains separately required |

| 0035-UP-03-module-worker-supervision-and-drafts.patch | UP-03 | stabilizing | DraftStore.AtomicSnapshotRetainsVersionsAndExportsDirtyHeaders; PrerequisiteModulesTests.ModuleWorker*; ci/module-worker-isolation.md | Upstream supervises only its owned compiler child, reaps before cleanup and exports actual atomic request drafts; actual server enablement remains separate |

| 0036-UP-03-windows-module-dag-macro-portability.patch | UP-03 | stabilizing | native Windows build; ci/module-worker-isolation.md | Upstream module DAG standard function calls compile with Windows min/max macros without changing scheduling |

| 0037-UP-03-module-worker-owner-lifetime.patch | UP-03 | stabilizing | PrerequisiteModulesTests.ModuleWorkerPreservesCapturedInputs; ci/module-worker-isolation.md | Upstream supervised compiler workers use a real inherited owner object and exit when that owner dies; orphan directory collection remains separate |

| 0038-UP-03-shared-module-worker-memory-budget.patch | UP-03 | stabilizing | PrerequisiteModulesTests.ModuleWorkerBudgetFailsClosedBeforeRequestRead; ci/module-worker-isolation.md | Upstream worker admission shares a checked owned cgroup budget and rejects unverifiable limits, membership and in-process fallback |

| 0039-UP-03-collect-leased-module-worker-units.patch | UP-03 | stabilizing | clangd/unittests/PrerequisiteModulesTest.cpp ModuleWorkerCollectionRequiresBothOwnersGone; ci/module-worker-isolation.md | Upstream owned worker units use parent and worker kernel leases and bounded maintenance collection without deleting live or unmarked data |

| 0040-UP-03-module-worker-address-space-limits.patch | UP-03 | stabilizing | tests/evidence/module-worker-address-space.json; ci/module-worker-isolation.md | Upstream worker launch checks configured address-space limits before frontend allocations and exits without recursive allocation diagnostics on exhaustion |

| 0041-UP-03-default-supervised-module-workers.patch | UP-03 | stabilizing | tests/e2e/module_worker_default.py; tests/e2e/module_worker_failure.py; tests/e2e/module_cold_completion.py; tests/e2e/module_request_inputs.py; ci/module-worker-isolation.md | Upstream default prerequisite builds supervise exportable worker inputs with shared pool limits, verified optional memory admission and separate bounded unit maintenance |

| 0042-UP-03-relative-worker-inputs-and-fixture-policy.patch | UP-03 | stabilizing | clangd/unittests/PrerequisiteModulesTest.cpp ModuleWorkerPreservesCapturedInputs; tests/e2e/module_worker_default.py | Upstream worker protocol preserves legal relative cc1 input spelling and compiler-hook fixtures explicitly select their execution policy |

| 0043-UP-03-collect-owned-worker-memory-budgets.patch | UP-03 | stabilizing | tests/evidence/module-worker-budget-collection.json; ci/module-worker-isolation.md | Upstream configured compiler budgets publish verified kernel ownership leases and independently collect marked crash-orphan cgroups while preserving live, replaced and mismatched groups |

| 0044-UP-03-reuse-verified-module-scan-failures.patch | UP-03 | stabilizing | ci/module-scan-memo.md; tests/evidence/project-qt-worker46.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream scan reuse preserves semantic failure diagnostics and verifies complete bounded request manifests, cancellation and real-path observations |

| 0045-UP-03-bounded-linux-worker-diagnostics.patch | UP-03 | stabilizing | tests/e2e/module_worker_diagnostics.py; tests/evidence/module-worker-diagnostics.json; ci/module-worker-isolation.md | Upstream Linux supervised workers bound queued diagnostics and retained prefixes without unbounded stderr files or truncating PCM output |

| 0046-UP-24-bounded-read-copy-maintenance.patch | UP-24 | stabilizing | tests/evidence/module-read-copy-maintenance.json; ci/module-read-copy-maintenance.md; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream copy-on-read orphan maintenance uses bounded resumable traversal outside requests and preserves active physical leases across aliases |

| 0048-UP-25-reuse-preamble-build-mode-in-completion.patch | UP-25 | stabilizing | ci/completion-preamble-policy.md; tests/evidence/completion-preamble-mode.json; clangd/unittests/ClangdTests.cpp; clangd/unittests/PreambleTests.cpp | Upstream completion carries the actual preamble build mode and avoids redundant policy scans while retaining fresh module validation |

| 0050-UP-23-asynchronous-module-preamble-policy.patch | UP-23 | stabilizing | ci/asynchronous-module-update.md; tests/e2e/module_preamble_mode.py; clangd/unittests/ClangdTests.cpp | Upstream document updates resolve current module preamble policy on the update worker and include that policy in AST input equality |

| 0051-UP-26-owned-preamble-trace-filenames.patch | UP-26 | stabilizing | ci/preamble-trace-lifetime.md; tests/evidence/preamble-trace-lifetime.json; clangd/unittests/PreambleTests.cpp | Upstream preamble trace attachments own filenames through retained asynchronous contexts and the delayed-context canary passes |

| 0052-UP-23-portable-response-generation-fixtures.patch | UP-23 | stabilizing | ci/response-generation-portability.md; clangd/unittests/GlobalCompilationDatabaseTests.cpp | Upstream response-generation fixtures serialize platform paths as JSON and retain all immutable-publication assertions on Windows |

| 0053-UP-03-bounded-scan-publication-coordination.patch | UP-03 | stabilizing | ci/module-scan-publication.md; tests/evidence/module-scan-publication.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream identical scan publications use bounded notification coordination and each follower validates the result against its own current VFS |

| 0047-UP-03-bounded-worker-output-and-captured-inputs.patch | UP-03 | stabilizing | ci/module-worker-payloads.md; tests/evidence/module-worker-payloads.json; tests/e2e/module_worker_default.py; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream bounded worker output covers reduced/implicit/index writers, capture preflight precedes writes, and older workers reject bounded protocol requests |

| 0054-UP-03-indexed-exact-scan-observations.patch | UP-03 | stabilizing | ci/module-scan-recording.md; tests/evidence/module-scan-recording.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream exact scan recording avoids quadratic accounting/search and includes bounded index/growth metadata while preserving every observation and fresh replay |

| 0055-UP-03-full-scan-content-fingerprints.patch | UP-03 | stabilizing | ci/module-scan-fingerprints.md; tests/evidence/module-scan-fingerprints.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream full content hashing avoids software SHA256 cost while preserving every byte, exact observations and current-view replay |

| 0056-UP-03-native-scan-publication-admission.patch | UP-03 | stabilizing | ci/module-scan-native-admission.md; tests/evidence/module-scan-native-admission.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream publication test covers both admitted Linux coordination and unsupported native fresh-scan behavior without assuming cache admission |

| 0057-UP-03-requesting-project-provider-commands.patch | UP-03 | stabilizing | ci/module-provider-commands.md; tests/evidence/module-provider-commands.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream buildability/prebuilt/DAG resolution uses the importing request generation for explicit external providers while preserving global/overlay command precedence |

| 0058-UP-27-optional-overlay-module-mangler.patch | UP-27 | stabilizing | ci/optional-overlay-mangler.md; tests/evidence/optional-overlay-mangler.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream default OverlayCDB module scanning guards its optional command mangler and actual default/explicit module AST controls pass |

| 0049-UP-03-owned-module-payload-admission.patch | UP-03 | stabilizing | ci/owned-module-payloads.md; tests/evidence/owned-module-payloads.json; clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_worker_default.py | Upstream persistent aggregate namespace admission precedes capture/output and immutable stable/copy generations retain kernel leases through parent/child consumption and verified retirement |

| 0059-UP-03-owned-implicit-module-bundles.patch | UP-03 | stabilizing | ci/owned-implicit-module-bundles.md; tests/evidence/owned-implicit-module-bundles.json; clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_worker_default.py | Upstream implicit producer paths retain full bounded durable bundle charge and independent main-copy/companion leases through publication, reuse and verified retirement |

| 0060-UP-03-native-full-content-scan-controls.patch | UP-03 | stabilizing | ci/native-full-content-scan-controls.md; tests/evidence/native-full-content-scan-controls.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream full-byte semantic controls preserve size and mtime while asserting only the actual native cache admission policy |

| 0061-UP-03-preserve-GCC-module-mapper-dialect.patch | UP-03 | stabilizing | ci/gcc-module-mapper-dialect.md; tests/evidence/gcc-module-mapper-dialect.json; clangd/unittests/CompileCommandsTests.cpp; tests/probes/project_completion.py | Upstream command adjustment preserves the proven GCC mapper dialect and unchanged-Clang/explicit-map plus real JSON insertion controls pass |

| 0062-UP-23-attached-module-preamble-policy.patch | UP-23 | stabilizing | ci/attached-module-preamble-policy.md; tests/evidence/attached-module-preamble-policy.json; clangd/unittests/PrerequisiteModulesTest.cpp; tests/e2e/module_scan_memo.py | Upstream preamble construction derives textual module policy from actual attached leased BMIs, preserving ordinary PCH and repeated semantic/lifetime controls |

| 0063-UP-20-published-prerequisite-generations.patch | UP-20 | stabilizing | ci/published-prerequisite-generations.md; tests/evidence/published-prerequisite-generations.json; clangd/unittests/PrerequisiteModulesTest.cpp StandardModuleProfileInvalidatesConsumer (in-patch) | Upstream consumer cache identity binds to the actual published dependency versions while normal compiler validation, changed-profile semantic rebuild and stable-chain/different-copy warm reuse pass; full historical save/recovery qualification remains required |

| 0064-UP-03-owned-module-build-publication-events.patch | UP-03 | stabilizing | ci/owned-module-build-events.md; tests/evidence/owned-module-build-events.json; tests/e2e/module_cycle.py | Upstream fresh owned publication preserves the established build event and actual cyclic recovery plus diamond imported semantic completion pass |

| 0065-UP-03-exact-module-scan-filesystem-queries.patch | UP-03 | stabilizing | ci/module-scan-relative-queries.md; tests/evidence/module-scan-relative-queries.json; clangd/unittests/PrerequisiteModulesTest.cpp | Upstream exact filesystem query recording preserves relative result names while real same-size/full-mtime byte changes still invalidate replay |
