---
subject: frozen-engine-kernel-cpu
status: diagnostic
---

# Frozen engine descendant kernel CPU

Audience: maintainers locating the remaining cold CPU cost before changing the runtime.

Question: which kernel paths account for the descendant-system CPU difference observed
on the original Linux x64 host type?

Excluded: production changes, a new LLVM build, performance qualification or changes to
the workload, safety limits and acceptance thresholds.

## Evidence and hypotheses

The frozen readiness experiment at commit 53f4d4a, run 42069065071, reproduces the original
failure without rebuilding LLVM. The unchanged cold CPU gate reports 15.20/12.75 = 1.192,
over 1.15. Four subsequent observations find no live child at readiness and stable waited
counters. Image waited-system CPU is 2.82 seconds twice; native is 1.65 and 1.62 seconds.
The image therefore adds 1.17 and 1.20 seconds in that kernel-accounted component.

Candidate paths are process/thread creation, supervision reading proc metadata, mapping
and page faults, and file operations. Their contributions have not been separated.
The separate compressed/plain PCM buffer observation explains file size; it does not
establish a CPU cause or justify enabling a compression dependency.

## Prescribed experiment

The manual workflow retains the same verified native and bundle from producer 41954537459,
the same 303-file resources, public platform 0.23.7 runner setup and original 304-unit,
three-file, 176-worker cold workload. The sequence is one native session, then one image
session. There are no replacement samples and no passing qualification artifact.

Before downloading/building the runner, a small real process control checks that sampling
inherits into its actual child and excludes a simultaneously busy sibling of the target.
It also requires at least 95% of sampled kernel stacks to contain resolved kernel symbols.
The workflow uses the runner's existing noninteractive sudo to attach perf and tests its
capability in that preflight; the engine remains the ordinary runner user. No sysctl,
privilege configuration or target grants are changed.
If perf or its required capability is absent, the diagnostic stops with retained evidence.

The actual engine starts with its original argv. Before the harness sends initialize,
it publishes the engine PID and kernel birth time through an atomic diagnostic gate.
A separate controller attaches perf to that PID with inherited events, kernel-only
cpu-clock sampling at 499 Hz, frame-pointer call chains and CLOCK_MONOTONIC timestamps.
The controller waits for the perf enable acknowledgement before releasing the gate.
Thus the Python harness and perf process are outside the target, while module workers
created after initialize inherit sampling. Initial engine startup before attachment is
outside this profile. Gate wait changes elapsed time, so these timings are not acceptance.

FIFO control is the documented perf mechanism, with an acknowledgement before measurement
starts. The local perf 6.8.12 acknowledgement includes a trailing NUL; the parser accepts
that terminator and retains the original bytes. Collection usually ends automatically
when the target ends; an explicit stop command covers the remaining owned recorder.

## Validity and interpretation

The decoder retains fork, comm, exit and lost-event records. Every sample PID must be
the attached engine or a descendant in the recorded fork ancestry; the Python controller
and harness are explicitly excluded. The target's exit must be present and lost records
are rejected. Samples are grouped into the main process and descendants, with leaf and
inclusive kernel-frame period sums. Inclusive counts overlap and are not added as CPU.
Sample periods are statistical weights, not a replacement for kernel rusage counters.

Original input and semantic checks remain active, including owned supervised workers,
176 actual module builds, complete standard-library indexing and resource availability.
Payload hashes are checked before and after. The two lanes' standard-library results
must agree. Collection is bounded to 128 MiB per perf file, the original session limits,
and the earlier memory/disk guards. A validity failure stops the second lane.

Local controls verify attach/enable, descendant inheritance, busy-sibling exclusion and
clean recorder exit. This host denies kernel symbol access and disallows sudo escalation;
only its explicitly labelled transport control accepts unresolved symbols. The actual
pair has no such option and the CI preflight requires resolved symbols. No local opaque
kernel addresses are used to claim a subsystem cause.

The next single-variable runtime experiment is chosen from the observed kernel paths.
For example, proc-supervision dominance would justify a same-compiler baseline/filtered
runner comparison; mapping dominance would instead require a mapping/placement control.
Neither change is preselected, and the original producer failure remains outstanding.

References: [perf record control and inheritance](https://man7.org/linux/man-pages/man1/perf-record.1.html),
[perf script task and lost-event output](https://man7.org/linux/man-pages/man1/perf-script.1.html).

## Hosted preflight correction

Run 42077631033 stopped in the small sampler control before downloading the engine inputs
or building the runner. Perf 7.0.14 successfully attached, acknowledged enable and recorded
the control, but decoding exited 255. The controller had already changed perf.data ownership
from root to the ordinary runner user; perf's root decoder therefore refused the file's owner.

The corrected sequence retains the recorder's ownership during checksum and decoding, then
returns that one newly created file to the runner for artifact collection, including failure
cleanup. It does not force-read the file or relax the ownership check. The original 17,279-byte
artifact and its failure logs remain preserved. No real engine profile or performance result
was produced by the failed preflight.
