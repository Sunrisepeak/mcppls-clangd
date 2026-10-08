# 0046: bounded copy-on-read BMI maintenance

Request preparation no longer performs synchronous recursive cache GC or builds
an unbounded vector of all PCM paths. Known cache roots register with existing
maintenance, including InProcess policy. Each root owns a persistent nofollow
cursor with fixed source-hash/command-hash/file layout depth and at most 32
examined entries per pass (helper absolute maximum 128). Worker/lock trees,
nonhash foreign directories, deeper trees and symlinks are pruned. At most eight
roots are snapshotted per wake; filesystem operations run outside RegistryMu.
Unfinished copy cursors request a 100 ms follow-up, otherwise the normal wake is
five seconds. The 30-second sweep cadence is measured from sweep start, not
completion. Shutdown drains the build pool before stopping/joining maintenance.
These bounds constrain traversal work, not arbitrary filesystem syscall latency.

POSIX fcntl locks can be dropped by closing another descriptor for the same inode
in the owner process. A lexical path-only registry cannot protect ancestor
aliases. Active path and physical UniqueID guards are now reference counted.
A pending-creator guard precedes sidecar creation and ends once constructed lease
ownership is registered, before copying PCM bytes. Active guards survive through
unlock/close/removal. Collector identity reservation precedes opening the lease
and lasts through close/unlink; active aliases and pending creators are skipped.
All open/status/lock/remove/unlock/close operations occur outside the short
registry mutex. Nofollow handles and repeated lease/PCM identity checks retain
unknown or replaced objects. The existing closed-copy lease authority from 0033
is unchanged; unleased stable/prebuilt/legacy files remain untouched.

Initial private b8b482f and follow-up ac0bfe3 are preserved; consolidated export
f2d8740 has their final tree. Only ModulesBuilder.cpp and its prerequisite unit
fixture change. Thirty-eight prerequisite tests pass in 371 ms using changed
objects ahead of compatible read-only archives. Existing stable mtime, active
copy and closed-orphan assertions remain. Since collection is asynchronous, an
exact orphan disappearance condition has a bounded two-second wait rather than
a fixed sleep. A separate implementation probe removes 96 closed orphans in 30
resumable passes with limit seven, maximum examined seven. A live physical lease
under an ancestor alias remains excluded to a separate fork's kernel try-lock
after all scans, proving collection did not open/close away its owner's lock.
Unleased stable/prebuilt/legacy files, symlinks and worker/lock directories survive.

The final combined root 1–46 rebuild passes all 100 related tests and both real
LSP worker fixtures. Ordered patch application matches 74 affected paths and
three overlays. Evidence is Linux focused development validation, not immutable
native release qualification. This patch does not impose a hard aggregate disk
budget on stable/staging/copy outputs or atomic conditional unlink against
arbitrary same-UID mutation. Those resource and native release gates remain open.

[Evidence](../tests/evidence/module-read-copy-maintenance.json)
