#!/usr/bin/env bash
# configure-openkal.sh <llvm-project> <build-dir> <toolchain.cmake> <host-tblgen-bin> <arch>
# HAVE_PREAD=0: openkal-musl 0.22.6 declares and links pread but answers ENOSYS (probe finding).
set -euo pipefail
src="$1" build="$2" tc="$3" tbl="$4" arch="$5"
cmake -G Ninja -S "$src/llvm" -B "$build" \
  -DCMAKE_TOOLCHAIN_FILE="$tc" \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_APPEND_VC_REV=OFF \
  -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" \
  -DLLVM_TARGETS_TO_BUILD="X86;AArch64" \
  -DLLVM_HOST_TRIPLE="$arch-unknown-linux-gnu" \
  -DLLVM_TABLEGEN="$tbl/llvm-tblgen" -DCLANG_TABLEGEN="$tbl/clang-tblgen" -DLLVM_NATIVE_TOOL_DIR="$tbl" \
  -DLLVM_ENABLE_PLUGINS=OFF -DLLVM_ENABLE_WERROR=OFF \
  -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF \
  -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_ENABLE_LIBEDIT=OFF -DLLVM_ENABLE_FFI=OFF \
  -DLLVM_ENABLE_LIBPFM=OFF -DLLVM_ENABLE_CURL=OFF -DLLVM_ENABLE_HTTPLIB=OFF \
  -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
  -DLLVM_BUILD_TOOLS=OFF -DLLVM_INCLUDE_UTILS=OFF \
  -DCLANG_ENABLE_ARCMT=OFF -DCLANG_PLUGIN_SUPPORT=OFF \
  -DLLVM_VERSION_SUFFIX="${FORK_SUFFIX:--mcppls.5}" \
  -DHAVE_PREAD=0 \
  ${CMAKE_EXTRA:-}
