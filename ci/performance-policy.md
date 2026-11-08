# Warm-prime release policy

The warm-prime report compares the image with the native engine on the same
host. Its workload is 304 translation units and three opened probes; one run
is a cold session over an empty project module cache followed by three warm
sessions, and its warm result is the median of the three.

## Sampling rule

This rule is registered before the measurements it governs and applies from
engine 0.0.21 (mcpp design 2026-11-07, §4.5 item 4 and D7).

- **Sample.** A sample is a pair: one run of the native engine and then one of
  the image, on the same runner. A measurement is at least eight pairs
  (O5; four before it), alternating native and image, so that a drift of the
  runner reaches both engines alike.
- **Statistic.** For each gated quantity the statistic is the median over the
  pairs of the image/native ratio, compared with its limit on the recorded
  values before display rounding.
- **Spread.** On one runner the cold processor-time ratio of four alternating
  pairs lies within 0.03 of its median (measurement O4: 24 sessions on three
  runners, ratios 1.041 to 1.103, median 1.082). The cold readiness ratio lies
  within 0.10 of its median where the runner measures readiness at all (O5,
  below). A measurement in which more than a quarter of the pairs (at least one)
  lie outside either bound is invalid; a quarter is admitted, since the median
  does not move with them. Warm ratios carry no spread bound: their absolute
  values are small and the median of the warm sessions already discards a
  single outlier.
- **O5, readiness (registered 2026-11-08, before the measurements it governs).**
  0.0.21's comparison run 42416069243 measured darwin-arm64 twice: cold
  readiness ratios of the pairs 1.173 to 1.398 (median 1.319) and 0.964 to
  1.409 (median 1.154), the native engine's own cold readiness 7.1 to 8.1 s in
  the first and 10.2 to 14.6 s in the second, while the cold processor-time
  ratios stayed within O4's bound. A probe on macos-15
  (Sunrisepeak/mcppls-clangd#20) measured the image's cold processor time at 0.84
  and 1.01 of native in two pairs, the median of its module workers at 37 and 40 ms
  against 46 and 45 ms, and its start at 7.4 ms against 17.2 ms (60 starts each), and the native engine's cold readiness at 9.3 and 11.9 s
  in two sessions of one runner. Readiness on that runner varies by more than
  the gate resolves with four pairs, and the rule had no bound on it. From this
  registration a measurement is eight pairs and bounds the readiness spread as
  above. The two measurements of 42416069243 are results under the rule they
  were made under, and they stand; the limit is unchanged.
- **0.0.21 (registered 2026-11-09, by the maintainer's decision).** darwin-arm64 gave three invalid
  measurements in comparison run 42464678787: the native engine's cold readiness on these runners spans
  7.5 to 14 s, and six of eight pairs lie outside the cold processor-time bound each time. 0.0.21 is
  released on its comparison with the release before it instead: on darwin-arm64 the image's absolute
  cold readiness and processor time are not above 0.0.20's measurement, and on one machine the two images,
  alternated in four pairs, differ by at most 3% in every gated quantity. A measurement here that is
  invalid three times running admits a release only so, on the previous release's numbers and a local
  pairing of the two images, and the changelog says so.
- **Invalid measurement.** A measurement is invalid when it has fewer than four
  pairs, when a report is not the version-3 measurement of the workload above,
  when a counter or an aggregate is missing or inconsistent with its raw
  sessions, or when the spread bound is exceeded. `warm_prime_accept.py` exits
  2 for an invalid measurement and 1 for a valid one that misses a limit.
- **Repetition.** Only an invalid measurement may be repeated, and the
  repetition is a complete measurement of at least four pairs. A valid
  measurement that misses a limit is the result; it is not repeated.

## Comparison runs

The engine is released only as the ok image; native engines are built to be
measured against, never released. A push or a pull request builds the image,
accepts it on the four systems against the pinned native reference
(`openkal.yml`), and builds one native engine, linux-x64, for the series' unit
and lit tests. The measurement above runs only in a comparison run: a manual
dispatch of `build-test` naming a platform or `all`, which builds those native
engines, packages them as a release would, and runs warm-prime and the shard
exchange on each. Every system's acceptance also runs the end-to-end
regressions against the image (`ci/e2e_suite.py`), so what users run is tested
on each system without a native build there.

A release whose engine inputs (`UPSTREAM`, `patches/`, `overlay/`, `openkal/`,
`ci/scripts/env.sh`) differ from the previous release's carries a comparison run
with `all` on a commit with the same engine inputs, and its changelog entry names
that run (`Comparison run: <run URL>`); the release workflow refuses a version
whose entry names none. A release that changes no engine input names the
comparison run of the release whose engine it carries.

## Limits

On Linux x64, Linux ARM64 and macOS ARM64, the limits are 1.15 times native
readiness latency and processor time, and 2.0 times complete-lifetime page
faults, for the cold session and for the warm median. Every session of both
engines must be ready, and both must build in supervised workers over the owned
cache. Windows records ratios without gating on them: its native engine
compiles in process with per-reader copies, whereas the image uses supervised
workers.

The limits are not raised by an option or by a release. Engine 0.0.20 carried
a one-release Linux x64 cold-CPU exception (at most 1.25 and 3.0 additional CPU
seconds); its qualifying measurement did not use it (cold CPU 1.109), and it
expired with that release. The record is in
[mcppls issue 77](https://github.com/Sunrisepeak/mcpp-language-server/issues/77).

## Observed experience and remaining limits

Historical measurement-version-2 Linux x64 cold CPU was 12.71 to 15.22 CPU
seconds while readiness was 8.798 to 8.006 seconds. This is extra CPU work,
not evidence that every user operation takes 19.7% longer.

Windows cold readiness was 11.667 to 16.534 seconds in that historical
workload; warm readiness was 9.361 to 5.344 seconds. The cold delay remains a
user-visible tradeoff despite the non-gating path comparison. Interactive
server latency and editor behavior require their existing independent checks.
