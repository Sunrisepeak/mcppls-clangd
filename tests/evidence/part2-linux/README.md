# Part 2 Linux-first implementation evidence

The user authorized implementation of the 2026-10-08 Part 2 plan. Intel
Darwin is outside the supported target matrix for this iteration; historical
negative evidence remains historical, not repaired or erased. Neither PR may
be merged. Release qualification, not a narrow smoke, is the final objective.

`prerequisite/` archives the previously private PCH-assisted canonical scanner
controls before broader implementation. The saved patch SHA is verified
against its identity record. Raw patch/log bytes are retained as deterministic
gzip archives, preserving their original whitespace and uncompressed hashes. Five targeted tests passed in 315ms with normal
validation, unchanged original scanner flags, current body/import/role/error
and macro observations, plus dependency/command/alias controls. This is a
prerequisite, not an integrated optimization or a latency qualification.

The first local joint67 third-party-import control passed all three scenarios:
unresolved import reuse, fat-header/import transition and mid-session provider
command discovery. Its version-1 PCH was 12,204,136 bytes; version 2 collapsed
to 268,856 bytes. Native run 37779932094 instead retained 12,187,172 bytes
in both versions and failed the collapse assertion. That native negative is
not yet explained by this local pass. Investigation must distinguish a valid
audited import-free PCH from an unsafe/stale retained PCH before changing the
assertion or implementation.

The strengthened canary now covers both legitimate 0066 outcomes. Final67
uses zero-prefix fallback (12,204,176 to 268,880 bytes); the private audited
prefix-frame control retains the 12,204,156-byte import-free PCH for a body
import, then collapses to 268,868 bytes when the header imports that module.
Both controls preserve five typed actual-Sema replies across transitions and
pass third-party reuse/provider-command discovery. Retention requires explicit
trace proof of construction, complete inputs, import-free emission, audited
open handles and an accepted textual PCH. Header imports still must collapse.
This repairs an obsolete unconditional body-collapse premise without treating
size alone as proof. The revised canary passed Linux job 113380909792 in run 37797560280.
Windows and ARM macOS remain pending at this checkpoint; this CI still builds
the formal 67-patch runtime, not the private assisted-scanner candidate.

Exact summaries, compressed unmodified replay reports and private build
identity are in `third-party-contract/`. The private control is not a production
assisted-scanner implementation or a performance result.

`manifest-profile/` preserves the complete private L1 replay profile, raw
reports, trace, patch and exact compile/link identity with deterministic gzip
and uncompressed SHA checks. In the main replay, 622 paths are each opened
and closed three times, but read only once (9.22 MB). Measured delegated FS
median is 7.53 ms; an extra shadow hash costs 2.17 ms and is instrumentation,
not exclusive original hashing time. Directory iterator increments are not
timed. All four typed Sema controls passed, with no insertion compilation in
this profiling run. A session-provenance-aware reduction of repeated opens
is only a proposed approximately 2.85 ms opportunity; no optimization was
implemented. Cross-request stat/hash reuse remains unsupported.

`empty-index-candidate/` archives a held private CodeComplete change that
skips USR matching when the index slab is empty. Existing 136 completion
unit tests and an earlier four actual GCC insertions passed. A short
1-start/5-round A/B/A preserved every typed Sema reply: warm medians were
167.49/163.63 ms for the baselines and 161.01 ms for the candidate; edited
medians were 239.51/241.32 versus 239.57 ms. This neither closes the edited
gate nor proves a matched p95 benefit. The change is not exported; canonical
scan and repeated proof costs remain the implementation priority.

The `third-party-contract/native-checkpoint.json` captures actual native
Linux and ARM macOS artifacts for run 37797560280, built merge checkout
771501f43131a716419f07068b33a16fded8d49b (PR head d214029 is separate).
Linux legitimately retains the same 12,187,172-byte body PCH implicated by
the earlier failure, with all required audit trace facts and five actual
typed Sema answers; the header import collapses it to 251,880 bytes. ARM
macOS takes the conservative collapse path (12,715,024 to 837,988 bytes).
All three scenarios pass on both platforms. Windows was still running;
these are formal67 canary controls, not private-assisted latency proof.
