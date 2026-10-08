Private candidate integration boundary (not implemented)

The completed prerequisite is not a production optimization. Base is final67
66ed2d104. Current diff changes only Preamble.cpp and PrerequisiteModulesTest.cpp.
No public layout changes have been linked, and no Qt latency probe was run.

Retained old evidence
- PreambleData continues to own its existing PrecompiledPreamble. No separate
  persistent PCH owner or transient PCH filename cache key is introduced.
- Borrow the immutable original canonical PREFIX cache Entry through an aliasing
  shared_ptr. Existing entry accounting remains charged after cache eviction and
  until the last borrower dies. This retains driver/toolchain discovery facts
  that the later finalized compiler invocation cannot reconstruct by itself.
- Retain the actual complete compiler BuiltInputs manifest, actual emitted-PCH
  import-free audit, exact prefix bytes, original command/CDB/env, and main
  spelling/native-alias proof. Reserve its owned metadata in the same 32 MiB,
  256-entry cache budget before retaining it. A denied reservation declines the
  candidate. Do not copy an uncharged manifest or erase matching-path facts.
- Independent replay requires BOTH prefix-scanner and compiler manifests on the
  exact-spelling prefix view, current prefix equality/CanReuse, current command,
  CDB and environment. Native alias partitions must remain proven. No FS I/O
  while holding the cache registry mutex.

Current request
- Prepare the owned CI/current full-main buffer/VFS before scanner construction.
  AddImplicitPreamble supplies the owned PCH and current full main. Its default
  validation suppression is reset to None. Preserve original scanner predefines,
  macros and other PP options. Transfer only the PCH/main integration fields and
  align the documented Compatible system-comment-retention setting.
- Use a fresh CanonicalPreprocessing scanner service on a miss. Preserve original
  full-draft key and original-key publication coordination. Current canonical
  scan determines providing role/imports and preserves diagnostics/PP callbacks.
- Its immutable request-local proof explicitly binds exact current full-main
  digest, command, CDB generation and environment, names/no-provides, complete
  observed inputs, and validated old prefix evidence. Revalidate before each
  names/textual consumer. The proof is never an opaque edited-main reuse token.
- Completion's names and textual checks consume this SAME request proof;
  isPreambleCompatible must similarly share one proof for its two checks. A
  subsequent original full-main scan would erase the proposed benefit.
- PCH lifetime is borrowed synchronously from the caller's existing PreambleData
  ownership. CI/main/VFS outlive scanner/worker destruction and final observation.
- Virtual PCH observations are not stored as ordinary raw-FS memo entries. Any
  future global publication of assisted results needs separate explicit evidence
  semantics; this boundary only returns a bounded request-local full-scan proof.

Failure
- Unsupported command, unknown generation/environment, expired/denied evidence,
  changed prefix/header/negative lookup/alias, providing role, incomplete audit,
  builtin nonreusability, PCH load incompatibility or canonical scan error declines
  assistance and retries original canonical once. Preserve its diagnostics and
  normal compiler/BMI verification. No total PCH disable or role lexical shortcut.

Remaining verification
- Public PreambleData/ProjectModules interfaces require all affected consumer TUs
  rebuilt against private headers before any integrated binary is executed.
- Matched original canonical vs integrated candidate controls must cover draft,
  conditional imports, same-size/mtime dependencies, command changes, providing
  role, current #error/time callbacks, aliases and missing/corrupt PCH fallback.
- Only after these controls: one original Qt std and JSON actual-Sema/GCC probe,
  exploratory latency only. Parent/scanner RSS, physical allocation and native
  performance qualification remain outside this prerequisite evidence.
