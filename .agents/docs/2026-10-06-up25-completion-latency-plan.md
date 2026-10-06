# UP-25 completion latency: root-cause layers and the fix plan (for review)

2026-10-06. Companion to [2026-10-06-clangd-fix-register-plan.md](2026-10-06-clangd-fix-register-plan.md)
§2.5 (measurements) and the PR1 plan §7. This document commits to actually
closing the remaining gap — "module-project completion at header-project
speed" — with a staged, verifiable engineering plan across clangd and clang.

## 1. Where the ~950 ms actually goes (measured)

qt-demo `main.cpp` (`import std; import nlohmann.json;`), steady state,
fork build with the validation memo (S1) landed, CLANGD_TRACE attribution:

| span | time | what it is |
|---|---|---|
| preamble-compat check (`canReuse`) | ~65 ms | memoized to a handful of stats (S1) |
| body parse | small | qt-demo body is ~200 lines |
| **BMI deserialization** | **~450–600 ms** | `std.pcm` (35 MB, ~18k symbols) + `nlohmann.json.pcm` loaded into a **fresh ASTContext** |
| **Sema completion collection** | **~300–930 ms** | `LookupVisibleDecls` walks the TU scope + module visibility → touches (and therefore deserializes) the imported decls en masse |

The independent fact that pins the diagnosis: a file **without imports** in
the same project answers in ~60 ms. The delta is exactly the per-parse module
work.

Why it repeats every keystroke: clangd answers completion by building a
**fresh CompilerInstance/ASTContext per request** (preamble PCM reused, but
prerequisite modules are re-attached via `-fmodule-file=` and re-deserialized).
Deserialized decls live in their ASTContext and cannot be handed to the next
request — the original S2 sketch ("LRU of loaded modules") is void. What
follows is the plan that does not depend on that impossible primitive.

## 2. The three fix layers

### S2-A (clangd only, days): standard-library-index fast path for identifier completion

**Fact:** clangd already builds a standard-library symbol index once per
preamble (`clangd/index/StdLib.cpp`; the trace shows `StandardLibraryIndex —
18031 symbols, 807 ms` **once**, not per request). The completion merge
already unions index results with Sema results — but clangd still pays full
Sema completion every time because the merge expects Sema to be authoritative.

**Patch shape (clangd, `CodeComplete.cpp`):** a fork-gated fast path — when

1. the completion point is a plain identifier position (not after `::`, `.`,
   `->`, `<`), and
2. the file's required modules are fully covered by the stdlib index (i.e.
   every imported module is the std module — detectable from
   `Preamble.RequiredModules`), and
3. the index has hits for the token prefix,

then skip the Sema completion entirely for that request and serve:
index symbols (std) + a cheap lexical scan of the open file's local scope +
macro table from the preamble. Anything else (member access, no index hits,
non-std modules) falls back to the full path unchanged.

**Why it is honest:** module-scope identifiers of `std` are exactly what the
index holds; visibility subtleties (using-decls, partitions) are approximated
by the index's symbol set. The fallback guarantees no regression beyond the
gated case. `mcppls` enables it only for detected forks (D4), vanilla keeps
today's behavior.

**Effort:** 2–5 days + probes. **Expected:** std-heavy files (qt-demo, most
`import std` projects) reach header-level latency on identifier completion
immediately; member completions keep today's cost until S2-B.

**Gate:** `bench` job — qt-demo warm identifier-completion p95 < 100 ms with
the fast path, < 950 ms fallback preserved when gated off.

### S2-B (clang core, 2–4 weeks): module completion tables in the BMI — the durable fix

**Root cause in clang's terms:** completion needs names and light descriptors,
but the only source of truth is the serialized decl. `LookupVisibleDecls`
visits every visible declaration context of the imported modules; each visit
deserializes the decl to print/reason about it. Lazy loading does not help
because completion's visibility walk touches all of it.

**What the BMI already has vs what it lacks:** `ASTWriter` already serializes
per-context **visible-decl name sets** (`WriteDeclContextVisibleUpdate`) —
names rehydrate without the decls. What it lacks is enough *descriptor* per
name to build a completion item. So completion today must materialize decls.

**Patch shape (clang Serialization + SemaCodeComplete):**

1. **Writer:** for each externally-visible decl in a module, emit a compact
   *completion-summary record*: identifier, kind (function/type/variable/
   namespace/...), printed type or signature **string** (computed once at
   write time), declaring module/part, access, and a deprecation flag — one
   pooled table per module, identifier-indexed (sorted, prefix-friendly).
