# Series history

The 0.0.12 series was developed as 74 incremental patches and regrouped into 25
topic patches with an identical patched tree. Notes under `ci/` and the raw
evidence (`tests/evidence/README.md`) name patches by their incremental number;
this table says which topic patch now carries each one. The incremental patches
themselves are in the `archive/0.0.12-joint` branch and in the evidence archive.

| incremental | carried by |
|---|---|
| `0001-UP-05-backport-handling-merging-predefined-decls-from-std.patch` | `0001-UP-05-backport-std-predefined-decl-merge.patch` |
| `0002-UP-25-memoize-module-file-validation-across-requests.patch` | `0002-UP-25-module-validation-memo.patch` |
| `0003-UP-18-break-module-cache-locks-whose-owner-died.patch` | `0003-UP-18-module-cache-locks.patch` |
| `0004-UP-09-semantic-tokens-range.patch` | `0004-UP-09-semantic-tokens-range.patch` |
| `0005-UP-22-const-correctness-ranges-pipeline.patch` | `0005-UP-22-const-correctness-ranges.patch` |
| `0006-UP-25-completion-index-fast-path.patch` | `0006-UP-25-module-index-completion.patch` |
| `0007-UP-13-windows-crash-dumps.patch` | `0007-UP-13-windows-crash-dumps.patch` |
| `0008-UP-25-semantic-module-completion-default.patch` | `0008-UP-25-module-importer-semantic-completion.patch` |
| `0009-UP-25-precise-validation-input-identity.patch` | `0002-UP-25-module-validation-memo.patch` |
| `0010-UP-13-crash-dump-declaration.patch` | `0007-UP-13-windows-crash-dumps.patch` |
| `0011-UP-25-validation-memo-respects-drafts.patch` | `0002-UP-25-module-validation-memo.patch` |
| `0012-mcpp-fallback-style.patch` | `0009-FEATURE-43-mcpp-format-style.patch` |
| `0013-UP-25-completion-refreshes-module-dependencies.patch` | `0008-UP-25-module-importer-semantic-completion.patch` |
| `0014-compiler-extension-semantic-completion.patch` | `0010-FEATURE-44-compiler-extension-completion.patch` |
| `0015-UP-01-module-directive-token-recovery.patch` | `0011-UP-01-module-directive-recovery.patch` |
| `0016-module-lock-wait-cancellation.patch` | `0003-UP-18-module-cache-locks.patch` |
| `0017-module-dependency-cycle-rejection.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0018-completion-stage-tracing.patch` | `0008-UP-25-module-importer-semantic-completion.patch` |
| `0019-third-party-imports-keep-resolvable-modules.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0020-prerequisite-reuse-dies-with-command-generation.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0021-UP-22-semantic-const-range-constraints.patch` | `0005-UP-22-const-correctness-ranges.patch` |
| `0022-UP-24-copy-on-read-owner-leases.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0023-UP-03-bounded-module-dag-compilation.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0024-UP-12-missing-bmi-directive-replay.patch` | `0011-UP-01-module-directive-recovery.patch` |
| `0025-UP-03-provider-command-generation-cache.patch` | `0013-UP-03-module-provider-command-cache.patch` |
| `0026-UP-23-request-buffer-module-scans.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0027-UP-15-module-separator-diagnostic-locations.patch` | `0011-UP-01-module-directive-recovery.patch` |
| `0028-UP-03-verified-module-dependency-scan-memo.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0029-UP-03-observe-module-scan-builtin-expansions.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0030-UP-03-response-input-CDB-generation-reload.patch` | `0015-UP-03-module-compile-command-inputs.patch` |
| `0031-UP-03-module-build-cancellation-boundaries.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0032-UP-25-first-module-completion-commands.patch` | `0008-UP-25-module-importer-semantic-completion.patch` |
| `0033-UP-24-owner-lease-gc-fixture.patch` | `0016-UP-24-module-cache-gc-ownership-test.patch` |
| `0034-UP-03-module-compiler-worker-protocol.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0035-UP-03-module-worker-supervision-and-drafts.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0036-UP-03-windows-module-dag-macro-portability.patch` | `0012-UP-03-module-prerequisite-dag.patch` |
| `0037-UP-03-module-worker-owner-lifetime.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0038-UP-03-shared-module-worker-memory-budget.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0039-UP-03-collect-leased-module-worker-units.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0040-UP-03-module-worker-address-space-limits.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0041-UP-03-default-supervised-module-workers.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0042-UP-03-relative-worker-inputs-and-fixture-policy.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0043-UP-03-collect-owned-worker-memory-budgets.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0044-UP-03-reuse-verified-module-scan-failures.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0045-UP-03-bounded-linux-worker-diagnostics.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0046-UP-24-bounded-read-copy-maintenance.patch` | `0018-UP-24-module-read-copy-maintenance.patch` |
| `0047-UP-03-bounded-worker-output-and-captured-inputs.patch` | `0017-UP-03-module-compiler-workers.patch` |
| `0048-UP-25-reuse-preamble-build-mode-in-completion.patch` | `0008-UP-25-module-importer-semantic-completion.patch` |
| `0049-UP-03-owned-module-payload-admission.patch` | `0019-UP-03-owned-module-payloads.patch` |
| `0050-UP-23-asynchronous-module-preamble-policy.patch` | `0020-UP-23-module-preamble-policy.patch` |
| `0051-UP-26-owned-preamble-trace-filenames.patch` | `0020-UP-23-module-preamble-policy.patch` |
| `0052-UP-23-portable-response-generation-fixtures.patch` | `0015-UP-03-module-compile-command-inputs.patch` |
| `0053-UP-03-bounded-scan-publication-coordination.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0054-UP-03-indexed-exact-scan-observations.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0055-UP-03-full-scan-content-fingerprints.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0056-UP-03-native-scan-publication-admission.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0057-UP-03-requesting-project-provider-commands.patch` | `0015-UP-03-module-compile-command-inputs.patch` |
| `0058-UP-27-optional-overlay-module-mangler.patch` | `0015-UP-03-module-compile-command-inputs.patch` |
| `0059-UP-03-owned-implicit-module-bundles.patch` | `0019-UP-03-owned-module-payloads.patch` |
| `0060-UP-03-native-full-content-scan-controls.patch` | `0014-UP-03-module-dependency-scan-memo.patch` |
| `0061-UP-03-preserve-GCC-module-mapper-dialect.patch` | `0015-UP-03-module-compile-command-inputs.patch` |
| `0062-UP-23-attached-module-preamble-policy.patch` | `0020-UP-23-module-preamble-policy.patch` |
| `0063-UP-20-published-prerequisite-generations.patch` | `0021-UP-20-published-prerequisite-generations.patch` |
| `0064-UP-03-owned-module-build-publication-events.patch` | `0021-UP-20-published-prerequisite-generations.patch` |
| `0065-UP-03-exact-module-scan-filesystem-queries.patch` | `0022-UP-03-module-scan-exact-queries.patch` |
| `0066-UP-28-verified-textual-module-preambles.patch` | `0023-UP-28-verified-textual-module-preambles.patch` |
| `0067-UP-29-GNU-standard-module-producer-dialect.patch` | `0024-UP-29-gnu-standard-module-producers.patch` |
| `0068-UP-25-selective-external-namespace-completion.patch` | `0025-UP-25-selective-completion-loading.patch` |
| `0069-UP-25-selective-guide-operator-completion.patch` | `0025-UP-25-selective-completion-loading.patch` |
| `0070-UP-25-selective-unqualified-completion.patch` | `0025-UP-25-selective-completion-loading.patch` |
| `0071-UP-25-joint-completion-input-validation.patch` | `0025-UP-25-selective-completion-loading.patch` |
| `0072-UP-25-canonical-constructor-completion.patch` | `0025-UP-25-selective-completion-loading.patch` |
| `0073-UP-24-cancellable-owned-payload-admission.patch` | `0019-UP-03-owned-module-payloads.patch` |
| `0074-UP-23-dependency-closed-producer-snapshots.patch` | `0021-UP-20-published-prerequisite-generations.patch` |
