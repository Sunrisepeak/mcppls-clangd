# mcppls-clangd

A patched clangd carrying the fixes [mcpp-language-server] needs, maintained as
a small repository on top of a pinned llvm-project revision — not a fork of the
monorepo, not a vendored source tree, not a runtime integration.

The model is openkal-style: pin the upstream revision (`UPSTREAM`), carry the
divergence as a numbered patch series (`patches/`) plus drop-in new files
(`overlay/`), build with upstream CMake, release per-platform binaries using
the same build paradigm as [clangd/clangd]'s releases, feeding
[mcpp-language-server]'s payload machinery. Every patch maps to one row of
the upstream-defects register ([mcpp-language-server#24]) and carries a drop
condition — when upstream lands the fix, the patch is dropped and the base is
bumped.

[clangd/clangd]: https://github.com/clangd/clangd

## Status

The 0.0.12 engine carries 25 patches ([patches/PATCHES.md](patches/PATCHES.md))
on llvm-project 23.1.0 and reports itself as `23.1.0-mcppls.0`. Each patch maps
to rows of the upstream-defects register and has a drop condition; every patch
is `steady`, which `ci/check_ledger.py --release` requires before a release.
The engine ships in mcpp-language-server 0.0.12, which pins it by binary SHA-256
and by the source identity in `engine.json`.

| Platform | Built on | Runs on |
|---|---|---|
| `linux-x64` | Ubuntu 20.04 rootfs, Clang 12 | glibc 2.31 and later; libstdc++ linked in |
| `linux-arm64` | Ubuntu 20.04 rootfs, Clang 12 | glibc 2.31 and later; libstdc++ linked in |
| `darwin-arm64` | macOS 14 | macOS 12 and later |
| `win32-x64` | Windows Server 2022, MSVC | Windows x64; static CRT, no separate runtime |

A release tag `v<version>` builds and publishes each platform's
`clangd-<engine version>-<platform>.tar.gz` (`.github/workflows/release.yml`).
Raw evidence is not kept in the repository: `tests/evidence/README.md` says
where each release's archive is, and `patches/HISTORY.md` maps the incremental
patch numbers older notes use to the current series. The plan and architecture
live in [.agents/docs](.agents/docs).

## License

Same as LLVM: Apache License v2.0 with LLVM Exceptions (see [LICENSE](LICENSE)).
Patches inherit it; each patch documents which register row it carries.

[mcpp-language-server]: https://github.com/Sunrisepeak/mcpp-language-server
[mcpp-language-server#24]: https://github.com/Sunrisepeak/mcpp-language-server/issues/24
