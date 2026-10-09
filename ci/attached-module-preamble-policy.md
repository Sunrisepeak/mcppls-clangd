Patch 62: preamble mode follows attached module prerequisites

Source da2d023318f9cd66514aad9f4b8aa0f45f8399a7, clean private tree /tmp/mcppls-preamble-order62, based on root joint source d0e287169. Only Preamble.cpp and PrerequisiteModulesTest.cpp changed. No shared source/archive/index writes.

Authoritative native58 failure is /tmp/mcppls-native58-scan-failure/module-scan-memo/result.json (run37725013312/job113141099243, SHAe7e40ee723888ed9920cb737f3ef498c5271ac11f586328251a9546b4b135737). Version3 emitted module_not_found from enable.h; first completion rebuilt prerequisites without reusing the old PCH and returned fn_m. Version4 reused version3's preamble, validated M successfully, but returned no symbols. Result exit-9 is the replay's failure cleanup, not proof of a spontaneous crash.

buildPreamble previously serialized includes before preparing/attaching prerequisites. Thus successful RequiredModules metadata could accompany a PCH that failed to import those modules. Moving preparation earlier removed the diagnostic but still did not restore completion because named imports must remain textual under the existing module/preamble policy. Patch62 therefore prepares and leases prerequisites first, derives the effective skip mode from their actual BMI mappings while preserving explicit skip, computes bounds before PCH build, and records the same mode in PreambleData. Empty mappings keep ordinary PCH caching. Reuse respects the published effective mode; existing ClangdServer propagation carries it into completion. The same owned prerequisites remain attached throughout PCH and consumer lifetime, without rebuilding or releasing them between stages.

Deterministic same-test before/after:
- before-final.log: unchanged joint Preamble.cpp object, test explicitly simulates a preliminary false skip policy; nonzero bounds/import diagnostic and BOTH fn_m completions fail (exit1).
- after-final.log: all84 PrerequisiteModules/Preamble tests pass889ms. New test proves zero bounds, repeated fn_m completion, live read-copy existence through both consumers, and read-copy removal only after PreambleData destruction. Existing RecordsPreambleBuildMode tests preserve ordinary non-module PCH and explicit skip controls.
- scan-final/result.json: maintained real LSP sequence with explicit root clang23 resource directory passes all expected symbols,65 hits/4 invalidations, unchanged main contents, exit0, readers stopped. This is Linux local evidence, not a claim that the native58 artifact has been reproduced or CI rerun has passed. Artifact download stalled and was terminated.

build.py independently compiles the two changed translation units and links private binaries against stable46 archives plus the existing joint47-60 replacement objects. No public headers changed. This is focused integration evidence, not full clean-recipe/native qualification. Final binary identity and exact controls are in evidence.json.

## Root combined verification

Root rebuilt Preamble.cpp and PrerequisiteModulesTest.cpp, then the61 mangler consumers. Selected75 prerequisite/preamble/patch tests pass784ms,18 mangler controls pass1ms. The actual scan replay passes65hits/5invalidations, all expected semantic symbols, unchanged main bytes, exit0/readers stopped. Original Qt qualified/member eight requests plus every selected GCC insertion compile pass. Proper ordered49–62/64 matches24 changed paths; no clean/native recipe is claimed.

[Compact evidence](../tests/evidence/attached-module-preamble-policy.json). Drop when upstream PCH creation derives its effective module policy from the actual attached leased prerequisites, and repeat semantic completion/ordinary PCH/lifetime controls pass. Corrected native CI remains pending.
