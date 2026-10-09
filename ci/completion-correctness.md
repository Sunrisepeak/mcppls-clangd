# Module completion: first root cause and containment

The focused fixture exports Cli::addHelpOption/addOption from an unindexed
module and requests cli., cli.ad and ptr-> on a middle line. documentSymbol
first waits for a built AST; this excludes the initial no-preamble fallback.
Current experimental bytes lose both expected symbols and offer unrelated
local/global identifiers. Raw logs confirm the modules fast path (no Sema).

0006 deliberately skips semantic analysis, even though the merged index does
not carry all module exports. Its boolean accepts any nonempty prefix, including
cli.ad. Its empty-prefix branch accepts member access. CurrentLine additionally
uses Content.rsplit rather than the line containing the requested offset. Fixing
that line or checking dot/arrow cannot establish lexical scope, template/member
semantics or unindexed exports for the remaining positions.

Containment: module support must not imply index-only completion. Keep the
index experiment behind its own explicit opt-in flag, default false. Correct
completion uses Sema until a replacement proves all W1 contexts. This change
restores correctness; it is not the required module completion optimization or
steady promotion. Raw performance and C7 isolation remain outstanding.

Reproduce: python3 tests/e2e/completion_quality.py --engine <candidate-clangd>
--clang <matching-clang> --workdir <isolated-directory>. The report preserves
engine SHA, returned names, timings and failure outcomes.
