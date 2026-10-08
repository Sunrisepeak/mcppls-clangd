# Current private combined through0056

Ordered 0047–0056, with0049 reserved, matches all23 changed source paths in
private7ca13e82e. After the prior134 related tests, the fingerprint/admission
changes rebuild ProjectModules and PrerequisiteModulesTest; both real binaries
link, and12 focused tests pass238ms. All four maintained preamble-mode semantic
transitions pass with normal exit. Shared root46 archives/source/binary remain
unchanged; this is private integration proof, not a clean native package.

The actual executable SHAab0cd926bdeb776c1826693f7609c609bb834f304ec041d6ba34c87f42c30215
passes four Qt semantic requests and strict UTF8/JSON trace parsing using the
original project/CDB/resource flags. Single-process sample: cold1799ms,
warm62.89/63.49ms, edited144.57ms. Complete content hashing plus exact-fact
indexing avoids measured repeated recording/replay costs. Candidate presence
is proved; insertion compilation, the full context distribution and release
percentiles remain open. No cache freshness or compiler option is removed.

Darwin53 CI exposed a test premise error: production admits only Linux host
and target discovery.0056 keeps all owner/follower semantic controls on all
hosts and additionally proves unsupported hosts create no cache publications.
Corrected native CI is pending; Windows53 separately failed directive diagnosis
and Ubuntu20's53 run lacks the already exported Python3.8 fixture correction.

[Combined evidence](../tests/evidence/combined-worker56.json),
[full fingerprint scope](module-scan-fingerprints.md),
[native admission scope](module-scan-native-admission.md).

# Historical private combined through0054

The ordered47/48/50/51/52/53/54 source matches all23 changed paths against
privated6ca614826. Eleven changed production TUs and four test TUs are rebuilt
and linked before read-only root46 archives;134 related units pass. This is
private integration proof, not a clean whole-tree recipe/native package.
Four real LSP module mode transitions without AST barriers, the1MiB bounded
worker dirty-header/default-supervisor fixture, and synthetic8MiB diagnostic
FIFO transport all pass with normal shutdown/semantic assertions. The latter
remains transport proof, not actual compiler crash qualification.

Private executablef95b420cd37b6066a18063f0507bd0bfa7cd46d4fbc9a673421f90bedc5b5c54
returns all four matched-resource Qt semantic requests and a strict UTF8/JSON
trace. This integration sample reports warm94/96ms, edited204ms, cold2178ms;
possible private compiler overlap is not ruled out, so no comparative timing
conclusion is drawn. Separate quiet54 measurements show edited204–210ms and
warm93–96ms. Edited200ms and the full context/insertion/statistical gate remain
open. The original Qt CDB/compiler flags remain unchanged. Root source,
archives, executable and applied-series marker still remain combined46.

[Combined integration evidence](../tests/evidence/combined-worker54.json),
[exact recording scope](module-scan-recording.md),
[worker output scope](module-worker-payloads.md).

# Historical combined 1–46 Qt measurement

Actual source 1c4fa5ed2, ordered-series identity fc75a976, executable SHA
2f91a4aa31c07c7f49b3ddbf6dfa04e1629f4d5668aa7339d8d8ab1f56f71011,
keeps the Qt CDB and compiler flags unchanged. All four semantic requests pass:
cold 2556 ms, settled warm 344/348 ms, edited 742 ms. Warm is about 52% lower
than the historical 42 baseline below, but remains above 200 ms. Positive and
negative scan manifest reuse both contribute. This one-process small sample
is not statistical release acceptance or insertion/context matrix qualification.

[Compact combined evidence](../tests/evidence/project-qt-worker46.json) retains
phase samples, exact arguments and raw report/log/trace hashes. Remaining
repeated policy inventory and validation costs are under investigation; no
compiler flag change or skipped freshness check is proposed.

# Real project completion measurement

