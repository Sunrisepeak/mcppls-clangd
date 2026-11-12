# Changelog

## [0.0.22]

- The include analysis no longer ends the engine on a header that has two
  identities (0048). `computeIncludeCleanerFindings` marked a used include by
  the ID of its resolved file entry and dereferenced that lookup unchecked; where
  the file system gave the header's resolved path another identity than the path
  it was entered by, the lookup was empty. The ok image ended there by an illegal
  instruction (`0xC000001D`, libc++'s hardening) on Windows 11 24H2, on the first
  build of any module unit that includes a header in its global module fragment,
  imports a module and uses a type of the header
  ([mcpp-language-server issue 86](https://github.com/Sunrisepeak/mcpp-language-server/issues/86)).
  An include is marked by the ID it was entered with; no include is reported
  unused where a used one cannot be identified.
- The engine reports itself as `23.1.0-mcppls.11` and declares the feature
  `include-ids-by-entry` in `engine.json`.
- `tests/e2e/gmf_include_analysis.py` is the report's shape and runs in every
  system's acceptance. `openkal.yml` gains a job on `windows-2025` (Windows
  build 26100), the one hosted system on which a file had two identities under
  okrun: it runs that case as a gate and the whole end-to-end suite as a report.
  Every Windows job ran on `windows-2022` (build 20348) before, where the
  condition cannot occur.
- No other patch of either series changes; the image is built over the same
  platform (openkal-platform 0.24.3). The platform's own correction of the two
  identities is openkal-windows 0.22.0, which a later platform pin takes.
- Comparison run: https://github.com/Sunrisepeak/mcppls-clangd/actions/runs/43188051127

## [0.0.21]

- The ok image (`clangd.okb`) and every native engine are built with zlib
  (`LLVM_ENABLE_ZLIB=FORCE_ON`; on Windows a static zlib over the static C
  runtime), so each reads the index shards the other writes. The image
  discarded them before ("Compressed string table, but zlib is unavailable")
  and indexed again; the native Windows engine had no zlib either, which the
  comparison run's shard exchange found.
- The image's zlib is zlib-ng in its zlib-compatible form (`compat.zlib-ng`
  2.3.3): the same API and streams, with inflate, adler32 and the deflate match
  search on NEON (aarch64) and SSE2 (x86_64), chosen at compile time since an
  image cannot ask the processor. With madler's zlib the image's warm start on
  darwin-arm64, against the native engine on macOS's NEON libz, took 1.214–1.332
  times the native processor time in every pair (limit 1.15); without zlib it
  took 0.973–1.107 (comparison runs 42369457883 and 42386660489).
- The engine reports itself as `23.1.0-mcppls.10`.
- The image is built over openkal-platform 0.24.4, stated only in
  `openkal/clangd/mcpp.toml` (CI writes its probes from that line): its runtime
  keeps a path's volume (`D:/a/..` stays on `D:`, 0.24.2), its okrun.exe
  reserves a thread's stack for the image's main thread on Windows, where
  clangd.okb with `--sync` overflowed 1 MiB indexing the MSVC headers (0.24.3,
  found by the image e2e on windows-2022), and its okrun enters the image in its
  convention's floating-point state, under which the C library reads a decimal
  number on Windows as elsewhere (0.24.4). CI builds with mcpp 2026.11.7.2,
  which resolves within the platform's version group.
- The warm-prime gate takes the median of eight alternating native/image pairs
  and classifies a measurement as invalid or failed; only an invalid one may be
  repeated ([policy](ci/performance-policy.md)). A measurement is invalid when more
  than a quarter of its pairs lie further than 0.03 from the cold processor-time
  median or 0.10 from the cold readiness median (O5, registered after comparison
  run 42416069243 measured darwin-arm64 readiness 1.319 and 1.154 times native with
  pairs from 0.964 to 1.409, and before the measurement that qualifies this
  release). The limits are unchanged. The 0.0.20 Linux x64 cold-CPU exception has
  expired.
- Comparison run: https://github.com/Sunrisepeak/mcppls-clangd/actions/runs/42464678787 . Linux x64 and Linux
  ARM64 pass the warm-prime gate; Windows records its ratios (cold readiness 1.47 and processor time 1.21 times
  native, 1.53 and 1.25 for 0.0.20). darwin-arm64 measured three times and each measurement is invalid under O5:
  six of eight pairs lie outside the cold processor-time bound (the native engine's own cold readiness spans 7.5 to
  14 s on these runners), with medians of 1.14 to 1.29 times native readiness and 0.87 to 0.93 times its processor
  time. The release is admitted on its comparison with 0.0.20 instead ([policy](ci/performance-policy.md), "0.0.21"):
  the 0.0.21 image's absolute cold readiness on darwin-arm64 (medians of the two complete measurements 11.3 and
  11.0 s) and processor time (12.0 and 11.8 s) are not above 0.0.20's (11.6 s, 14.1 s), and on one machine the two images, alternated in four pairs, differ by at
  most 3% (0.0.21 against 0.0.20: cold readiness 1.03, processor time 1.01, faults 1.02, warm readiness 1.00,
  processor time 0.99; Linux x64, okrun of openkal-platform 0.24.4).
- A build-test run puts the image it built on the draft release `ci-artifacts` (assets replaced by each run, the
  run and commit in `ci-artifacts.txt`), from which a local analysis downloads it at a release asset's speed.
- The engine is released only as the ok image: a release publishes
  `clangd-23.1.0-mcppls.10-openkal.tar.gz` and `openkal-acceptance.json`, and no
  native archive (0.0.20 is the last with them; mcpp-language-server has used
  only the ok image since 0.0.20). A push or a pull request builds the image,
  accepts it on the four systems and builds one native engine, linux-x64, for the
  series' tests. The other native engines, the Ubuntu 20.04 floor packages,
  warm-prime and the shard exchange run in a comparison run, a manual dispatch of
  `build-test`; a release's entry names its comparison run, which the release
  workflow checks.
- The end-to-end regressions (`tests/e2e`) run against `clangd.okb` under okrun on
  the four systems, in each system's acceptance (`ci/e2e_suite.py`; the scripts
  take the runner from `MCPPLS_ENGINE_RUNNER`). The two cases that read a BMI
  another compiler wrote need the engine's own clang and are reported as not run
  there; they run on the native engine.
- The image starts a module worker program other than itself
  (`--modules-builder-worker-executable`) directly; only the image itself is
  started again through its loader.
- The shard exchange names each engine absolutely, since each session runs in
  its project's directory.

## [0.0.20]

- Readiness CPU measurement uses version 3 accounting, avoiding a child-reap
  double count and including waited descendants under live intermediate processes.
- Linux x64 cold CPU has a temporary release exception: image/native at most
  1.25 and additional CPU at most 3.0 seconds in the unchanged warm-prime
  fixture. The original 1.15 target and any failure remain visible separately
  from release eligibility. Other performance and correctness gates are unchanged.
  The exception expires after 0.0.20. See the
  [policy](https://github.com/Sunrisepeak/mcppls-clangd/blob/v0.0.20/ci/performance-policy.md) and
  [performance investigation](https://github.com/Sunrisepeak/mcpp-language-server/issues/77).
- Windows native/image paths differ. Historical cold readiness was 11.667 to
  16.534 seconds and warm readiness was 9.361 to 5.344 seconds. These results
  describe the tested workload, not a general latency guarantee. Final server
  and editor UX checks remain required.
