# The openkal series

These patches adapt LLVM to run as an openkal ok image (openkal clause 12): one
ELF program per architecture that a loader starts on Linux, macOS and Windows.
They are neither upstream defects nor optimizations of clangd. They are kept
apart from `patches/` for that reason:

- `patches/series` carries upstream defects and product features of every
  engine, native and ok image alike;
- `openkal/patches/series` carries only what an ok image needs, and is applied
  after `patches/series` and the overlay when, and only when, the tree is built
  as an ok image (`ci/scripts/apply.sh --openkal`, `.github/workflows/openkal.yml`).
  No native engine carries it.

The 0.0.20 OpenKal additions are `steady` after
[build-test run 42155475833](https://github.com/Sunrisepeak/mcppls-clangd/actions/runs/42155475833)
passed the final image and four-host acceptance, absent-name and warm-prime
controls. The macOS cold timing passed on a single-job repeat under the same
threshold.

Every change is under `__OPENKAL__`. What LLVM decides at compile time from the
host is decided when the image starts, from what the loader states:

- the native path style is the system's (`kal_env_system`), and what follows
  from it: clangd's absolute parents and case folding, a file's real name on
  Windows, the name of an in-memory preamble;
- the program's own name is the image the loader started (`kal_env_image`),
  made absolute against the directory it started in;
- the default target is the system's, on the image's architecture;
- on macOS the SDK and the system's clang are what clangd asks `xcrun` for, as
  every Apple build of clangd does, so a command that names no SDK reaches the
  system's headers;
- a module worker is started by the loader that started this image
  (`kal_env_loader`); it forms a unit of its own and holds it to its bound as
  a memory limit (`kal_process_job_limit`, openkal 0.20), since openkal states
  no address-space ceiling; it is given its owner's identifier and ends when
  the owner has ended (`kal_process_open_id`), since a started program
  inherits no descriptor but its three streams;
- the owned module cache reads what openkal states where a POSIX system states
  an owner, a permission word and a count of names (openkal states none of
  them), syncs no directory's names (openkal has no such operation), and
  publishes a worker root's marker and `llvm::LockFileManager`'s lock file by
  a rename that does not replace, since openkal makes no second name for a
  file; how a worker group is held to a budget is `kal_process_props`' answer;
- a module worker records what it reaches of the directories it holds
  (`KAL_DIR_RECORDED`, openkal 0.23, through the C library's
  `okm_preopen_attenuate`), and a module is rebuilt when a name its worker
  found absent now exists: a header created since, earlier on the search
  path than the one the module read, which clang's validation of the BMI
  does not see, since that header is not one of its inputs;
- `/proc/self/fd` names the loader's descriptors and is not read; a file system
  is local; `<endian.h>` is the C library's;
- the physical cores and a thread's claim on the processors are openkal's
  (`kal_task_cores`, `kal_task_set_priority`, openkal 0.19), where LLVM's answer
  for an unknown target made every heavyweight pool one thread and left
  background threads at the default claim. A lock owner's identifier is the C
  library's `getpid`, the environment's since openkal-musl 0.24.0.

The engine's identity covers both series: `ci/series_identity.py --openkal` is
the `patch-series-sha256` of `clangd.okb`; a native engine's covers
`patches/series` alone. `ci/check_ledger.py` holds this ledger to the rules of
`patches/PATCHES.md`.

The Windows environment adds a shared lock beside an exclusive lock of the
same open file rather than converting it. The publication handoff takes the
shared lock first, then releases only the exclusive one, so ownership remains
continuous. The cache measurement also releases its shared scratch locks before
writing: Windows locks are mandatory, and cache payloads and leases are separate
files. The four-host acceptance and warm-prime jobs qualify this path.

Positional reads and writes on Windows use another open handle to preserve the
file's stream position. The ledger therefore locks a fixed byte beyond its
maximum data extent, where mandatory exclusion serializes ledger users without
blocking their data transfers. This range overlaps an older whole-file lock;
the cache checks positional IO while holding the lock before using the volume.
POSIX retains its existing ledger lock protocol.

Regular payload files reopened for durable publication use a writable handle
on Windows, whose file flush requires write access. Directory handles and
ordinary readers retain their existing access mode. Publication still checks
the opened nodes' identities and reports any failed flush before making the
generation stable.

## Ledger

| patch | rows | state | tests | drop |
|---|---|---|---|---|
| 0001-FEATURE-45-ok-image.patch | FEATURE-45 | steady | .github/workflows/openkal.yml (the four acceptance columns on Linux x64 and arm64, macOS arm64 and Windows x64; ci/openkal_check.py, ci/openkal_accept.py) | dropped when upstream decides the native path style, the program's own name and the default target when an image for several systems starts, or when clangd stops shipping as an ok image |
| 0002-FEATURE-45-ok-image-module-cache.patch | FEATURE-45 | steady | .github/workflows/build-test.yml warm-prime (path parity and the ratios on Linux x64 and arm64, macOS arm64 and Windows x64; ci/warm_prime_accept.py) | dropped with 0001, or when openkal states an owner, a count of names and a descriptor a started program inherits |
| 0003-FEATURE-45-ok-image-absent-names.patch | FEATURE-45 | steady | ci/module_inputs_canary.py (absent-names: on the final clangd.okb under okrun in the identity job, and on Linux x64 and arm64, macOS arm64 and Windows x64 in the acceptance jobs of .github/workflows/openkal.yml) | dropped with 0001, or when clang validates a BMI against the names its header search found absent |
| 0004-FEATURE-45-continuous-shared-lease.patch | FEATURE-45 | steady | .github/workflows/openkal.yml (four-host absent-names); .github/workflows/build-test.yml (four-host warm-prime); ci/module_inputs_canary.py; ci/warm_prime_accept.py | dropped with 0002 when upstream retains continuous lease ownership with the lock semantics stated by the environment |
| 0005-FEATURE-45-ledger-lock-outside-data.patch | FEATURE-45 | steady | ci/module_inputs_canary.py (four-host absent-names); ci/warm_prime_accept.py (four-host warm-prime); .github/workflows/openkal.yml (module import and the owned-cache measurement with positional IO) | dropped with 0002 when upstream serializes its ledger without blocking positional IO through the environment's separate handle |
| 0006-FEATURE-45-writable-payload-sync.patch | FEATURE-45 | steady | ci/module_inputs_canary.py (four-host absent-names); ci/warm_prime_accept.py (four-host warm-prime); ci/openkal_check.py (module import and parallelism through the final image) | dropped with 0002 when upstream opens payloads for durability with the access required by the environment's file flush |
