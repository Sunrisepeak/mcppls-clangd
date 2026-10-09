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


## Fast historical upstream capture

`win-historical-crash-capture.yml` investigates UP-12 using the official
23.1.0 Windows executable and official debug-symbol archive. Both downloads
are SHA-pinned; executable/PDB GUID and age, debug/public streams and an actual
clangdMain lookup are required before capture. This does not build the fork
or count as native fixed-engine validation.

The replay retains its LSP stdin/stdout while CDB attaches by PID before any
protocol traffic. Attachment consumes the same replay deadline and failed
setup still reaps the engine/readers. The initial attach breakpoint is handled;
later genuine second-chance exceptions emit the exception record, context,
symbolic stacks and minidump, then continue unhandled so the OS supplies the
natural crash exit. This follows Microsoft's [exception-command semantics](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/sx--sxd--sxe--sxi--sxn--sxr--sx---set-exceptions-)
and [last-chance termination contract](https://learn.microsoft.com/en-us/windows/win32/debug/debugger-exception-handling).

Capture requires the actual 0x80000003 replay exit, executed second-chance
marker and exception record, real symbolic stack rows, MDMP header, stopped
readers and no forced debugger termination. Echoed commands and lookup output
do not qualify as stack frames. Controlled classifier and launch-cleanup
checks pass on Linux; they are explicitly synthetic and do not prove native
capture. The fast native workflow remains required.

Native run 37687209535 loads the official matching PDB and executes the
second-chance handler with exception 0x80000003 and natural engine exit.
The actual stack includes TokenCollector::Builder::build, TokenCollector::consume
and ParsedAST::build, consistent with the Linux missing-BMI token replay
failure. Full capture eligibility remains false: CDB stripped backslashes
from the nested dump command and wrote outside the intended artifact path.
The command now uses forward slashes and parses native colon-separated stack
rows; rerun is required to verify the minidump. Actual native evidence is in
tests/evidence/up12-native-symbolic-stack.json. Older llvm-readobj prints raw
GUID bytes; identity now normalizes that PE little-endian layout, with the
official pair verified on Linux using both LLVM 18 and the newer reader.

Corrected run 37687987936 collects the 98,187-byte minidump in its intended
artifact directory, actual exception record and symbolic frames; the natural
exit and debugger exit are both 0x80000003 with no forced termination. This
passes the original function-stack/minidump capture gate. The joint plan also
requires source-location information, so capture now explicitly enables
[.lines -e](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/-lines--toggle-source-line-support-)
before loading symbols and requires source file/line annotations in actual
stack rows. A new native run must prove that stronger gate.
