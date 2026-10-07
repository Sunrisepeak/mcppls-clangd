# Missing BMI directive recovery (patch 0024)

## Root cause and attribution

The normalized historical GalTranslPP input retains its six explicit
`-fmodule-file=NAME=absent-bmis/NAME.pcm` hints and real on-disk compilation
database. Removing those hints previously allowed the Linux candidate to pass;
that narrower fixture did not reproduce the failure described here.

Both `/tmp/mcppls-dag-engine-before` (before patch 0023) and the current engine
with 0023 time out on the explicit-hint candidate. Live gdb attachment shows
the AST worker spinning in `clang::syntax::TokenCollector::consume()` under
`ParsedAST::build()`, while the main thread reads LSP input and the preamble
thread waits. Neither stack waits on the new bounded module compiler pool.
The hang therefore predates patch 0023.

Temporary, subsequently removed diagnostic instrumentation of the token
mapping failure identifies two successive `kw_import` tokens at the same
source location: expanded indices 9 and 10, raw source location 55. Later
imports show the same duplicate. After the first missing named BMI, the module
loader's fatal flag remains set. Recovery continues parsing later named
imports, but `Preprocessor::HandleIdentifier()` handles each directive by
queuing its keyword and suffix and then returns the original keyword because
the sticky flag is true. The queued stream later delivers that keyword again.

`TokenCollector::Builder::advance()` cannot consume the second keyword after
the spelled-token cursor passed it. Its `llvm_unreachable` path traps in an
assertions-enabled build and has no guaranteed termination in the release
build measured here. This explains the release spin without changing the
token buffer's mapping invariants or discarding malformed expanded tokens.

## Fix and regressions

Patch 0024 changes `HandleIdentifier()` to consume the original contextual
keyword whenever processing successfully queued a C++ module directive stream,
including when an earlier named import set the fatal-loader flag. A fatal
header/module-loader path that queued no directive retains its existing stop
behavior. Nonfatal directives already consumed the original keyword.

The in-patch token collector test provides two absent named BMI paths and
requires exactly two import keywords and a terminal EOF. The in-patch clangd
test requires a later `marker` symbol after both missing imports, then edits
the document and requires `recovered`. It passed `FileCheck` with the fixed
engine; the pre-0023 binary times out on that minimal test after a bounded
three-second negative control. The token collector unit test is added for the
normal upstream test target; no full unit-target build was run locally.

## Linux evidence

`tests/evidence/missing-bmi-directive-recovery.json` contains the compact
comparison, fixed binary hash and exact semantic assertion. Before/current
comparison replays use the same candidate and 12-second observation deadline;
the candidate's committed 60-second deadline is unchanged.

- Before patch 0023: timeout, killed after the bounded observation; live stack
  in TokenCollector. Raw local evidence: `/tmp/up12-before.json` and
  `/tmp/up12-before.stack`.
- With patch 0023 and without 0024: same timeout and live stack. Raw local
  evidence: `/tmp/up12-current.json` and `/tmp/up12-current.stack`.
- With patch 0024: normal exit 0; documentSymbol answers in **17.53 ms** and
  result index 14 is `NameType`, kind 10, satisfying the candidate's semantic
  expectation. Raw local evidence: `/tmp/up12-fixed.json`.
- Minimal missing-BMI lit case: old binary timeout (exit 124), fixed binary and
  FileCheck exit 0. `ci/check_ledger.py` verifies 24 patch entries; reverse
  `git apply --check` verifies the exported patch against the modified source.

The final build directly invoked only the generated compiler commands for
Preprocessor.cpp and the restored Tokens.cpp, their two archives and clangd's
link command. An initial Ninja invocation proposed thousands of recompiles
because generated compiler options had changed; it was interrupted, and no
full rebuild was allowed to finish. All temporary diagnostic source changes
were removed before the fixed build and exported patch.

## Native qualification remains open

The historical Windows evidence reports exception `0x80000003`. The normalized
candidate still needs to reproduce its historical baseline on native Windows
with matching symbols. A Linux token-mapping spin, even with the original
explicit hints retained, does not establish that exact native crash stack or
promote this input into a qualified Windows crash corpus. The candidate stays
explicitly unqualified; patch 0024 is stabilizing, not a release-ready claim
for all UP-12 manifestations.

Drop 0024 when upstream's contextual directive handling consumes queued
keywords after prior named-BMI failure and these token/semantic recovery
regressions pass without the patch. The change is independent of the bounded
module-DAG scheduling patch and should be submitted upstream as a separate
lexer recovery fix.
