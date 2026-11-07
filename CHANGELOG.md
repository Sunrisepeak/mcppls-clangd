# Changelog

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
- The warm-prime gate takes the median of four alternating native/image pairs
  and classifies a measurement as invalid or failed; only an invalid one may be
  repeated ([policy](ci/performance-policy.md)). The 0.0.20 Linux x64 cold-CPU
  exception has expired.
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
