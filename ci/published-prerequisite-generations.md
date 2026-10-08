# 0063: consumer caches bind to published prerequisite generations

63: published prerequisite generations participate in consumer cache identity

Clean private source /tmp/mcppls-module-chain63-final, commit9a969b36f1bbd8753356828a22ee31fdadedf9d1, base rooteb4605693. Only ModulesBuilder.cpp and PrerequisiteModulesTest.cpp changed; no shared source/build/index writes.

A consumer's semantic compile command previously selected its persistent and in-memory BMI cache identities regardless of the actual prerequisite producer versions. Compiler validation is retained, but standard-module imports omit the producer signature in the AST IMPORTS record; successful input validation alone cannot establish that a consumer was built under the current std compile profile.

The new versioned key includes the sorted published dependency chain plus each producer's stable file identity (size/device/inode/full timestamp). Leased copies use the original published identity captured when the read view was created, never their temporary path/inode/timestamp. Existing supplied prebuilts use their published identity; an unavailable identity refuses admission. No validation option is weakened. The same existing bounded prerequisite DAG supplies the chain; no global cache/registry lock performs new filesystem I/O. Existing source-scoped locking remains around lookup/validation/build/publication. Owned namespaces and in-memory caches use the augmented command identity; legacy stable storage adds a producer-chain-v1 directory component so old unqualified artifacts are not treated as certified.

Meaningful normal two-module test StandardModuleProfileInvalidatesConsumer:
- module std exports a constexpr value from its compilation profile; module Consumer exports the evaluated constant.
- change only std's -DPROFILE=1 to2, keep Consumer's command and source unchanged.
- before.log: unchanged joint builder reuses the old Consumer BMI; published path is unchanged and semantic static_assert(consumer_value==2) AST diagnostics fail (exit1).
- after.log: changed producer triggers a distinct published consumer generation, semantic AST has no diagnostics; a new warm reader gets a different temporary copy while reusing the identical published consumer BMI.
- all64 PrerequisiteModulesTests pass790ms, including normal module semantics and current lease/lifetime controls.

Two private changed TUs compiled successfully against the requested eb4605693 headers and linked with read-only stable46 archives plus existing joint replacement objects (Preamble62 replacement included). This is focused integration evidence, not a clean whole-recipe/native build. Binary SHA9052437d175c75b2b4f4a87fa12baef74bc9028b4ac4f527a360ae8a5408ea96.

This patch qualifies cache version consistency. It does not by itself establish that the historical full UP20 save/recovery case is fixed; root owns that actual follow-up. Prior normal-project reproduction/debug logs are separate evidence, not a substitute for the cache regression controls. No malicious inputs were constructed. No tool/platform rejection occurred during these final compilation/cache controls; GDB's earlier pretty-printer/libthread_db auto-load warnings did not prevent source-level diagnosis and are not engineering pass/fail evidence.

Drop when upstream consumer cache admission provides equivalent published-producer version binding, the two-module semantic update and warm-copy controls pass, and historical save/recovery qualification is complete. [Compact evidence](../tests/evidence/published-prerequisite-generations.json). State remains `stabilizing`; no full UP20 fix is claimed.

## Original Linux save/recovery follow-up

Root joint7214ddce4 through0063/0064 produces the identical9052437d... binary. The recovered original U7b case now passes in61.59s with fresh cache and unchanged source/CDB/scenario/product/CPU affinity:0 crashes/restarts,8 importers republish6.313s, probe clears2.306s, recovery6.481s against60s. Maintained59 negative control had6 natural crashes and319.50s recovery failure. Root64 prerequisite tests pass923ms, and proper numbered49–64 application including63 matches all24 changed paths. The compact evidence contains the exact invocation, measures and private raw-log digest. This qualifies one Linux development run; full native/1000-save/resource and final immutable payload qualification remain open. Seven interactions and75% engine share do not pass the latency gate.