2026-10-08 historical 42 baseline: source 777503b85 (patches 1–42), development
binary SHA cfa2a39a56c2fb9b1678f5c4f006bcf6e64d22d851f8cb4d5d6fc07c4b403307,
unaltered current Qt project CDB. All eight `std::ve` requests contain `vector`,
but cold completion is 3165 ms, four settled warm samples are 725–730 ms and
three edited samples are 1302–1314 ms. This supersedes the historical latency
observations below for the current source/project combination. It fails the
intended warm performance target; the small sample is not statistical acceptance.

The trace separates roughly 150 ms of Sema completion (104–106 ms module
validation and 41–44 ms semantic execution) from repeated failed GCC `std.cc`
scanning in synchronous request setup. Each didChange takes 574–576 ms. A
controlled separate CDB removing only GCC `-fmodules` permits real std and
nlohmann worker builds but worsens warm completion to 1203–1241 ms. That
counterexample is not a proposed compiler flag change. Strict failed-scan reuse
is under investigation; no optimization or release gate is claimed yet.

Compact measured evidence, phase samples, trace spans and hashes of raw local
reports/logs: `tests/evidence/project-qt-worker42-baseline.json`. The probe accepts
repeatable `--engine-flag=...` arguments and retains effective arguments in both
its replay case and report, so controlled configurations remain distinguishable.

`tests/probes/project_completion.py` inserts a completion expression in an
unsaved draft of an existing project, derives its UTF-16 cursor from the exact
unique source anchor, and validates required semantic candidates on every
request. Body edits produce new document versions. Raw replies and timings
are retained; replay requires normal shutdown. Source bytes remain unchanged.
The request time includes outstanding didChange work rather than hiding it
behind an arbitrary sleep. The initial documentSymbol settles initial AST work.

The Qt demo std::ve exploratory run returns vector in all three requests but
p95 is about 1297 ms. This is evidence of the remaining performance gap, not
release acceptance or a claimed improvement. Current full Sema completion is
still too slow. A single process and context do not satisfy three starts,
30 rounds/context, insertion compilation, the required context matrix, or
before/after speedup. Those remain required after a substantive optimization.

Raw evidence: tests/evidence/project-qt-std-completion-exploratory.json.

The one-request stage trace reports module validation ~297 ms and semantic
execution ~854 ms; the results callback takes ~0.2 ms. Raw stage events are
recorded in tests/evidence/project-qt-std-completion-trace.json. Patch 0018
adds separate spans around these phases without changing semantic behavior.
This identifies two remaining costs rather than claiming an optimization.

2026-10-07 update: the stage trace pointed at two root causes, both fixed by
patch 0019. First, qt-demo's direct imports (`std`, `nlohmann.json`) have no
buildable unit in the project, so the prerequisite builder returned
FailedPrerequisiteModules forever: every request re-ran the dependency build
(the 297 ms validation stage) and parsed without any BMI. Second, upstream
clangd skips the preamble for any file with required modules, so semantic
execution reparsed all textual headers on every request (the 854 ms stage).
With third-party imports kept textual and the preamble retained for files
that load no BMI, the same probe measures a ~50 ms warm steady state (first
request ~0.4 s, one-time index+verdict cost). See ci/third-party-imports.md
for the behavioral evidence and the remaining acceptance limits.


The probe now accepts --phases to distinguish the immediate first completion
following didOpen, AST-settled warm requests, and completion following edits.
Cold-open means a new engine process; existing persistent BMIs are not cleared.
Each phase reports requested, answered and missing counts, p50/p95 and raw
latencies. Failed semantic replies remain in the raw evidence and fail the run;
missing and timed-out requests are not silently removed to obtain a passing
latency result. The overall semantic-pass field must accompany any statistics.
Without --phases the original edited-request mode remains available.

--resources samples the owned Linux engine process via /proc every 100 ms,
retaining CPU time and observed VmRSS/VmHWM. Sampling is a CPU lower bound and
can miss the final process peak; it does not measure descendants, enforce a
memory ceiling or establish cross-platform release acceptance. Sampler errors
and shutdown are recorded. Process hashes use bounded streaming reads.
