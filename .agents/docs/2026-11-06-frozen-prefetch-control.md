# Frozen image prefetch control

This record addresses the remaining Linux x64 cold CPU failure in mcpp #885.
The original engine and bundle from producer 41954537459 remain immutable.
It supplements the kernel CPU diagnostic; it does not change release admission.

Kernel diagnostic 42079596479 recorded 1552 native and 1795 image samples,
with resolved kernel frames in 99.94% and 100% of samples. Both process trees
contain the engine and 176 workers. Image descendants have 173 samples in
`mmap -> __mm_populate -> populate_vma_page_range`, across 173 processes;
native descendants have none. User return frames name `kal_exec_map_part`.
The 346.7 ms period weight identifies a path, not an exact CPU accounting value.
The original uninstrumented cold ratio remains failed at 1.192 in 42069065071.

The pinned loader requests `OKLD_MAP_PREFETCH` for ranges in the image's touch
note. The Linux backend implements it with `MAP_POPULATE`. The engine producer
collects touches across a full cold session and all its processes, then writes
their union into one image note. The frozen x64 note names 305 blocks in 166
ranges. It describes the combined execution, not the pages every worker needs.
This is a candidate cause of repeated eager mapping, not a conclusion that all
remaining CPU overhead has this cause.

A three-mode local mapping control used the same frozen runner and bundle.
Default and explicit `touch` each populated 20025344 bytes in three mappings;
explicit `0` populated none, and all three version commands succeeded. These
are executable and read-only file mappings, not eager private data copies.
The existing knob also changes how mapping runs are split. The experiment
therefore tests prefetch policy, not a claim that precisely one syscall flag
is the sole changed operation.

The next experiment has the following fixed design:

| Item | Prespecified condition |
|---|---|
| Inputs | Original native binary, bundle, 303 matching resource files, unchanged full warm-prime harness |
| Treatment | Same runner and bundle, `OKRUN_PREFETCH=touch` versus `OKRUN_PREFETCH=0`; `KAL_RESOURCES=balanced` in both |
| Sequence | native, touch, 0, 0, touch, native |
| Workload | Each case: original 304 units, three probes, one cold and three warm sessions; each cold builds 176 modules in supervised workers |
| Cache | Fresh module cache for each case; one shared loader cache; OS page cache untouched |
| Observation | Same readiness formula, additional role accounting and complete lifetime counters; observer excluded from engine CPU |
| Validity | All semantic checks, exact resource application, complete matching standard-library index, unchanged bytes, no observer errors, no failed adopted child |
| Preflight | Repeat default/touch/0 mapping identity control on the same CI runner; no kernel settings or limits changed |
| Stop | First validity failure ends the batch; no sample extension, automatic retry, or LLVM rebuild |
| Interpretation | Paired direction, parent/child user/system CPU, complete CPU, readiness, warm behavior, and faults reported together; diagnostics do not admit a release |

One local image-only cold run checks orchestration and evidence extraction before
dispatch. It is not added to the performance comparison. No new backend policy,
worker default, compression library, or producer threshold is adopted here.
If the intervention consistently removes the observed overhead, the follow-up
must choose its ownership from the loader policy and producer profile contract,
then verify the selected change on the original uninstrumented admission suite.
Native Darwin, Windows, and arm64 behavior remains a separate acceptance scope.
