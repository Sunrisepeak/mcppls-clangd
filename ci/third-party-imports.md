# Third-party module imports keep resolvable prerequisites and the preamble

`tests/e2e/third_party_import.py` covers two behaviors the qt-demo real
project exposed through the completion stage trace (`0018`):

1. A direct import whose module unit the project cannot supply — a toolchain
   `std` whose unit source the scanner cannot resolve, or a registry wrapper
   outside the project without a compile command — must not discard the
   modules that did resolve. Before the fix the prerequisite builder returned
   `FailedPrerequisiteModules` forever: `canReuse` never held, every request
   re-ran the dependency build (the ~300 ms validation stage) and the parse
   ran without any BMI and without the preamble (the ~850 ms semantic stage).
   The probe asserts `dep_value` completes semantically while
   `third_party_missing` stays textual, and that the unresolved-import log
   count tracks the preamble-build count instead of the request count.
2. A file whose imports are all textual never loads a named-module BMI, so
   the upstream `SkipPreambleBuild` guard against PCH+modules mixing does not
   apply and the file keeps its real preamble. The probe builds a fat header
   (20k generated declarations), observes a ~12 MB preamble and a completion
   of `fat::S3999` through it, then adds `import dep;` on disk. The verdict
   re-derives (the cache is keyed by the file's on-disk identity plus its
   import-name set, and compile-command changes clear it), the preamble
   collapses to the trivial one before any BMI loads, and both `S3999` and
   `dep_value` complete after the flip.

Real project effect (qt-demo, `std::ve` in `src/main.cpp`, same probe and
machine as the `ci/project-completion-performance.md` baseline): warm requests
moved from ~1.0–1.3 s (and ~1.3 s before the stage split) to a ~50 ms steady
state, with a one-time first request of ~0.4 s covering the c++23 standard
library index and the initial verdict derivation. `cli.`/`window.` member and
`std::string` qualified-name contexts return their expected symbols at the
same steady state. Raw evidence: `tests/evidence/project-qt-std-completion-thirdparty.json`
and `tests/evidence/third-party-import-reuse.json`.

Limits: this is a single-machine exploratory measurement with 10 rounds and
one process start, not the release gate. The plan's three starts, 30 rounds
per context, full context matrix, insertion compilation and baseline
speedup ratio on identical methodology remain required for acceptance. The
one-time first-request cost and background AST update costs are visible in
the raw samples and are not hidden.

Full matrix (2026-10-07, local linux-x64 engine, qt-demo, 3 starts × 30
rounds per context, raw samples retained per request):

| context | p95 | per-start first request |
|---|---|---|
| `cli.` member | 26 ms | ~372 ms |
| `window.` member | 35 ms | ~378 ms |
| `std::ve` qualified | 59 ms | ~400 ms |
| `std::str` qualified | 77 ms | ~419 ms |

All 12 start/context outcomes pass with the required symbols. The
first-request cost is the c++23 standard-library index plus the initial
verdict derivation; every later request in each start is at the steady
state. Evidence: tests/evidence/w1-full-matrix/*.json. The plan's
200/300 ms budgets hold with margin on this machine; a same-methodology
pre-fix A/B binary and the VS Code product layer remain to be run for
the release record.

Patch 0020 adds the provider-gain closure: an empty prerequisite set is
stamped with the compile-command generation it resolved under, and
`canReuse` rejects a stale generation before consulting BMI freshness.
The scenario drives the change in one process: `dep2` is forbidden in
completion while it has no compile command, then the database gains the
entry, the directory CDB reloads after its five-second revalidation
interval, and `dep2_value` completes semantically from the rebuilt BMI.

Same-session A/B (2026-10-07 evening, linux-x64, qt-demo, 3 starts × 30
rounds per context, identical probe; the pre-0019 binary is the same tree
before patch 0019, kept beside its clang resource directory):

| context | pre-0019 p95 | post-0019 p95 |
|---|---|---|
| `std::ve` qualified | 1323 ms | 59 ms |
| `cli.` member | 1376 ms | 26 ms |
| `window.` member | 1368 ms | 35 ms |
| `std::str` qualified | 1361 ms | 77 ms |

State markers are retained in the raw evidence: the pre runs show the
per-request `Failed to build module std` loop with a trivial ~271 KB
preamble, the post runs show the third-party skip logs with a real ~33 MB
preamble. A methodology note for reruns: the in-process dependency scanner
resolves its clang resource directory relative to the engine binary, so a
copied engine must keep `lib/clang/<version>` beside it — without it the
scan fails inside the toolchain headers and no import is discovered at all,
which measures a different regime (~160 ms for any engine) rather than the
module path. Evidence: tests/evidence/w1-full-matrix/pre-0019/*.json.
