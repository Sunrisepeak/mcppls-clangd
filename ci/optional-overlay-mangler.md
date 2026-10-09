# 0058: guard the optional OverlayCDB module mangler

The unmodified pinned llvmorg-23.1.0 source archive confirms that OverlayCDB's
public constructor defaults CommandMangler to null, but getProjectModules
installs a callback that invokes it unconditionally. Ordinary getCompileCommand
already tests the optional mangler. The defect was registered as
[UP-27](https://github.com/Sunrisepeak/mcpp-language-server/issues/24#issuecomment-6051758755)
before implementation. The normal ClangdMain supplies a nonempty mangler; this
is proven API-default exposure, not a claim about every editor startup.

Guard the optional call inside the existing callback. Nonempty command
configuration, explicit overlay precedence, filesystem replay and immutable
request-generation resolution stay unchanged. The real external-provider
fixture now additionally uses default OverlayCDB(&CDB), queries its MODE2
provider command, scans required module M and actually imports new_value from
its built AST. The existing explicit overlay still imports old_value.

Same test object linked against unchanged production callback naturally exits
SIGSEGV(-11), with no forced kill. Private GDB independently records null PC
through getCompileCommandForFile/ModuleDependencyScanner::scan. Only the
GlobalCompilationDatabase production object changes in the positive link;
14 focused tests pass265ms, including real default/explicit external ASTs,
old/new immutable CDB generations, divergent request publication, draft safety
and scheduling/completion mode controls. All four creators derived from the
extended57 virtual facade were rebuilt before either link, including test-only
EmptyModules. Root46 archives stay read-only. Ordered47–58 (49 reserved) matches
all25 changed source paths. No clean whole-tree/native recipe is claimed.

Raw args/logs/negative control: /tmp/mcppls-joint53-build; pinned source extraction
and original GDB evidence remain private. [Compact evidence](../tests/evidence/optional-overlay-mangler.json).
Drop when upstream guards this optional callback and equivalent real default
module-scanning/imported-AST controls pass. Corrected native CI remains pending.
