# 0049 — persistent owned module payload admission and generation leases

Source commit: `461b21a3bd3c7a8866f7d9bf3a194739c0b49506`.
Base: accepted 0047 private source `6c265ca45d3e122829c80e6a5848e4fb6c0e2298`
(tree-identical to consolidated 0047). Tree: `766053a3413433774530e3836b8701c9417b782d`.
Clean private worktree: `/tmp/mcppls-worker-owned49`.
Patch: `0049-owned-module-payload-admission.patch` in this directory.
No shared source, archive, build or product changes were made.

## Boundary and policy

Linux production module builds now use one `.owned-payload-v1` namespace per
project cache root. The default logical payload reservation ceiling is 1024 MiB;
`--modules-builder-owned-cache-payload-mib=0` disables this new admission.
`--modules-builder-owned-cache-generations` defaults to 4096 fixed generation
slots, maximum 4096. This counts reservations, stable generations and read copies,
NOT every captured/compiler file. A worker separately allows at most 4096 captured
files and 64 logical compiler output paths. Control files/ledger/leases, filesystem
metadata, block rounding, sparse allocation, scanner/parent memory and RSS are
outside this logical payload ceiling. Multiple project namespaces are independent;
this is not a global server or physical filesystem quota.

A positive owned ceiling requires supervised workers and exportable request FS.
The worker output envelope defaults to 256 MiB and capture envelope to 64 MiB;
positive explicit per-worker limits remain authoritative. Reserve their sum before
any snapshot payload write. The default two-worker pool can therefore admit two
320 MiB envelopes when existing charges leave space. The 0047 pre-write stream
and ModuleCache writer bounds remain active. Captured main/overlay/YAML/request
bytes are checked before writes. The bounded output backend now writes directly
into the unpublished private unit, eliminating OnDiskOutputBackend.keep's
rename-failure copy fallback and its transient duplicate payload. Parent
publication stays an atomic same-filesystem rename.

Other platforms default owned admission to zero. Configured owned admission on
unsupported platforms and explicit InProcess with positive admission fail closed.
The established in-process module semantics fixture explicitly saves/restores
quota zero. All clients opening an existing namespace must use the recorded
ceiling and slot count; mismatched limits fail closed rather than splitting the
shared quota. Changing these values on an existing populated namespace needs
coordinated namespace administration, not automatic deletion of legacy files.

Ordinary -MD/-MMD/-MF/-MT dependency-file options are admitted in the owned-default
path only when clangd's EXISTING sanitizer has already removed the final
DependencyOutputOpts.OutputFile. Only that proven inactive filename is removed
from the ORIGINAL invocation's validation probe; actual invocation flags are not
newly modified. Plugin, header-include, DOT, module-dependency, diagnostics and
other unsupported writer checks remain. Direct optional 0047 raw worker requests
still reject a dependency writer. Explicit compile-command module-file/search-path
references into the reserved namespace (including canonical aliases) are rejected
before parent AST/preamble preparation: they have no lifetime lease. Foreign
prebuilt paths outside this namespace and legacy cache files are retained.

## Admission and lifetime

The fixed-size ledger has two checksummed durable banks per slot. Reservations
are acknowledged before payload writes. Slot-local generation counters make paths
immutable across reuse. Generation markers bind slot/generation and physical
lease identity; roots/ledger/generations/sidecars are checked for ownership,
permissions, nofollow type, device/inode and link count as appropriate. OFD leases
exclude both other processes and other descriptors in this process. They support
atomic exclusive-to-shared conversion, avoiding flock's conversion gap.

The source lock and prerequisite leases remain alive through the supervisor's
specific-child reap. Publication verifies worker cleanup, synchronizes the main
payload, and changes the SAME charged record from envelope reservation to actual
stable size without releasing/reacquiring its lease. Every read copy reserves its
exact size before a bounded copy loop; its record persistently names its stable
companion. Both leases remain held through validation and consumers. Each worker
independently acquires managed prerequisite copy AND stable companion leases
before frontend reads. Parent SIGKILL therefore cannot make a still-consuming
child's prerequisites collectible. Protocol 3 is mandatory for owned admission;
an old v2 worker rejects it rather than silently bypassing this lifetime contract.

Background maintenance scans bounded slot batches (32, clamped to 128), takes
exclusive generation and nonblocking existing source guards, and performs cleanup
outside admission/registry mutexes. Stable generations remain cached without
pressure; failed admission publishes bounded cross-process pressure metadata.
No PID/age is used to authorize generation deletion; the pre-existing source-lock
manager keeps its own upstream dead-owner handling. Worker retirement additionally
uses both 0039 kernel leases and its fail-closed retired startup marker. Unknown,
symlinked, identity-mismatched or incompletely initialized entries stay charged.
Cleanup is acknowledged as Erased only after directory unlink, directory sync and
an unlinked directory descriptor; an absent path alone could be a rename and
cannot clear a charge. Torn/ambiguous cleanup windows conservatively retain charges
and can exhaust admission rather than invent free space.

