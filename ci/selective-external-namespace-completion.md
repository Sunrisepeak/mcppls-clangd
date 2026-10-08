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

## Resource phase correlation

The probe and replay record time.monotonic_ns on raw request send/observed
response spans and /proc sample read intervals. Context answers retain the
request markers. Deferred completion markers end when the client awaits and
observes the response; they are not server execution timestamps. Resource
samples are not atomic CPU/RSS snapshots and exclude descendants. A stable
window audit must distinguish cold/index preparation, account for sample
coverage and report missing boundary coverage; lower-bound sampled CPU alone
cannot prove a hard process-tree memory limit or the final 20% regression gate.
Historical records without these markers remain unchanged and do not gain
stable-phase qualification retroactively.

`python3 -m unittest discover -s tests/probes -p test_resource_timeline.py -v`
passes a real framed subprocess with ordinary/deferred replies and /proc
sampling. Four `ci/test_soak.py` regression controls also pass after the shared
replay change. This validates measurement plumbing, not engine performance.


## Final Linux floor bytes: 0069 qualification in progress

The same 69-patch source completed the offline Ubuntu 20.04/glibc 2.31
Clang 12 build, 16 lit tests, 255 selected clangd tests, namespace/memo
controls and all seven frontend consumer stages. Packaging and actual floor
startup/dependency checks passed. The stripped engine SHA is
`b7eba8bfdd1c26ff93ba4fba53678916a9f8d3d4e79ce3cf1a97375a07593e8f`;
its build records fork `affe666292c6b53b842df1d217a811bdfc85e47c` and
source `4b26052750b46f7fbfaceb5bd3c7c16b0d01f2ca`.

All 12 short contexts and 52 selected GCC insertions passed. The full native
std AST-ready stock/candidate/stock 3x30 comparison passed all 549 typed Sema
replies, item/edit parity and 49 selected native insertions. Edited p95 was
89.234/22.159/89.194 ms. Stable main-process CPU conservative ratios were
0.56885/0.56860 and maximum per-start observed RSS p95 ratios were
0.57910/0.57324. This is one fixture, excludes cold completion explicitly,
and does not certify descendants or a hard memory ceiling. Stock cold
negative records remain unchanged in `clean-selective69`.

The final Qt 12-context full distribution is still running. Its completed
first-column context failed the 200 ms edited p95 budget at 201.221592 ms,
while all semantic replies and selected insertions passed. Preserve this
negative; do not qualify the candidate from the short controls or native
fixture alone. The Scope expression path still uses ordinary visible lookup,
which is an attribution lead, not a proven exclusive cause. Isolated traces
must wait for the distribution to terminate. Product, other-platform and
long-term qualification remain incomplete; the ledger stays stabilizing.
Evidence and exact recipes: `tests/evidence/part2-linux/portable-selective69/`.


## Unqualified Scope/TU follow-up: 0070 (stabilizing)

The final 0069 Qt matrix completed with all 2,232 request checks and 251
selected GCC insertions passing, but first-column/ordinary edited p95 failed
at 201.221592/210.724679 ms. Independent final-byte native traces and private
batch CPU attribution found that unqualified completion still enumerated
10,488 TU declarations per lookup (about 29 ms CPU enumeration plus 6 ms
consumption in the GCC development build).

0070 applies the borrowed completion name predicate to ordinary-name and
expression Scope traversal, and permits selection of external C++ TU names.
Local scope, using traversal, visibility, overloads, ordinary lookup, empty
patterns and C behavior remain intact. The new Sema method is nonvirtual;
class layout and the existing virtual ABI do not change. Two changed Sema
objects and completion tests were rebuilt with unchanged 0069 consumers;
this is a private candidate, not a full clean 0070 consumer build. Two new
controls and 146 existing CompletionTests pass.

Default top100 comparisons varied even between unchanged baselines at index
cutoff boundaries; the original failure is retained. Independent unlimited
engine-response controls compare actual returned fields and equal legacy
incomplete flags, then compile 24 actual selected edits. This does not imply
that the index has returned every possible symbol. With the default limit and
publication/positive index gates restored, 1x5 A/B/A checks all returned items
against that verified reference, all typed Sema and 39 selected GCC edits pass.
First-column edited p95 is 181.596/168.870/177.618 ms, ordinary is
172.074/157.217/178.541 ms. No all-default-top100 equality or final-byte
qualification claim follows from these short controls.

Export source/series identity: `selective-unqualified-export70/identity.json`.
Private implementation and original/corrected experiments:
`unqualified-visible-candidate70/audit.json`. All paths are under
`tests/evidence/part2-linux/`. Final full-series clean build, distributions,
product, supported native platforms and release gates remain incomplete.
