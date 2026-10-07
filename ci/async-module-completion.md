# Completion must refresh invalid module dependencies

The async member probe fails after opening an updated Api.cppm draft: the AST
update detects invalid dependency inputs, but completion uses the old preamble
and its copy-on-read BMI before the new preamble is published. A documentSymbol
barrier does not imply the new preamble is ready. Disabling the experimental
index path or fixing the validation memo alone does not repair this.

0013 supplies ModulesManager to completion/signature-help ParseInputs. Before
using attached prerequisite modules, semantic completion validates them against
the request filesystem. Invalid dependencies are rebuilt, the old preamble and
stat cache are bypassed, and the consumer is parsed using fresh module copies.
Valid body edits keep their preamble and disk validation fast path.

On the same bounded asynchronous sequence, the baseline misses freshItem and
0013 passes. Disk replacement also passes, including prefix and pointer context
assertions. Raw outcomes, symbols, request timings and binary SHA are recorded
in tests/evidence/asynchronous-module-completion.json. CI now executes both disk
and draft probes with asynchronous scheduling. This does not establish all
command/provider/unsaved-import generation cases or the real-project budgets.
