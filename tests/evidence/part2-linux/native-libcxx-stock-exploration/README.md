# Correct native libc++ stock exploration

The installed Clang 23.1.0 actual compiler produced libc++ std PCM and compiled the importer with explicit kit/sysroot and --no-default-config. This is a separate native compiler fixture, not a replacement for the GCC Qt project.

The stock engine missed the typed vector candidate on its cold reply; its remaining three warm/edited replies passed typed Sema. Candidate 0068 passed all four. The initial insertion binding supplied only int for libc++ vector's two template placeholders, so both arms failed actual insertion compilation. Original failed reports are preserved. Offline correction applied the same actual returned edits using int and std::allocator<int>; all available stock replies (three) and all candidate replies (four) compiled. Stock cold failure remains a failure.

The preparation helper now emits both legal bindings for future fixtures; this does not overwrite the original context or reports. Full reports and corrected insertion proofs are retained. Compilation overlapped clean building; neither engine's timing qualifies performance. This does not satisfy the stock 50% release comparison or a cold correctness gate.
