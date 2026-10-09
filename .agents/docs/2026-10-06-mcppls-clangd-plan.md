# mcppls-clangd: overall plan and architecture (v1, for review)

> 2026-10-07 review update: the [joint 0.0.12 release contract](2026-10-07-joint-0.0.12-release-plan.md) supersedes this draft's release sequencing and unproven cache/performance assumptions. Current patches are not release-ready. Correctness, root-cause evidence and four-platform product acceptance are mandatory; general mcppls containment is retained.

2026-10-06. First PR. Everything here is a proposal to review — nothing is
built yet.

Review round 1 (2026-10-06): D1/D2/D4 accepted as proposed. D3 re-aligned —
v1 replicates the clangd/clangd release build paradigm instead of a custom
static-linking matrix (facts from their public release workflow, §4.1).
Repository layout reworked so the path fix → verify → stabilize → upstream is
first-class (§3), and CI verification per carried fix specified (§4.3, and the
verification map in the fix-register document).

Inputs: the upstream-defects register
([mcpp-language-server#24](https://github.com/Sunrisepeak/mcpp-language-server/issues/24)),
the working discussions of 2026-10-06, and two precedents:
[openkal-llvm-runtime](https://github.com/mcpplibs/openkal-llvm-runtime)
(pinned upstream, marked one-sentence changes, enumerated in a PATCHES file)
and JetBrains' patched clangd builds shipped with CLion (the existence proof
that a carried patch set over clangd is maintainable and shippable).

Companion document: [2026-10-06-clangd-fix-register-plan.md](2026-10-06-clangd-fix-register-plan.md)
— every register row triaged into a patch plan; UP-25 (the ~1 s per-completion
module reload) designed in depth. That document is the *what*; this one is the
*how and where*.

## 1. Why this repository exists

mcppls bundles clangd 23.1.0 and works around its defects from the outside
(`WA-CLANGD-*` in `src/engine/clangd/workarounds.cpp`, listed by
`mcppls report`). That ceiling is reached:

- The worst defects are architecture, not surface. UP-25 re-loads the module
  context on every completion (~1 s on qt-demo's 23 module files vs 60 ms for
  a file without imports). UP-03 builds modules one at a time. UP-08's
  background index never builds module imports. No budget tuning outside
  clangd removes these.
- Most register rows are unfiled upstream; upstream latency is unbounded while
  mcppls releases are weekly-ish.
- Backports exist (UP-01 fixed on LLVM main, UP-05 fixed in 23.1.1) but mcppls
  cannot take them until the next clangd/clangd release.

Conclusion: maintain a patched clangd as its own small repository, release
per-platform binaries, and feed them into mcppls's existing payload machinery
(`packaging/payload.lock.json`, digest-pinned).

## 2. Decisions

Final for v1; each is one sentence plus its why.

| # | Decision | Why |
|---|----------|-----|
| D1 | **Not "based on openkal"** — no runtime integration; upstream CMake unmodified | clangd is a standalone LSP process; it has no ABI coupling with openkal programs. Integrating openkal-musl adds a cross-compile matrix and a bootstrap cycle for zero functional gain. |
| D2 | **Patch series + overlay on a pinned upstream ref** — no git fork of the monorepo, no vendored sources | clangd cannot compile without the clang+LLVM tree, but the repository does not have to *contain* it: fetched at build time against the pin in `UPSTREAM`. Repo stays at KB scale; the divergence stays small and enumerable. |
| D3 | **Build paradigm aligned with upstream clangd binaries** — replicate the clangd/clangd release recipe per platform (extracted from their public release workflow into `ci/recipe.md`, §4.1) | Fork artifacts become drop-in replacements for the binaries mcppls already bundles: same toolchain family, same linking model, same compat floor. No custom static-linking experiments in v1. musl fully-static stays an optional later phase (Termux-native, less PRoot) — not a v1 prerequisite. |
| D4 | **Fork builds identify themselves**: `LLVM_VERSION_SUFFIX=-mcppls.N` | `clangd --version` is the detection contract for mcppls: bundled fork vs user-provided vanilla clangd must be distinguishable, and `mcppls report` must be able to list carried patches. |
| D5 | **Composition-first patches**: logic in new files under `overlay/`, diffs to upstream files minimized to insertion points | The module area (where most of our defects live) is under active upstream rework; minimal insertion points are what survives a rebase. openkal's discipline — every change fits one sentence — applied to patch form. |
| D6 | **Upstream-first**: file every row that is unfiled; every patch carries a drop condition | The register is the single source of truth; the fork is a staging ground for upstream PRs, not a rival. UP-05 was fixed upstream within weeks of being noticed — filing shrinks the patch series over time. |
| D7 | **UP-25 is the payload of this fork** | Without committing to the UP-25 fix (see the fix-register document, §UP-25) the fork is infrastructure without cargo, and staying on workarounds + upstreaming is the better trade. The spike exists to confirm the pipeline cheaply; the UP-25 decision follows it. |

## 3. Repository model

```
mcppls-clangd/
  README.md               what this repo is; status; license
  LICENSE                 LLVM's Apache-2.0 WITH LLVM-exceptions text
  UPSTREAM                the pin: repo, ref, reason (one file, three lines)
  patches/
    series                ordered list, one path per line
    0001-...patch         each patch = fix + its tests + LLVM-style commit message
    PATCHES.md            ledger: register row ↔ patch ↔ tests ↔ state ↔ drop condition
  overlay/
    clangd/               NEW files only (drop-in after apply, zero conflicts)
                          + their unit tests; never submitted upstream as-is
  upstream/
    drafts/               per-row submission packages: PR description, links,
                          review status — the material a "steady" patch needs
  ci/
    recipe.md             the clangd/clangd release recipe, extracted per platform
    scripts/              fetch.sh apply.sh configure.sh build.sh package.sh —
                          one composable stage each, no monolith
  tests/
    probes/               bench scripts (completion p95, rescan counters) + README
    e2e/                  black-box scenarios driven through mcppls's entry point
    conformance.md        how the mcppls fixtures are fetched (pinned ref) and run
  .github/workflows/      verify-series, build-test, bench, soak, upstream-drift,
                          win-symbols, release (§4.3)
  .agents/docs/           plans and reviews (this document)
```

- `UPSTREAM` pins `llvmorg-23.1.0` initially — the exact revision mcppls's
  `payload.lock.json` already trusts (`clangd-version: 23.1.0`).
- The llvm-project tree is never committed. CI fetches the pinned ref (release
  source tarball, ~130 MB, digest-recorded, or a shallow fetch of the tag),
  applies `patches/` with `git am` (authorship preserved), copies `overlay/`
  in, configures, builds the `clangd` target, strips, packages
  `clangd-<version>-<platform>` + `SHA256SUMS`.

Layout principles — the tree is arranged so that **fix → verify → stabilize →
upstream** is the normal path, not an afterthought:

1. **A patch is the unit of upstreaming.** Every patch is one self-contained
   commit: the fix, its tests, and a commit message written in LLVM style
   (`[clangd] ...`). `git format-patch -1 <steady-patch>` plus its
   `upstream/drafts/` entry is a ready llvm-project PR. Register row ids never
   appear inside patch code or tests (upstream reviewers must not meet our
   bookkeeping); the ledger is the only place row ↔ patch ↔ test are mapped.
2. **Fork-only glue lives only in `overlay/`.** Wrapper files (e.g.
   `CachedModulesBuilder`) that exist for mcppls and are not upstream
   candidates are isolated there; carry patches never mix fork-only edits in.
3. **`patches/PATCHES.md` is the single source of truth.** One line per patch:
   register row, state (§6), test map, upstream link, drop condition.
   `ci/check-ledger` (part of `verify-series`) enforces the shape, the same
   way mcppls's devtools `check` commands do.
4. **Verification is declared next to the fix.** Each ledger entry names its
   tests and its bench metric up front (verification map in the fix-register
   document); CI only executes what the ledger declares.

## 4. Build, CI, release

### 4.1 Configure/build (upstream CMake, unmodified — D1)

```
-DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra"
-DLLVM_TARGETS_TO_BUILD="host;X86;AArch64"     # target infos needed to parse cross triples; add on demand
-DLLVM_ENABLE_PLUGINS=OFF                       # clangd loads no plugins
-DLLVM_CCACHE_BUILD=ON  -DLLVM_CCACHE_DIR=...   # the key CI lever
-DLLVM_VERSION_SUFFIX=-mcppls.N                 # D4; verify --version output in Phase 0
-DLLVM_INCLUDE_TESTS=ON                         # check-clangd is a gate (CI builds only)
-Ninja  -DCMAKE_BUILD_TYPE=Release
```

Build recipe per platform (D3) — **replicated from clangd/clangd's public
release workflow** (`.github/workflows/autobuild.yaml` in the clangd/clangd
repository, inspected 2026-10-06); the extracted per-platform flags land in
`ci/recipe.md` as a Phase 0 deliverable rather than being hard-coded here:

| platform | upstream's recipe (what we replicate) |
|----------|---------------------------------------|
| linux | built inside an `ubuntu:20.04` container — the old-glibc compat floor is the container, not flags; `-DCMAKE_EXE_LINKER_FLAGS_RELEASE="-static-libgcc -Wl,--compress-debug-sections=zlib"`; `linux-static-deps.cmake` forces `find_package` onto static libs (`.a`, e.g. zlib) |
| darwin-arm64 | `macos-14`, default system linking, nothing special |
| win32-x64 | `windows-2022` + MSVC (`vcvars`), `-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded` (static CRT); **a separate `clangd-debug-symbols` artifact ships the PDBs** — which is also the tool for the UP-12/13/20 stack hunt |

Deviations we intend (recorded, not silent): gRPC/remote-index stays off
(clangd/clangd vendors gRPC for remote index; mcppls does not use it — one
less dependency to bootstrap); only the `clangd` binary is packaged, not the
indexing tools. Where clangd/clangd ships no binary (linux-arm64), the linux
recipe runs on a native arm64 `ubuntu:20.04` host.

### 4.2 CI economics

The platform matrix is exactly `payload.lock.json`'s four platforms. First full
build is 1–3 h per platform (linking clangd wants ~10 GB RAM); ccache keyed on
the `UPSTREAM` ref makes every patch-only iteration minutes — only clangd and
patched objects rebuild. This one number decides the whole plan's cost, which
is why **Phase 0 measures it before anything else** (§7).

CI minutes are kept sane by tiering (§4.3): per-push jobs run linux-x64 only;
the full matrix runs nightly and on release tags. Release cadence: driven by
mcppls needs, not by LLVM. ~2 LLVM releases/year is the rebase ceiling; between
bumps, releases are patch-driven and cheap (warm ccache).

### 4.3 CI verification

Nine jobs; the ledger (`patches/PATCHES.md`) declares what each patch
contributes to which job, and `bench`/`soak`/`e2e` consume the verification
map in the fix-register document. The CI has two levels on purpose:
clangd-level jobs prove the fix in the patched tree; the `e2e` job proves the
fork inside the shipped product.

| job | trigger | what it does | fails when |
|-----|---------|--------------|------------|
| `verify-series` | every push | apply the series on the pinned ref; check the ledger's shape: every patch has a row, a test map, a state, a drop condition; row ids absent from patch contents | apply conflict, or a patch without declared verification |
| `build-test` | every push (linux-x64); nightly + tag (full matrix) | build the `clangd` target with ccache; run the **targeted tests of every touched patch** first (fast feedback from its test map), then `check-clangd` — full suite on linux, modules/preamble/completion suites minimum elsewhere | any test fails |
| `bench` | nightly + tag | probe benches against the built binary; per-row metrics from the verification map (e.g. UP-25: qt-demo warm completion p95 < 100 ms; UP-04/23: resolution/rescan counters; cold-path no-regression baseline) | a metric crosses its gate |
| `conformance` | nightly + tag | fetch mcppls **source** at a pinned ref; run its conformance fixtures and engine tests against the forked binary — the regression net during development | a fixture fails |
| `e2e` | nightly + tag | **black-box through the mcppls entry point**: take the latest mcppls release, re-pack its payload with the fork's clangd via mcppls's own `payload` tooling (digest pinning stays intact — the kit is rebuilt, not tampered), then drive the shipped configuration over LSP: module projects, completions, diagnostics, edit/close/restart loops, `mcppls report` showing fork detection and carried patches. Each `steady` patch's acceptance scenario runs here against the real product — a fix is reliable only if it survives the whole stack (budgets, workarounds, payload) | a scenario fails, or a crash/hang in the loop |
| `soak` | nightly | sanitizer build (linux-x64, ASan+UBSan) plus a scripted hours-long session loop — open/edit/close module files, rapid edits, kill -9 mid-build, restart (the UP-18/24 lifecycle, the UP-07 class) | crash, hang, leak, or sanitizer report |
| `upstream-drift` | weekly | apply every patch onto **llvm-project main tip**; publish the applies-clean matrix as a status comment on the ledger | advisory — never red by itself; a patch drifting > 2 weeks opens an issue (§6) |
| `win-symbols` | weekly + on demand | the Windows build with debug symbols per the upstream recipe; the stack-capture channel for UP-12/13/20 | n/a (artifact channel) |
| `release` | tag | full matrix, gates 1–5 green, package + `SHA256SUMS`, feeds `payload.lock.json` | any gate |

Two verification policies bind all jobs:

1. **Every carried fix proves itself in CI.** A patch lands only with the
   verification its row's kind demands — a lit regression that fails without
   it for functional rows, a bench metric for perf rows, a soak scenario for
   lifecycle/crash rows (the full mapping per row is the verification map in
   the fix-register document). "Fixed but unverifiable" does not merge.
2. **Tests are named by behavior, not by row** (`modules/lock-cleanup.test`,
   never `up-18.test`) — patches must read as upstream contributions, and the
   ledger does the row ↔ test mapping (layout principle 1).

## 5. mcppls integration

- **Detection**: mcppls runs `clangd --version`; a `-mcppls.N` suffix means
  forked. Vanilla clangd keeps every current workaround and budget.
- **Workaround retirement**: with the fork, `WA-CLANGD-012` (UP-25's adaptive
  budget) is skipped or re-tuned; each carried patch names the WA-* entries it
  retires, so `mcppls report` shows the true state either way.
- **Fallback stays intact**: user-provided vanilla clangd remains a supported
  configuration; nothing in mcppls requires the fork to run.
- **Payload**: `payload.lock.json` gains fork artifacts as the `clangd` entry
  per platform, replacing clangd/clangd downloads one platform at a time as
  the matrix fills.

## 6. Patch lifecycle

- One patch ↔ one register row. A patch without a row, or a row closed while
  its patch is still carried, fails review.
- Each patch in `PATCHES.md`: what it fixes (row), where the analysis lives,
  the upstream issue/PR link once filed, and the **drop condition** — usually
  "upstream lands an equivalent; then bump the base and drop this".
- **States**, carried in the ledger and enforced by `verify-series`:

  `draft` → `stabilizing` → `steady` → `upstream-submitted` → `landed (dropped)`

  A patch enters `stabilizing` when its verification map is complete and
  green; it becomes `steady` after 7 consecutive green nightly `soak` + `bench`
  runs (N = 7 to start). Only `steady` patches ride a release.
  `upstream-submitted` means the `upstream/drafts/` package is filed upstream;
  the patch stays carried until the upstream fix ships in a release we bump
  to — then it drops per its drop condition.
- **Stabilization is a schedule, not a mood.** The soak/sanitizer and bench
  jobs run nightly, so a patch sits in `stabilizing` for at least a week by
  construction; whatever it breaks surfaces there, not in an mcppls release.
- **Upstream extraction**: for a `steady` patch, `git format-patch -1` — the
  commit already carries its tests and its LLVM-style message — plus the
  `upstream/drafts/<row>.md` package, submitted to llvm-project. The weekly
  `upstream-drift` job keeps every patch main-compatible in the meantime, so
  submission never waits for a rebase.
- Rebase drill (per LLVM bump): bump `UPSTREAM` → `git am`, triage conflicts →
  warm-ccache rebuild → gates → release. With ≤ 8 patches this is a 1–2 day
  drill; the risk concentrates in the modules area (§8). Drift monitoring
  makes the drill boring on purpose: conflicts are known weeks in advance.
- Windows crash rows (UP-12/13/20) are blocked upstream on missing stacks.
  The fork's Windows build *with debug symbols* (the `win-symbols` job — the
  same artifact channel upstream's own releases use) is the tool that will
  produce those stacks — the fork unblocks its own future rows here.

## 7. Roadmap

| Phase | Content | Exit gate | Size |
|-------|---------|-----------|------|
| 0 — spike | linux-x64 only: unpatched build of `llvmorg-23.1.0` in CI with ccache; extract the clangd/clangd release recipe into `ci/recipe.md` (windows/mac/linux facts, §4.1); `verify-series` + `build-test` jobs live from day one; backport UP-05 (llvm-project#218152) and UP-01's main fix as the first two patches; verify version suffix | first build ≤ 3 h; patch-only warm rebuild ≤ 15 min; `check-clangd` green; `--version` shows `-mcppls.N`; recipe recorded; both backports ship as `23.1.0-mcppls.1` | ~1 week |
| 1 — mechanical carry | UP-18, UP-24, UP-15 (+ UP-01 if main's fix needs adapting); `bench`/`conformance`/`soak`/`upstream-drift` jobs come online; wire fork artifacts into `payload.lock.json` for linux-x64; expand matrix to the other three platforms | fork bundled in an mcppls release for all four platforms; first patches reach `steady`; `upstream/drafts/` filed for the backports; register rows updated | 1–2 weeks |
| 2 — the core | UP-25 per the fix-register design: S1 resolution memoization (days), S2 loaded-module LRU cache (2–4 weeks focused); retire/stretch WA-CLANGD-012 | qt-demo warm completion p95 < 100 ms with the gate in CI; UP-25 upstreamed (best effort) | 2–4 weeks |
| 3 — optional | musl fully-static builds (Termux-native, less PRoot); scheduler rows (UP-03/06/07/21) revisited; indexing (UP-08/17) as the second campaign | open | open |

Decision point: **after Phase 0**. The spike validates the build economics and
delivers two free backports; committing to Phase 2's engineering (D7) is a
separate, explicit decision after seeing the numbers.

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Upstream rewrites the modules area (ModulesBuilder churn) and the UP-25 patch keeps breaking | D5 composition-first: the cache is a wrapper with one insertion point; the S1/S2 staging keeps the carried diff small; drop conditions keep us honest about what upstream already fixed. |
| Cached module objects grow memory in long sessions | LRU bound (module count quota), mirroring mcppls 0.0.10's own cache philosophy: bounded, visible, sweepable; the bound is a clangd flag so vanilla semantics remain reachable. |
| Two clangd variants in the wild confuse support | D4 version suffix + `mcppls report` lists carried patches; user-provided vanilla clangd stays a first-class path. |
| CI minutes (macOS ×10, Windows ×2 multipliers) | Per-push jobs are linux-x64 only; the full matrix runs nightly and on release tags (§4.3); ccache makes releases warm; the matrix expands only after the spike proves the numbers. |
| A carried patch drifts from LLVM main until a rebase becomes painful | The weekly `upstream-drift` job applies every patch to main tip and publishes the applies-clean matrix; drift beyond two weeks opens an issue — the bump drill is never a surprise. |
| Single-maintainer bus factor on a clangd internals fork | D6 upstream-first: everything worth keeping gets filed; `PATCHES.md` keeps the series legible to a newcomer; the register maps every row to a plan. |
| The fork quietly becomes a feature fork | D7/D6: no patch without a register row; scope is fixes for defects mcppls hit, not clangd features. |

## 9. License

LLVM's Apache License v2.0 with LLVM Exceptions, carried verbatim as
`LICENSE`. Patches are part of this repository under the same terms; upstream
attribution travels in the `git am` metadata.
