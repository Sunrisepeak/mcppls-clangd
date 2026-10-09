# 0054: indexed exact scan recording

0054: bounded index for exact module dependency scan observations

Source cf62a35f9, parent0053 9bc61ed85, private tree
/tmp/mcppls-module-scan-flights. Export
/tmp/0054-index-exact-module-scan-observations.patch. No shared source/build or
root product edits. Actual changed ProjectModules/PrerequisiteModulesTest
objects were compiled privately; copied private50 ClangdServer/Preamble/
TUScheduler overrides precede stable root46 archives. identity.json records the
exact binary and partial-object provenance; this is not a clean whole-tree build.

Root cause and measured cost

Prior add() linearly searches all earlier exact facts for each idempotent input,
then ownedBytes() walks every retained observation on every distinct insertion.
These are two quadratic loops during every fresh canonical scan. Private
measurement-only aggregated timers preserve raw evidence in
/tmp/mcppls-scan54-profile/qt.{json,trace.json,log}. The edited main has5731 facts
and730 duplicates: freshDSS142.980ms, add31.735ms, including dedup10.984ms and
ownedBytes20.063ms. Moc4859, std3928, nlohmann3226, qrc183 facts show the same
recording cost, decreasing with fact count. Timer overhead is included; these
are stage observations, not a release timing distribution.

Implementation and invariants

A flat, open-addressed index uses operation/path hashes only to select candidate
facts. EVERY recorded field still participates in equality (all status fields,
alias identity, bytes, names, errors, request sizes and flags). Differing outcomes
are retained even under identical hashes. Directory begin/next remain ordered
and never deduplicated. Index capacity is at most16384 uint32 slots (64KiB), with
bounded collision probing; expected lookup is constant, worst-case collisions
remain bounded by the8192-fact admission limit. No input normalization, compiler
flag changes, scanner mode changes or filesystem snapshot assumptions.

Insertion accounting tracks observed string capacities incrementally and
explicitly plans vector/index capacity growth. Index storage and old+new
allocation peaks during growth count against the existing32MiB per-manifest
metadata boundary; retained index metadata counts against the unchanged32MiB
process cache budget. Oversized status names now decline admission too.
The observation vector is exposed as a const view, preventing untracked edits
from invalidating the index/accounting invariant. Public ownedBytes() still
recomputes actual capacities after manifest copies. The cancellation test's
filtered manifest is reconstructed using add(), retaining the intended read-only
replay control. Existing fresh-service-on-miss, full known-input replay before
publication/hit, cancellation, environment/command/CDB/draft/response and
unsupported-operation guards remain unchanged.

Resource and correctness evidence

focused-final.log:11 focused unit tests pass213ms. They cover full same-hash
fact differences through index growth/copy, duplicate compaction, ordered
8192-fact boundary, large status-name refusal, canceled replay/publication,
negative-header creation, preserved size/time byte edits, drafts, command/CDB
and provider transitions, same-key publication coordination and divergent
request filesystem views. No redundant fullLLVM suite.

The exact final Qt probe is qt-final.{json,trace.json,log}: strictUTF8/JSON trace,
all4 semantic requests pass; cold2174.31ms, warm92.55/94.72ms, edited209.91ms.
The earlier quiet probe qt-quiet.{json,trace.json,log} is retained too:
cold2178.16ms, warm96.32/95.54ms, edited204.31ms. Matched resource dir is the
same build lib/clang/23 as the0053 baseline (edited234.78ms). This slice removes
about25–30ms; it does NOT close the200ms edited target. Six retained entries now
own14,351,170 bytes, versus14,086,498 before:264,672 extra bytes, still<32MiB.
No RSS claim, complete context matrix, insertion-compilation proof or release
percentile claim.

An initial probe deliberately remains in compiler-overlap.{json,trace.json,log}:
private unit compilation overlapped it (edited275.45ms,warm133–162ms). It is
excluded from the quiet A/B interpretation, not deleted or passed off as a
controlled regression measurement.

Remaining route: first-request canonical preprocessing plus full publication
replay still dominates edited latency. Upstream clang-scan-deps itself defaults
to DependencyDirectivesScan for P1689; auditing that official mode's builtin,
lexical-failure and VFS-observation guarantees is a possible separate slice.
This patch keeps CanonicalPreprocessing and exact main-content invalidation.

Drop when upstream performs bounded exact-fact indexing and incremental
admission accounting with equivalent complete collision/growth/fresh-view
canaries. Native full recipe remains pending.
[Compact evidence](../tests/evidence/module-scan-recording.json).
