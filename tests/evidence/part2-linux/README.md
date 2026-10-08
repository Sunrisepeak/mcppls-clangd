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
size alone as proof. Final native verification remains pending.

Exact summaries, compressed unmodified replay reports and private build
identity are in `third-party-contract/`. The private control is not a production
assisted-scanner implementation or a performance result.
