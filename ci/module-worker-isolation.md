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
