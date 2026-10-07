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
machine-specific paths, strips include/SDK locations and missing BMI hints,
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
