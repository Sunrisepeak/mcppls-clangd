# 0055: full scan content fingerprints

0055: full cryptographic content fingerprints with LLVM BLAKE3

Private source ec868840b, parent0054 cf62a35f9, tree
/tmp/mcppls-module-scan-flights. Export
/tmp/0055-use-full-blake3-scan-content-fingerprints.patch. Only
ModuleDependencyScanCache.h and PrerequisiteModulesTest.cpp change. Source/binary
identity and partial-object provenance are in identity.json; compile/link args
and logs are /tmp/mcppls-scan55-build/. Shared root source/archives/build remain
untouched. Private ProjectModules and test objects plus copied private50
ClangdServer/Preamble/TUScheduler objects precede stable root46 archives.

Measured root cause and matched stage proof

ModuleScanManifest fingerprint hashed every complete opened buffer with LLVM's
generic software SHA256, once during canonical scan recording and again during
full publication/hit verification. Timing-only private instrumentation in
/tmp/mcppls-scan55-profile/qt.{json,trace.json,log} shows edited main's691 reads
cover18,371,153bytes. Fresh109.201ms contains34.853ms hashing; publication replay
45.982ms contains34.773ms hashing. Reopening files for FileStat/Read generates
1382 additional opens but costs only2.595ms, so changing session semantics is a
poor first optimization compared with the61ms content-hash opportunity.

Identically instrumented BLAKE3 proof is
/tmp/mcppls-scan55-blake-profile/qt.{json,trace.json,log}: edited main still has
exactly5731facts, same691reads and18,371,153bytes, same1809stat/691open/691fileStat/
1810absolute/36directory-begin/2directory-next/1realpath observations. Fresh
80.398ms has3.954ms hashing; replay15.265ms has3.857ms hashing. Content hashing
falls from69.626ms total to7.811ms (61.815ms saved). All four semantic requests
pass in both instrumented runs. Timers are temporary and are not exported.
Raw instrumentation code copies and actual binaries are retained with identity.

Implementation and safety boundary

Only complete content fingerprints use BLAKE3's full default32-byte output.
Every byte is consumed; byte-count/flags/errors/status/alias/CWD/directory
observations and full current-request filesystem replay remain. Exact command
comparison, immutable CDB identity, environment SHA256, persistent BMI/source
keys, scan freshness, unknown-input refusal, cancellation and8192fact/32MiB
metadata boundaries are unchanged. The memo is process-local with no persisted
fingerprint format to migrate. LLVM Support/BLAKE3.h documents the full output
as256-bit preimage/second-preimage and128-bit collision resistance. The bundled
BLAKE3 implementation uses runtime CPU dispatch plus portable fallback; no
compiler target flags or architecture assumptions are added.

CanonicalPreprocessing remains mandatory for the current observer/diagnostic
contract. Readonly audit found DependencyDirectivesScanner skips ordinary body
lines and explicitly skips #error/#warning directives, so switching scanner
mode could change HadError/failure diagnostics and actual time-builtin callback
observations. That alternative was rejected; no token normalization or ignored
input is part of this patch. File-session replay redesign is deferred because
measured extra-open cost is only~2.6ms and requires a larger provenance contract.

Verification and limits

focused-final.log:12 focused tests PASS255ms. Prior11 cover missing-header
creation, preservedmtime/same-size byte changes, draft/command/CDB/response and
provider invalidation, full fact equality/index growth, admission budgets,
cancellation and concurrent publication with divergent request filesystems.
New actual disk control covers padding1023/1024/1025/65535/65536/65537/1MiB:
changing only the tail import M->N, with identical size/identity/fullmtime and
unchanged main/CDB, invalidates the memo and returns N. This checks complete
content rather than mirroring the hashing implementation.

Exact uninstrumented final Qt evidence: qt-final.{json,trace.json,log}.
Strict UTF8/JSON trace; all4 semantic requests PASS. Cold1717.80ms,
warm68.41/63.55ms, edited149.38ms. Same source/resource/flags as0054's quiet
baseline209.91ms edited (earlier quiet204.31ms also retained). This is a
60.53ms reduction for this exploratory edit, consistent with61.82ms hash-stage
saving. The four semantic checks confirm expected candidate presence, not
insertion compilation or a complete performance context matrix. A single
edited sample below200ms does not close the release context/percentile gates.
Native performance proof is Linux x64 only; other native targets and portable
fallback throughput require CI measurements. Cache metadata remains exactly
14,351,170bytes across six retained entries; no RSS claim.

Drop when upstream uses equivalent full cryptographic fingerprints with complete-content invalidation and unchanged observation/replay guards. Native full recipe and release distributions remain pending.

[Compact evidence](../tests/evidence/module-scan-fingerprints.json).
