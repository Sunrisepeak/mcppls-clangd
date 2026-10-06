# Module validation: same-second input replacement

The module-member quality fixture replaces addOption with newOption on disk
(same byte length) and assigns a different nanosecond timestamp in the original
second. It then reports the watched-file change, edits the consumer and waits
for its AST before requesting newOption. The semantic-default candidate returns
no newOption. Existing validation-cache FileIdentity truncates modification
time to seconds, so unchanged size makes the memo incorrectly reuse its verdict.

Keep filesystem-native modification precision and file UniqueID in the memo
identity. Only the comparison to Clang's FileEntry should truncate to seconds,
because FileEntry uses second precision; the memo must store the full disk
identity. Copy-on-read source identities use the same precise representation.
This eliminates the demonstrated same-second collision, without rehashing every
BMI on each request. It does not prove draft overlays, concurrent-validation
races, CDB invalidation, or timestamp-preserving in-place changes; those remain
W2 requirements. Performance remains to be measured on the real-project inputs.
