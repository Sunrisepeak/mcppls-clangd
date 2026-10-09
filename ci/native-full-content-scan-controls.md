# 0060: complete-content scan controls respect native admission

The new0055 test originally required cache hit/invalidation counters on every host, although production intentionally admits this scan cache only on Linux. Native Darwin arm64 and x64 run37725013312 both report exactly one failing test: ScanMemoHashesCompleteLargeHeaderContents; all seven large-header semantic M→N checks succeeded, but the expected counters remained0.

Keep every complete-byte semantic, equal-size and full-mtime control for padding lengths1023/1024/1025/65535/65536/65537/1048576. Linux still requires warm hits and invalidations. Other hosts require unchanged hits, invalidations and stores instead of claiming cache admission. No test is skipped, no compiler flag or deadline is weakened. This only corrects the maintained test premise; it does not broaden production cache admission.

Private source a0e69de939ae592eb7f41fb01a4a85d7f44f55be (test-only), integrated with59 in d0e287169. Two focused controls passed74ms before59, and the combined64-test selection passes1100ms. Proper numbered49–60 application matches all22 changed paths over the accepted47/48 fixture. Native CI on the corrected complete series is pending.

[Compact evidence](../tests/evidence/native-full-content-scan-controls.json). Drop when equivalent upstream test coverage respects actual cache admission while preserving full-byte semantic invalidation controls.
