# Malformed module directive recovery

Raw clangd hangs on `import hello.` and `export module hello.` followed by a
newline. Ordinary clang parsing exits with diagnostics for the same input.
The measured stack is TokenCollector::consume in ParsedAST construction.
A logical tok::eod newline has no spelled C++ token; attempting to advance to
it reaches an unreachable failure path that can spin in a release build.
Patch 0015 excludes that logical token from collection rather than imposing a
request deadline. It adds syntax-token and raw clangd lit regressions.

The raw LSP probe covers six malformed variants, then a real didChange to a
valid declaration, didClose/reopen and clean shutdown. Two before-fix controls
actually time out and are recorded as failures, never successful recovery.
Evidence is tests/evidence/module-directive-recovery.json. Native CI and the
Ubuntu floor run the same six candidate assertions. The syntax unit test is
added but has not yet been executed locally. This evidence does not prove
cancellation, missing-provider deadlocks or preservation of later declarations
in invalid grammar. Product WA-CLANGD-001 remains enabled pending capability
proof and selective retirement.
