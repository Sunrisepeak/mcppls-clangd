# 0053: bounded scan publication coordination

Patch 0053: bounded exact-key scan publication coordination

Base: private 98d37921f (48, 50, 51, 52 atop root46). Only
ModuleDependencyScanCache.h, ProjectModules.cpp and PrerequisiteModulesTest.cpp
change. Shared source/build archives are untouched; private50 ClangdServer,
TUScheduler and Preamble objects are copied read-only before the root46 archive.
Compile/link argument arrays and logs are in ../mcppls-flights53-build/.

The key is immutable CDB identity, exact adjusted command (all CompileCommand
fields), exact main contents digest and complete existing environment digest.
A flight contains publication notification only: no scan result, service or VFS.
After waiting, each follower performs ordinary cache lookup and full interruptible
manifest replay against its own current request VFS. Invalid/canceled/declined
publication or timeout follows the original fresh-service scan path. Owners
recheck lookup too, closing the initial-miss/acquisition publication race.
Same-thread recursive acquisition bypasses coordination. No FS/scanner activity
or waits run under a cache/registry mutex. Owner RAII always wakes followers,
including semantic failure, admission refusal, cancellation and early return.

Bounds: max64 active keys, individual pre-copy estimate limited to64KiB,
independent4MiB owned flight metadata allowance including fixed registry/index
and allocation overhead. Completed keys borrowed by followers remain charged
until the last handle releases them. Retained manifest budget remains32MiB;
these bounds describe owned metadata, not process RSS or compiler allocations.
Wait deadline150ms, cancellation polls at most5ms: this bounds coordination
waiting, not scanning, scheduling or total request latency. Timeout deliberately
permits independent duplicate work; no in-flight result or unverified FS sharing.

Concrete prior duplication: immutable private50 baseline evidence in
../mcppls-inflight53-baseline/qt.{json,trace.json,log}, identity.json.
Edited main MISS at1.97ms and57.81ms after didChange; stores186.57ms and244.28ms,
128.76ms active overlap. Second identical-key publication raised retained bytes
14,086,498 ->17,489,993 (extra3,403,495). Cold scans each~185–186ms.
Baseline warm99.41/96.14ms, edited233.53ms, cold2329.9ms; all4 semantics pass.
Baseline raw trace has the previously fixed51 filename ownership defect; it is
retained unchanged, never presented as a clean trace.

Initial53 matched-resource real Qt probe: ../mcppls-flights53-build/qt.json,
qt.trace.json and qt.log. Four semantic requests pass; strictUTF8/JSON parses.
Warm95.18/95.74ms, edited238.15ms, cold2315.90ms. Edited main single store,
worker publication wait then full own-VFS cache hit; entries6/14,086,498B.
This removes duplicate active scan/publication, not first-request scan latency:
edited still exceeds200ms. No claim of a latency improvement or closed gate.

Focused unit controls exercise actual concurrent scanner calls: identical VFS
=>one store+follower hit; same main/CDB but equal-size/equal-timestamp differing
unsaved headers =>replay invalidation, independent scan, M versus N; canceled
owner =>declined store and follower fresh scan. Direct controls cover recursive
bypass, full64-slot admission, oversized keys, canceled follower, publication
without admission and bounded timeout with no shared verdict.

Final exact-source verification: focused-final.log,9tests PASS233ms;
qt-final.{json,trace.json,log},all4 semanticrequests PASS,strictUTF8JSONvalid.
Warm95.84/100.86ms,edited234.78ms,cold2271.63ms. Singleeditedmain
publication retained6entries/14,086,498B; secondworker waits and replays.
Source/binary identity in identity.json. Edited200ms target remains open.

Drop condition: upstream provides equivalent bounded publication coordination,
including independent follower manifest replay, cancellation and recursive
bypass, and the concurrent fresh-view canaries pass. Native full recipe and
cross-platform qualifications remain pending; this private link is not a
release artifact. Raw local trace/report and focused logs are retained in the
handoff evidence directory. [Compact evidence](../tests/evidence/module-scan-publication.json).
