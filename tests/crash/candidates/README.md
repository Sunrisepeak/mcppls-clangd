# Real crash reduction candidates

These inputs are recovered from recorded failures. They are kept separate
from tests/crash/windows until the normalized case reproduces the historical
engine failure on the actual OS. A passing candidate cannot make an empty
qualified crash corpus eligible for release.

UP-12 contains the original GPPDefines.ixx from GalTranslPP commit
84bac7b25d7fee3277a11acbc5e7b4ca528700dc, with its Apache-2.0 license.
It is attributed to the GalTranslPP contributors; the source is unmodified.
Historical evidence records source SHA, exact original compile command,
archived --check exit 0x80000003 and CI/artifact identity. The replay normalizes
machine-specific paths, strips include/SDK locations and keeps the explicit unresolved BMI hints,
and retains Windows target, C++23, optimization/debug/LTO flags and the
missing -c that distinguished E3a from E3b. These differences must be qualified,
not assumed harmless. No third-party dependency or std BMI is supplied: this
is the unresolved-import scenario, not the UP-13 working-BMI crash.

The semantic assertion requires the original NameType enum and enum kind
from documentSymbol after opening the file, followed by normal shutdown.
The combined local Linux engine passes this Windows-target replay. That
cross-target result is recorded in tests/evidence/up12-candidate-linux.json;
it does not reproduce or close the native Windows failure.

The Windows corpus workflow now first downloads the SHA-pinned historical
23.1.0 release and runs ci/qualify_crash_candidates.py. A successful replay,
protocol error or semantic failure cannot qualify a baseline crash. Qualified
candidates then run against the PDB-bearing fork. The still-empty complete
release corpus continues to fail; UP-13 and UP-20 and symbolized crash stacks
remain required. If the normalized baseline does not crash, refine its input
and environment rather than relabeling a passing test as a crash regression.

Replay text uses ${FILE_TEXT:GPPDefines.ixx}; reads stay inside the fixture.
${PROJECT_PATH} expands absolute command paths and dictionary keys;
${PROJECT_URI} expands LSP document locations.


The first native qualification run (37674003750) used an in-memory CDB
notification and passed on the exact historical binary SHA dbd52c13...:
clangd reported no ProjectModules because its producer map requires a disk
CDB. That run is ineligible, and exposed a missing replay premise rather than
an engine fix. The candidate now writes a real compile_commands.json before
opening the source and restores/removes it on exit. The updated native
baseline verdict is required. The local Linux replay passes with that disk CDB.

The disk-CDB native attempt (37674275741) also passed on the historical
binary, despite reproducing the LTO scanner failure. The next candidate
preserves all six original -fmodule-file hints, directed at explicitly absent
BMI paths. The former normalization omitted those ASTReader inputs, so its
passing result cannot qualify a crash regression. Native qualification is
still required; these retained failure conditions are not invented corrupt
BMIs or forced process kills.


Native run 37684762425 with all six explicit hints exits 0x80000003 on the
exact historical binary SHA dbd52c13d21ef9d284f4f0627efe76c81adf2fe0998f230127f554a54fc9dde7.
The old harness initially labeled it error because EOF arrived before poll()
observed termination. Replay now waits briefly for natural exit after EOF;
a controlled delayed-crash regression requires exit9, while clean early EOF
remains a failed semantic replay. A forced kill cannot qualify a crash.
The native exit record is retained in tests/evidence/up12-native-baseline-crash.json.
Corrected-harness native run 37685946237 now qualifies this crash, retaining
exit 0x80000003, the exact engine SHA, raw initialization and reaped readers
in tests/evidence/up12-native-qualified-baseline.json. Native fork validation
and symbolized crash stacks remain pending.

The now-qualified UP-12 normalized input is also enrolled in
`tests/crash/windows/up12-galtranslpp.json`, sharing the original attributed
source directory. Enrollment records the actual baseline binary/run/exit,
not a fixed-engine verdict. The corpus is now nonempty but incomplete:
UP-13/UP-20 and actual fixed-fork native/symbol qualification remain required.
Earlier empty-corpus statements describe the historical checkpoints above.
