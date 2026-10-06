# UP-12/13/20 Windows crashes: from "no stack" to fixes (for review)

2026-10-06. Companion to the fix-register plan. These three rows are the
crash class mcppls keeps containing on the outside:

- **UP-12** — Build AST crash on a module unit with unresolved imports
  (crash input set aside in mcppls 0.0.5; avoided by `-c`).
- **UP-13** — Build AST crash on some units even with correct commands
  ("Windows release prints none" — no stack has ever been captured).
- **UP-20** — crash **loop** on a fan-out save of `mcpp.manifest.types`;
  mcppls 0.0.8 records carry LLVM's stack dump + clangd's SHA-256 (K-3), so a
  partial stack may already exist for this one.

This plan turns the fork's Windows builds from "packaging target" into the
crash-analysis instrument, then fixes each crash at its root and retires the
mcppls-side containment.

## 1. Why no stack exists today (three separate gaps)

1. **Symbols**: release binaries ship without debug info next to them, so even
   LLVM's own `PrintStackTrace` renders frames as addresses. → the
   `win-symbols` job already builds with PDBs; its artifact must become the
   analysis input.
2. **No capture on the user's machine**: an access violation in a worker thread
   kills the process silently; WER eats it unless LocalDumps is configured.
   → enable capture both in CI (debugger-driven) and in the field (fork crash
   handler, below).
3. **Crashes that only happen under mcppls' orchestration** (fan-out saves,
   module lock churn) never run in a bare `clangd --check` repro.
   → the corpus must replay **scenarios**, not just files (§2 C0).

## 2. Staged plan

### C0 — crash corpus (days, mcppls + this repo)

- Collect from mcppls's crash records (0.0.5 set aside a crash file; 0.0.8
  records carry SHA-256s): the failing inputs, their compile commands, and the
  mcppls scenario that triggered them (save fan-out for UP-20; unresolved
  import unit for UP-12).
- Land them as `tests/crash/windows/` with a manifest: input file(s), CDB,
  clangd flags, expected outcome on 23.1.0 (crash / hang / pass), register row.
  Corpus inputs containing third-party code get reduced to minimal
  reproducers as work proceeds (one reduction per row).

### C1 — capture (days, CI)

New job `win-crash-corpus` (windows-2022):

1. Build the fork with PDBs (reuse `win-symbols` cache keys; artifacts shared).
2. For each corpus entry, run clangd under **cdb** (ships with the Windows SDK
   already on the runner):
   `cdb -lines -g -G -c ".symfix; .reload; sxe -c \"~*kb 200; .ecxr; kb 300; q\" av;bpe; q" clangd.exe ...`
   — full symbolized stacks for AV/breakpoint/termination.
3. Additionally enable **WER LocalDumps** for `clangd.exe` (registry) and run
   the mcppls-orchestrated scenarios (save fan-out loop for UP-20 via the
   lsp_driver didChange loop) so dumps land for orchestration-only crashes.
4. Artifacts: stack logs + dmps, attached to the register rows; the run fails
   while any corpus entry still crashes (that failing state IS the row's
   status).

### C2 — the fork crash handler (1–2 days, carried patch 0006, Windows-only)

`PrintStackTrace` exists but shows nothing without symbols and catches only
LLVM's registered signals. Add an SEH-based last-chance handler around clangd's
main and the worker-thread entry: `__try/__except` → `MiniDumpWriteDump` into a
flag-gated directory (`--crash-dumps-dir=`, default off upstream-side; mcppls
enables it for its bundled builds) → process continues to terminate. Effects:

- every future field crash on Windows yields a .dmp analyzable with the public
  PDBs — UP-13's "prints none" blocker disappears **at the source**;
- it is additive, Windows-only, and off by default — upstreamable as a
  diagnostic feature (LLVM already has `-fcrash-diagnostics-dir` for compiler
  crashes; this extends the idea to the LSP server's hard crashes).

### C3 — root-cause and fix (per row, after C1 stacks)

Working hypotheses to confirm/refute with the first stacks:

| row | hypothesis | candidate fix |
|---|---|---|
| UP-12 | null deref downstream of a failed prerequisite build (unresolved import path returns `FailedPrerequisiteModules` and a consumer assumes success), or clang modules code hitting an unimplemented Windows path | guard + diagnostic at the clangd module-builder boundary (upstreamable), else clang fix per stack |
| UP-13 | same family as UP-12 with correct commands — points at clang core (serialization/Sema) on Windows; stack decides | clang fix per stack |
| UP-20 | **stack overflow** is the prime suspect: a crash *loop* on rapid saves of one generated file smells like recursive parse/instantiation blowing the worker stack, then mcppls restarting into the same file. Also verify content: `mcpp.manifest.types` fan-out may present pathological macro/initializer depth | (a) raise clangd worker-thread stack (Linux default 8 MB; verify what the Windows threads get and set 32–64 MB in the fork), (b) recursion guard if a specific recursion shows, (c) upstream the stack-size finding |

### C4 — acceptance and retirement

- `win-crash-corpus` green = every corpus entry survives (no crash, no hang)
  on the fork build; loop scenarios (UP-20) run 1000 iterations.
- mcppls retires the corresponding containment (`-c` avoidance for UP-12,
  backoff/bundle for UP-20) once the fix ships in a bundled fork; register
  rows close with the stacks, repros, and fixes linked.
- Every fix upstreamed (crashes in clang modules on Windows are upstream's
  bugs as much as ours); carried only until the upstream fix lands in a base
  we bump to.

## 3. Deliverables checklist

| artifact | lands in | review point |
|---|---|---|
| corpus + manifest | `tests/crash/windows/` | C0 |
| `win-crash-corpus` job (cdb + LocalDumps + scenario replay) | `.github/workflows/` | C1 |
| crash-dumps handler (`--crash-dumps-dir=`) | patch 0006 (overlay + win build) | C2 |
| worker stack size (measured, then set) | patch 0007 or build flags | C3 |
| per-row fixes | patches per stack | C3 |
| retire mcppls containments | mcppls repo | C4 |

## 4. Risks

| risk | mitigation |
|---|---|
| corpus unreproducible outside mcppls orchestration | C1 replays scenarios via lsp_driver, not bare files; LocalDumps catches what cdb misses |
| crash is timing-dependent (locks/threads) | soak-style repetition counts in the job; dmp + stack from cdb on the failing iteration |
| SEH handler masks LLVM's own diagnostics | handler runs last (LLVM signal path first), is flag-gated off upstream, and writes the dump before terminating |
| MSVC STL + ASan interaction on the corpus job | keep the corpus job on the PDB release build; ASan Windows variant only as a follow-up if stacks are insufficient |
