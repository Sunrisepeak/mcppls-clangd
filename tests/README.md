# The engine's tests

One program, `engine-cts`, whose cases are the series' end-to-end regressions: each is a session of
the engine over a project the case writes. It is C++ over [mtest](https://github.com/mcpp-community/mtest)
(`mcpplibs.mtest` 0.6.3), a conformance suite run against a **subject** — the engine the environment
names, the ok image under its runner or a native build — which may lack what a case needs.

```
tests/
  mcpp.toml            the program: mtest, mcpplibs.os, nlohmann.json, over the image's platform
  src/harness.cppm     the subject, a session of steps (replay), an engine talked to step by step (Client)
  src/main.cpp         mtest's run
  e2e/*.cpp            the cases, a file per subject matter
  crash/, probes/, soak_loop.py, e2e/{lsp_driver,accept,compare}.py
                       measurements and the crash corpus: tools of their own workflows, Python still
```

## Built once, run on every system

`mcpp pack --target openkal --mode self-contained --systems all` builds the program as an ok image of
both architectures with the runner of every system. CI does that once per run
(`.github/workflows/engine-cts.yml`, the artifact `engine-cts`), and every job that tests an engine
runs that one tree through mtest (`.github/actions/engine-cts`, `ci/scripts/engine-cts.sh`): the
native build, the acceptance of the image on four systems, the Windows 11 24H2 gate with its control,
the Ubuntu 20.04 floor. Such a job needs neither mcpp nor a compiler for the tests.

Locally:

```sh
(cd tests && mcpp pack --profile release --target openkal --mode self-contained --systems all \
     --pkg-format zip,okb -o /tmp/engine-cts/)
ci/scripts/engine-cts.sh --tree /tmp/engine-cts --engine <clangd.okb> --runner tree \
     --clang "$(command -v clang)" --out /tmp/engine-cts-run -- --case 'module-dag*'
```

or, while writing a case, the host's own build and the program alone (it lists with `--list`, and
runs the cases named after it, one after another):

```sh
(cd tests && mcpp build)
MCPPLS_ENGINE=<clangd> MCPPLS_ENGINE_CLANG=<clang> tests/target/*/*/bin/engine-cts module-cycle
```

Dispatching `engine-cts` by itself runs the program against a released image on every system: the
tests are tested in minutes, without the hour an image takes.

## The subject

| Environment | Says |
|---|---|
| `MCPPLS_ENGINE` | the engine: `clangd.okb`, or a native `clangd` |
| `MCPPLS_ENGINE_RUNNER` | what starts an image (`okrun`); unset for a native engine |
| `MCPPLS_ENGINE_CLANG` | the compiler the compile commands name |
| `MCPPLS_ENGINE_PLATFORM` | `linux-x64`, ...; unset: this system's |
| `MCPPLS_ENGINE_HAS` | what it has beyond what the program sees: `matching-clang`, `two-identities` |
| `MCPPLS_ENGINE_TIDY`, `MCPPLS_ENGINE_C_INDEX_TEST`, `MCPPLS_ENGINE_CLANG_REPL` | a build tree's tools: `clang-tidy`, `frontend-tools` |
| `MCPPLS_ENGINE_CONTROL` | an engine without a fix, started as the subject is: `control` |
| `MCPPLS_ENGINE_KEEP` | a directory each case's project and answers are kept in |

The program adds the system (`linux`, `darwin`, `win32`) and `native` or `image`. A part that needs
what the subject lacks is not run and says so (`skip`, `unsupported: matching-clang`): that is stated
from what the subject is, never from a run that went wrong, and it is never a pass.

## The cases

Each is a case of its own that mtest lists, selects (`--case 'module-dag*'`) and schedules; its parts
run against the subject under the name `image` or `native` (`module-dag/image/wide with 2 at once`).

