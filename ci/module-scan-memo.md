# Current scan memo contract (0044)

Patch 0044 extends the historical successful-result memo below. Semantic scan
failures may be reused only when the scanning tool actually emitted errors and
the complete observed manifest, exact request bytes, adjusted command, immutable
CDB generation and environment all revalidate. Hits retain the original failure
and command diagnostics and return nullopt. They never invent a provider, module
name or BMI. Failure diagnostics retain at most 64 KiB and count toward the
unchanged 32 MiB/256-entry shared metadata budget.

RealPath now records original spelling, CWD, exact error and canonical result,
then replays against the current request VFS. Initially populated outputs and
unknown operations decline. Exact duplicate idempotent facts compact only when
all operation/status/error/name/UID/metadata/read digest/size/binary/null/found
fields match. Different outcomes remain; directory events remain ordered.
Recording uses bounded linear lookup (quadratic worst-case comparisons).

The explicit observation cap rises from 2048 to 8192. Actual complete Qt manifests
need 5731 facts for main, 4859 for moc, 3928 for failed GCC std.cc, 3226 for
nlohmann and 183 for qrc; six entries charge 14,086,498 bytes. Worst-case replay
work rises fourfold; this is neither an RSS cap nor permission to skip freshness.
Oversized manifests/diagnostics, unsupported native discovery, actual time
builtins, response-file commands, missing provenance and opaque inputs still
reject admission. Every replay operation and the final operation poll
cancellation. Store rechecks after replay, under the lock, during budget
reservation and before publication; canceled candidates release reserved bytes
and do not evict valid hit entries.

Private initial 0aa9f31 plus cancellation follow-up dfac5eb are preserved; export
18de83e has their final tree. Eight focused tests pass, covering failure repair
including equal-size/equal-mtime bytes, newly created headers, drafts, CDB and
response changes, oversized diagnostics, cancellation at the final read,
real-path alias changes, exact compaction and retained ordered differences.
Private links put changed objects before unchanged root archives; that scope is
not a full clean release build. The combined root 1–46 verification rebuilds all
four changed translation units and passes 100 related tests. Ordered application
matches 74 affected paths and three overlays. See
[combined evidence](../tests/evidence/project-qt-worker46.json).

Matched-resource Qt measurement on actual combined source gives warm 344–348 ms
versus 725–730 ms at 42, edited 742 ms versus 1302–1314 ms. Both positive manifest
admission and failed std scan reuse contribute; this is not an isolated negative
cache speedup. All four semantic requests pass. The 200 ms target, insertion
compilation and statistical context matrix remain open. An earlier private run
without the explicit resource directory changed the workload and is discarded.

## Historical 0028 contract (superseded where specified above)

# 0028: verified positive module-dependency scans (UP-03 / W2)

The previous request-buffer fix makes scans correct but removed an unsafe disk-stat verdict cache. This change reuses successful P1689 scans only after replaying the filesystem inputs observed by a fresh scanner. It preserves module provider mapping on a hit and leaves source/provider/BMI validation in ModulesBuilder in place.

Initial admission requires a Linux host and a reviewed effective GNU/Linux target. Driver executable target/mode parsing and explicit target overrides are checked; cross targets, Android, clang-cl/other modes, native CPU selection and config/offload target indirection decline. Default .cfg reads also decline because they may redirect to native registry discovery. Windows/MSVC, Darwin and other target toolchains are not claimed observable by this Linux proof.

The key contains the immutable loaded CDB generation (weak ownership), complete adjusted CompileCommand, exact main-buffer SHA-256, CWD and complete process environment fingerprint. JSON loader provenance is checked BEFORE response expansion. Any original @response argument declines sharing for that whole CDB generation. Fixed/plugin CDBs and external callers without explicit provenance also decline. This does not fix the existing response-file loader reload gap itself.

A recording VFS captures successful/failed status, exists, open, file status/name, exact read bytes and buffer API arguments, makeAbsolute, and lazy directory begin/increments. Directory replay compares the observed ordered prefix, entry type, termination and errors; it never enumerates extra entries during recording. File IDs are compared as a bijective alias partition so independent immutable draft overlays can hit while preserving pragma-once/FileManager identity relationships. Every file read is hashed even when size and the full mtime are unchanged. Negative lookup observations invalidate when a missing header appears. Realpath, locality queries, child-VFS visitation and a changed CWD decline the entire scan; no unsupported operation silently disappears from a manifest.

Every miss constructs a fresh DependencyScanningService. The worker/service is destroyed before the manifest is finalized, preventing internal filesystem caches and deferred close observations from escaping the request. Inputs are replayed against a new current request view before publication and against the current request view before each hit. No failures, unresolved-provider verdicts or in-flight waits are cached. Time builtins (__DATE__, __TIME__, __TIMESTAMP__), token pasting, escaped identifier spellings and plugin-loading commands decline admission conservatively. Lexical screening can reject harmless literals/comments and macro-heavy standard headers; this is deliberately narrow initial admission, not a claim that arbitrary standard-library scans now hit.

The process-wide LRU reserves at most 256 live entries and 32 MiB of owned metadata (allocation capacities plus bookkeeping allowance), including evicted entries still borrowed by validators. Each scan records at most 2048 observations. IO validation happens outside the cache mutex. These limits bound cached metadata; concurrent recording, compiler allocations, mmap buffers and total RSS are NOT covered. Independent compiler/worker admission with deadlines remains a separate mandatory W2 follow-up. Provider inventory adjustment still costs O(N) mangler calls because no reliable per-file config epoch exists; this patch does not silently weaken config invalidation to remove that cost.

Initial isolated validation artifacts were retained under /tmp/mcppls-scan-memo-review: unit.log (six focused tests pass) and raw-final/result.json. These private artifacts are not part of the repository or an immutable release package. Final integrated evidence is tracked under tests/evidence. The raw fixture keeps main contents identical through repeated requests, missing-header creation, equal-size EXACT preserved-mtime header replacement, a header draft that overrides disk, and a second header draft. It checks real semantic completions fn_m/fn_n and clean shutdown, and requires positive memo hit/invalidation counters from verbose logs. Its private replay.py adds only a preserved-mtime action and asserts the actual filesystem timestamp remains exactly equal. The unit also checks fresh draft snapshots with equal artificial timestamps and configured imports/provider mapping on hits and successful Windows cross-target scans declining reuse.

Private binaries are linked from isolated ProjectModules/GlobalCompilationDatabase/unit objects before the existing native archives. Other objects are the root's native 0026/0027 tree, with its independent request-overlay lifetime repair. This is focused mixed-tree validation, not an immutable full-source release build. No shared objects, archives or engine executable were written by this task.

The combined test initially exposed MockFS process-CWD leakage: its real fallback is the process-wide filesystem, and scanner CWD changes survived until fixture deletion. gdb confirmed valid RequestModuleFS strings but getcwd() returned NULL; PrerequisiteModulesTests now saves/restores process CWD before deleting its directory. The same combined six-test filter passes with this fixture isolation, without skipping a test or adding a production suppression.

Patch 0029 replaces the lexical admission screen with actual preprocessing observations; see [module-scan-builtins.md](module-scan-builtins.md).
