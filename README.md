# mcppls-clangd

A patched clangd carrying the fixes [mcpp-language-server] needs, maintained as
a small repository on top of a pinned llvm-project revision — not a fork of the
monorepo, not a vendored source tree, not a runtime integration.

The model is openkal-style: pin the upstream revision (`UPSTREAM`), carry the
divergence as a numbered patch series (`patches/`) plus drop-in new files
(`overlay/`), build with upstream CMake, release static per-platform binaries
for [mcpp-language-server]'s payload machinery. Every patch maps to one row of
the upstream-defects register ([mcpp-language-server#24]) and carries a drop
condition — when upstream lands the fix, the patch is dropped and the base is
bumped.

## Status

Planning. The overall plan and architecture (v1, for review) lives in
[.agents/docs](.agents/docs) and is under review as PR1. Nothing is built yet.

## License

Same as LLVM: Apache License v2.0 with LLVM Exceptions (see [LICENSE](LICENSE)).
Patches inherit it; each patch documents which register row it carries.

[mcpp-language-server]: https://github.com/Sunrisepeak/mcpp-language-server
[mcpp-language-server#24]: https://github.com/Sunrisepeak/mcpp-language-server/issues/24
