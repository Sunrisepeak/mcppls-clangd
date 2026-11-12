# The engine's tests

A directory says what kind its tests are, as [mtest](https://github.com/mcpp-community/mtest) lays a
project's tests out (`docs/layout.md` there): the kind a case states and the directory it is in agree.

| Directory | Kind | What | Written in | Run by |
|---|---|---|---|---|
| [`cts/`](cts/README.md) | conformance (`CTS`) | the series' regressions as cases of one program, `engine-cts`, run against a subject: a native build, or the ok image on each system | C++, `mcpplibs.mtest` | `engine-cts.yml` builds it once; `build-test`, `openkal`, `release` and the Ubuntu 20.04 floor run it (`.github/actions/engine-cts`) |
| [`e2e/`](e2e/README.md) | end to end | the engine behind mcppls over a generated or a real project, as an editor's user has it: scenario checks and latency | Python | `conformance.yml`, `e2e.yml` |
| `crash/` | corpus | sessions that once ended an engine, and what replays them (`replay.py`) | Python, JSON | `win-crash-corpus.yml`, `win-historical-crash-capture.yml`, `ci/qualify_crash_candidates.py` |
| `probes/` | measurement | completion latency and insertion, the resource window, the projects they are measured over, with the probes' own unit tests (`test_*.py`) | Python | `bench.yml`, and the workflows above for their projects |
| `soak_loop.py` | soak | sessions over one project and one cache, cycle after cycle | Python | `soak.yml` |
| [`evidence/`](evidence/README.md) | — | where a release's raw evidence is published; none is kept here | | |

The engine's unit tests are not here: a patch carries its own, in the tree it changes
(`clangd/unittests`, `clangd/test`, `clang/unittests`), and `patches/PATCHES.md` names each beside
its patch. `ci/check_ledger.py` fails when a test the ledger names is missing.

A new regression of the series is a case in `cts/`. Nothing in `e2e/`, `crash/` or `probes/` is a
`CTS` case; what is still Python there is to be written as `E2E` and `Bench` cases in directories of
those kinds (`.agents/docs/2026-11-13-tests-as-mtest-cases-plan.md`).
