# Frozen worker CPU stage closure

This diagnostic serves the remaining cold CPU difference in issue 885. It
compares the unchanged native/image engine pair after the published Linux
supervisor correction. It does not qualify a release or modify the 1.15
acceptance limit.

The previous corrected-meter hosted cohort assigns 0.88 s and 0.70 s of the
respective 1.01 s and 0.91 s child differences to kernel CPU. Earlier detailed
stage data came from a different hosted CPU model. Those milliseconds cannot
be subtracted from this batch. The final image stage also precedes profile
writing and kernel teardown; that remainder must remain explicit.

`ci/worker_phase_closure.py` runs exactly N/F/F/N, each with one cold and one
warm session. It preserves 304 units, three probes, 176 cold module workers,
the 303 resource files and the actual frontend command identity. Original
native and bundle SHA256 values are asserted before and after. The runner's
original objects are reproduced, and only the already-published Linux
supervisor implementation differs from the baseline. LLVM and clangd are
never rebuilt.

Native phase interposition and the image's existing phase hooks report
RUSAGE_SELF and RUSAGE_THREAD. Their actual control checks returning from
main, explicit exit, immediate exit, and an additional CPU-consuming thread.
The 8-session cohort requires 712 unique process reports. Stage deltas are
summed by parent/worker role. Actual waited child user/system at readiness
minus the worker profile totals remains a separately reported signed
remainder, allowing for kernel tick rounding. It includes observer output
and unmeasured exit work and is not assigned to a particular kernel path.

Native main and exit callbacks are separate. The image entry includes its
runtime guard, main, exit callbacks and stdio. Import-call timing is disabled:
the preceding local experiment established that timing every cached context
identity query would dominate that path's cost. The parent and worker
accounting remain distinct, including the standard-library indexing work.

The local preflight completed all 8 sessions and 704 workers. All inputs,
profiles, semantics and snapshot checks passed. The two native worker system
totals at readiness were 0.80 s and 0.74 s; the two image totals were 0.76 s and 0.82 s.
This local batch does not reproduce the larger hosted kernel difference.
The hosted run is therefore the next bounded comparison, with its actual
CPU model recorded. A different hosted model will be reported as such rather
than retried until a desired machine or result appears.

A validity failure stops the cohort. No extra samples are selected after
seeing performance. Every profile and failure remains available; hosted
workflow success means the diagnostic completed, not that performance passed.
