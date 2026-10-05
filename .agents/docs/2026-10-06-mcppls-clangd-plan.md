# mcppls-clangd: overall plan and architecture (v1, for review)

2026-10-06. First PR. Everything here is a proposal to review — nothing is
built yet.

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
| D3 | **Static per-platform binaries**; v1: glibc dynamic + `-static-libstdc++` on linux, default linking on darwin, llvm-mingw `-static` on windows | Fully-static glibc is not worth it (NSS/locale). musl fully-static is an optional later phase (Termux-native, less PRoot) — not a v1 prerequisite. |
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
  overlay/                NEW files, dropped into the tree after apply, zero conflicts
    clangd/...            e.g. CachedModulesBuilder.{h,cpp} for UP-25
  patches/
    0001-UP-18-release-module-locks-left-by-a-killed-clangd.patch
    ...
    series                ordered list, one line per patch
    PATCHES.md            one sentence per patch: register row, upstream link,
                          drop condition (openkal's PATCHES.md discipline)
  ci/                     scripts: fetch / apply / configure / build / package
  .agents/docs/           plans and reviews (this document)
```

- `UPSTREAM` pins `llvmorg-23.1.0` initially — the exact revision mcppls's
  `payload.lock.json` already trusts (`clangd-version: 23.1.0`).
- The llvm-project tree is never committed. CI fetches the pinned ref (release
  source tarball, ~130 MB, digest-recorded, or a shallow fetch of the tag),
  applies `patches/` with `git am` (authorship preserved), copies `overlay/`
  in, configures, builds the `clangd` target, strips, packages
  `clangd-<version>-<platform>` + `SHA256SUMS`.

The patch format is a plain `git format-patch` series. Nothing here invents a
patch tool: `git am`, `quilt`-style `series`, and a markdown ledger are enough.

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

Static linking per platform (D3):

| platform | v1 linking | notes |
|----------|-----------|-------|
| linux-x64 | glibc dynamic + `-static-libstdc++ -static-libgcc` | same shape as clangd/clangd's binaries; runs anywhere with glibc ≥ build host |
| linux-arm64 | same as linux-x64 | native arm64 runners are free for public repos |
| darwin-arm64 | default system linking | full static is not possible against darwin system libs |
| win32-x64 | llvm-mingw, `-static` | self-contained exe; the toolchain mcppls already uses for its win payload |

### 4.2 CI economics

The platform matrix is exactly `payload.lock.json`'s four platforms. First full
build is 1–3 h per platform (linking clangd wants ~10 GB RAM); ccache keyed on
the `UPSTREAM` ref makes every patch-only iteration minutes — only clangd and
patched objects rebuild. This one number decides the whole plan's cost, which
is why **Phase 0 measures it before anything else** (§7).

Release cadence: driven by mcppls needs, not by LLVM. ~2 LLVM releases/year is
the rebase ceiling; between bumps, releases are patch-driven and cheap
(warm ccache).

### 4.3 Gates

A fork release requires, per platform:

1. `patches/` applies cleanly on the pinned ref; `PATCHES.md` and the register
   agree one-to-one.
2. `check-clangd` passes — at minimum the modules, preamble and completion
   suites; full suite where the platform allows.
3. The mcppls conformance fixtures + probe benches run against the built
   binary (the `/tmp/lsp_probe_*.py` harnesses graduate into committed bench
   scripts; the UP-25 gate is qt-demo warm completion p95 < 100 ms).
4. Artifact digests land in the release; `packaging/payload.lock.json` pins
   them exactly the way it pins clangd/clangd binaries today.

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
- Rebase drill (per LLVM bump): bump `UPSTREAM` → `git am`, triage conflicts →
  warm-ccache rebuild → gates → release. With ≤ 8 patches this is a 1–2 day
  drill; the risk concentrates in the modules area (§8).
- Windows crash rows (UP-12/13/20) are blocked upstream on missing stacks.
  The fork's Windows build *from source with symbols* is the tool that will
  produce those stacks — the fork unblocks its own future rows here.

## 7. Roadmap

| Phase | Content | Exit gate | Size |
|-------|---------|-----------|------|
| 0 — spike | linux-x64 only: unpatched build of `llvmorg-23.1.0` in CI with ccache; backport UP-05 (llvm-project#218152) and UP-01's main fix as the first two patches; verify version suffix | first build ≤ 3 h; patch-only warm rebuild ≤ 15 min; `check-clangd` green; `--version` shows `-mcppls.N`; both backports ship as `23.1.0-mcppls.1` | ~1 week |
| 1 — mechanical carry | UP-18, UP-24, UP-15 (+ UP-01 if main's fix needs adapting); wire fork artifacts into `payload.lock.json` for linux-x64; expand matrix to the other three platforms | fork bundled in an mcppls release for all four platforms; register rows updated | 1–2 weeks |
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
| CI minutes (macOS ×10, Windows ×2 multipliers) | Phase 0 measures linux-x64 first; ccache makes releases warm; the matrix expands only after the spike proves the numbers. |
| Single-maintainer bus factor on a clangd internals fork | D6 upstream-first: everything worth keeping gets filed; `PATCHES.md` keeps the series legible to a newcomer; the register maps every row to a plan. |
| The fork quietly becomes a feature fork | D7/D6: no patch without a register row; scope is fixes for defects mcppls hit, not clangd features. |

## 9. License

LLVM's Apache License v2.0 with LLVM Exceptions, carried verbatim as
`LICENSE`. Patches are part of this repository under the same terms; upstream
attribution travels in the `git am` metadata.
