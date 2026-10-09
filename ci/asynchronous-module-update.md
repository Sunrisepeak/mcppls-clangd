# 0050: resolve module preamble policy on the update worker

Document updates previously called the module provider inventory synchronously
on the LSP thread. After0048, that inventory remained the edited completion's
largest avoidable main-thread delay. addDocument now captures the explicit
server option; ASTWorker resolves the module policy after obtaining the current
adjusted command, under the existing file context, before compiler invocation
and preamble creation. Both cached AST and latest diagnostic input comparisons
include SkipPreambleBuild, so provider changes invalidate an otherwise equal
input. No public data layout or explicit compiler flags are changed.

The actual-server blocking inventory regression proves addDocument returns
while provider discovery is blocked. The test releases the discovery gate
before assertions/destruction, then requires current imported symbols. The
same test object against0048 production fails the return assertion after two
seconds;0050 passes. This is a scheduling proof, not a deadline extension.
All26 TUScheduler tests and the new case pass873ms;0048's stored-policy control
also passes. Four response-generation controls from0052 pass alongside both
policy cases in the final private link (six tests23ms).

The maintained real LSP fixture module_preamble_mode.py requires correct and
forbidden symbols immediately after each input change, without an AST settle
barrier: cold header import M, same-size/preserved-mtime header import N,
unsaved plain text, then unsaved buildable M. It verifies normal shutdown,
reader termination and the original disk source. The private final engine
passes all four; native CI runs the fixture on every engine platform.

Matched-resource Qt reports preserve all four semantic assertions. Final
private48+50+51+52 warm samples are95/116ms and edited236ms, versus0048's
warm94/99ms and edited500ms. didChange itself drops to about0.05ms, while the
update worker still performs its inventory. These are single-process samples,
not statistical or insertion/context acceptance. Edited200ms remains open.
The pre0051 trace has borrowed-filename corruption and is retained unchanged;
the final0051 trace parses as strict UTF8/JSON. Neither is silently repaired.

Private source007316f64752baa16315adad25bcf44b727fe263 implements0050;
final source98d37921f also includes48,51,52 over root46. Changed production
and test objects precede read-only root46 archives. This is not a clean full
recipe or cross-platform package qualification. Remove the maintained patch
when upstream performs equivalent asynchronous policy resolution and both
blocking-inventory and fresh-symbol canaries pass.

[Compact evidence](../tests/evidence/asynchronous-module-update.json)
