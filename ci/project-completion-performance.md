# Real project completion measurement

`tests/probes/project_completion.py` inserts a completion expression in an
unsaved draft of an existing project, derives its UTF-16 cursor from the exact
unique source anchor, and validates required semantic candidates on every
request. Body edits produce new document versions. Raw replies and timings
are retained; replay requires normal shutdown. Source bytes remain unchanged.
The request time includes outstanding didChange work rather than hiding it
behind an arbitrary sleep. The initial documentSymbol settles initial AST work.

The Qt demo std::ve exploratory run returns vector in all three requests but
p95 is about 1297 ms. This is evidence of the remaining performance gap, not
release acceptance or a claimed improvement. Current full Sema completion is
still too slow. A single process and context do not satisfy three starts,
30 rounds/context, insertion compilation, the required context matrix, or
before/after speedup. Those remain required after a substantive optimization.

Raw evidence: tests/evidence/project-qt-std-completion-exploratory.json.

The one-request stage trace reports module validation ~297 ms and semantic
execution ~854 ms; the results callback takes ~0.2 ms. Raw stage events are
recorded in tests/evidence/project-qt-std-completion-trace.json. Patch 0018
adds separate spans around these phases without changing semantic behavior.
This identifies two remaining costs rather than claiming an optimization.
