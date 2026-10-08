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

Implemented (Phase 0 complete + the UP-25 core fix, first stage). The plan and
architecture live in [.agents/docs](.agents/docs); the carried patches are in
[patches](patches) with their ledger; CI builds and verifies them per platform
(see `.github/workflows`). The carried clangd reports itself as
`23.1.0-mcppls.0`. See [PR1](https://github.com/Sunrisepeak/mcppls-clangd/pull/1)
for the full review trail.

The 0.0.12 Part 2 target matrix is Linux x64, Windows x64 and Apple Silicon
macOS. Implementation and performance qualification proceed on local Linux
first, followed by the other native targets. Intel macOS is outside this
iteration; historical evidence is retained without claiming its failures fixed.
The current experimental engine is not release-qualified and PRs remain draft.

## License

Same as LLVM: Apache License v2.0 with LLVM Exceptions (see [LICENSE](LICENSE)).
Patches inherit it; each patch documents which register row it carries.

[mcpp-language-server]: https://github.com/Sunrisepeak/mcpp-language-server
[mcpp-language-server#24]: https://github.com/Sunrisepeak/mcpp-language-server/issues/24
