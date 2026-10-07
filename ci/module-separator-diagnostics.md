# Missing module separators stay on their directive

Patch 0027 repairs two UP-15 causes. clangd's diagnostic fallback re-lexed with
whitespace skipping, so an insertion location at line end highlighted the next
line's token. It now reads only at the actual location, preserving full-token
ranges for real token diagnostics (including dereference suggestions).

For module declarations, preprocessing peeked at the next line and diagnosed
that token directly. If the original directive already ended, the missing
separator diagnostic and semicolon insertion now refer to its last token,
before a trailing comment. Same-line unexpected-token handling is unchanged.
Parser recovery and suppression policy are unchanged.

Four raw cases cover ordinary and physical-continuation import/module forms.
All four fail on the immutable 25-patch baseline and pass on the candidate;
normal shutdown is required. Thirty related units pass, including the complete
DiagnosticsTest suite and the four exact range/fix-it cases. The new compiler
verify regression fails on the old driver and passes on the updated driver.
Reports with raw replies and identities are retained in
tests/evidence/module-directive-diagnostics.json.

tests/e2e/module_directive_diagnostics.py is a reusable raw capability canary.
Local development-link evidence does not establish native final-package
acceptance or retire the product's compatibility workaround. A final stripped
package must pass the canary before declaring the capability; product policy
must keep compatibility for engines without that verified capability.

Upstream independently with the compiler and clangd tests. Drop when upstream
keeps missing-separator diagnostics and insertion fixes at the original
directive while preserving real-token diagnostic ranges.
