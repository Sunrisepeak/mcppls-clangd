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
  publishes a worker root's marker by a rename that does not replace, since
  openkal makes no second name for a file; how a worker group is held to a
  budget is `kal_process_props`' answer;
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

## Ledger

| patch | rows | state | tests | drop |
|---|---|---|---|---|
| 0001-FEATURE-45-ok-image.patch | FEATURE-45 | steady | .github/workflows/openkal.yml (the four acceptance columns on Linux x64 and arm64, macOS arm64 and Windows x64; ci/openkal_check.py, ci/openkal_accept.py) | dropped when upstream decides the native path style, the program's own name and the default target when an image for several systems starts, or when clangd stops shipping as an ok image |
| 0002-FEATURE-45-ok-image-module-cache.patch | FEATURE-45 | stabilizing | .github/workflows/build-test.yml warm-prime (path parity and the ratios on Linux x64 and arm64, macOS arm64 and Windows x64; ci/warm_prime_accept.py) | dropped with 0001, or when openkal states an owner, a count of names and a descriptor a started program inherits |
