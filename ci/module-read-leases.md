# Copy-on-read lifetime and orphan collection

Patch 0022 repairs the UP-24 collector/ownership path rather than reducing its
three-day threshold. Previously `collectModuleFiles` gathered every `.pcm`, and
GC removed each one with an old access time. Neither age nor an unreferenced
published path proves that Clang has stopped using a BMI. The focused baseline
changes only the published BMI's access time to zero; the next engine removes
and rebuilds it (inode/mtime changed). `tests/evidence/module-read-leases.json`
records that failing identity assertion and the repaired candidate.

Each newly created copy now has a unique sidecar (`.pcm.lease`). The creator
acquires a nonblocking exclusive kernel file lock before the copy can become
visible. `CopyOnReadModuleFile` owns that lease for its entire shared lifetime.
Normal destruction removes the copy before releasing the lease. Process exit,
including SIGKILL, releases the kernel lock without destructor execution.

GC leaves published BMIs and old unleased copies untouched. For leased copies
it opens the sidecar without creating it and attempts the exclusive lock. An
unavailable or failed lock leaves the copy alone; an acquired lock proves there
is no participating owner, so GC deletes the copy and sidecar. Multiple
collectors compete for that same lock. No deadline, PID-reuse heuristic or
filesystem access time decides reader liveness. On Windows, locking the sidecar
rather than the BMI keeps byte-range locks away from Clang's own file reads.

POSIX fcntl locks are process scoped: closing another descriptor for the same
lease can release our lock. A process-wide mutex and live-path set prevent GC
from even opening a locally owned lease; creation, ownership removal and GC
lookup are serialized. LLVM's filesystem lock/descriptor API handles native
Windows and Unix semantics; native test results are still required.

The raw multi-process regression runs with the old GC threshold set to zero.
Six assertions pass on local Linux candidate bytes: published identity survives
reuse, an artificially aged live reader copy survives another engine's GC,
published identity stays unchanged, killing a reader allows immediate orphan
reclamation on the next engine start, another live reader's copies survive,
and the published BMI survives reclamation. Every live engine also returns the
actual module function with Function completion kind and normal shutdown.
The baseline fails the published-identity assertion and has no reader leases.

```sh
python3 tests/e2e/module_cache_lease.py --engine build-linux-x64/bin/clangd \
  --clang build-linux-x64/bin/clang --workdir /tmp/module-cache-lease
```

The four-platform PR workflow runs this probe and retains raw outcomes. The
legacy threshold option remains accepted for command-line compatibility; it
no longer controls leased-copy ownership. This patch stays stabilizing until
native and final-package results qualify it. Drop it when upstream uses a
reader lifetime/lease protocol with crash reclamation and equivalent canaries.

Limits: legacy copies without leases cannot safely be attributed and are not
removed here. A process dying between sidecar creation and copy publication can
leave a small empty sidecar; the current collector visits copies, not detached
sidecars. This is not proof of the complete workspace/disk budget or RC soak.
