# Patch ledger

One entry per carried patch: the register rows it carries, its state, its test
map, and its drop condition. `ci/check_ledger.py` enforces this file against
`patches/series` (plan doc §3, layout principle 3; verification map:
fix-register doc §1).

States: `draft` → `stabilizing` → `steady` → `upstream-submitted` → `landed (dropped)`.
Only `steady` rides a release. Row ids never appear inside patch code or tests —
they live here and in patch *filenames* only; a filename carries the patch's
primary row, the `rows` column every row it serves.

This series carries upstream defects and product features of every engine. What
only an openkal ok image needs is the openkal series, `openkal/patches/`
(its ledger and boundary are in `openkal/patches/README.md`), applied after this
series for the ok image alone.

A patch is **steady** when the series it belongs to, applied to the pinned
tarball, builds on every release platform (`build-test`), every test its row
maps passes in that run, the Ubuntu 20.04 floor package passes its runtime
controls, and no known negative remains open against it. A change to a steady
patch returns it to `stabilizing` until the same run passes again.
For the 0.0.20 additions, [build-test run 42155475833](https://github.com/Sunrisepeak/mcppls-clangd/actions/runs/42155475833)
passed every release-platform build and mapped native test, both Ubuntu 20.04
runtime packages, all four OpenKal acceptances and all four warm-prime gates.
The macOS warm-prime gate passed on a single-job repeat after one cold timing
outlier; the threshold was not changed.

## The 0.0.12 series

The 0.0.12 series carries 25 topic patches. They were regrouped from 74
incremental patches without changing the patched tree (both apply to
`a2e92ba00e6666eaa5d1f975a4bd65b80537dbab`); each multi-change patch lists the
changes it combines in its message. Running the product against the engine
since then found the following, each fixed in the patch it belongs to:

- 0014, scan memo: a hit replays a file's observations through one handle, and
  does not read again a header that is on disk with the identity, size and
  modification time it had, last modified well before the scan (the metadata
  clang trusts for a module's inputs). A hit on `std.cppm` no longer reads and
  hashes every libc++ header.
- 0014, admission: a scan whose driver read a configuration file beside its
  compiler (an xlings or mcpp LLVM's `clang++.cfg`) is admitted, its bytes
  replayed like any input. A command whose target is MSVC and that names its
  Visual C++ tools and Windows SDK, or Darwin and names its SDK (as
  mcpp-language-server's do), is admitted on any host; only Linux hosts and
  targets were. Either refusal left every file mixing headers with module
  imports (Qt, `<windows.h>`) without a verified preamble, so all its headers
  were parsed again for each request. The first input that replays differently
  is logged.
- 0017, module worker: a command directory that does not exist yet is reported
  and the build goes on, as an in-process build does.
- 0019, owned cache: a stable generation whose files changed on disk is
  skipped instead of failing the module for good. A clangd started with
  another payload bound (a changed cache budget) adopts the ledger with it
  instead of failing every module build; charges above a lowered bound wait
  for space like other pressure. A lookup tries the slot its key was last
  found in before the others: each slot looked at costs a lease and a ledger
  read, which made every prerequisite of a request about 12 ms to reuse (a
  completion after an autosave waited 1-2 s on ux-xlings for 100 of them). An
  admission scans the ledger after checking its identity once, not at each
  slot, and its caller is told of pressure before the first wait.
- 0021, published prerequisite generations: a consumer binds to its producers'
  names and bytes (a digest read once per publication), not to their file
  identity or the path they were published to. A producer built again to the
  same bytes, a lost or evicted BMI, kept no importer: every one was rebuilt
  (ux-mcpp U11: 42 importers of `mcpp.ui` after its BMI was removed, recovery
  7 s in 0.0.11, 25 s here). The module files last built for a file are kept
  by the builder (32 files at most, let go of when admission meets pressure):
  a set dropped for a moment, an import being typed or a bounded build
  answered late, was copied again module by module, a reservation and a full
  BMI write each.
- 0023, textual preamble: a preamble whose prefix another scan records with
  another key holds while the PCH construction's own reads replay unchanged
  (the key is then remembered), and a preamble found incompatible says which
  check failed, down to the file `PrecompiledPreamble::CanReuse` found changed
  (an optional reason out-parameter). Each new scan of a `<windows.h>` prefix
  recorded its inputs differently: the first edit of such a file rebuilt its
  preamble (3.6 s) and completion parsed every header meanwhile (1-3 s each).
- 0023, textual preamble audit (and 0025 for every replay): a directory is
  compared by its name and type only, since the temporary directory the
  preamble itself is written to changes its time and size, and an overlay of
  open drafts makes up the rest for the directories holding them; nor is the
  main file, whose draft changes with each keystroke during the build and
  whose prefix the audit proves apart. Either declined the preamble and built
  it again without one. A status that replays differently is logged with the
  fields that changed.
- 0025, completion: inside the preamble region or the module and import
  declarations (an import line being typed, a blank line among them) the
  prerequisites are not rebuilt. An import added since the preamble that
  nothing in the project builds keeps the preamble's modules, and an import
  being typed is looked for last when deciding whether a file has a buildable
  import. The rebuild an edited dependency needs is waited for 250 ms; past
  that the completion is answered from the modules as they were and the
  rebuild goes on for the next request. A module newly imported is still built
  for the answer. A draft whose text after its preamble holds no directive and
  no module declaration is scanned as its preamble, a scan that stays memoized
  while only the body changes, plus the `import` declarations in that text:
  typing in such a file no longer preprocesses all its headers again (seconds
  per keystroke with `<windows.h>`). One document update or one completion
  replays each memoized scan once, however many of its queries ask for it
  (`ModuleScanEpoch.h`); a preamble build replays afresh.
  `ExternalUnqualifiedNamesPreserveScopesAndUsing` compares, for an empty
  pattern, only the names its header declares (the ordinary lookup lists
  target predeclarations and macros differently for a preamble and a main file
  on x86_64-pc-windows-msvc).

The engine also proves `unresolved-import-recovery` on its package
(`ci/unresolved_import_canary.py`): a module unit importing a module nothing
provides leaves its importer answering. The tree is now
`3e8bb5b08e63c30f7e04391a07c04c0359a86c7b`.
The incremental history and the raw evidence it produced are in the `archive/0.0.12-joint` branch and the `evidence-0.0.12`
release (`tests/evidence/README.md`).

## The 0.0.13 additions

Three patches follow the 0.0.12 series, for what running the product on large projects found
(mcpp-language-server's 0.0.13 design). The engine reports itself as `23.1.0-mcppls.1`.

- 0026, rebuild reasons: before building a module, clangd says at info why the BMI it had is not
  reused (none for this command and these prerequisites, and how many were built with others, or
  the first problem a reporting read of the stale BMI finds: the input that changed). Each file's
  prerequisites say what they cost: modules reused, built and failed, and the time in reuse
  checks, builds and the rest. Why a preamble is not compatible is logged at info.
- 0027, bounded waits: completion in a module importer waits for its first preamble up to
  `--completion-first-preamble-wait-ms` (600) and for a newly imported module up to
  `--completion-module-wait-ms` (250); past them it answers as without them, marked incomplete,
  while the builds go on.
- 0028, partial prerequisites: one module that does not compile no longer leaves its importers
  with no module at all. The others are built and used, the failure is reported with the
  compile's first error, and the set is tried again once the failed unit's source changes.

`ci/module_resilience_canary.py` proves all three on the package (`partial-prerequisite-modules`,
`module-rebuild-reasons`, `bounded-module-wait` in `engine.json`). The tree is now
`d5ff4a25edade769a0a222e72abcdfc72c04fad7`.

## The 0.0.14 additions

One patch, for what the 0.0.13 product's CI found on Windows: typing in a module unit whose global
module fragment includes a platform header, with an importer open, left the typed file's
completions at the server's one-second deadline. The engine reports itself as `23.1.0-mcppls.2`.

- 0029, a module unit's body: a draft's body is scanned as its preamble plus its imports when it
  holds no directive and no module declaration; a module unit's body starts with its module
  declaration, so every module unit was scanned whole on every keystroke and completion, its
  global module fragment's headers preprocessed again each time. The declaration, and the imports
  right after it, now belong to the scanned prefix (a module unit typed in: completion's module
  validation 37 ms to 0.1 ms on Linux).

No feature is declared for it: it changes how fast, not what, the engine answers. The tree is now
`8992c4ec675d717eaef4c4a59dbaa73789da5ae2`.

## The 0.0.15 additions

Three patches, for what makes a completion and a second opening slow on Windows: every check of whether
a memoized scan or a BMI is still good is a stat or an open per input file, and a stat on Windows opens
a handle and resolves its final path; and a BMI whose global module fragment includes a platform header
carried every declaration of it. The engine reports itself as `23.1.0-mcppls.3`.

- 0030, where inputs come from: under a store given with `--managed-input-root`, a file belongs to a
  package version (`<store>/<package>/<version>/`) checked by the version's markers, which its package
  manager rewrites whenever it changes the version; under a system root of the command (`-isystem`,
  `-idirafter`, the sysroot, the driver's toolchain, `INCLUDE`, the Windows SDK and Visual Studio's
  headers) an input is replayed once per session, as clang's
  own module input validation skips system inputs; everything else is checked every time, as before,
  and what the command searches as user headers, its directory and the file's win over the toolchain's
  root, which is no system root when the project lies within it.
  The validation cache checks outside its lock. With `--module-memo-dir` the verdicts and scans are
  written to a directory and read back by the next session, each checked again before it is used.
- 0031, costs: a completion in a module importer that takes 200 ms or more logs where its time went
  (input checks by source, the wait for modules); `--max-retained-asts` sets how many ASTs of files not
  being edited are kept (three).
- 0032, the reduced BMI: the declarations of an `extern "C" { }` or `extern "C++" { }` block in the
  global module fragment that nothing in the module reaches are left out, as those of a namespace
  there already were. Platform and C library headers declare almost everything in such blocks, so a
  module unit including `<windows.h>` wrote all of it (9.5 MB reduced or not for a header of 20,000
  declarations; 20 KB now), and a completion in an importer of many such modules loaded every copy
  (2.2 s for `::` in an importer of 25 of them; 0.28 s now). No feature is declared for it: it changes
  how large a BMI is, not what the engine answers.

`ci/module_inputs_canary.py` proves 0030 and 0031 on the package (`managed-input-roots`,
`persistent-module-memos`, `retained-asts-option` in `engine.json`);
`clang/test/Modules/reduced-bmi-linkage-spec-in-gmf.cppm` covers 0032. The tree is now
`79b44aac3cc120f9d2cf52a7c1f02e84a7113bff`.

## The 0.0.16 additions

Three patches, for what keeps a completion in a module importer slow once its modules are built, and
for completions that wait behind other files' builds. The engine reports itself as `23.1.0-mcppls.4`.

- 0033, a check that holds: with `--module-input-recheck=<seconds>`, a check that found the inputs
  of a memoized scan or a BMI verdict as they were holds for that long while the client reports no
  file change; a saved document, or a watched file, makes the next check read them all again (an edit
  too, with `--use-dirty-headers`). The BMI itself is checked every time. A change the client does not
  see is found after the interval, as clang's once-per-build-session validation finds one at the next
  session. The default, 0, checks every time. A slow completion's cost line counts the checks that
  held (an importer of 25 modules: its project inputs, re-statted for every completion, 0.7-1.0 s
  on Windows).
- 0034, the preamble's declarations: with module support, Sema was made to load the preamble's
  declarations for every completion, since the index has no symbols of imported modules; a file that
  imports no module has them all in the index, and now completes as without module support (a
  header-heavy file: 0.59-0.70 s per completion to about 0.4 s). "Imports" is what the request sees:
  a module imported since the preamble was built, typed in the file or brought in by a header it
  includes, is built for the request alone and still loaded by Sema.
- 0035, interactive actions: with `--interactive-actions=<N>`, code completion and signature help run
  on N slots of their own instead of queueing behind AST and preamble builds of other files. The
  default, 0, counts them with the others.

`ci/module_inputs_canary.py` proves 0033 and 0035 on the package (`module-input-recheck`,
`interactive-actions` in `engine.json`) and 0034 (a file that imports no module gets as many results
from Sema with module support as without); 0034 changes how fast, not what, the engine answers, and
declares nothing. The tree is now `534729c792963c194c4afd6675f6befa89e63c62`.

## The 0.0.17 additions

Two patches, for what an idle clangd costs and for what sanitizer builds of the module workers could
not do. The engine reports itself as `23.1.0-mcppls.5`.

- 0036, memos that did not change: the memo store (0030, `--module-memo-dir`) wrote every 30 seconds
  by copying both caches and building the JSON of every memo, and only then found nothing had changed
  since the last write. An idle clangd did this all the time, with a project's 30 MB of memos. A write
  now compares the counts the caches' snapshots report first, and copies and serializes nothing when
  they are those it last wrote: an idle clangd's CPU fell by an order of magnitude in mcppls's nightly.
  Its resident memory can still grow over ten idle minutes when the allocator gave memory back just
  before them (mcpp-language-server#59, U13); 0036 did not change that growth, so the memo writes were
  not its cause, and it is not attributed yet.
- 0037, module workers under sanitizers: a module worker (0017) sets `RLIMIT_AS` to its share of the
  address-space budget; under ASan, HWASan, MSan or TSan the runtime had already mapped terabytes of
  shadow memory, so the worker's first mmap failed and every module built through a worker failed.
  The soak job's sanitizer lit runs had not built a module since the workers landed. Under a
  sanitizer on Linux the ceiling now bounds what the worker maps beyond what it has.

`clangd/unittests/PrerequisiteModulesTest.cpp` proves 0036 (`UnchangedMemosAreNotSerializedAgain`,
which fails on the store without it); the soak job's ASan+UBSan lit runs of `modules.test`,
`modules-stale-lock.test` and `modules-validation-cache.test` prove 0037. Neither declares a feature:
they change what the engine costs and where it can be tested, not what it answers. The tree is now
`d0a555c75fe557cbb2f3ff1de7ab35715b1db4f4`.

## The 0.0.18 additions

No patch of this series changes, and the tree stays `d0a555c75fe557cbb2f3ff1de7ab35715b1db4f4`. The
release adds clangd as an ok image, `clangd.okb`, whose tree is this series and then the openkal series
(`openkal/patches/`); the engine reports itself as `23.1.0-mcppls.6` on every platform and as the ok
image.

## The 0.0.22 additions

One patch is added. 0048 (UP-41): clangd's include analysis marked an include of the main file as used by the ID
of the include's *resolved* file entry and dereferenced the lookup behind an assert alone
(`computeIncludeCleanerFindings`, two sites). The ID is found by the file's identity, and the resolved entry is
made from the include's canonical path, which need not be the path the header was entered by; a file system
that gives the two paths two identities leaves the include structure without an ID for that entry. The ok
image met exactly that on Windows 11 24H2 (builds 26100 and 26200), where openkal-windows through 0.21.0 gave
an open file another volume word than its name (corrected in openkal-windows 0.22.0): the engine's own probe of
0039 printed "an open file is not the node its name refers to", and the image, built with libc++'s fast
hardening, ended by an illegal instruction (`0xC000001D`) in `optional::operator*` on the first build of any
module unit that includes a header in its global module fragment, imports a module and uses a type of the
header ([mcpp-language-server issue 86](https://github.com/Sunrisepeak/mcpp-language-server/issues/86); the
frames were named from the image's own symbol table under a debugger on a `windows-2025` runner). A native
build read an indeterminate ID there instead. The condition needs the header to be entered with the main file
-- the skipped preamble of a file that imports modules -- since a textual preamble's stat cache answers both
paths alike. An include is now marked by the ID it was entered with, taken from the include itself; the
resolved entry is asked only for an include that has none; and where neither answers, no include is reported
unused. `mayConsiderUnused` no longer dereferences a failed lookup of the header's real path. The unit test
gives a file one identity where it is opened and another by name and enters the headers with the main file;
the end-to-end case (`tests/cts/gmf_include_analysis.cpp`) is the report's shape -- a module unit, a header
under a search path that is not its resolved path, an import, a use -- and runs in every system's acceptance
and on `windows-2025`, the hosted runner of build 26100, which no job of this repository ran on before. The
engine reports itself as `23.1.0-mcppls.11` and declares the feature `include-ids-by-entry`.
The comparison run of this addition is the one the changelog's 0.0.22 entry names: every native engine, both Ubuntu
20.04 packages, the four acceptances with the end-to-end suite, and the `windows-2025` gate with its control. On that
runner (10.0.26100) the image with 0048 passes the case with the engine reporting two identities, and 0.0.21's image
ends on it ("server stdout closed"); of the rest of the suite there, `module-cache-lease` alone fails, the owned cache
being the thing 0039 steps aside from while a file has two identities.

## The 0.0.21 additions

No patch of either series changes. The ok image is built with zlib, as the native engines are: llvm-project is
configured with the headers of `compat.zlib-ng` (zlib's API, zlib-ng's implementation with NEON and SSE2
paths chosen at compile time) and the image links the library that dependency builds for the target
(`openkal/okgen`, `openkal/clangd/mcpp.toml`). An index shard written by an engine with zlib compresses
its string table, and the image built without it discarded every such shard ("Compressed string table, but zlib
is unavailable") and indexed the files again. The image is built over openkal-platform 0.24.3 (its runtime keeps a path's volume; its okrun.exe reserves a thread's stack for the image's main thread on Windows), stated once in
`openkal/clangd/mcpp.toml`, from which `ci/scripts/probe-platform.sh` writes every probe of CI. The warm-prime
gate is the median of four alternating native/image pairs under a registered sampling rule
(`ci/performance-policy.md`), measured in a comparison run; the 0.0.20 cold-CPU exception has expired. From
0.0.21 the engine is released only as the ok image. The engine reports itself as
`23.1.0-mcppls.10` on every platform and as the ok image.

## The 0.0.20 additions

Five patches are added. 0038: the provider index is built from a mangled inventory once rather than once per
request; the facade a request is given keeps its mangler's name when ModulesBuilder gives it the request's file
system, where the first form of the patch lost it and mangled every command again. Every request that asked which source provides a module mangled every command of the database
before finding its index unchanged; in mcppls's own project (481 commands) that ran twice for every file
the server prepared, a third of the engine's time while 176 modules were made ready, and clangd.okb took
30 s to be ready again in a new session where the native clangd took 5 s. The ok image is built over
openkal-platform 0.20.2, whose C library serves threads that allocate together from their own caches and
compares strings a word or a vector at a time (openkal-musl 0.25.0); clangd.okb had passed every
acceptance case while using less than one of four processors behind the C library's one allocation lock,
and the acceptance now indexes a dozen files on four workers at once (`parallel-index`), within 1.3 times
the native clangd's time. 0039: the owned module cache and supervised workers follow what the system
provides (ModuleCachePlatform: open-file locks, relative directories, removal while open), measured once in each
cache directory (APFS reports an open directory whose name was removed with the count it had, and a directory
has one name there), where they were compiled for Linux alone; macOS and the ok image take them, and the native
Windows engine keeps a copy of each BMI for each reader. A reader holds one open file for each module it reads,
so the number of files a process may hold open is raised to the system's most, and a worker's leases share one
open cache of their root (a cache for each lease exceeded macOS's 256 open files and the ok image's 64 open
directories for a module importing 175). 0040: a module in the owned cache is read where it was published,
under its own lease, where each reader was given a copy. 0041: a worker's end is seen when it happens: the
worker's owner monitor slept ten milliseconds between looks and the worker waited for it on the way out, and
the parent looked at a running worker every ten milliseconds; a cold build of 176 modules was ready in 3.4 s
instead of 4.9 s (the median worker 9 ms instead of 20 ms). 0042: a worker is held to its share of the address-space
bound by watching it where the system holds no ceiling: on macOS every process maps hundreds of GiB before
main, the kernel refuses a ceiling below that (every worker of the native engine failed with "Invalid
argument"), and one above it holds nothing, so clangd watches the worker's physical footprint and ends it past
its share. The openkal series adds the answers openkal gives
the owned cache and its workers (`openkal/patches/README.md`), and the image is built over openkal-platform
0.21.1 (openkal 0.21; openkal-musl 0.26.0, whose allocator is mimalloc and whose open directories report their
identity; openkal-image 0.3.1, whose loader maps an image's instructions from its file and whose runner admits
an okb member it has compared before without reading it). The ok image's cold
and warm sessions of the warm-prime workspace are within 1.04--1.12 times the native engine's ready time,
processor time and page faults (Linux x86_64; `ci/warm_prime.py`, `ci/warm_prime_accept.py`). The engine
reports itself as `23.1.0-mcppls.9` on every platform and as the ok image.

## The 0.0.19 additions

No patch of this series changes, and the tree stays `d0a555c75fe557cbb2f3ff1de7ab35715b1db4f4`. The
openkal series learns at run time what LLVM and clangd decide at compile time for a host they know: the
physical cores, which sized every heavyweight pool of the ok image to one thread; a thread's claim on the
processors; and on macOS the SDK clangd asks `xcrun` for, without which a command naming no SDK reached no
system header (`openkal/patches/README.md`). The image is built over openkal-platform 0.20.1: a program's
identifier and its lock files are the environment's (openkal-musl 0.24), and on macOS a context's identity
costs no system call (openkal-macos 0.17.1), which an image's C library asks for at every thread-local
access. The engine reports itself as `23.1.0-mcppls.7` on every platform and as the ok image.

| patch | rows | state | tests | drop condition |
|-------|------|-------|-------|----------------|
| 0001-UP-05-backport-std-predefined-decl-merge.patch | UP-05 | steady | clang/test/Modules/pr218152.cppm | upstream landed it in 23.1.1 (52774473867e); drop when the base is bumped past 23.1.0 |
| 0002-UP-25-module-validation-memo.patch | UP-25 | steady | clangd/test/modules-validation-cache.test; clangd/test/modules-validation-overlay.test; tests/cts/completion_quality.cpp | upstream memoizes BMI validation for preamble reuse, keyed by precise input identity and verified against the request filesystem |
| 0003-UP-18-module-cache-locks.patch | UP-18, UP-21 | steady | clangd/test/modules-stale-lock.test; tests/cts/module_directives.cpp | upstream breaks dead-owner module locks (Windows included) and cancels lock waits when the document closes |
| 0004-UP-09-semantic-tokens-range.patch | UP-09 | steady | clangd/test/semantic-tokens-range.test | upstream implements textDocument/semanticTokens/range |
| 0005-UP-22-const-correctness-ranges.patch | UP-22 | steady | clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-ranges.cpp; clang-tools-extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-range-constraints.cpp; tests/cts/build_tree_tools.cpp | upstream validates const range consumption with instantiated constraints |
| 0006-UP-25-module-index-completion.patch | UP-25 | steady | tests/cts/completion_quality.cpp (the opt-in index path stays off; the semantic default is asserted) | upstream serves module completion without re-deserializing BMIs per request; the opt-in flag goes with it |
| 0007-UP-13-windows-crash-dumps.patch | UP-13 | steady | ci/test_windows_crash_capture.py; .github/workflows/win-crash-corpus.yml | upstream gains native crash-dump diagnostics for the LSP server |
| 0008-UP-25-module-importer-semantic-completion.patch | UP-25 | steady | tests/cts/completion_quality.cpp; tests/cts/module_completion.cpp; clangd/unittests/PreambleTests.cpp | upstream completion keeps semantic results on module importers, refreshes stale BMI views and waits for the resolved command |
| 0009-FEATURE-43-mcpp-format-style.patch | FEATURE-43 | steady | clangd/test/mcpp-format-style.test; clangd/test/mcpp-format-fallback.test | upstream supports the pinned mcpp preset or an equivalent explicit fallback configuration |
| 0010-FEATURE-44-compiler-extension-completion.patch | FEATURE-44 | steady | tests/cts/compiler_extensions.cpp | upstream offers attribute introducers, cleanup references and target-aware SEH without index-only keyword pollution |
| 0011-UP-01-module-directive-recovery.patch | UP-01, UP-12, UP-15 | steady | clangd/test/module-directive-recovery.test; clangd/test/missing-bmi-token-recovery.test; clang/test/Modules/missing-module-semicolon-location.cpp; tests/cts/module_directives.cpp; ci/module_directive_canary.py | upstream token collection, missing-BMI keyword handling and separator diagnostics recover in place |
| 0012-UP-03-module-prerequisite-dag.patch | UP-03, UP-24, UP-25 | steady | clangd/test/modules-bounded-dag.test; ci/unresolved_import_canary.py; tests/cts/module_dag.cpp; tests/cts/module_directives.cpp; tests/cts/third_party_import.cpp; tests/cts/module_cache.cpp | upstream schedules prerequisite builds as a bounded cancellable DAG with cycle rejection, third-party import fallback and reader leases |
| 0013-UP-03-module-provider-command-cache.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_scans.cpp | upstream reuses provider command facts across equivalent CDB generations |
| 0014-UP-03-module-dependency-scan-memo.patch | UP-03, UP-23 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_scans.cpp; tests/cts/module_scans.cpp; tests/cts/module_cache.cpp | upstream reuses dependency scans only after replaying every observed input |
| 0015-UP-03-module-compile-command-inputs.patch | UP-03, UP-23, UP-27 | steady | clangd/unittests/GlobalCompilationDatabaseTests.cpp; clangd/unittests/CompileCommandsTests.cpp; tests/cts/module_completion.cpp | upstream reloads response-file generations, resolves external module commands per project and preserves the GCC mapper dialect |
| 0016-UP-24-module-cache-gc-ownership-test.patch | UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp | the owned cache divergence (0017, 0019) is dropped |
| 0017-UP-03-module-compiler-workers.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_workers.cpp; tests/cts/module_workers.cpp; tests/cts/module_workers.cpp | upstream isolates module compilation in supervised, budgeted workers |
| 0018-UP-24-module-read-copy-maintenance.patch | UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_cache.cpp | upstream maintains copy-on-read orphans outside requests with bounded traversal |
| 0019-UP-03-owned-module-payloads.patch | UP-03, UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_workers.cpp | upstream owns module payloads through admission and kernel leases with cancellable bounded waits |
| 0020-UP-23-module-preamble-policy.patch | UP-23, UP-26 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_completion.cpp | upstream resolves the module preamble policy from the attached prerequisites |
| 0021-UP-20-published-prerequisite-generations.patch | UP-20, UP-03, UP-23 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_directives.cpp; tests/cts/module_dag.cpp | upstream binds consumers to published dependency generations and limits producer snapshots to their closure |
| 0022-UP-03-module-scan-exact-queries.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_scans.cpp | upstream scan recording preserves relative query spelling |
| 0023-UP-28-verified-textual-module-preambles.patch | UP-28 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/completion_quality.cpp | upstream proves textual-prefix reuse with complete PCH input and import audits |
| 0024-UP-29-gnu-standard-module-producers.patch | UP-29 | steady | clangd/unittests/CompileCommandsTests.cpp; tests/cts/module_cache.cpp | upstream dependency scanning recognizes installed GNU standard module producers |
| 0025-UP-25-selective-completion-loading.patch | UP-25 | steady | clangd/unittests/CodeCompleteTests.cpp; clang/unittests/Serialization/NamespaceLookupTest.cpp; tests/cts/build_tree_tools.cpp | upstream completion loads only names that can match the typed prefix and emits each constructor overload once |
| 0026-UP-32-module-rebuild-reasons.patch | UP-32 | steady | ci/module_resilience_canary.py | upstream logs why a prerequisite BMI is rebuilt and what a file's prerequisites cost at the default level |
| 0027-UP-31-bounded-module-completion-wait.patch | UP-31, UP-25 | steady | clangd/unittests/TUSchedulerTests.cpp; ci/module_resilience_canary.py; tests/cts/module_completion.cpp | upstream completion in module importers answers within a bound while the first preamble or a new import is still being built |
| 0028-UP-30-partial-prerequisite-modules.patch | UP-30 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; ci/module_resilience_canary.py | upstream serves an importer with the prerequisite modules that did build when one fails |
| 0029-UP-33-module-unit-body-scan.patch | UP-33, UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp | upstream keeps a module unit's dependency scan memoized while its body is typed in |
| 0030-UP-35-module-input-sources-and-memos.patch | UP-35, UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; ci/module_inputs_canary.py | upstream checks module inputs by where they come from, and keeps scan and validation memos across sessions |
| 0031-UP-36-module-completion-costs.patch | UP-36 | steady | ci/module_inputs_canary.py | upstream logs where a slow module completion's time went, and makes the retained AST count an option |
| 0032-UP-37-reduced-bmi-linkage-spec-in-gmf.patch | UP-37 | steady | clang/test/Modules/reduced-bmi-linkage-spec-in-gmf.cppm | upstream elides the unreachable declarations of a linkage specification in the global module fragment from the reduced BMI |
| 0033-UP-38-module-input-recheck.patch | UP-38, UP-35 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; ci/module_inputs_canary.py | upstream lets a client that reports file changes have module input checks hold between them |
| 0034-UP-39-preamble-load-for-module-importers.patch | UP-39, UP-25 | steady | ci/module_inputs_canary.py; clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_scans.cpp; tests/cts/module_cache.cpp | upstream forces Sema to load preamble declarations only where the index lacks them (module importers) |
| 0035-UP-40-interactive-action-slots.patch | UP-40 | steady | clangd/unittests/TUSchedulerTests.cpp; ci/module_inputs_canary.py | upstream schedules completion and signature help apart from AST and preamble builds |
| 0036-UP-35-unchanged-memos-not-serialized.patch | UP-35 | steady | clangd/unittests/PrerequisiteModulesTest.cpp | dropped with 0030 when upstream keeps module memos across sessions |
| 0037-UP-03-module-workers-under-sanitizers.patch | UP-03 | steady | tests/soak_loop.py and the soak job's ASan+UBSan lit run of the module suite (modules, modules-stale-lock, modules-validation-cache) | dropped with 0017 when upstream isolates module compilation in supervised workers |
| 0038-UP-03-module-provider-index-mangled-once.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_scans.cpp | dropped with 0013 when upstream reuses provider command facts across requests of one database generation |
| 0039-UP-03-module-cache-platform.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp (OwnedCacheDirectoryIsMeasured, OwnedInputLeasesShareTheirRootsCache); tests/cts/module_cache.cpp; .github/workflows/build-test.yml (path parity, warm-prime) | dropped with 0017 and 0019 when upstream isolates module compilation in supervised workers and owns its module payloads on every system |
| 0040-UP-03-owned-module-reads-in-place.patch | UP-03, UP-24 | steady | clangd/unittests/PrerequisiteModulesTest.cpp; tests/cts/module_cache.cpp | dropped with 0019 when upstream owns its module payloads |
| 0041-UP-03-module-worker-end-seen-at-once.patch | UP-03 | steady | ci/warm_prime.py (worker times); tests/cts/module_cache.cpp | dropped with 0017 when upstream supervises its module workers |
| 0042-UP-03-module-worker-ceiling-watched.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp (WorkerCeilingIsOwnOrWatched); the darwin-arm64 lit run of the module suite; warm-prime on macOS | dropped with 0017 when upstream supervises its module workers |
| 0043-UP-03-worker-output-native-paths.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp (ModuleWorkerOutputPathsUseTheirPathStyle); ci/module_inputs_canary.py (four-host absent-names); ci/warm_prime.py | dropped with 0017 and 0019 when upstream bounds worker outputs and owns module payloads using the host path style |
| 0044-UP-03-physical-fs-initial-cwd.patch | UP-03 | steady | llvm/unittests/Support/VirtualFileSystemTest.cpp; clangd/unittests/FSTests.cpp; ci/warm_prime.py | upstream creates independent filesystem views at the requested working directory without first resolving the process directory |
| 0045-UP-03-owned-ledger-scan-candidates.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp (OwnedLookupSeesNewKeysAcrossLedgerChunks, OwnedLookupRejectsTruncatedLedgerOnMiss, OwnedLookupRejectsAmbiguousUnusedLedgerTail); ci/warm_prime.py | upstream filters owned-cache lookup candidates from validated bounded ledger scans before acquiring leases, retaining post-acquisition identity and payload validation |
| 0046-UP-03-inline-checked-bitstream-reads.patch | UP-03 | steady | ci/warm_prime.py; BitstreamTests (unchanged upstream reader and writer tests run by ci/ci_build.sh) | upstream keeps checked buffered bitstream reads visible to BMI decoder callers without changing their bounds, refill or error handling |
| 0047-UP-03-reuse-operation-input-replay.patch | UP-03 | steady | clangd/unittests/PrerequisiteModulesTest.cpp (ScanPublicationReplayIsSharedWithinOperation, FailedScanMemoRejectsOversizedAndCanceledEntries); ci/warm_prime.py | upstream accounts complete scan publication as the operation replay and reuses normalized input classifications without skipping observations |
| 0048-UP-41-include-ids-by-entry.patch | UP-41 | steady | clangd/unittests/IncludeCleanerTests.cpp (HeaderWithAnotherIdentityByName); tests/cts/gmf_include_analysis.cpp (every system's acceptance; windows-2025 in `openkal.yml`) | upstream marks a used include by the ID it was entered with, or checks the ID of its resolved entry before using it |
