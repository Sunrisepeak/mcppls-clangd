# Exact filesystem queries in module scan manifests

Patch `0065-UP-03-exact-module-scan-filesystem-queries.patch` preserves the actual query spelling for `status`, `exists` and opened files. The manifest separately freezes and revalidates the working directory. Directory order, absolute-path operations, real-path results, failed lookups, file metadata/alias relationships and complete content fingerprints retain their existing checks.

A real PCH/FileManager query `status(".")` exposes the original spelling in the returned status name. Recording an invented absolute replay path changes that result even when the disk has not changed. This blocked a strict actual-input audit; accepting a differently named status would weaken the manifest contract. Replaying the original query fixes the cause.

The matched real-filesystem control exercises relative directory status, relative file status/open/name/full read and a failed lookup. It then replaces header content with equal bytes count and preserved full mtime: replay must still fail. The identical final unit source fails the initial unchanged-filesystem assertion against the baseline and passes against patch65. Baseline source is `eb4605693`; fixed source is `ed882ae6c`. Both restore CWD before temporary-directory deletion through the existing fixture lifetime.

Raw logs, executable/source hashes and exact private compile/link arguments are retained in [the evidence manifest](../tests/evidence/module-scan-relative-queries.json) and [raw before](../tests/evidence/module-scan-relative-queries/before-result.log)/[raw after](../tests/evidence/module-scan-relative-queries/after-result.log). The only changed-header consumers are `ProjectModules.cpp` and `PrerequisiteModulesTest.cpp`; the fixed private build recompiles both and reads the other stable objects/archives. No shared LLVM source or archive was changed.

This is an UP-03 scan-observation prerequisite. It does not change preamble policy, permit unknown inputs, or qualify a performance gate. Actual native Windows/Darwin verification remains open.
