# Module compiler worker isolation: proposed implementation sequence

Patch 0034 introduces the internal worker protocol after 0031 compiler-boundary cancellation and 0033 owner-lease fixture correction. It is not enabled in ModulesBuilder and does not advertise a resource-bound capability. Parent supervision and filesystem exporting are ongoing followups.

## Input preservation and ownership

1. Parent keeps source publication lock and every prerequisite ModuleFile
   shared_ptr/read lease until the worker is reaped. Child never renames into
   the persistent published path and never owns the parent's read leases.
2. Parent finalizes the same CompilerInvocation used by buildModuleFile:
   original expanded compile command/target/resource/SDK/header-map settings,
   SkipODRCheckInGMF, ValidateASTInputFilesContent and prerequisite copy paths.
   Serialize getCC1CommandLine *before* prepareCompilerInstance adds native
   remapped-buffer pointers. Compiler executable/version is the same clangd.
3. Parent writes exact main-buffer bytes in binary mode into an owned request
   directory. Capture every overlay/draft backing file similarly. Preserve
   virtual filenames, timestamps, alias identity and overlay precedence, not
   only source text. Source/header maps and external includes retain their
   actual paths and command flags. Request lifetime ends only after reap.
4. RealThreadsafeFS can explicitly export disk semantics. RequestModuleFS can
   append its immutable exact-main-buffer overlay. Other ThreadsafeFS wrappers
   require a real export implementation; default is Unsupported. Arbitrary
   virtual filesystem metadata, hidden paths or negative lookups cannot be
   guessed by walking a workspace. If YAML cannot express a wrapper faithfully,
   reject it or implement a filesystem broker rather than falling back to disk.
5. Each worker has an owned implicit-module cache directory as well as its
   staged main PCM. The parent removes both on failure, cancellation or kill;
   successful final publication remains under the existing source lock.

## Foundation implemented here

ModuleBuildWorker.{h,cpp}: version-1 JSON protocol, finalized CC1 argument
serialization, explicit captured-FS declaration (Unsupported by default),
absolute CWD/main/byte-snapshot/overlay paths, rejection of native remapped
buffer pointers. Main bytes stay out of JSON so arbitrary encodings survive.
Worker reconstructs CI, physical base FS plus ordered YAML overlays, installs
captured main buffer and executes GenerateReducedModuleInterfaceAction.
Compiler failure removes staged output. Missing fields/version/unsupported
filesystem are normal errors. Parent remains responsible for cleanup if the
worker cannot read its descriptor or is killed/crashes before returning.

ClangdMain dispatches --module-build-worker <request-file> before ordinary
LSP/flag parsing, including CLANGD_FLAGS. Its stdout is not an LSP channel.
Caller must redirect stdin/stdout/stderr separately, with bounded diagnostics.
This is an internal standalone entry, not yet the default builder path.

## Required parent supervisor step

Use the same executable path, an owned request directory and a steady-clock
wall deadline. Child launch, cancel polling and specific-child termination/reap
must be one RAII unit. Never release lock/leases or delete child inputs until
reap succeeds. On caller cancellation, timeout or an exception, terminate the
exact child, reap it and discard outputs; on natural success validate the
result, recheck cancellation, then perform the existing atomic publication.
Keep the pool's existing concurrency bound and collect CPU/peak-memory stats
for actual evidence. Child performs only an in-process frontend action, so no
subordinate compiler subprocess should escape supervision.

LLVM Program.h ExecuteNoWait can launch with redirected files, but its Unix
Wait(timeout) implementation changes process-global SIGALRM and uses wait()
on timeout. Its own comments warn that another thread/child can receive that
alarm or be reaped. Avoid that path in parallel module workers: use per-child
waitpid/wait4(WNOHANG), monotonic polling, kill(exactPID,SIGKILL), and specific-
PID blocking reap on Unix; WaitForSingleObject/TerminateProcess/CloseHandle
for the owned handle on Windows. No ordinary unbounded ExecuteAndWait.

Memory: LLVM's MemoryLimit sets RLIMIT_DATA/RSS on Unix, ignores setrlimit
errors and does not enforce hard RSS on Linux. Windows assigns a memory Job
*after* CreateProcess, so the generic helper alone has a startup race. A real
limit needs checked worker/bootstrap rlimits (RLIMIT_AS is an address-space
limit, not an RSS measurement), or Linux delegated cgroup v2 memory.max;
Windows suspended CreateProcess, owned Job with kill-on-close/commit limit,
assignment before ResumeThread. Darwin semantics need actual native tests.
Do not describe commit/virtual-memory limits as an already-qualified hard RSS
limit. Bound failure must fail closed rather than silently launch unlimited.

