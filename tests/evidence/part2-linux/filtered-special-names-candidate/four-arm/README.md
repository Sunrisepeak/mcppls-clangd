# Exact operator candidate: matched full distribution

Candidate source 31c43d3a2, binary e716110a08281c0b64101a74344677ddd5e82153696decb8c49590b0f0ea4d0f; baseline67 binary 200acd4f71d3e8f9927d9923b7005db7b98923e42f42880ef5e39ef483ce6d49. Three starts, 30 rounds per arm; original URI, CDB, resources and independent cache directories. Settled replies require actual index origin, not merely an index log message.

Valid arms: baseline-headers, baseline-modules, candidate-headers, candidate-modules-retry2. All 744 typed Sema replies passed; per dependency mode all 186 baseline/candidate reply item/edit tuples agree. Cross-mode result sets differ (23 header items, 65 module items). The 83 selected GCC insertions passed; this does not mean all 744 replies were compiled.

Edited p95: headers 180.13 → 134.67 ms; modules 250.61 → 144.09 ms. Candidate edited difference 9.43 ms (~7.00%); warm p95 remains 37.90 vs 76.16 ms. This qualified scene is not complete release qualification or universal header/module parity.

Invalid timing attempts retained: candidate-modules overlaps monitored external compilers; candidate-modules-retry1 overlaps our private clangd profiler. Compiler-only monitoring did not detect that profiler, so independent ownership evidence excludes retry1. Profiler report completed 37.42 seconds before baseline-modules started; it does not overlap the retained subsequent arms. No private instrumentation in valid engine.

Watchers sample compiler/ninja activity at 200ms and report zero observed overlap, no errors and stopped threads for valid arms; this is not proof of total host idleness. All insertion compilation follows corresponding timing, and retained prior proofs are reused without mutating prior reports. Cold results remain separate. Full semantic/build/platform/resource/release gates remain pending; no PR merge.

Manifest hashes refer to uncompressed original bytes. Cache artifacts omitted; CDB bytes, commands, reports, replay cases, logs, workloads and insertion proofs retained.
