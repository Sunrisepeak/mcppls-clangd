# mcppls-clangd

A patched clangd carrying the fixes [mcpp-language-server] needs, maintained as
a small repository on top of a pinned llvm-project revision — not a fork of the
monorepo, not a vendored source tree, not a runtime integration.

The model is openkal-style: pin the upstream revision (`UPSTREAM`), carry the
divergence as a numbered patch series (`patches/`) plus drop-in new files
(`overlay/`), build with upstream CMake and with mcpp as an ok image, and
release the ok image to [mcpp-language-server]'s payload machinery. Every patch maps to one row of
the upstream-defects register ([mcpp-language-server#24]) and carries a drop
condition — when upstream lands the fix, the patch is dropped and the base is
bumped.

[clangd/clangd]: https://github.com/clangd/clangd

## Status

The 0.0.21 engine carries 43 main patches ([patches/PATCHES.md](patches/PATCHES.md))
on llvm-project 23.1.0 and reports itself as `23.1.0-mcppls.10`. Each patch maps
to rows of the upstream-defects register and has a drop condition. A release
requires every ledger entry in both series to be `steady`, as checked by
`ci/check_ledger.py --release`.
The engine ships in mcpp-language-server, which pins it by binary SHA-256
and by the source identity in `engine.json`.

From 0.0.18 the engine is also an ok image (`openkal`): one `clangd.okb` of
`x86_64-openkal` and `aarch64-openkal` that each system's okrun starts. Its tree
is `patches/series` and then the openkal series, `openkal/patches/`, which only
adapts LLVM to an ok image and is kept apart from the upstream defects and
features of `patches/` (`openkal/patches/README.md`). `openkal/clangd` is the mcpp project that builds it: its build program
runs `openkal/okgen`, which reads mcpp's contract for the target, builds
llvm-project's libraries with it through CMake, and names them for the link
mcpp performs and seals. The release measures it against the native engine on
the four systems and publishes where it is accepted (`openkal-acceptance.json`);
mcppls uses `clangd.okb` where it is.

The separate warm-prime check records readiness latency, CPU and complete
page faults against native engines built from the same source, in a comparison
run that is dispatched by hand; its [policy](ci/performance-policy.md) states
the sampling rule, the gates and when a release carries such a run.
The remaining OKE/OKB performance work is tracked in
[mcppls issue 77](https://github.com/Sunrisepeak/mcpp-language-server/issues/77).

From 0.0.21 a release publishes only the ok image. The native engines are built
for the series' tests (linux-x64, on every change) and for comparison runs (all
four), and are not released; 0.0.20 is the last release with native archives,
and `v0.0.17`'s remain the acceptance reference.

| Platform | Built on | Runs on |
|---|---|---|
| `linux-x64` | Ubuntu 20.04 rootfs, Clang 12 | glibc 2.31 and later; libstdc++ linked in |
| `linux-arm64` | Ubuntu 20.04 rootfs, Clang 12 | glibc 2.31 and later; libstdc++ linked in |
| `darwin-arm64` | macOS 15, deployment target 12.0 | macOS 12 and later |
| `win32-x64` | Windows Server 2022, MSVC | Windows x64; static CRT, no separate runtime |
| `openkal` | Ubuntu 24.04, mcpp (`openkal/clangd`), clang 23 for `x86_64-openkal` and `aarch64-openkal` | every system an okrun serves: one `clangd.okb` of both architectures (`.github/workflows/openkal.yml`) |

A release tag `v<version>` builds and publishes
`clangd-<engine version>-openkal.tar.gz` and `openkal-acceptance.json`
(`.github/workflows/release.yml`); its changelog entry names its comparison run.
Raw evidence is not kept in the repository: `tests/evidence/README.md` says
where each release's archive is, and `patches/HISTORY.md` maps the incremental
patch numbers older notes use to the current series. The plan and architecture
live in [.agents/docs](.agents/docs).

## Integrating with mcppls

A change here reaches users through mcpp-language-server's payload, so it is
tested there before it is released:

1. A PR's CI (`build-test`) packages the ok image's part as a release does,
   with its proved `engine.json`, as the artifact `clangd-openkal`.
2. The mcpp-language-server PR that takes the change names that run in
   `packaging/engine-candidate.json`; its CI assembles every payload from those
   parts and runs its whole suite on them
   ([docs/92-release.md, "A new engine"][new-engine]).
3. Only when both PRs are green is this PR merged and tagged. The release
   rebuilds the same source; the product then pins the released archives and
   drops the candidate file.

A patch that changes behaviour the product relies on, or a feature in
`engine.json`, is not merged on this repository's CI alone.

[new-engine]: https://github.com/Sunrisepeak/mcpp-language-server/blob/main/docs/92-release.md#a-new-engine

## License

Same as LLVM: Apache License v2.0 with LLVM Exceptions (see [LICENSE](LICENSE)).
Patches inherit it; each patch documents which register row it carries.

[mcpp-language-server]: https://github.com/Sunrisepeak/mcpp-language-server
[mcpp-language-server#24]: https://github.com/Sunrisepeak/mcpp-language-server/issues/24
