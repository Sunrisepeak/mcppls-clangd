# Module dependency cycle rejection

Patch 0017 separates the active DFS path from completed dependencies. A back
edge returns an explicit error before construction and the consumer receives
the normal failed-prerequisite state. Completed nodes remain reusable for
acyclic diamond dependencies. Traversal also checks the current cancellation
context between nodes. This is a serial graph correctness change; parallel
worker limits, provider generations and dependency-depth budgets remain open.

The raw LSP probe builds A importing B importing A, requires the actual
cycle-error log, edits the consumer to a healthy declaration, asserts its
symbol and requires normal shutdown. Local Linux unstripped bytes pass;
final floor package and native CI are pending. The probe is wired into both.
Raw evidence: tests/evidence/module-cycle-recovery.json.
