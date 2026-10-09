# Canonical constructor completion

An importer with both textual headers and named modules can expose multiple
redeclarations of each constructor in `Record->lookup`. Ordinary completion
already guards canonical declarations; constructor expansion appended every
lookup entry. In the Qt control, vector had 39 constructor records for 13
canonical overloads and _Vector_base had 24 for 8, within one expansion each.
This produced 65 results for the same 23 distinct label/kind/edit combinations
as the textual control. This is not evidence of additional APIs being exposed.

Constructor expansion now merges canonical declarations locally, retaining the
later encountered declaration's details as ordinary completion does. Distinct
ordinary and function-template constructors remain. No text-based filtering,
result truncation, persistent cache, public layout/interface or BMI format change
is involved. The complete lookup still loads its declaration records.

`ConstructorsFromSharedHeaderModulesAreUnique` includes the same template class
header in two module global fragments and the importer. Before the change,
three overloads each appear three times and the fixture fails with nine; after
the change, exactly three remain and it passes. This regression is not a mock
of container internals. Another 169 existing completion, documentation and
constructor signature controls pass.

Private headers/modules A/B/A controls each run one start and three rounds.
All 48 typed-Sema answers retain the full set of actual edit fields and
documentation, changing only constructor redeclaration multiplicity in modules;
headers retain their full multiset. All 33 first/last/slowest selected actual GCC
insertions compile. Baseline and candidate executables use the same data disk.
Compiler/independent-engine group sampling observes no overlap, but does not
prove total idleness or process-tree resources. Short latency variation is
visible: no stable formal latency improvement is claimed for this correction.

Evidence is in `tests/evidence/part2-linux/canonical-constructor-completion72/`,
with declaration identity profile, original failed profile compile, fixed build,
baseline-failing/candidate-passing fixture, existing controls, raw short reports,
insertion proofs and a replayable audit. Final clean portable package,
distributions, native/product/platform/resource and long-term release gates
remain required. The ordered-comment experiment stays outside the series.

The whole72 clean Ubuntu20/Clang12 recipe now passes all 4744 build steps,
16 lit cases, 259 selected clangd tests (including the new constructor and joint
input regressions), five namespace tests, two memo controls and seven frontend
stages. The final stripped engine SHA is
`696e8caa5246525669583eb0f999f23cb21a87191f3b1be59a0c3952a5d1a0b1`;
its glibc2.31 dependency/startup check reports no problems, maximum symbol2.29.
Final-byte12-context1x1 controls pass48 requests (36 typed-Sema requirements)
and52 selected GCC insertions. The build's original mount126 startup failure
remains recorded, separately from the successful physical-path retry.

This evidence is in `tests/evidence/part2-linux/portable-canonical72/`.
Final72 full distributions, product/kit, process-tree resources and platform/
long-term gates remain open. State remains stabilizing; short timing is not a
release performance conclusion.

Final72 now also passes the full12-context3x30 distribution:2232 request checks
(1674 typed-Sema requirements),263 exactly selected GCC insertion proofs and
all applicable warm/edited budgets. The original invocation exits0; no remainder
run was needed. Standard-qualified warm/edited p95 is72.722900/145.368447ms.
The compressed-archive audit replays the per-request/input/workload/proof checks.
Native independent cold control passes4 Sema replies/four insertions, and the
AST-ready short stock/candidate/stock control passes9 replies/nine insertions
with identical actual edit-field multisets. Stock cold failures remain unchanged.
Native full distribution, matched header comparison, product/kit, process-tree,
platform and long-term release gates remain open; state stays stabilizing.
