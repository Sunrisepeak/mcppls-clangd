# 0057: requesting-project provider commands

An explicit provider can reside outside the directory ancestry of the importing
project's compile_commands.json. The maintained0019/0023 buildability and DAG
checks rediscovered its command through the global directory-based database,
ignoring the already resolved importing-project command. Actual Qt nlohmann.json
was discovered but then treated as nonbuildable, returning empty completions.
The original GCC main.cpp command compiles successfully with unchanged flags.

ProjectModules now exposes an explicit adjusted command from its immutable
request generation; backends without command information return nullopt.
CachingProjectModules forwards that API. A single ModulesBuilder helper uses
existing global/overlay commands first, then the request-generation fallback.
Buildability, prebuilt extraction and DAG wave dispatch all use that helper.
No cross-project global command cache, invented command, flag removal or VFS
freshness relaxation is added. All classes derived from the extended virtual
interface must be rebuilt: ProjectModules.cpp, ModulesBuilder.cpp,
PrerequisiteModulesTest.cpp and ClangdTests.cpp. Root joint integration rebuilds
those creators; private agent proof alone did not rebuild the unused EmptyModules
fixture and cannot establish broad binary-interface coverage.

Private7424065f685fecf681a39e274e25a2c97a85898b (parent7ca13e82e),
actual clangd9e999ab107769976f1a7653e399408b117725f18bac83c6087a09ae0821d1c14:
six focused tests pass66ms. New ExternalProviderUsesImportingProjectCommand
actually compiles a disk external module and imports its AST; same-count CDB
MODE1→2 changes produce distinct immutable old/new commands and exported ASTs;
source/directory-aware mangling stays isolated; explicit overlay commands win.
The separate prebuilt relative-path test passes, with an observed279s retained
run, which is not claimed as a latency improvement or release distribution.
Raw args/logs/identity and all failed controls are in
/tmp/mcppls-provider57-evidence; compact identities are tracked below.

Actual Qt JSON now reaches and naturally completes worker compilation, but47's
implicit prerequisite guard refuses mainBMI whose private implicit PCMs would
vanish on unit cleanup. The original -fmodules remains; both before and after
JSON semantic controls still fail. A separate owned implicit bundle publication
and lease change is required. A default empty OverlayCDB callback also exposed
an independent original23.1 null-call crash, now registered UP-27 and owned by58.
57's explicit noop overlay fixture preserves production-shaped precedence;
it does not qualify the default/null API.

Drop when upstream provider command resolution honors explicit commands from
the requesting project with equivalent external AST/generation/mangler/override
controls. Clean full recipe, native and full context/insertion gates remain
open. [Compact evidence](../tests/evidence/module-provider-commands.json).
