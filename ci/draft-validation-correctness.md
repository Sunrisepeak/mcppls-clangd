# Validation memo must use the request filesystem

IsModuleFileUpToDate receives a VFS containing unsaved drafts when
--use-dirty-headers is active. The carried memo checks only physical disk
identities before returning true, bypassing ASTReader even when the request's
module/header input is an in-memory replacement. recordValidationInputs skips
some overlays after slow validation, which cannot protect this early return.

Lookup must compare each recorded input to the request VFS status as well as
the current disk identity. A DraftStore InMemoryFileSystem input has a different
UniqueID; reject that memo hit even if size and second-precision mtime match.
Recording must also compare FileEntry UniqueID against physical disk, rather
than assuming matching size/time means the input came from disk. No draft
validation verdict becomes a disk-only memo entry. Preserve the disk fast path
for inputs whose identities match exactly. This is a root-cause fix for the
memo bypass, not proof that all scheduling/generation defects are fixed.
