# Document close during a live-owner module lock wait

The old preamble worker only set its stop flag, leaving active module cache
lock waits alive indefinitely. Patch 0016 gives the active preamble build a
cancellation context and invokes its canceler when the worker stops. The
module builder checks cancellation between one-second lock wait intervals and
between prerequisite modules. Cancellation never removes another owner's lock.

The local raw-LSP probe waits for an actual lock-wait log event, cancels a
deferred documentSymbol request, closes the blocked document, opens a healthy
document and asserts its symbol, then requires normal managed shutdown. The
current candidate passes and preserves the live owner's lock. The pre-fix
binary replies for the healthy document and to shutdown but fails to exit
before the 15-second deadline; the replay records timeout and forced teardown.

Raw evidence: `tests/evidence/module-lock-close-cancellation.json`. This is local
unstripped Linux evidence, not final packaged bytes or native Windows proof.
The portable canary is registered in the patch ledger and four-platform CI.
Final packaged proof and native CI results remain required. Request cancellation alone need not cancel a shared preamble;
this change targets ownership ending on document close and server teardown.
