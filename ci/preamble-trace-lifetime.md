# 0051: own asynchronously retained preamble trace filenames

[UP-26 register](https://github.com/Sunrisepeak/mcpp-language-server/issues/24#issuecomment-6050569335)
records this unfiled upstream defect. SPAN_ATTACH constructed a borrowed
json::Value(StringRef); JSONSpan emits only when its Context is destroyed.
A callback can retain that Context after buildPreamble returns, outliving the
filename buffer. Both BuildPreamble and CreatePreamblePatch now attach
FileName.str(), preserving ownership. Disabled tracing does not evaluate the
attachment. Generic serialization and unrelated metadata are unchanged.

The regression invokes actual buildPreamble and retains Context::current()
from its callback. After return, it overwrites the caller's filename with
same-length ASCII x characters and releases the retained context. The old
production emits x characters instead of the original path; the new production
emits the exact original filename. The same test object is used for both links.
This deterministic canary does not rely on allocator reuse or malformed input.
It exercises BuildPreamble; source inspection identifies the identical borrowed
expression at CreatePreamblePatch. Three focused after tests pass22ms.

The original byte-exact0048 Qt trace fails strict UTF8 parsing at byte182878.
It is retained in the local evidence directory without rewriting. The final
private51 trace passes ordinary UTF8/json.load, and seven preamble/patch
filename values equal the actual complete source path; all four semantic
completion assertions pass. The later combined50+51+52 Qt trace also passes
strict parsing. This proves metadata lifetime, not a semantic crash repair or
performance improvement. The single cold6077ms sample remains recorded;
edited completion and statistical acceptance remain separate open gates.

Private sourced4ca05e95466e2581bc29d40bf76274e33bf8d83 applies51 to48
on combined46. Changed Preamble/test objects precede stable read-only root46
archives. Clean builds, native platforms and release artifacts are pending.
Drop the maintained patch when upstream owns these attachments and the
retained-context regression passes.

[Evidence](../tests/evidence/preamble-trace-lifetime.json)
