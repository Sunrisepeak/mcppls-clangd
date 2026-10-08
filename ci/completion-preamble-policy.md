# 0048: completion preserves the actual preamble build mode

Completion previously recomputed hasBuildableRequiredModules merely to decide
whether to patch/reuse an already constructed preamble. The root46 Qt trace
spends252–256 ms on this inventory, including repeated main/nlohmann manifests
and moc/std/qrc provider inventory; its later45 ms main manifest validation and
about45 ms semantic execution are separate necessary work. This fixture has no
actual loaded BMI; validationMemo is not responsible for the45 ms cost.

PreambleData now explicitly records Inputs.Opts.SkipPreambleBuild from the actual
build. Completion uses that stored mode plus the existing explicit server
option when computing bounds/patching the old preamble. The late current module
name, CDB generation, input and BMI guard remains unchanged; drift disables
preamble reuse and constructs the current prerequisites. Empty bounds alone
cannot distinguish deliberate skipping from a naturally empty preamble, so
inference from bounds was not used. Linux old/new sizeofPreambleData is648 and
prior field offsets remain unchanged; this is not a native ABI qualification.

Private sourcea5fabab4e on combined46 compiles both production creators/readers
and both changed test TUs before linking read-only native archives. Four focused
units pass39 ms; the same counting-CDB test object fails against old production
(two queries versus required one) and passes with the remaining late query.
Actual LSP cold, unsaved import M→none→N, response M→N and same-size/preserved
mtime header-only M→N transitions pass. Plain→buildable draft completion also
passes without an AST settle barrier, including required and forbidden symbols.

Matched resource/flags Qt semantic replies all pass: warm94/99 ms versus
combined46's344/348; edited500 ms remains above200 ms because synchronous
update still scans the inventory. This small sample is not statistical or
insertion/context acceptance. That update cost is a separate0050 change.
The first raw trace has invalid UTF-8 filename metadata. It is preserved byte
for byte and documented separately under UP-26/0051; its valid structured report
and semantic assertions are not rewritten to conceal that diagnostic defect.

[Evidence](../tests/evidence/completion-preamble-mode.json)