## Qualification still required

- Same compile args and draft/header overlay produce identical usable modules;
  aliases/header maps/SDK/prebuilt transitive imports/response inputs canaries.
- Real long frontend work is terminated and reaped within deadline; no zombies,
  staged PCM or child caches; caller cancellation also terminates it promptly.
- Parent crash closes worker Job or equivalent lifetime owner; Unix parent-death
  behavior requires a supported bootstrap/watchdog rather than inherited locks.
- Native Linux/macOS/Windows memory and timeout tests, including launch-limit
  errors and multiple simultaneous module workers, without fake platform claims.

Persistent published-BMI disk growth remains a separate open lifecycle issue.

Integrated Linux development evidence: [module-worker-protocol.json](../tests/evidence/module-worker-protocol.json). All 82 relevant units pass in 607 ms. The actual executable entry compiles a 34648-byte PCM from captured main/header snapshots while disk versions contain #error; malformed protocol and captured compile failure exit normally with errors and no staged output. The child stdout remains empty, and invalid CLANGD_FLAGS cannot contaminate this internal entry. All 66 touched source paths from the ordered 34-patch fixture and three overlays match. No hard limit, default worker selection or release package is claimed.

## 0035 owned child supervision and actual drafts

The separate buildModuleInWorker API now captures the actual ClangdServer
DraftStore filesystem with one mutex-protected snapshot and immutable buffers.
RequestModuleFS appends the exact main input last. Unknown filesystems decline
export; Required fails closed, while WhenSupported may select the original path
only before launch. Started workers never fall back after failure or a bound.
The default remains InProcess, and ModulesBuilder does not yet call this API.

The supervisor uses its exact child PID/handle, polls a steady deadline and
cancellation, kills/reaps before deleting its unit directory and staged PCM,
and bounds parent diagnostic reads to 64 KiB and the actual file size. Snapshot
I/O itself is not interruptible. Explicit prerequisite leases remain caller
owned. Generated implicit dependency PCMs cause rejection because unit cleanup
would invalidate their lifetime.

Private Linux source 03a76e8de supplied real-child success in 11 ms, frontend
timeout in 103 ms and cancellation in 102 ms. All retained fixtures prove disk
main/header differ from captured bytes; stop cases retain no staged PCM, unit
directory or child, and an unrelated child remains alive/unreaped. Four focused
units pass. These use changed compilation units and existing archives: a full
dependent rebuild is required before default enablement. No native macOS or
Windows, parent-death cleanup, hard RSS limit or release package is claimed.
The initial diagnostic-slice SIGBUS was corrected before these final runs.

## 0036 Windows compilation repair

Native historical Windows run 37685946237 stopped during compilation, before
fork crash qualification: Windows min/max macros expanded the module DAG's
std::min/std::max calls. Parenthesized standard function names avoid expansion
and preserve scheduling behavior. The historical stock crash remains proven,
but this failed build supplies no fixed-fork execution claim. Native rerun
remains required.

Root integration at ordered patch 0036 has now recompiled all 166 affected
clangd units, rearchived daemon/support/tweaks/remote/main libraries and
relinked clangd and ClangdTests. The focused prerequisite/CDB/draft/scheduler
set passes 66 units in 436 ms; all 26 DiagnosticsTest units pass in 114 ms.
Actual first cold completion and unsaved import/update replay return correct
symbols, unchanged disk and normal exit. This resolves mixed-archive validation
for this development head; production worker default remains unwired, and no
final floor/native package or hard resource qualification is implied.

## 0037 parent owner lifetime

Supervised workers inherit an actual owner object and start a monitor before
request/frontend execution: POSIX FIFO reader with the sole writer held by
the parent (atomically CLOEXEC), Windows SYNCHRONIZE process-object handle.
No PID lookup can confuse reuse with ownership. The monitor exits the worker
when the owner disappears; normal completion joins it. Explicit FIFO unlink
precedes normal recursive directory cleanup. Direct argc3 internal protocol
probes remain ownerless; API-launched workers always receive the owner token.

Private Linux parent SIGKILL during actual frontend work stops and reaps the
worker in 9.37 ms. Success/timeout/cancel still preserve an unrelated child
and clear normal units. The killed owner's directory intentionally remains:
neither SIGKILL nor immediate worker exit runs cleanup. Following collection
must acquire both parent/worker leases, protect same-process active units and
leave unmarked legacy units untouched. Native Windows/Darwin execution,
orphan sweep and actual default server policy remain unqualified.

