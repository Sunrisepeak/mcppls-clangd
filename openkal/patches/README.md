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
- a module worker is started by the loader that started this image
  (`kal_env_loader`), with no address-space ceiling, which openkal does not
  state;
- `/proc/self/fd` names the loader's descriptors and is not read; a file system
  is local; `<endian.h>` is the C library's.

The engine's identity covers both series: `ci/series_identity.py --openkal` is
the `patch-series-sha256` of `clangd.okb`; a native engine's covers
`patches/series` alone. `ci/check_ledger.py` holds this ledger to the rules of
`patches/PATCHES.md`.

## Ledger

| patch | rows | state | tests | drop |
|---|---|---|---|---|
| 0001-FEATURE-45-ok-image.patch | FEATURE-45 | stabilizing | .github/workflows/openkal.yml (the four acceptance columns on Linux x64 and arm64, macOS arm64 and Windows x64; ci/openkal_check.py, ci/openkal_accept.py) | dropped when upstream decides the native path style, the program's own name and the default target when an image for several systems starts, or when clangd stops shipping as an ok image |
