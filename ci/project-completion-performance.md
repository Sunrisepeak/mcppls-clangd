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
