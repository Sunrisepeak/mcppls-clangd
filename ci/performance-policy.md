# Warm-prime release policy

The warm-prime report compares the image with the native engine on the same
host. Its workload is 304 translation units, three opened probes, one cold
session and three warm sessions. Cold means an empty project module cache.
The warm result is the median of the three sessions.

On Linux x64, Linux ARM64 and macOS ARM64, the default limits are 1.15 times
native readiness latency and CPU, and 2.0 times complete-lifetime page faults.
Every semantic session and the owned-cache/supervised-worker path must pass.
Windows records ratios without gating on them: its native engine compiles in
process with per-reader copies, whereas the image uses supervised workers.

## Engine 0.0.20 exception

For distribution version 0.0.20 only, Linux x64 cold CPU may exceed 1.15 if
both image/native CPU is at most 1.25 and the increase is at most 3.0 CPU
seconds. Comparisons use the recorded values before display rounding. The
approval, experiments and follow-up are recorded in
[mcppls issue 77](https://github.com/Sunrisepeak/mcpp-language-server/issues/77).

The exception changes no readiness-latency, warm-CPU, other-host CPU, fault,
semantic, resource, cancellation, crash, packaging or final server/editor UX
gate. Measurement version 3 with consistent stable-reap Linux observations
is required. A malformed measurement or either exceeded ceiling refuses
release; the limits are not increased automatically.

`warm_prime_accept.py --release-version 0.0.20 --source-commit <full-sha>`
enables this rule only on `linux-x64`. The measured reports' command prefixes
must still name readable native, runner and image files. Their SHA256 values
and the producer source identity are recorded with the exception.

The JSON result keeps `target_met` and `target_failures` separate from
`accepted` and blocking `failures`. An accepted exception records
`release_exception.applied=true` while retaining `target_met=false`.
`waived_failures` identifies the bounded cold-CPU deviation; a different
failure still makes `accepted=false` and `applied=false`. These fields concern
this performance check only, not the entire release qualification.

CI reads the distribution version from `RELEASE_VERSION`. Release tags must
match that file. A subsequent version, or a call without `--release-version`,
uses the strict target; there is no inherited or global `--limit` increase.
The LLVM fork version remains the separate identity in `ci/scripts/env.sh`.

## Observed experience and remaining limits

Historical measurement-version-2 Linux x64 cold CPU was 12.71 to 15.22 CPU
seconds while readiness was 8.798 to 8.006 seconds. This is extra CPU work,
not evidence that every user operation takes 19.7% longer. Corrected-meter
pairs still included a strict-target failure. Historical runs do not qualify
the final artifacts under the new policy.

Windows cold readiness was 11.667 to 16.534 seconds in that historical
workload; warm readiness was 9.361 to 5.344 seconds. The cold delay remains a
user-visible tradeoff despite the non-gating path comparison. Interactive
server latency and editor behavior require their existing independent checks.
The performance issue stays open after a release using this exception.
