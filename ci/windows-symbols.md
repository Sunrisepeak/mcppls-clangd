# Linked Windows symbols, with identity evidence

The old symbol workflow only set CMAKE_MSVC_DEBUG_INFORMATION_FORMAT. That
controls compiler debug information; the Release executable linker did not
receive /DEBUG, and collecting every *.pdb could select compiler PDBs rather
than a usable clangd linked PDB. Missing symbols produced a warning artifact,
which was not crash-investigation evidence.

The first native run (37674009173) exposed a second defect: LLVM_ENABLE_PDB
adds /Zi, and parallel sccache/CL invocations sharing a target compiler PDB
failed C1041 even with /FS. The symbol recipe now uses CMake CMP0141 NEW and
Embedded debug information (/Z7), the per-object format supported by sccache.
It explicitly links /DEBUG /OPT:REF /OPT:ICF, preserving Release optimization
and generating the executable's linked PDB without shared compiler PDB writes.
LLVM_ENABLE_PDB stays off to avoid its unconditional /Zi addition.
Each job builds llvm-readobj
and llvm-pdbutil, checks the executable CodeView GUID and age against the linked
bin/clangd.pdb, and requires debug/public symbol streams. It then launches CDB
at its initial debugger stop, reloads clangd symbols, and requires an addressed
clangdMain symbol result. An echoed lookup command cannot satisfy the check.
The artifact carries that exact executable/PDB pair, their SHA-256 values,
raw inspection output, CDB log and engine-build.json; absent or mismatched
symbols fail the workflow. Compiler PDBs are not collected.

Local Linux proof cross-compiles two tiny Windows PE executables and linked
PDBs with clang-cl/lld-link. The matching pair passes inspection, while an
actual unrelated PDB is rejected by GUID/age. Raw output is recorded in
tests/evidence/windows-symbol-identity.json. This is identity-parser evidence,
not proof that clangd's native Windows PDB or CDB stack lookup works. Native
workflow results remain required. CDB symbol lookup is a precursor to crash
stacks, not a replay of the still-empty real Windows crash corpus.

Windows jobs use the same pinned sccache action as the normal build. Debug
build commands have their own compiler cache keys. Cache hits and duration
remain unmeasured. These workflows are artifact/investigation channels and do
not qualify the final packaged engine or replace joint release acceptance.


References: [sccache MSVC guidance](https://github.com/mozilla/sccache/blob/main/README.md)
and [CMake debug-information format](https://cmake.org/cmake/help/latest/variable/CMAKE_MSVC_DEBUG_INFORMATION_FORMAT.html).
Native build, identity and CDB lookup must all pass before claiming usable
clangd symbols; the failed /Zi build did not reach those checks.
