# 0056: native scan publication admission

Native Darwin arm64 run 37718071132, head 757a040, built successfully but failed `PrerequisiteModulesTests.ScanPublicationReplaysEachRequestView`: all three cases returned the correct M/N modules, while stores and followers stayed zero. Production `hasObservableDriverInputs` intentionally requires both a Linux host and Linux target, because native Darwin/Windows toolchain discovery can observe state outside the recorded VFS. The new test incorrectly assumed every host admitted scan manifests.

Keep all three actual owner/follower cases on every platform: identical header views, differing unsaved same-size/time headers, and owner cancellation. Linux retains the follower-join, store, hit, invalidation and cancellation assertions with the original two-second deadline. Other hosts assert unchanged store/hit/invalidation/decline/follower counters, correct independent semantic results, and no live publication entries after both requests finish. No test skip, longer deadline, production admission expansion or compiler flag changes.

Linux local integration after 0047–0055 plus this patch compiled the two affected translation units and linked both actual binaries. Twelve focused scan/publication tests pass in 238 ms. Ordered application of 0047–0056 (0049 remains reserved) matches all 23 changed paths in the private combined source. This is a partial-object proof using unchanged 0046 archives; corrected native CI remains required.

Drop when upstream integration tests cover admitted and unsupported native hosts with equivalent semantic/counter assertions. [Compact evidence](../tests/evidence/module-scan-native-admission.json).
