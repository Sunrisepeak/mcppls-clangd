# Template guide filtering private candidate

Source commit 5cd03e1fd (parent c3af7d151) changes only ASTReader's existing predicate helper and two CompletionTests; no public interface, format or layout changes. Guides are selected by their class template identifier. Ordinary lookup and full loading remain available.

All 144 CompletionTest pass. Initial failures are retained: the original fixture preloaded the ordinary template and its guides; later checks incorrectly assumed the first implicit guide is not wrapped in FunctionTemplateDecl. The final test checks that the template is still unloaded after selective completion, then accepts implicit wrapped and explicit guide declarations on ordinary lookup. Result parity explicitly requires matching alias/class names and compares signatures/snippets with textual declarations.

Short same-URI/CDB/cache-independent A/B/A: all 36 typed Sema replies and selected actual GCC insertions pass. All 65 returned items per reply retain label/kind and full actual edit fields. Unrelated xlings release compilation began after the no-compiler preflight, so all timing is excluded from performance qualification. Do not export 0069 based on this run.
