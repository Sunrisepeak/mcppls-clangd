# Intel Darwin DAG shutdown diagnosis

The retained `bfce1f1` run 37767844227 / job 113279779233 / artifact
11549619310 completed all four module tasks and returned four actual Sema
completion items. It logged a shutdown reply and `LSP finished` before the
30-second replay deadline, but remained alive until replay cleanup killed it.
A dynamic standard-library index had started immediately before completion.
The retained artifact has no final thread stack, so this is a candidate cause,
not a proven unique blocker.

The normal DAG matrix, its 30-second deadline, semantic assertions and worker
assertions remain unchanged. The optional `--case wide-1` selection requires a
fresh directory. It explicitly enables config in both A/B cases; only the
control writes `.clangd` with `Index.StandardLibrary: false`. This does not
change production defaults. A timeout remains a timeout even if the server
exits while diagnostic sampling runs.

On opted-in Darwin timeouts, replay checks that the original PID is still
alive, then invokes `/usr/bin/sample` for one second. The sampling subprocess
has a separate process group, a three-second execution limit and a 256-KiB
retained output limit. Its group is killed/reaped and its nonblocking reader
is stopped/closed before normal server cleanup. Sampler failures are recorded
without changing the replay verdict. No forced kill qualifies as success.

`build-test` uploads `darwin-x64-dag-diagnostic-payload` after a successful
Intel build, before the DAG step. Its tar preserves the clang++ symlink and
contains the same-build unstripped clangd, clang, resource headers, engine
marker, byte hashes and native SDK/Xcode/runner metadata. No historical Darwin
payload existed for the failed run: a future package is **not** described as
that run's original engine/compiler.

Dispatch `darwin-dag-shutdown-diagnostic` with the immutable artifact ID. It
builds nothing. It compares the artifact's workflow head to API metadata,
while retaining a separate `built_checkout_sha` verified against `git HEAD`
and the engine marker. For PR runs, this can be the merge checkout rather
than the PR head; the PR head is never labeled the exact binary source.
Compiler bytes, SDK path/version/settings hash and Xcode must match. OS and
runner-image fields are recorded but are not equality requirements, so this
is not a claim of identical full host state.

Both cases run sequentially at the same generated project path, with fresh
caches. Raw files are retained separately after each run. The summary compares
all generated source and CDB byte hashes, flags and records the policy file.
A failed default replay still runs the control; the workflow retains failure
and always uploads raw results and any sample. Missing artifacts or identity
mismatches fail explicitly. One run per policy provides diagnosis, not a
latency distribution or release performance gate.

Local verification: Python compilation and YAML parsing; sampler subprocess
controls for output truncation and hard timeout (server untouched), and CLI
rejection of a control without the single-case selector. Native sampling and
the real A/B remain pending the first matching artifact.

The opt-in single-case fixture also passed locally with final joint67 binary
`200acd4f71d3e8f9927d9923b7005db7b98923e42f42880ef5e39ef483ce6d49`:
both default and standard-library-disabled runs returned all four actual
Sema items and preserved the one-worker bound. Document symbols took 1061ms
and 1123ms respectively. These Linux runs used separate fresh directories;
they validate fixture plumbing, not native shutdown attribution or matched
same-path A/B performance.