## Necessary 0045/0039 maintenance repair

After parent SIGKILL, its diagnostics destructor cannot unlink the 0045 stderr
FIFO. LLVM recursive removal skips FIFOs. The old 0039 collector therefore left
retired units and reservations forever. Cleanup now removes only the verified
same-user known owner.pipe/stderr.log FIFOs; bounded unit inventory rejects
unknown names, symlinks and inappropriate types before recursive deletion. Known
compiler-cache files/atomic temp spellings are bounded too. Unknown entries retain
the whole generation and its charge. This is a maintenance interaction repair,
not a newly discovered upstream defect or a weakened assertion.

## Actual Linux evidence

Private executable SHA256:
`d8fa16318d0554d3bac77f3b11276cb0edb4ae715cd3c899264d2adb23da6ad9`.

* `prereq-final.log`: all 54 PrerequisiteModulesTests pass, 624 ms. Added controls
  cover pre-write aggregate denial, exact-copy/live leases, real fork SIGKILL
  persistent charges, changed directory and lease identities, unknown/symlink
  units, foreign namespace non-adoption, and unleased managed prebuilt refusal.
* `default-mmd-final/result.json`, `default-md-final/result.json`: real default
  LSP workers, relative CDB spellings, dirty header 41→42, completion fn_m,
  actual protocol3 capture; -MMD and -MD with -MF/-MT admitted. Existing M.d
  sentinel unchanged, no Use.d, no -dependency-file in captured cc1 arguments;
  clean parent shutdown and no surviving worker units.
* `low-admission-verified/result.json`: 1 MiB namespace vs 2 MiB envelope rejects
  before generation/capture/request creation, no BMI or launched-worker failure;
  independent ControlValue semantic request succeeds; parent exits0.
* `launched-failure-final/result.json`: real 16 MiB address-limit child failure,
  no BMI/fallback, independent ControlValue, parent exit0/reap/readers stopped.
* `old-worker-v2-final/result.json`: actual 0047/v2 worker rejects protocol3;
  no BMI/fallback, independent ControlValue, normal parent exit.
* `owner-proof-before.json` and `owner-proof.json`: SAME current parent/worker
  and workload; negative collector links unchanged shared46 Storage object,
  positive collector links current Storage object. Live parent and paused live
  worker retain the 320 MiB charge in both. Parent actually exits -9; child is
  resumed and naturally exits1 on owner EOF, then is waitpid-reaped by a real
  subreaper. Old collector removes0/leaves FIFO+charge; fixed removes1/charge0.
  SIGSTOP exposes the live-worker interval; no forced child kill is a success.
* `owner-proof-prerequisite.json`: real A→M graph. Under forced quota pressure,
  M's independent child OFD leases retain A stable+copy (35268 bytes each) plus
  M's 320 MiB envelope after parent SIGKILL. Natural child exit/reap precedes
  collection of all3 generations and charge0.

Scripts/commands are retained in this directory. Changed consumer TUs compiled:
ModuleBuildCache, ModuleBuildWorker, ModuleBuildWorkerOutput,
ModuleBuildWorkerStorage, ModulesBuilder, Compiler, PrerequisiteModulesTest.
Private links also use the exact accepted47 CompilerInstance/FrontendAction/
GlobalModuleIndex overrides BEFORE the stable combined46 archives. Existing
public class vtables/layouts are unchanged; new Options/Inputs fields' actual
consumers were rebuilt. Root must still perform its normal complete integration
build and native qualification.

## Explicitly open

This slice preserves the parent guard rejecting a main BMI that references its
private implicit module-cache PCMs. Actual Qt/nlohmann with original -fmodules
therefore remains unqualified and requires the following immutable implicit-bundle
publication slice. Do NOT drop that guard or remove semantic compile flags.
A compatible extension keeps producer unit paths stable, stores bounded MainPath
and MainBytes separately from total bundle charge, purges captured/control payloads
only after reap, and atomically transfers the same reservation. Main read-copy
charges stay exact while their existing companion lease retains the whole bundle.

Physical allocation/metadata ceilings, aggregate namespaces, parent/scanner RSS,
large-project warm-body performance, unusual strict CDB side outputs, and native
non-Linux owned admission remain open. These Linux controls do not establish
completion of the user's full resource/performance/crash objective.

Drop when upstream provides equivalent prewrite durable admission, same-record stable publication, exact read-copy reservation and parent/child kernel lease/identity/retirement canaries. Final logical/physical/native release gates remain open.

[Compact evidence](../tests/evidence/owned-module-payloads.json).
