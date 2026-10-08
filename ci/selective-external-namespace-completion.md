# Selective external namespace loading during completion

Qualified namespace completion previously loaded every visible serialized
identifier before clangd applied its fuzzy matcher. The carried change passes
the consumer's actual matcher to a synchronous, exact-source/context scope and
selects name keys before deserializing declarations. Empty patterns and other
consumers keep complete loading. All declarations for a selected name remain;
nonidentifier traversal names, ordinary lookup, visibility and partial external
storage retain their existing contracts. BMI format and validation are unchanged.

The upstream register maps this patch to the existing completion performance
problem. The patch stays stabilizing: local measurements do not qualify the
final native kits or product payload.

Executable controls:

- `clang-tools-extra/clangd/unittests/CodeCompleteTests.cpp`: 142 CompletionTest
  cases, including six new scope, ordinary lookup, fuzzy/overload/using, alias
  and name-hiding controls. The cancellation test verifies scope cleanup,
  not immediate cancellation latency for every Sema operation.
- `clang/unittests/Serialization/NamespaceLookupTest.cpp`: five cases, including
  two new real named-module cases with independent/merged and updated lookup
  tables, all overloads and subsequent ordinary lookup of omitted names.
- `tests/probes/project_completion.py`: original Qt URI/CDB, actual typed
  replies and LSP insertion edits compiled using the original GCC command.

`ci/ci_build.sh` rebuilds ClangdTests, AllClangUnitTests, the CIndex test tool and
clang-repl from the same applied source. It runs CompletionTest and
NamespaceLookupTest on each supported native target. CLI/CIndex/interpreter
build coverage is explicit; final runtime and distribution evidence remains
necessary.

Local evidence:

- `tests/evidence/part2-linux/filtered-lookup-matrix-distribution/audit.json`:
  with the separate std distribution, 12 contexts each 3 starts × 30 rounds,
  2,232 replies, 1,674 required typed Sema replies, 432 actual GCC insertions.
  The std context compiles every selected reply; other contexts sample first,
  last and slowest replies per start/phase, all expected symbols. This does not
  claim that every returned item or every reply was compiled.
- `tests/evidence/part2-linux/filtered-lookup-four-arm/audit.json`: matched
  headers/modules × baseline/candidate, 186 replies per arm and 81 selected
  GCC insertions. Within each dependency mode, all returned item edit tuples
  match the baseline on every reply. Edited p95 in ms: headers 184.52 → 155.90,
  modules 255.22 → 188.61. Modules still exceeds candidate headers by 32.71 ms.
  Textual macro/declaration exposure differs from module exports; cross-mode
  item sets are not asserted identical.
- `tests/evidence/part2-linux/selective-lookup-export68/identity.json`: exact
  exported source/patch bytes, local test recipes and logs. Development objects
  are not substitutes for a clean source/build and immutable kit.

Pending qualification includes clean source/consumer identity, correct matched
stock comparison, resolve/snippet/module visibility, CPU/RSS/cancellation,
product/VS Code, native Windows/Apple Silicon and long-term release gates.

## Follow-up guide/operator selection (0069)

The follow-up passes StringRef names to the same scoped predicate. Deduction
guides use the template identifier; operators use exact Sema completion TypedText
spellings (not diagnostic names), including operatorco_await. Unknown names and
other declaration-name categories retain conservative loading. No BMI format,
public class layout or persistent cache changes. All consumers must be rebuilt.

146 CompletionTest and five NamespaceLookupTest controls pass in development
objects. The full matched Linux four-arm distribution has 744 typed replies,
83 selected GCC insertions and within-mode item/edit parity. Edited p95 in ms:
headers 180.13 -> 134.67; modules 250.61 -> 144.09. Warm p95 remains 37.90 vs
76.16. Full records include two invalid load-overlap attempts, explicitly
excluded; final candidate-modules-retry2 timing ran independently.
Evidence: tests/evidence/part2-linux/filtered-special-names-candidate/four-arm/.
Clean 0069 source/build and final consumer/platform/product qualification remain
pending; this is stabilizing evidence, not release approval.