Actual root development integration after 0037 repeats all 92 related units
(567 ms), real child success (21 ms), frontend timeout (102 ms) and cancellation
(103 ms). All normal paths reap only the worker, preserve another child and
leave no new unit directory. Killing the actual supervisor during marked
frontend work causes natural worker exit 1 and adopted reap in 7.26 ms; its
unit remains and no staged PCM exists. tests/evidence/module-worker-owner-lifetime.json
records current engine identity and separate private/root evidence.

## 0038 shared kernel memory admission

A caller-provisioned delegated cgroup-v2 root can now own one private budget
shared by all admitted worker calls. The factory verifies the actual cgroup
filesystem/domain, writes and reads back memory.max, zero swap and group OOM,
and requires owned group-kill support. Child bootstrap verifies device/inode,
limits and its actual membership before request/frontend work. Once a group
is configured, InProcess and unsupported WhenSupported fallbacks are errors.
The group owner remains held through specific-child reap and kills remaining
descendants before normal removal. Shared controllers and the parent process
are never modified or moved.

Private Linux proof has two workers allocate 40 MiB each under the same
64 MiB group: oom_group_kill=1 and oom_kill=2, both receive SIGKILL, the parent
survives and its private group is removed. Actual frontend success under
128 MiB takes 31 ms and preserves an unrelated child. Modified limits reject
bootstrap; unavailable child controllers reject the factory without leaking
a group. Three related units pass. The current populated terminal scope
cannot delegate memory, but its empty parent slice already has the controller
enabled for private children; only those private children were used.

The bound covers kernel-accounted admitted group memory/descendants, not
parent/scanners, pre-migration charges or an exact sum-RSS ceiling; the kernel
permits temporary overshoot. All covered calls must share the same owner.
Parent-death group directory collection and default/native integration remain
required. Evidence retains the private source and executable identities in
tests/evidence/module-worker-memory-budget.json.

## 0039 leased worker units and maintenance collection

A versioned owned root now holds each request, overlays, implicit cache,
private output, stderr and owner FIFO. The parent holds parent.lease before
publishing ownership; a worker acquires worker.lease and checks the marker
after locking. Successful natural reap transfers output to caller staging.
Normal destruction removes the unit, including an explicit FIFO unlink.

Collection is a separate maintenance API with a persistent cursor, 30-second
cadence and bounded entry count. It requires both nonblocking kernel leases,
reserves physical directory identity against same-process alias ownership,
and retires the marker before deletion to reject delayed worker startup.
No filesystem I/O happens under the process registry mutex. Unmarked legacy
or partial startup units remain untouched. Published BMIs and caller staging
remain outside this collector's ownership.

Private actual Linux proof kills the supervisor during marked frontend work:
the worker exits naturally in 3.16 ms. A fresh collector removes exactly that
orphan while retaining live parent-only and worker-only units and unmarked
legacy data; after helpers close it removes their two units. Success, timeout
and cancellation reap only the worker and clean all normal units. This proof
is based on 0037; the exported integrated patch includes 0038 admission but
that combined root and default server still require validation. See
tests/evidence/module-worker-collection.json.

## 0040 checked worker address space

An optional protocol field supplies a launched worker's address-space ceiling.
After reading the small request, before overlays/main/frontend allocation,
bootstrap sets both RLIMIT_AS limits and verifies exact readback. It respects
an existing tighter hard limit. Invalid protocol values and unsupported
positive limits fail closed. This complements explicit shared kernel-memory
admission; it does not replace or bypass its checks.

LLVM's usual OOM reporting can itself allocate after exhaustion. A worker
with a positive limit therefore installs an allocation-free bad-allocation
exit callback. A deliberately small 16 MiB ceiling now ends naturally in
11 ms with no PCM, reaped child and cleaned unit. A 1 GiB success and active
frontend timeout observe both actual OS limits at 1073741824 bytes and retain
an unrelated child. Negative, string and boolean protocol values are rejected.
Evidence in tests/evidence/module-worker-address-space.json identifies the
private binaries and source, separate from pending combined root proof.

Address space differs from RSS and kernel-accounted shared group memory.
WhenSupported may select compatibility execution for an unexportable filesystem
before launch; this option then supplies no in-process bound. Parent/scanner
allocations and native platform qualification remain separate work.
