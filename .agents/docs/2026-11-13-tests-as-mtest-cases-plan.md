# The engine's tests as cases of one mtest program: plan

2026-11-13. Asked for with mcpp-language-server #89: the tests under `tests/` and the end-to-end
regressions are written in C++ over the latest mtest (0.6.3), and CI is rebuilt around that.

## What there was

- 25 Python scripts under `tests/e2e/`, each a regression of the series with its own argument
  parsing, report file and exit status, over `tests/crash/replay.py` (a session of fixed steps).
- `ci/e2e_suite.py` ran 24 of them against the image in each acceptance; the native job of
  `build-test.yml` ran them as about 25 steps with an upload after each; `ci/scripts/linux-floor.sh`
  ran ten; `ci/ci_build.sh` ran one inside the build.
- A case could not be selected, scheduled or rerun by anything but its own command line; "not run
  here" was a table in a Python file.

## What there is

One program, `tests/` (`engine-cts`), C++ over `mcpplibs.mtest` 0.6.3:

- `src/harness.cppm`: the subject (the engine the environment names, with what it has), `replay`
  (the session of steps, the same steps and the same result as `replay.py`), `Client` (an engine
  talked to step by step), `lit_test`, `tool`.
- `e2e/*.cpp`: 26 cases. Each is a `CTS` object, so mtest lists, selects and schedules it; its
  parts run under `cts::against` the subject, and a part that needs what the subject lacks
  (`cts::needs{"linux"}`, `matching-clang`, `clang-tidy`, `control`) is reported `unsupported`,
  never passed.
- Built once per run as an ok image of both architectures with every system's runner
  (`engine-cts.yml`, `mcpp pack --target openkal --mode self-contained --systems all`), and run by
  every job that tests an engine through `.github/actions/engine-cts` (`ci/scripts/engine-cts.sh`).

## Tasks and what each depends on

| # | Task | Depends on |
|---|---|---|
| T1 | `tests/mcpp.toml`, `src/harness.cppm`: subject, `replay`, `Client` | mtest 0.6.3 in mcpp-index |
| T2 | The cases of the image's suite (the 24 of `ci/e2e_suite.py`) | T1 |
| T3 | The cases only a build tree has (`const-correctness`, `frontend-completion-consumers`) | T1 |
| T4 | The Windows 11 24H2 control as a part of `gmf-include-analysis` (`control`) | T2 |
| T5 | `ci/scripts/engine-cts.sh`, `ci/mtest.env`, `.github/actions/engine-cts` | T2 |
| T6 | `engine-cts.yml`: the tree built once; dispatched alone, the cases against a released image | T5 |
| T7 | `build-test.yml` (native job: one step), `openkal.yml` (acceptance, the 24H2 gate), `release.yml`, the floor | T6 |
| T8 | The Python scripts and `ci/e2e_suite.py` removed; the identity's directive canary moved to `ci/`; ledger and documents name the C++ files | T2, T3, T7 |
| T9 | Every system green: the released image on four systems and windows-2025 (T6), the pull request's run, one comparison run for the floor and the other native builds | T7, T8 |

T2 and T3 were checked case by case against the image of 0.0.22 on Linux before T8 removed what
they replace; T9 is where macOS and Windows are first seen.

## What stays Python, and why

Measurements and evidence tools with workflows of their own, none of them a regression a pull
request runs: `tests/crash/` (the Windows crash corpus and `replay.py`, which
`ci/qualify_crash_candidates.py`, `ci/windows_crash_capture.py` and `ci/test_release_gates.py` load
as a library), `tests/soak_loop.py`, `tests/probes/`, `tests/e2e/{lsp_driver,accept,compare}.py`.
Their successors are `Bench` cases and a corpus case over the same harness; that is the next change,
not this one. `ci/darwin_dag_diagnostic.py` (darwin-x64, a platform no longer built) went with the
script it ran.

## Found on the way

- mtest 0.6.3 does not list or select a part declared inside `cts::against`: `mtest list` shows the
  subject, `--case 'x/image/part'` selects nothing, and `--failed` reruns the whole subject. Hence a
  `CTS` object per regression, with `against_subject` as its body.
- mtest recognises a protocol program by a marker in the file: the launcher script of a packed tree
  has none, so mtest is given the `.okb` with `--run-under <the tree's okrun>`.
- mcpp warns that `mcpplibs.mtest.cts` and `mcpplibs.mtest.e2e` are not public modules of the
  package, though mtest's guide tells a test to import them.
