# Checked bitstream reads in module workers

Patch 0046 keeps `SimpleBitstreamCursor::Read` and `ReadVBR64` inline at their
call sites. The buffered fast paths otherwise become out-of-line calls in
the image build. Bit extraction, word refill, VBR overflow checks and error
handling retain their existing implementation. Compiler security flags and
the persistent BMI format do not change.

The exact preceding image's complete cold profile identifies both readers
as CPU hotspots. An isolated component reads all 176 PCM payloads produced
by that complete cold workload, fully traversing their bitstreams. Baseline
and candidate builds use matching flags and libraries within each native or
image lane, and every decoded aggregate agrees. Component results identify
an optimization to qualify; they do not establish complete-engine ratios.

The active native CI entry builds and runs the unchanged upstream reader
and writer `BitstreamTests`, including the Windows executable suffix. The
ordinary clangd, Clang and module integration tests remain required, as do
all native/image builds and the unchanged cold/warm readiness, CPU and
complete-lifetime fault gates. The [0.0.20 qualification run](https://github.com/Sunrisepeak/mcppls-clangd/actions/runs/42155475833)
passed those gates on all four hosts (the macOS cold measurement passed on its
single-job repeat); patch 0046 is `steady` for this release.
