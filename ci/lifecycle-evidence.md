# Module lifecycle smoke

`tests/soak_loop.py` exercises generated modules using the same project/cache
across independent processes. Successful completion must include **every**
`fnN` exported by the `import mN;` units, with Function completion kind.
An AST operation precedes the clean-cycle completion, so early identifier
fallbacks during initial parsing cannot pass the gate. LSP errors, unrelated or empty
completion, initialization without capabilities, abnormal exit and a shutdown
which outlives the cycle deadline all fail.

Every third cycle sends a completion, deliberately terminates the engine's
process unit and reaps it. A new engine then has to complete semantically and
exit normally. Intentional kills never count as answered requests. The kill
is after request submission; it does not assert that BMI construction was
still active at the instant of termination. The dedicated live-lock-close
probe supplies that separate assertion.

On POSIX, teardown signals the whole owned process group even if its leader
has already exited. Reader threads must stop before a cycle succeeds; inherited
pipes cannot leave a lifecycle cycle apparently complete. Windows uses
`taskkill /T /F` for a live engine; crashed-parent descendant tracking is not
proved on Windows by this smoke and remains a platform validation item.

Each report includes the engine SHA256, raw request responses, required and
observed symbols, per-process elapsed time and exit code, kill counts, recovery
outcomes and semantic pass counts. The sanitizer nightly carries the JSON as an
artifact, including on failure. `ci/test_soak.py` supplies controlled negative
cases for wrong symbols, lexical-only results, request errors, crashes, shutdown hangs, deadlines and
POSIX inherited-descriptor cleanup. The series verifier runs those controls.

This is the short lifecycle gate required before qualifying nightly history;
it does **not** provide a real crash corpus, two-hour RC load, 1000-save fan-out,
RSS/cache-growth acceptance or Windows PDB/stack identity. Historical green
runs of the previous reply-only loop do not satisfy those gates.

## Local Linux evidence (2026-10-07)

The four-module project completed ten lifecycle cycles on engine SHA
`a55e539c221e27948963d028951bd7ee40ed0f125865dbf43381939ac1d7d499`:
ten semantic completions/clean exits and three separately recorded intentional
kills, each followed by semantic recovery. The first pre-barrier attempt
returned only a lexical `fn1`, and the new all-function assertion rejected it;
the AST barrier fixes the harness timing without relaxing semantic acceptance.
Eight fast negative-control test groups pass (four release/corpus groups,
four lifecycle groups). These bytes are the local development build, not an
immutable final package or evidence for other platforms.

Commands (project and raw report stay outside the PR):

```bash
BENCH_CLANG="$PWD/build-linux-x64/bin/clang" python3 tests/probes/gen_bench_project.py /tmp/joint-soak-semantic 4
python3 tests/soak_loop.py build-linux-x64/bin/clangd /tmp/joint-soak-semantic --cycles 10 --timeout-seconds 15 --output /tmp/joint-soak-10.json
python3 ci/test_release_gates.py
python3 ci/test_soak.py
```

The corpus harness now also signals the POSIX process group after a crashed
leader exits, joins its readers and closes finished streams. The inherited-pipe
negative control fails on the old harness and proves no live pipe holder remains
with the repair. This repairs evidence-process cleanup; it does not claim an
engine crash root cause has been fixed.

PR builds and series verification now run once on `pull_request`; `push` covers
`main`. Previously the same draft update scheduled duplicate runs, one cancelled
the other, and cancelled check records persisted alongside passing PR jobs. The
native build workflow lets its active revision finish and save caches before
starting the newest queued revision, avoiding repeated cancellation of the
multi-hour Windows build. Manual platform selection remains available.
