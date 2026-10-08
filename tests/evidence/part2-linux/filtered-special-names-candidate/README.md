# Exact external operator name selection

Private source 31c43d3a2 extends guide filtering (5cd03e1fd) with StringRef spelling predicates and namespace operator selection. Actual Sema TypedText spellings are used; diagnostic DeclarationName formatting differs for co_await. Unknown/unsupported special names keep conservative loading. No BMI format, object layout or persistent cache change. Consumer signature changes require full consumer rebuild.

All 141 clangd consumer objects and seven related LLVM objects rebuilt. The sandbox transition terminated the original process after 75 completed objects; only the remaining 73 were resumed. ASTReader's first object predated the spelling correction; the final link uses the separately compiled corrected object. 146 CompletionTest and five real Modules NamespaceLookupTest pass. CIndex/interpreter and final clean package qualification are not claimed.

Short same-URI/CDB independent-cache A/B/A against guide-only candidate: all 36 real typed Sema replies and all 36 selected actual GCC insertions pass. All 65 returned items per reply preserve key fields and full actual edit tuples. Index match controls pass. 200ms compiler/ninja monitoring records zero overlap/error and normal watcher termination; this is not proof of complete system idleness.

Edited p95: baseline before 175.57ms, operator candidate 135.83ms, baseline after 177.92ms. This is short matched benefit, not a release distribution or same-mode headers alignment. All engine timing finishes before insertion compilation. Full original source/build/resume recipes, diagnostic logs, source and binary identity, original reports and actual insertion proofs are retained.
