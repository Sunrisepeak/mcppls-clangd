---
subject: frozen-engine-readiness-accounting
status: diagnostic
---

# Frozen engine readiness CPU accounting

Audience: maintainers investigating the remaining engine cold CPU failure in mcpp#885.

Question: which engine and waited-child CPU components differ on the host type of the
original failure, and how does the readiness boundary differ from complete exit?

Excluded: production optimization, changed acceptance thresholds, release qualification,
or a new LLVM build. This branch is a manual diagnostic and is not a release candidate.

## Evidence and missing observation

Producer 41954537459 at a139538 fails Linux x64 cold CPU: 15.22/12.71 = 1.197,
against 1.15. Its 176 completed worker logs sum to an additional 1.359 seconds,
subject to integer-millisecond truncation. The original artifacts do not retain separate
main-process utime/stime and waited-child cutime/cstime readings at readiness.

Four local observed cold sessions retain the original 304-unit graph, three probes and
176 workers. All semantic and input checks pass. Native readiness CPU is 5.58 and 6.02
seconds; image is 5.67 and 5.54 seconds. At readiness no sampled worker remains alive,
and independent bracket reads observe stable waited-child fields. This does not reproduce
the producer's regression, replace its failed result or exclude accounting races elsewhere.
The local host has different headers and concurrent independent build activity.

Offline inspection also finds 653 compressed source-buffer records in native PCM files
and 653 plain records in image PCM files. All 176 declaration/type block record counts
and encoded lengths match. Image PCM bytes increase by 3,546,072; source-manager block
bytes increase by 3,546,556. The image configuration disables zlib/zstd, while ASTWriter
uses an available compressor. This explains size, not CPU. No compression dependency or
compiler flag is changed by this experiment.

## Fixed inputs and prescribed sequence

The workflow verifies artifact ID, producer ID, source commit, expiration, archive digest,
CRC and extraction paths before executing anything from the frozen artifacts. It then
checks the exact native and bundle digests and equal 303-file compiler resource trees.
The public platform 0.23.7 runner is built by the original setup route; its actual digest
is recorded. It is not claimed identical to a retired historical runner binary.

Only Linux x64 on ubuntu-24.04 runs. The sequence is fixed:

1. A real live-parent/reaped-child control checks the Linux stat parser against psutil
   and complete wait4 CPU. This has passed locally.
2. Original native cold plus three warm sessions, followed by the original image sequence.
3. The unchanged acceptance script records its result. A failed ratio remains failed.
   The manual workflow continues observation without qualifying or promoting a candidate.
4. Four observed cold sessions in native, image, image, native order. Each uses a new
   project/module cache, the original flags and safety limits. No failed sample is replaced.
5. Offline evidence collection and upload, including the first paired PCM inputs.

A validity failure stops subsequent samples. Project source digests, complete standard-library
index results, three actual AST commands, owned worker behavior and 176 PCM outputs are
checked. Payloads and the warm-prime script are not rewritten. No resource override is needed
on this runner because the complete native and image packages retain their resource layout.

## Observation and interpretation

The observer executes the unchanged warm-prime project and session code. It retains the
same Linux readiness CPU formula, saving its components from the same stat read. An
additional parent/tree/parent bracket is read after that value was computed. Its time span
and any waited-child changes are saved; it cannot retroactively alter the original value.

A separate Python thread samples process/thread CPU and scheduler counters every 25 ms.
It records process birth identities and distinguishes observed module-worker commands from
other children. Short workers can escape samples; their last samples are not presented as
complete totals. The kernel's waited-child counters and original completed-worker logs
provide complementary boundaries. Sampled per-thread scheduler time is diagnostic only.

Subreaper adoption is recorded separately from the original complete-wait metric. Root CPU
includes all threads in that process; it is not described as main-thread CPU. A live child's
own and waited-descendant time are distinct, and changing counters invalidate an atomic
interpretation of a bracket.

The experiment records OS, CPU model, affinity, memory, disk, resource tree and runner
identity. It does not clear the host page cache. Start requires 3 GB disk and 2 GB available
memory; periodic observation stops its owned root below 2 GB disk or 1 GB available memory.
Original readiness/shutdown limits remain in effect. The workflow budget is 45 minutes,
mostly for installing/building the small public runner; it never compiles clangd/LLVM.

This instrumentation and the hosted scheduler may affect timings. Only the uninstrumented
pair is evaluated by the unchanged acceptance script, and neither path qualifies the original
producer. The next optimization must follow the measured component difference, with a
single-variable control and the original final qualification still required.

## Validation

The observer's real reaped-child accounting control passes. Its portable entry also passes
the full local image workload with 304 units, three probes, 176 supervised workers and the
owned cache. Python compilation, Actionlint, whitespace and private-path checks pass before
dispatch. Hosted results are pending; successful collection alone is not performance success.
