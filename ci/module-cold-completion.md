# Initial module completion and resolved commands (UP-25)

The first completion immediately after didOpen could return no imported symbols.
Two independent scheduler decisions caused this: ParseIfReady allowed a missing
initial preamble, and a waiting preamble task captured the provisional fallback
compile command before the first update resolved the compilation database.
Waiting for a preamble alone still produced no fn_m because the fallback command
did not describe the C++20 module translation unit.

Module-enabled completion now waits for the first preamble unless NeverParse was
explicitly requested. Existing stale preambles still serve edits without waiting
for their rebuild. Other completion modes retain their existing policy. After
waiting, the task refreshes the resolved compile command before invoking the
semantic callback. Failed compilation and explicit fallback remain possible;
this patch does not manufacture index-only symbols or suppress diagnostics.

The raw module_cold_completion.py fixture creates a unique empty-cache project,
opens the importer and immediately asks for fn_m. It has no documentSymbol,
index-ready wait, sleep, or other AST barrier. The final stripped 29-patch
baseline responds without fn_m; the candidate returns fn_m and shuts down
normally with unchanged source bytes. The baseline's subsequent -9 is replay
cleanup after a failed semantic assertion, not a natural engine crash.

The phase probe additionally checks one cold-open, four AST-settled warm and
three edited requests. All eight candidate requests return the required symbol;
one development sample measured about 21 ms cold, 3–6 ms settled and 5–6 ms
edited. These small synthetic samples establish the repaired cold correctness,
not broad performance thresholds. Existing fallback/command/preamble scheduler
and cancellation cases total ten passing focused units. Final native binaries,
installed editors, full statistical context matrix and resource deadlines remain
separate release requirements.

[Integrated evidence](../tests/evidence/module-cancellation-and-cold-completion.json) records both identified binaries, raw semantic outcomes, phase samples and all 68 focused unit passes.
