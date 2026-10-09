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
