# Compiler extension completion

The semantic baseline already completes GNU attribute names such as cleanup,
but omitted the __attribute__ introducer and Windows __try statement pattern.
Patch 0014 supplies declaration-position attribute syntax and a statement-only
SEH pattern, gated by Microsoft extensions, Windows triple and TargetInfo's
actual SEH support. Comments, strings, ordinary expressions and unsupported
Linux targets do not gain these constructs.

A real insertion probe also exposed cleanup argument completion inserting a
call instead of a function reference. The parser now invokes dedicated Sema
completion at the first cleanup argument. It returns visible pointer-taking
single-argument functions (including static methods/function templates), uses
reference insertion, and bypasses unrelated index symbols in this attribute
context. GCC's simple-identifier form is covered. Qualified-name cleanup is a
Clang extension and this patch does not add a dedicated qualified-name path.

Unmatched index entries named __try/__except/__finally/__leave are excluded
from semantic completion. This stops a libstdc++ macro being mistaken for SEH
on Linux. Visible declarations/macros already supplied by Sema remain present; a Linux
macro declaration is a positive canary for that preservation.

Run tests/e2e/compiler_extensions.py with --engine, --clang and --workdir.
Eleven asserted raw LSP cases check grammar and target boundaries. The probe
applies the actual edits and fills snippet fields, then compiles those results:
GNU introducer, cleanup attribute, cleanup function reference and Windows SEH.
A minimal unsupported Linux SEH example must fail for the specific target
reason. PR CI runs this focused probe on all three supported hosts; the Ubuntu floor
recipe also checks packaged bytes. Raw baseline and local candidate evidence
is in tests/evidence/compiler-extensions.json. This does not prove release soak,
real-project latency or a native Windows run before CI completes.