2. **Reader:** load the table eagerly (it is small relative to decls — measured
   target: < 5% of the BMI), keep it beside the visible-sets; no decl
   deserialization for table consumers.
3. **SemaCodeComplete:** when completing at module scope with prebuilt module
   files, collect candidates from the tables first (prefix filter on the sorted
   table is O(log n + k)); deserialize full decls only for the ranked top-N
   items that are actually returned. Snippets/signatures come from the printed
   string; full decl load remains available for `resolveCompletionItem`.
4. **clangd:** no changes — it consumes Sema completion as today; the win is
   under the hood.

**Why this meets the acceptance point:** the constant BMI-deserialization term
disappears from the completion path (the table replaces the walk), so
module-project completion converges to header-project cost structurally, not
heuristically. It is also *the* upstreamable fix — faster module completion
benefits every clangd user, which is what makes the llvm-project PR credible.

**Effort:** 2–4 weeks focused senior-clang work (format record + writer pass +
reader API + SemaCodeComplete integration + lit tests under
`clang/test/Modules` + `clangd` e2e). Staged internally:

- **B1** (week 1): writer/reader record + reader-side API; lit tests for
  round-trip; measure table size on libstdc++ std module (target < 5%).
- **B2** (week 2): SemaCodeComplete table-first candidate collection behind
  `-fmodules-completion-tables` (default on for explicit `-fmodule-file=`
  modules); clangd runs untouched.
- **B3** (week 3–4): ranking/top-N lazy materialization, `resolveCompletionItem`
  wiring, benchmarks, upstream PR (llvm-project) with the measurements.

**Gate:** qt-demo warm completion p95 < 100 ms **through the full Sema path**
(no fast path), synthetic 20-module project p95 < 50 ms; `check-clangd` +
module lit suites green; a completion-quality diff harness (item sets before/
after on a corpus of prefixes) showing no missing symbols.

### S2-C (research, not scheduled): shared module AST cache

One process-wide cache of deserialized module ASTs reused across
CompilerInstances would fix every consumer at once, but it is a clang-architecture
project (context-independent decl representation does not exist; ownership,
invalidation, and thread-safety are all open). Recorded so nobody re-derives
it; revisit only if S2-B's table proves insufficient for member completion.

## 3. What this plan deliberately does NOT do

- No BMU/LRU of live ASTContexts (impossible, §1).
- No `-fmodules-embed-all` into the preamble PCM: it moves the same bytes into
  one file; total deserialization is unchanged (measured reasoning in §1).
  Re-evaluate only as a measurement step inside B1.
- No mcppls-side-only "fix" claimed as the acceptance: the client-side
  `isIncomplete=false` filtering (mcppls 0.0.12) amortizes keystrokes but the
  clangd-level gates above are the acceptance for the fork.

## 4. Sequencing and dependency

| step | depends on | lands where | review point |
|---|---|---|---|
| M0: profile one completion (perf/instrumented build): eager-vs-lazy split of the 600 ms; confirm LookupVisibleDecls share | none (local) | measurements appended here | numbers confirm §1 |
| S2-A fast path | M0 | mcppls-clangd (clangd patch 0006) | this review |
| S2-B1 tables in BMI | M0 | clang core (patch series in this repo) | this review |
| S2-B2 SemaCodeComplete integration | B1 | clang core | after B1 gates |
| S2-B3 quality diff + upstream PR | B2 | llvm-project | after B2 gates |
| mcppls 0.0.12 client filtering | none | mcppls | separate repo |

S2-A ships value immediately and is independent of S2-B; S2-B replaces it as
the default when it lands (fast path stays as a fallback toggle).

## 5. Risks

| risk | mitigation |
|---|---|
| completion-summary strings go stale vs lazy decl contents | strings are computed at module-build time from the same decls the BMI serializes; a module is immutable once built — staleness is impossible by construction; BMI identity is part of the S1 cache key anyway |
| table-first collection changes ranking | quality-diff harness in B3 gates the switch; flag to revert |
| fast path (S2-A) returns non-visible std symbols | gated to std-only module sets; fallback flag; upstream never sees it |
| libstdc++/MSVC STL BMI differences change table size share | B1 measures both (MSVC STL via the win job) before B2 |
