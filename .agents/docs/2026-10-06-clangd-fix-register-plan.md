# Fix register → mcppls-clangd patch plan (v1, for review)

2026-10-06. Companion to [2026-10-06-mcppls-clangd-plan.md](2026-10-06-mcppls-clangd-plan.md)
(the architecture). This document triages every clangd/LLVM row of the
upstream-defects register
([mcpp-language-server#24](https://github.com/Sunrisepeak/mcpp-language-server/issues/24))
into a patch plan, and designs UP-25 — the per-completion module reload — in
depth, because it is the payload of the fork (decision D7).

Rules inherited from the register: one patch ↔ one row; a patch carries a drop
condition; mcpp rows (UP-M*) and PRoot rows (UP-P*) are out of scope here.

## 1. Triage

Tiers: **C** = carry in the fork; **R** = research first (no patch until a
reduction/stack exists); **X** = not for the fork. Order within a tier is the
build order.

### Tier C1 — mechanical, Phase 0/1 (marked-region style, low rebase risk)

| Row | Problem | Patch plan |
|-----|---------|------------|
| UP-05 | MSVC STL aligned allocation rejected (`align_val_t` ambiguous) | **Phase 0 backport**, already fixed in 23.1.1 (llvm-project#218152). Zero design; proves the whole fetch→apply→build→package pipeline. |
| UP-01 | Module name ending in `.` hangs the preprocessor (crashes on Windows) | **Phase 0 backport** of the fix already on LLVM main (register notes "fixed on main? (deferred)" — the spike confirms what to cherry-pick). Sanitize the trailing dot where the module name is parsed. |
| UP-15 | Missing `;` after `import` reported on the next line | Diagnostic location fix: adjust the reported range to the import token. Small, local, testable in `check-clangd`. |
| UP-18 | A module lock left by a killed clangd is never released (Windows waits forever) | Startup sweep for stale locks (pid liveness / lock age), plus RAII on the lock acquisition path so a crash cannot strand the next session. mcppls currently clears locks itself (0.0.7) — the patch moves that into clangd where other consumers benefit; the mcppls workaround retires on adoption. |
| UP-24 | Copy-on-read BMI left behind when clangd dies before releasing it; the only GC waits 3 days and reads atime (unreliable on Windows; also removes published BMIs) | Three coordinated fixes in the module-cache path: RAII ownership of the copy-on-read temp so death releases it; GC stops trusting atime (size+mtime+content identity instead); GC scope excludes published BMIs. Mirrors C-7/C-8/C-13 from mcppls PR #39, moved inside clangd. Same file area as UP-25/UP-19 — build it in the same campaign. |

### Tier C2 — medium, Phase 1/2 (feasible from the outside; measure before and after)

| Row | Problem | Patch plan |
|-----|---------|------------|
| UP-04 | Finding a module's unit scans the whole database | Memoize module → unit/BMI resolution keyed by the same identity the UP-25 cache uses. This is **UP-25 S1** (§2) — do them as one piece of work, land it first. |
| UP-19 | One BMI directory per command, never removed | Bound the per-command BMI directories (keep newest N, prune rest) inside the module builder — the clangd-side twin of `mcppls cache --prune` (0.0.7). Same area as UP-24; same campaign. |
| UP-02 | Unresolved import can deadlock the unit's build | Guard the module-build wait path: bounded wait, failure reported as a diagnostic instead of a hang. Needs a failure-injection test to prove the deadlock is really broken. |
| UP-14 | Imports added in an unsaved buffer are not built until save | Feed the module builder the buffer's import set (it already reaches clangd through the preamble path) instead of reading the file from disk (UP-14's root). |
| UP-10 | `import std;` then an unprovided `export import` never finishes | Detect the unresolvable `export import` and fail the prerequisite build with a diagnostic; never-finish is the defect, not the failure. |
| UP-09 | No `textDocument/semanticTokens/range` | Implement the range request by slicing the existing full-file token stream at the LSP layer of clangd. Self-contained protocol gap; no modules involvement. |
| UP-22 | clang-tidy `misc-const-correctness` false positive on filter/drop_while/chunk_by/split views | Reduced case is ready (issue #37): fix the check's const propagation for view adaptors, in clang-tidy (shipped inside clangd). Independent of everything else. |

### Tier C3 — architectural, Phase 2/3 (the campaigns)

| Row | Problem | Patch plan |
|-----|---------|------------|
| **UP-25** | Every completion on a file that imports modules costs ~1 s even unchanged (module context re-loaded per request; 60 ms without imports) | **The core.** Full design in §2. |
| UP-23 | `--experimental-modules-support` rescans module dependencies on every completion (~3× slower on heavy headers) | Largely **absorbed by UP-25's cache** (the rescan is the same per-request module work). Re-measure after S1/S2; if a residual gap remains, gate the rescan on a real change to the module set. mcppls's WA-CLANGD-009 (off without modules) may still be right for vanilla clangd. |
| UP-08 | Background index does not build module imports (definitions indexed apart from their declarations) | Second campaign (with UP-17). Extend the background-index unit selection to enqueue module prerequisite builds; cf. clangd/clangd#2569. Larger because it touches the index scheduler, not just the module builder. |

### Tier R — research before any patch

| Row | Problem | What unblocks it |
|-----|---------|------------------|
| UP-03 | Modules a file needs are built one at a time | Parallel prerequisite build is the shape; but it multiplies the concurrency surface of the exact area UP-25 is rewriting. Deferred until UP-25 lands and is stable; then measure whether the ~1 s→cache-hit change makes parallelism unnecessary for mcppls's projects. |
| UP-06 / UP-07 / UP-21 | Scheduler pathologies: stops answering one file while answering others; stuck with no CPU after rapid edits; closed unit keeps a worker spinning | Highest-churn area in clangd; every patch here fights upstream rework. mcppls's StuckWatch/quarantine/K-restart containment works. Revisit in Phase 3 with fresh stacks; not worth rebase debt before then. |
| UP-17 | A function defined in an open unit is missing from the index | Not reduced yet. First task is the reduction (probe scripts can bisect); then it likely joins the UP-08 campaign. |
| UP-12 / UP-13 / UP-20 | Windows: Build AST crashes (with/without unresolved imports); crash loop on a fan-out save | Blocked on stacks. The fork's Windows build **from source with symbols** is the unblocker — capture the stack, file upstream, then decide whether a carry is needed. Until then mcppls's containment stands. |

### Tier X — not for the fork

| Row | Why not |
|-----|---------|
| UP-11 | Fixed in mcppls 0.0.5 itself (link-phase driver error handling). |
| UP-16 | C++26 contracts/reflection — upstream work in progress; carrying an implementation is a feature fork, which this repo is not. |
| UP-M1…M7 | mcpp defects; fixed/filed in mcpp. |
| UP-P1/P2 | openkal-linux/PRoot defects; fixed/handled in openkal-linux 0.15.1. A musl fully-static clangd (Phase 3, optional) reduces the PRoot surface but these rows stay openkal-linux's. |

### Verification map — what CI runs per row

Every carried patch declares its verification in the ledger; the CI jobs of
the plan document (§4.3) execute it. Rules: **functional rows carry a lit
regression inside the patch that fails without the fix and passes with it;
perf rows carry a bench metric with a gate; lifecycle/crash rows carry a soak
scenario.** "Fixed but unverifiable" does not merge. Tests are named by
behavior, never by row id — the ledger does the row ↔ test mapping.

Verification has two levels: the rows below are proven at **clangd level**
(targeted, fast, inside the patched tree); once a patch is `steady`, its
acceptance scenario is re-proven at **product level** by the `e2e` job — the
latest mcppls release with its payload re-packed around the fork's clangd,
driven black-box through the mcppls entry point over LSP. A fix is reliable
only when it survives the whole stack (budgets, workarounds, payload).

| rows | kind | verification artifact | CI job / gate |
|------|------|----------------------|---------------|
| UP-05, UP-01 | backport equivalence | upstream's own lit tests (already in the tree), run on the patched series | `build-test` green |
| UP-02, UP-10, UP-14, UP-15, UP-22, UP-09 | functional | one lit regression per patch (deadlock guard fires; unresolvable `export import` reports instead of hanging; unsaved-buffer import builds; `;` location; view const no-diagnostic; range request slices) | `build-test` targeted run |
| UP-18, UP-24, UP-19 | hygiene, lifecycle paths | lit for the deterministic paths + soak scenarios for what lit cannot reach: kill -9 mid-module-build, restart loops, temp-BMI litter, per-command dirs beyond bound | `build-test` + `soak` |
| UP-04, UP-23, UP-25 | perf | probe bench metrics: UP-25 qt-demo warm completion p95 < 100 ms; UP-04 module-resolution cost; UP-23 rescan counter; cold-path and no-import baselines must not regress beyond noise | `bench` nightly + tag |
| UP-12, UP-13, UP-20 | crash, stack hunt first | debug-symbols Windows build (upstream's own artifact paradigm) → capture stack → file upstream → then decide carry | `win-symbols` artifact channel |
| UP-03, UP-06, UP-07, UP-21, UP-17, UP-08 | research/architectural | verification designed with the patch, before it lands (these rows start at `draft` by definition) | per-patch, when promoted |
| all carried rows | product-level integration | black-box e2e: latest mcppls release, payload re-packed with the fork's clangd, per-fix acceptance scenarios + stability loop (open/edit/close/restart, kill -9, `mcppls report` shows fork detection) driven through the mcppls entry point | `e2e` for `steady` patches |

## 2. UP-25: the core fix

### 2.1 Symptom and measurement

qt-demo (23 module files): every completion on a file that imports modules
costs ~1 s, unchanged or not; a file without imports in the same project
answers in ~60 ms. Probes (`/tmp/lsp_probe_*.py`) attribute the second to the
per-request module-context build; mcppls's WA-CLANGD-012 (0.0.11, PR #41) only
stretches the request budget adaptively — it does not remove the second.

### 2.2 Root cause

clangd builds the prerequisite modules for a file per request: for each
`import`, locate the module's unit and load its BMI. BMIs have an OS-level
persistent cache, but *loading* has none at clangd level — and because imports
live in the file body (not the preamble), nothing upstream reuses the loaded
context across completions. ~40 ms × 23 imports ≈ the observed second.

### 2.3 Fix shape: `CachedModulesBuilder` (composition wrapper — D5)

New files under `overlay/clangd/`, wrapping the existing modules builder at
its single construction/call site (clangd 23.x:
`clang-tools-extra/clangd/ModulesBuilder.{h,cpp}`; insertion point = where the
builder is constructed and where `buildPrerequisiteModulesFor` is invoked).
No deep inlining: the wrapper intercepts, the existing builder does the work
on a miss.

**Cache key** (per import): `(BMI path, size, mtime)` + the module unit's
compile-command fingerprint. One key covers all three invalidation causes:

- mcpp (or any build system) rebuilt the BMI → file identity changes → miss;
- the module unit's compile command changed → fingerprint miss;
- clangd itself rebuilt the BMI → identity changes on the next stat → miss.

**Value**: the loaded module context (the deserialized module objects the
builder hands to the parse). A hit skips locate + deserialize entirely — the
second becomes a lookup.

**Bounds and concurrency**: LRU with a module-count quota (default 64,
clangd flag), coarse mutex — loads are ~40 ms, contention is not the problem.
Mirrors mcppls 0.0.10's own module-cache philosophy: bounded, visible,
sweepable; `mcppls report` gains a line for fork-carried caches.

**Staging**:

- **S1 — resolution memoization** (days): cache module → unit/BMI resolution
  and freshness verdict only; deserialization still happens per request.
  Kills the UP-04-class scans, partial latency win, and is independently
  upstreamable (it may be acceptable upstream on its own — file it).
- **S2 — loaded-module LRU** (2–4 weeks focused): hold the deserialized
  context per §2.3. This is the 1 s → tens-of-ms step.

### 2.4 Acceptance (existing harnesses, promoted to CI gates)

1. Probe bench in CI (`bench` job): the validation memo must show zero
   regressions on the synthetic module project (warm p95 within noise of
   vanilla) and the in-patch lit test must hit the cache; the qt-demo warm
   p95 < 100 ms figure is the **S2 target**, not the S1 gate — §2.5's
   measurement attributes ~900 ms of the round trip to per-parse BMI
   deserialization, which S1 does not touch.
2. `check-clangd` modules + preamble + completion suites green on the patched
   tree (`build-test` job; correctness: a hit must be equivalent to a rebuild
   — the key decides, not the cache).
3. mcppls conformance fixtures green against the forked binary (`conformance`
   job).
4. Invalidation proven by test: edit a module unit → next completion on an
   importer reflects the edit (no stale BMI), with the cache warm — lit where
   deterministic, plus a `soak` scenario (rapid module edits, restarts) since
   the lifecycle is where a wrong key would hide.
5. Product level (`e2e` job, once `steady`): the same completion p95 measured
   through the mcppls entry point on the latest release re-packed with the
   fork's clangd — proving the fix end-to-end, with WA-CLANGD-012 re-tuned
   for detected forks rather than fighting the cache.

### 2.5 Measurement update (2026-10-06, qt-demo, patched build vs clangd 23.1.0)

The first carried implementation (the validation memo) was measured against
the real qt-demo scenario (imports `std` + `nlohmann.json`, heavy headers),
with chrome-trace attribution (`CLANGD_TRACE`) — the numbers below replace
the plan's earlier estimates:

- vanilla 23.1.0: completion p50 ≈ 1003–1032 ms (reproduces the register
  row); patched: the memo hits on every round and the validation share
  (≈ 60–100 ms) leaves the profile.
- trace anatomy of a steady-state completion (total ≈ 950 ms, user-perceived):
  - ≈ 450 ms — the completion's own parse loads `std.pcm` +
    `nlohmann.json.pcm` into the fresh AST (`-fmodule-file` prebuilts);
  - ≈ 930 ms — `Sema completion`: the completion collector materializes the
    imported modules' visible decls (the "591 results from Sema");
  - ≈ 65 ms — preamble-compatibility check, of which the memoized validation
    is now a handful of stats (this is what S1 removed; vanilla pays more);
  - the parse and the collector are the *same* CompilerInstance; the trace
    shows them as one BuildAST span.
- clangd has no speculative-reuse for sema completion results (the
  "speculative" machinery upstream only covers the index fuzzyFind), so every
  completion re-parses and re-deserializes.

What this means:

1. **S1 is landed and worth carrying** (upstreamable; lit test pins it), but
   it is the small share.
2. **S2's original sketch ("hold deserialized module objects in an LRU") is
   void**: deserialized declarations are ASTContext-bound. The honest S2 is a
   clang-core problem — candidates: amortize the two loads by completing
   inside the diagnostic AST build; a shared deserialization cache in
   ASTReader; `-fmodules-embed`-style PCH embedding for preamble-carried
   imports. None is a patch-sized change; S2 stays `draft`, estimate
   withdrawn.
3. **The near-term parity lever lives at the client**: clangd answers with
   `isIncomplete=false`, so mcppls's editor layer can filter locally as the
   user types and re-query only on real changes (mcppls 0.0.12's completion
   plan) — the 950 ms is then paid once per completion *context*, not once
   per keystroke, which is how header-only projects already feel.

The bench scripts (`tests/probes/`) and the qt probe numbers are committed so
the next iteration re-measures against the same baseline.

The bench scripts (`tests/probes/`) and the qt probe numbers are committed so
the next iteration re-measures against the same baseline.

### 2.6 Retirement path

Fork release `23.1.0-mcppls.N` carries S1; mcppls re-tunes (not skips)
WA-CLANGD-012 for detected forks since ~100 ms of the round trip is gone.
S1 is simultaneously upstreamed (llvm-project PR; the module-perf area has
active reviewers) — when it lands, the patch drops per its drop condition and
the base bumps. S2 remains carried here only if a proven design emerges; its
register row stays open either way until completion latency on module-heavy
files is actually fixed.

## 3. Campaign summary

| Campaign | Rows | Area |
|----------|------|------|
| Phase 0/1 — mechanical | UP-05, UP-01 (backports) → UP-15, UP-18, UP-24, UP-19 | diagnostics + module-cache hygiene |
| Phase 2 — the core | UP-25 (S1→S2), absorbing UP-04 and likely UP-23 | modules builder |
| Phase 3 — second campaign | UP-08, UP-17 (index), then scheduler rows UP-03/06/07/21 if still needed | index + scheduler |
| Parallel, always | file every unfiled row (D6); Windows stacks via fork builds (UP-12/13/20) | upstream |
