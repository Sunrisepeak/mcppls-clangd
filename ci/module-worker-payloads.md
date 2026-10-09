# Patch 47: per-worker output and captured-input payload bounds

Private source: `6c265ca45d3e122829c80e6a5848e4fb6c0e2298`, parent `1c4fa5ed28e2087ba2037ad0cb0cfcbcc4647a5e`.
Preserved source history: `5074c29331027fac9370354c79413ffb64aa148b` then `6c265ca45d3e122829c80e6a5848e4fb6c0e2298`. Consolidated export commit `045e15a6fff996d70f513d0a1c7448b3473458e3` has exactly the same source tree `c741a5aae374bd6b53e3b2f767caf4d1559527c0`.
Worktree `/tmp/mcppls-worker-payload47` is clean. Export: `0047-bounded-worker-output-and-captured-input-payloads.patch`.
Qualified Linux private clangd SHA256: `04aaf09a69ef5357a6b8aec0b76bd0e21f4d4aa20ddecac50087e16580f92150`.

## Contract and limits

`--modules-builder-worker-output-mib` and `--modules-builder-worker-capture-mib` default to zero (disabled). A nonzero setting rejects InProcess and unsupported-filesystem fallback. Existing default worker execution remains enabled on Linux. This patch does not enable an aggregate persistent-cache quota. Proposed 1GiB owned-cache/256MiB worker envelope defaults belong to the reserved 49 design, not this patch.

Captured-input preflight counts main.snapshot, every flattened overlay (including a duplicate main when present), YAML, and request JSON before the first snapshot payload write. Any configured payload bound also caps captured files at4096. It does not bound draft-store enumeration or serialization memory in the parent. Worker output accounting shares a conservative byte reservation and64-output-file ceiling across all compiler clones: bytes stay charged after discard/removal during a unit; repeated output paths decline rather than overwriting a charged file. The stream checks bytes/offset growth before underlying writes, and legal pwrite rewrites do not double-charge existing bytes.

These are payload-byte/file-count bounds, not filesystem-block/metadata quotas, an aggregate stable/staging/copy cap, or a total parent/scanner RSS bound. Input and output ceilings are independently optional. Physical filesystem allocation and all follow-on49 ledger/publication/read-lease/crash-accounting work remain open. No new Windows/Darwin qualification is claimed.

## Exact writer coverage

- Reduced BMI: worker-local ReducedBMIGenerator subclass retains PCHGenerator serialization and named-module selection, and sends its completed buffer through OutputBackend. Upstream CXX20ModulesGenerator raw_fd_ostream is bypassed only for this explicitly bounded worker action.
- OutputBackend: bounded unbuffered raw_pwrite_stream and sticky shared failure, cloned across CompilerInstance implicit compilers.
- ModuleCache.write: shared private cache routes complete implicit PCM buffers through the same backend before growth. Worker-private advisory locks/timestamps use memory and private cache pruning has no disk output. This cache is never shared with another process; weak duplicate compilation remains permitted by the LLVM advisory-lock contract.
- GlobalModuleIndex: retained legacy writeIndex API plus explicit backend/cache overload; both CompilerInstance index-load paths and FrontendAction index output route through it. Default cross-process cache preserves LockFileManager behavior. Worker-private cache creates no index lock files. A swallowed optional index quota error remains sticky and fails the worker before success/publication.
- Module-from-source pragma: CompilerInstance routes its temporary PCM through configured OutputBackend; strict worker refuses a foreign temporary path before payload growth and removes the initially allocated empty file.
- Requested diagnostics logs/serialization, dependencies, statistics, time traces, minimization hints, symbol graphs, plugins and module-file extensions decline strict admission. ModulesBuilder inspects actual driver cc1 arguments before its existing disableUnsupportedOptions strips plugins/dependency writers. ModuleOutputPath remains unchanged: it is inactive for the reduced-only action, which exclusively emits OutputFile.

A bounded child request uses protocol2 whenever output or address-space enforcement is requested. Existing unbounded protocol1 requests remain accepted; positive bound fields in protocol1 are rejected. This prevents a custom old worker from ignoring new fields while reporting success.

## Linux evidence

`compile.py` compiled8 changed TUs (new WorkerOutput, Compiler, CompilerInstance, FrontendAction, GlobalModuleIndex, Worker, ModulesBuilder, PrerequisiteModulesTest); `link.py` placed all changed objects before stable46 archives. No existing public class layout/vtable changed; old prepareCompilerInstance and writeIndex symbols remain. Worker input/options struct consumers were all rebuilt. Shared source/archives/binaries were not modified.

- `prereq-final.log`:49/49 PrerequisiteModulesTests pass,370ms. Includes cross-backend shared admission, legal pwrite/cache accounting, sticky index rejection, capture-before-launch and protocol downgrade rejection.
- `child-proof.py`, `child-evidence.json`: real clang-driver cc1 arguments and exact main snapshots. Unbounded and64KiB bounded simple module both emit35248-byte BMI, consumed by real clang with static_assert(Value==42).128KiB implicit positive emits main35652, implicit35780 and index580 bytes; real clang also consumes it successfully.
-16-byte ceiling: actual main and implicit cache writes fail, no PCM remains.71432-byte ceiling: main+implicit fit but index does not; swallowed index error is caught, main is removed, index absent, remaining private implicit PCM35772bytes stays within cap. A direct internal-mode probe has no supervisor, so its private partial cache is intentionally recorded; production supervisor owns cleanup after reap.
- Actual side-output and module-build pragma controls reject before side/foreign PCM payload; no foreign temporary remains.
- `default-export47/result.json`: existing real LSP default fixture passes with1MiB capture/output ceilings, one actual2GiB supervised child, relative CDB spellings, unsaved header41→42, completion fn_m, unchanged disk and normal shutdown.
- `before-control-evidence.json`: exact stable46 binary `2f91a4aa31c07c7f49b3ddbf6dfa04e1629f4d5668aa7339d8d8ab1f56f71011` runs version1 unbounded writer controls; it ignores the formerly unknown output field and writes main/implicit/index/side/module-source outputs. These are unbounded controls, not a claim that46 advertised this new ceiling.
- `old-worker-v2-rejection.json`: same old binary rejects protocol2 before output.
- `old-worker-parent-final/result.json`: actual new LSP parent configured with the exact old worker executable launches it, gets genuine unsupported-protocol failure, produces no BMI/fallback, then serves independent ControlValue document symbols and shuts down/reaps normally.

Reproduce focused checks with `compile.py`, `link.py`, `child-proof.py`, `old-worker-lsp.py`; shared46 archives must remain stable for read-only private linking.49 is reserved and not included.

Drop when upstream implements equivalent pre-write capture and complete
worker-output accounting, sticky optional-output failures and protocol
compatibility refusal, and actual compiler/LSP controls pass. Aggregate quota,
physical disk allocation and process RSS remain independent release work.
[Compact evidence](../tests/evidence/module-worker-payloads.json).
