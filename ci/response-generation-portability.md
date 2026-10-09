# 0052: portable response-generation test paths

The native Windows0042 build compiled successfully but two of40 provider/CDB
unit cases failed: ResponseInputsPublishImmutableGenerations and
UnstableResponsePublicationRetainsPreviousGeneration. Both assembled JSON by
concatenating the test directory; C:\clangd-test contained an unescaped
backslash and the parser reported an unrecognized escape, so no compilation
database was loaded. RealResponseEditRefreshesProviderGeneration already used
JSON serialization and passed. This is a maintained fixture portability error,
not a newly established compiler or production cache defect.

Both failing fixtures now build their compilation database with existing
llvm::json::Object/Array and formatv. Assertions and test semantics remain
unchanged. Four focused response-generation cases pass2ms on Linux; the final
private policy/response link passes six cases23ms. This proves the Linux
fixture still works; corrected-head native Windows execution is required to
qualify the Windows fix. Previous46 Windows CI still contains the old fixtures.

Private source032854d43 changes only GlobalCompilationDatabaseTests.cpp over
46+48. The changed TU is compiled before linking against read-only root46
archives. Drop the maintained fixture patch when upstream carries equivalent
portable serialized paths and native response-generation controls pass.

[Compact evidence](../tests/evidence/response-generation-portability.json)
