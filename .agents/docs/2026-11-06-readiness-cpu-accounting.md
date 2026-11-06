# Linux readiness CPU accounting across process reaping

Date: 2026-11-06. Scope: the warm-prime measurement harness for mcpp issue 885.
This record concerns measurement correctness. It does not attribute the original
1.197 image/native ratio entirely to a measurement error or change its 1.15 limit.

The previous collector sampled each visible process's own CPU, then read the root
process's own and waited-child counters. If the root reaped a sampled child between
those reads, the child's CPU appeared in both terms. The same collector omitted a
reaped grandchild while its intermediate parent was still alive: the intermediate
process's own CPU did not include its waited CPU.

A real-process control ran the unmodified frozen collector. A child consumed
approximately 0.25 CPU seconds and blocked before exit. Allowing its parent to reap
it at the collector's existing read boundary produced 0.480 reported seconds, while
the parent's complete `wait4` usage was 0.263422 seconds. Live-child and already-reaped
controls reported 0.240 seconds against complete totals of 0.264350 and 0.263287.
The difference in the stable controls includes clock-tick quantization and final
shutdown. The original production run lacks the per-read data needed to quantify
this race's contribution retrospectively.

Version 3 collects the rooted process tree twice. It accepts the second reading
only if process identities, parentage, membership and all waited counters agree.
The sum includes each remaining process's own and waited usage. A reap or tree
change causes another observation, with a fixed bound of eight attempts. Failure
to obtain a stable reading fails the session; sampled historical values are not
substituted. Own CPU may advance during the finite read window, whose duration is
reported. The collector retains `/proc` clock-tick resolution and does not claim
an atomic nanosecond snapshot.

The Linux acceptance check requires the recorded stable observation to agree with
the session CPU and readiness fault values. Its warm CPU aggregate must equal the
median of the three raw warm sessions. Both lanes require version 3. Existing
version-2 reports are retained as historical evidence and cannot qualify a new
comparison. Readiness latency, complete-lifetime faults, workload size, semantic
assertions, process isolation and the 1.15 CPU/time limits are unchanged.

Local validation completed ten accounting tests and six acceptance tests. Real
process controls cover live/reaped children, a reap between the two reads, an
already-reaped grandchild under a live intermediate process, unrelated trees and
unavailable observations. The acceptance CLI still rejects a consistent 1.16 CPU
ratio and rejects missing, inconsistent or legacy observations.

Frozen native/image inputs then ran N/F/F/N, each one cold and three warm sessions,
with the published Linux supervision correction and the original 304-unit,
three-probe, 176-worker cold workload. All 16 sessions and 704 workers passed.
Cold CPU values were 4.84, 5.17, 5.28 and 4.78 seconds; paired ratios were 1.068 and
1.105. Warm CPU ratios were 1.125 and 1.064. All observations succeeded on the first
attempt and contained only the root process, because its workers were already
reaped. These samples validate the corrected harness; they do not establish that
the old race occurred in the original failing CI run. The observed read windows
were approximately 0.61–1.59 ms.

Evidence is retained under `<evidence-root>/mcpp-885-readiness-reap-race/` and
`<evidence-root>/mcpp-885-readiness-accounting-workload/`. Hosted frozen-artifact
validation and final producer qualification remain outstanding at this record's
creation. No LLVM build or performance threshold adjustment was performed.