| Case | File | Asserts | Needs |
|---|---|---|---|
| `code-actions` | code_actions.cpp | a class's name, an expression and a deduced type each have their refactoring (mcpp-language-server #89) | |
| `compiler-extensions` | compiler_extensions.cpp | GNU attributes and Windows' structured exceptions complete only where the target has them, and what is inserted compiles | |
| `const-correctness` | build_tree_tools.cpp | the engine suggests const where clang-tidy does, and the fixes compile | `clang-tidy` |
| `frontend-completion-consumers` | build_tree_tools.cpp | the driver's and the C index's completion agree on a header's text and its PCH | `frontend-tools` |
| `gmf-include-analysis` | gmf_include_analysis.cpp | a header of the global module fragment is analysed whatever identity its path has (mcpp-language-server #86); the control ends on it where a file has two | `two-identities`, `control` for those parts |
| `module-cache-lease` | module_cache.cpp | BMI readers read owned generations under leases; portable copies are reclaimed | |
| `module-cache-lease-legacy` | module_cache.cpp | readers with a copy each: the cache before generations | `linux` |
| `module-cold-completion` | module_completion.cpp | the first completion of a session carries the module's names | |
| `module-cycle` | module_directives.cpp | a cyclic graph is refused and left behind by an edit; a diamond over the same names builds | |
| `module-dag` | module_dag.cpp | ten graph shapes build within the worker and dependency bounds | `matching-clang` |
| `module-directive-diagnostics` | module_directives.cpp | a missing separator is reported on the directive's own line | |
| `module-directive-recovery` | module_directives.cpp | six unfinished directives are recovered from | |
| `module-drafts` | completion_quality.cpp | members after an edit of the module in an open draft | |
| `module-lock-close` | module_directives.cpp | a document that waits on a live owner's lock can be closed | |
| `module-preamble-mode` | module_completion.cpp | the names follow the header's import, then the draft's | |
| `module-provider-cache` | module_scans.cpp | three files over one prebuilt module share one inventory | `matching-clang` |
| `module-quality` | completion_quality.cpp | members after `.`, a prefix and `->`, and after an edit of the module on disk | |
| `module-request-inputs` | module_cache.cpp | each draft's imports are the ones its answers come from | |
| `module-response-inputs` | module_completion.cpp | a response file's edit reaches the module the file imports | |
| `module-scan-builtins` | module_scans.cpp | a verified scan observes the compiler's actual builtins | `linux` |
| `module-scan-memo` | module_scans.cpp | a scan is kept until an input it read changes | `linux` |
| `module-worker-default` | module_workers.cpp | a worker is started and bounded, and a dependency file is left alone | `linux` |
| `module-worker-diagnostics` | module_workers.cpp | a worker's diagnostics are bounded and its parent goes on | `linux`, `native` |
| `module-worker-failure` | module_workers.cpp | a worker that fails under a small address space leaves its parent answering | `linux` |
| `module-worker-payloads` | module_workers.cpp | a worker whose output and capture are bounded at a megabyte | `linux` |
| `third-party-import` | third_party_import.cpp | an import that cannot be resolved leaves the resolvable modules, the preamble and a later provider working | |

`.github/workflows/engine-cts.yml` fails when this table and the program's cases differ.

## Writing a case

```cpp
import std;
import engine.harness;

using namespace mcpplibs::mtest;
using namespace engine;

namespace {

CTS cold{"module-cold-completion", [] { against_subject([] {
    "the first completion of a session carries the module's names"_test = [] {
        const fs::path project { work() };                      // the case's own directory
        write(project / "A.cppm", "export module A;\nexport int item;\n");
        ...
        write_database_for(project, { project / "A.cppm", source });
        Session session { .id = "cold", .project = project, .flags = { "--experimental-modules-support" } };
        session.sequence = json::array({ initialize(project), initialized(), did_open(source, text), ... });
        passed(replay(session), project);                       // fails with the detail and the log's end
    };
    "..."_test[cts::needs{"linux"}] = [] { ... };               // not run where the subject is not Linux
}); }};

}  // namespace
```

- A case is an object at namespace scope: it holds no allocation before `main` (a namespace-scope
  object that allocates crashes before `main` on macOS), and the body runs when the case is selected.
- A session's steps are JSON as an editor sends them, with what the harness adds: `expect` (JSON
  pointers into the answer), `expected_symbols` / `forbidden_symbols` of a completion, `defer` and
  `await`, `await-log`, `replace-file`, `sleep` (src/harness.cppm states each).
- A new file under `e2e/` is one more translation unit of the program (`[build] sources`); name the
  case in the table above.
