# mcppls-clangd release recipe (per platform)

Extracted from clangd/clangd's public release workflow
(`.github/workflows/autobuild.yaml`, inspected 2026-10-06) per decision D3:
fork artifacts replicate the upstream release build paradigm so they are
drop-in replacements for the binaries mcpp-language-server already bundles.
Deviations are listed at the bottom, never silent.

## Pinned source

- llvm-project `llvmorg-23.1.0` (see `UPSTREAM`)
- source tarball (codeload of the tag):
  sha256 `d8657b2a7291e518407bf13c4b41c85ef2cded2d4354097a2f451644dfc817b0`

## Common (all platforms)

```
-DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra"
-DLLVM_TARGETS_TO_BUILD="host;X86;AArch64"   # target infos needed to parse cross triples
-DLLVM_ENABLE_PLUGINS=OFF                    # clangd loads no plugins
-DLLVM_VERSION_SUFFIX=-mcppls.N              # D4: the detection contract
-DLLVM_INCLUDE_TESTS=ON                      # check-clangd is a gate (CI builds)
-DCMAKE_BUILD_TYPE=Release
-Ninja
```

clangd/clangd also sets `-DLLVM_APPEND_VC_REV=OFF` for reproducibility — we
do the same.

## linux (x64, arm64)

- inside an `ubuntu:20.04` container — the old-glibc compat floor is the
  container, not flags (upstream: `container: ubuntu:20.04`)
- `-DCMAKE_EXE_LINKER_FLAGS_RELEASE="-static-libgcc -Wl,--compress-debug-sections=zlib"`
- `linux-static-deps.cmake` equivalent: `-DCMAKE_FIND_LIBRARY_SUFFIXES=".a"`
  so `find_package` links static libs (upstream links zlib statically)
- bootstrap compiler: apt.llvm.org clang (or distro gcc); native arm64 runner
  for arm64 (clangd/clangd publishes no linux-arm64 binary; mcppls takes it
  from LLVM's own release — our fork builds it with the same recipe)

## windows-x64

- `windows-2022` runner + MSVC via `vcvars64`
- `-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded` (static CRT)
- a separate debug-symbols artifact ships the PDBs (upstream:
  `clangd-debug-symbols-*.7z`) — the `win-symbols` job reuses this channel
  for the UP-12/13/20 stack hunt

## darwin-arm64

- `macos-14` runner, default system linking, nothing special

## Packaging (all platforms)

`ci/scripts/package.sh` produces the **mcppls payload "clangd part"** layout —
identical to what `mcppls.pack.clangd` reduces an official release to:

```
dist/clangd-<version>-<platform>/
  clangd/bin/clangd[.exe]            stripped
  clangd/lib/clang/<major>/include/  clang's builtin headers, found beside clangd
  SHA256SUMS
```

## Deviations from clangd/clangd's recipe (intended, recorded)

1. gRPC / remote index stays OFF (upstream vendors gRPC for
   `--remote-index-address`; mcppls does not use it — one less dependency to
   bootstrap). `-DCLANGD_ENABLE_REMOTE=OFF` equivalent by default.
2. Only the `clangd` binary is packaged — not `clangd-indexer` or the
   index-server tools.
3. The version suffix `-mcppls.N` (D4).
4. Our patch series applies on top of the pinned ref.
