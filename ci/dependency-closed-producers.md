# Dependency-closed producer snapshots

The build-wave snapshot previously included unrelated completed roots. Every producer bound its cache generation to that entire snapshot, so a consumer importing or editing an unrelated root could rebuild a shared producer. Each planned node now records its transitive dependency closure and receives an immutable filtered snapshot. Files outside the source plan remain conservatively available for unknown prebuilt imports. Worker limits, cycle rejection and cancellation boundaries remain intact.

`PrerequisiteModulesTests.UnrelatedRootDoesNotChangeProducerGeneration` exercises Leaf → Base → Shared and an independent Noise root. Plain and mixed consumers publish the same Shared generation; editing Noise invalidates the mixed consumer without changing Shared; editing Leaf invalidates and rebuilds Shared. This test fails the two unrelated-root generation assertions before the fix and passes with it. The regular `PrerequisiteModulesTests.*` CI filter includes it.

See [private correctness evidence](../tests/evidence/part2-linux/producer-closure74/README.md). This repairs fork-owned planner/cache binding; it does not establish a newly discovered upstream defect. Native platform and full release qualification remain open.
