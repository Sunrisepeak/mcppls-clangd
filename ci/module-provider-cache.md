# Provider command inventory by compilation database generation

Patch `0025-UP-03-provider-command-generation-cache.patch` addresses a remaining
W2 cost after bounded DAG scheduling. Each call to getProjectModules previously
created a CompileCommandsProjectModules with an empty provider index. Its first
name-state/provider lookup enumerated every CDB file, retrieved and adjusted
its command, expanded response files, acquired an FS view and reconstructed the
producer/consumer maps. ModulesBuilder's source-name cache does not eliminate
this work: its lookup first asks the fresh facade for the module name's state.

The directory CDB now retains one lazy command cache for its current immutable
CDB object. It retains that shared_ptr as the generation identity, preventing
address reuse from accepting an old generation. A newly loaded CDB gets a new
inventory; facades already using the previous generation remain valid. Ordinary
compile-command lookups do not acquire or construct the module command cache.
The cached inventory preserves getAllFiles order and the existing first-command
selection policy. It is initialized once under a mutex.

A CDB generation alone cannot identify a provider index. OverlayCDB's command
mangler evaluates per-file configuration, which may change independently of the
CDB. Every new facade therefore adjusts a copy of the inventory on its request
thread. Exact equality of all adjusted CompileCommand fields, without a hash
collision or callback-address assumption, determines whether the previously
built immutable provider index can be reused. The cache retains one adjusted
command variant and one provider index per generation; switching configuration
replaces that variant. Concurrent requests can retain their immutable indexes
until they finish. Manglers and dependency scanners remain facade-local.

An adjusted command containing an `@response` token bypasses index memoization,
because response-file bytes are not identified by the command vector. It is
expanded and parsed again. DirectoryBasedCDB already expands response files
while loading its CDB; this patch preserves that loader's existing reload
contract and does not claim to fix independent response-file invalidation there.
Compile-command provider hints are still checked against a fresh scan of the
candidate source. No source dependency scan result is shared across requests.

Focused unit regressions prove inventory reuse across three facades, mangler
changes and reversion, independently changed raw response-file contents, a CDB
content reload with a still-live old facade, and source module renaming after a
warm command-index hit. Existing unique/duplicate module names and command
adjustment regressions remain in the focused filter.

```sh
build-linux-x64/tools/clang/tools/extra/clangd/unittests/ClangdTests \
  --gtest_filter='PrerequisiteModulesTests.Provider*:GlobalCompilationDatabaseTest.ProviderIndexFollowsDatabaseGeneration:PrerequisiteModulesTests.UniqueModuleNameStateResolvedFromCompileCommands:PrerequisiteModulesTests.DuplicateModuleNamesResolvedFromCompileCommands:PrerequisiteModulesTests.ModuleWithArgumentPatch'
python3 tests/e2e/module_provider_cache.py \
  --engine build-linux-x64/bin/clangd \
  --clang build-linux-x64/bin/clang++ \
  --workdir /tmp/mcppls-module-provider-cache
```

The raw replay uses 132 CDB entries and three successive importer documents.
All three must return actual `dep_value` completion and cleanly shut down.
The observed inventory count is one and provider-index reuse count is six.
The retained report is `tests/evidence/module-provider-cache.json`; it includes
raw replies, engine SHA-256 and logs. The local engine used focused object,
archive and link commands against existing libraries. It is development
evidence, not a clean packaged artifact or a high-level stability claim.

This change removes repeated CDB command retrieval, command-fact parsing and
provider-map reconstruction for unchanged adjusted commands. It still performs
O(N) command copies, mangler calls and exact comparison per new facade. No
latency/RSS improvement threshold is claimed. A stable configuration generation
API or a narrower command adjustment dependency contract is required to safely
eliminate that work. Precise scan-result reuse, memory admission and the full
joint-release performance/soak gates remain open.

Upstream the cache as a separate change with the unit regressions. Drop it only
when upstream shares provider facts across facades with equivalent CDB,
configuration, response-file, source-validation and lifetime guarantees.
