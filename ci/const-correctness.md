# Const correctness and constrained range consumption

`0021-UP-22-semantic-const-range-constraints.patch` supersedes the broad
operator-pipe heuristic introduced by patch 0005. Keep both commits in the fork
series; for an LLVM submission, combine the final const-correctness change and
its tests against the pinned upstream base, without the intermediate heuristic.
No standard-library type-name list is used.

The mutation analyzer inspects the already instantiated non-const program.
A const `begin()` declaration can exist but have unsatisfied constraints on the
specific specialization. Forwarding pipe templates have the same problem: the
original non-const argument satisfies their constraints, while a const argument
may not. Thus absence of mutation alone is insufficient to offer a const fix.

The follow-up asks the current Sema to check actual member range-for consumption
and free operator-pipe calls with an isolated const lvalue. Member lookup, overload
resolution, template argument deduction and constraints use the compiler's normal
rules. Calls retain their qualifier and explicit template arguments, and ADL is
used where the original call allows it. Access checking uses the variable's
original declaration context. User pipes accepting const objects, const-capable
ranges, and values that are only discarded continue to receive valid suggestions.
This also preserves a const `ref_view` over a non-const-iterable filter: its const
member functions still operate on the referenced mutable range.

The tidy context owns no Sema object. Standalone clang-tidy sets/clears a borrowed
pointer through its AST consumer's InitializeSema/ForgetSema lifecycle; clangd
sets/clears it around its tidy matcher invocation. Other integrations that do not
provide Sema retain their existing mutation analysis. Probe expressions are not
attached to or substituted into the original expression tree. They run in an
unevaluated context, with provisional analysis and diagnostic suppression restored
by RAII. Deduced return types can require normal semantic instantiation and warm
Sema's template/constraint caches; those caches are not rolled back. A regression
with a failing provisional static_assert checks that no error escapes and a later
real const warning still appears.

Current scope is concrete record values consumed by member range-for iteration
or free operator-pipe calls. ADL-only iteration and unresolved dependent
expressions stay with the existing mutation analyzer. This patch does not claim
a general proof that every function call can be rewritten with const arguments.

## Focused verification

The in-patch test
`clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-range-constraints.cpp`
contains no real standard library and covers both satisfied and unavailable
dependent const-iterator constraints, mutable element references, ordinary user
pipes, constrained forwarding pipes, explicit pipe syntax, private const
iterators, unused mutable ranges, and provisional body diagnostic isolation.
Run it with llvm-lit together with the original ranges, values and templates
const-correctness tests.

The repository regression uses the actual installed standard library and raw
clangd without product filtering:

```sh
python3 tests/e2e/const_correctness.py \
  --engine build-linux-x64/bin/clangd \
  --clang-tidy build-linux-x64/bin/clang-tidy \
  --clang build-linux-x64/bin/clang++ \
  --workdir /tmp/mcppls-const-correctness
```

It requires exactly the five valid suggestions (`answer`, `input`, `reference`,
`safe`, `safeAgain`), rejects errors and extra warnings on the filter/transform
chain or mutable iteration, applies all clang-tidy fixes, and compiles the result.
The report and logs remain outside the repository. This is correctness evidence,
not a crash corpus, performance benchmark or release-soak result.
