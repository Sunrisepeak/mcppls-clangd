# Changelog

## [0.0.21]

- The ok image (`clangd.okb`) is built with zlib, as the native engines are, and
  reads the index shards an engine with zlib writes. It discarded them before
  ("Compressed string table, but zlib is unavailable") and indexed again.
- The engine reports itself as `23.1.0-mcppls.10`.
- The image is built over openkal-platform 0.24.1, stated only in
  `openkal/clangd/mcpp.toml`; CI writes its probes from that line.
- The warm-prime gate takes the median of four alternating native/image pairs
  and classifies a measurement as invalid or failed; only an invalid one may be
  repeated ([policy](ci/performance-policy.md)). The 0.0.20 Linux x64 cold-CPU
  exception has expired.

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
