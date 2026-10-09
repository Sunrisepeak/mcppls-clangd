# Joint completion input validation

A completion with a verified textual preamble used separate canonical queries
for its imports and its ordinary-TU role, replaying the same full draft twice.
The built-in scanner now returns imports and ordinary-TU proof from one scan.
The textual prefix still receives independent import-free verification. The
result stays local to the request; no content, filesystem observation, command,
CDB generation, environment, cancellation or negative lookup check is skipped.
Custom backends retain their conservative separate queries by default.

`CompletionInputsKeepDraftRoleAndPrefixIndependent` checks the two-replay warm
path, body draft changes, module-unit role rejection, command mismatch and a
request without imports. Existing textual tests retain fresh header bytes,
unknown-input/header-import rejection, actual-command checks and fallback;
the complete completion suite also runs.

The new virtual operation requires rebuilt consumers. The private candidate
rebuilt all 141 prior clangd consumers, then linked with unchanged compatible
LLVM/Sema70 objects. This is not the required full clean portable package.

Private short headers/modules A/B/A controls use the same GCC recipe, original
URI/CDB/drafts/producer and matching final resource headers. All 48 typed-Sema
replies preserve actual edit fields and documentation within each mode; 32
first/last/slowest selected actual GCC insertions compile. Four warm samples
per arm are too few for release distribution claims. Module warm p95 is
70.53/61.33/75.12 ms; edited is 141.67/133.21/137.27 ms. No compiler or independent
clangd group overlap was observed in 200 ms sampling; this is not total-load
or process-tree resource proof. Headers/modules expose different candidate
sets and are not required to return identical answers to each other.

Evidence: `tests/evidence/part2-linux/joint-completion-inputs71/`, including
source/build identities, recipes, all consumer logs, 154 passing semantic
controls, short raw reports, insertion proofs and a replayable audit.
Full clean final package, distributions, product, platform, resource and release
gates remain open. Preserve final70 evidence as evidence for those exact bytes.
