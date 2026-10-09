# 0067: installed GNU standard-module producer dialect

Source commit: `a06708402f42154fea6cab9c012fc74d394cdb56`.
Base: `8243fa6546e7ab5ee4b59c980ff9317d87745cb0` (includes 0063/0064/0065).
Private tree: `/tmp/mcppls-gnu-std67`; no shared source/archive/product writes.
Registration: UP-29, https://github.com/Sunrisepeak/mcpp-language-server/issues/24#issuecomment-6058644891 .

The real Qt CDB's GNU `bits/std.cc` producer has canonical `g++`, `-fmodules`,
C++23, ordinary GCC sysroot/binutils flags and no mapper. Patch 0061's mapper
marker intentionally excludes that command. Clang then implicitly discovers
its builtin header module map, enters `_Builtin_inttypes`, and dependency
scanning fails in the actual GCC sysroot with unknown `intmax_t`/`uintmax_t`.

This patch recognizes only canonical GNU std/std.compat producer paths in the
same GCC installation (`bin/<GCC spelling>` and
`include/c++/<numeric version>/bits/std[.compat].cc`), with an unconditional
actual `module; ... export module std[.compat];` source role. It adds only
`-fno-implicit-module-maps`, preserving `-fmodules` and normal compiler
validation. Any explicit Clang module map/file/prebuilt/implicit-map request,
`-fno-modules`, unknown language/header-unit role, unsupported filesystem
observation, foreign installation, source link escape or missing file retains
the original command.

The helper runs after creation of the scanner's actual RequestFS and in the
builder's actual TFS view before command identity and worker invocation. It
introduces no CommandMangler layout/callback, no host-filesystem bypass, no
source-role cache and no compiler execution. It admits known regular source
files at most 128 KiB, checks path and opened-file identity/size/mtime before
and after the read, validates returned size, and lexes at most 32 KiB. Actual
GNU std.cc is 113,108 bytes. `vfs::File::getBuffer(FileSize)` is a size hint:
this is source admission/recognition, **not** a hard allocation/read guarantee
for arbitrary custom VFS implementations or a resource-goal completion.

Changed production TUs: CompileCommands.cpp, ProjectModules.cpp,
ModulesBuilder.cpp. Public header change is only a free function declaration;
no existing object layout or vtable changes. These three TUs and the changed
CompileCommandsTests TU compiled privately against default root65 object
consumers and the immutable root46 support archives. No joint66, clean recipe
or native qualification claim is made.

Focused unit evidence: 84 CommandMangler + PrerequisiteModulesTests pass.
New controls cover valid std/std.compat, explicit Clang inputs, disabled
modules, non-C++/header roles, Clang driver/aliases, ordinary/user std paths,
other installations, same-inode/size/mtime changed role, dirty overlay role,
conditional role, late role beyond lexical bound, oversized source and source
symlink escape. No threshold/assertion relaxation.

Real normal-project evidence uses a byte-identical copy of the original Qt
CDB in separate private directories. All argv/cwd/source spellings are
preserved; only clangd's CDB selection isolates its owned BMI cache. The
maintained std-qualified context measures cold open, settled warm, one edit
and settled warm; each selected vector insertion is compiled with the original
GCC command and module mapper. Before: two std scan failures, textual std
fallback, one owned nlohmann PCM. After: no std scan failures, a real owned std
PCM plus nlohmann PCM, valid Sema vector class-kind 7 and GCC insertion exits 0.
Before also yields valid Sema vector via header exposure: this patch must not
claim that completion existence alone proves the dialect defect fixed.

All observed requests exceed the existing 200 ms context budget, including
warm requests. This is **not** a Qt performance release qualification or a
whole-context/native/resource gate. Existing compiler validation remains
necessary. Directly editing/checking std.cc as the main editor TU is outside
this dependency-producer scan/build slice.

Raw captures and hashes are indexed in `tests/evidence/gnu-standard-module-producer-dialect.json`. Generated
private BMI caches remain outside the export. No original project/root cache
was removed.

## Integration status

Stabilizing. The private source and local controls above precede root joint66
integration. Root is rebuilding all affected consumers with the newer headers;
that rebuild and its real context/native matrix are not included in this
qualification. The ordered series keeps 0067 after 0066.

The role has no device/inode/size/mtime cache: same-size, same-inode and restored
full-mtime source changes are re-read and rejected when the module role changes.
The stated 128 KiB limit is whole known-size admission, followed by returned
buffer checks, and the lexical prefix is separately limited to 32 KiB. It does
not establish a hard allocation limit for an arbitrary VFS implementation.

Root joint0066–0067 integration now rebuilds all141 affected header consumers and final four0067 TUs, links both binaries, and passes92 focused tests. Actual std and JSON contexts both produce audited import-free PCHs, real Sema and all8 GCC insertions. std warm180–194ms/edit265ms still does not qualify the200ms context gate. [Exact final source/binary/hash evidence](../tests/evidence/joint66-67/README.md). Earlier private65 evidence above remains independently scoped; no native/full-context qualification is inferred.
