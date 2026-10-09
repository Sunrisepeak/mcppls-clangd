# Exact request contents in module scans

Patch 0026 repairs a filesystem boundary: the project-module scanner captured
the compilation database filesystem even when prerequisite building received
the request filesystem. Preamble safety/reuse and completion could therefore
use disk imports while parsing an unsaved buffer.

Production facades now rebind their scanner and command backend to the request
filesystem, preserving the command mangler and generation inventory. The exact
captured main buffer overlays disk and a different global draft. Preamble
safety, prerequisite construction and import-set reuse checks use that buffer.
Completion compares current import names before accepting old prerequisites.
Workers drain before the temporary filesystem dies; returned prerequisites
retain paths and reader leases, without borrowing that filesystem.

The scanner service caches borrowed VFS buffers between worker views.
InMemoryFileSystem returns a buffer wrapper over its storage, so making each
view own a fresh content copy left cached bytes dangling once that view died.
The combined candidate reproduced a natural SIGSEGV in the diamond provider
scan. Overlay wrappers now borrow the immutable string owned by RequestModuleFS;
that string outlives all scanners and drained jobs. This also avoids repeated
main-buffer copies. The unchanged diamond replay now returns all four module
symbols and exits normally. All ten DAG cases pass after the repair, including
worker bounds, shared dependencies, failures, prebuilt BMIs and concurrent
importers. The DAG fixture saves raw evidence before checking assertions.

The disk-only buildability verdict memo is removed: main-file stat identity
does not identify header imports, drafts or provider availability. Fresh scans
temporarily cost more. Verified-input scan reuse with bounded ownership remains
required; this patch makes no warm-performance or hard RSS claim. Other files
use the supplied request filesystem, without promising an atomic snapshot of
all concurrently changing disk/header inputs.

The old 25-patch engine fails the actual unsaved import case with missing
draft_value. The candidate passes M → no import → N, requiring current AST
symbols and actual imported completion while the disk file remains unchanged.
The unit also proves supplied filesystem overlays and exact main contents
overriding another draft. Thirty related module/provider/diagnostic units pass
on the combined development link. Raw evidence is in
tests/evidence/module-request-inputs.json. This is not the final package proof.

Run tests/e2e/module_request_inputs.py with --engine, --clang and --workdir;
normal native CI repeats it. Upstream/drop condition: request snapshots reach
every module dependency scan, prerequisite build and preamble/completion reuse
check with equivalent filesystem ownership and invalidation guarantees.
