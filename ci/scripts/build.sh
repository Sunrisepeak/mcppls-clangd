#!/usr/bin/env bash
# build.sh — build the clangd target (and test helpers when TEST=1).
source "$(dirname "$0")/env.sh"

TARGETS=(clangd)
if [[ "${TEST:-0}" = "1" ]]; then
  TARGETS+=(check-clangd SupportTests)   # builds FileCheck/not/lit deps too
fi

cmake --build "$BUILD_DIR" --target "${TARGETS[@]}" -j "${JOBS:-$(nproc 2>/dev/null || echo 4)}"

if [[ "${TEST:-0}" = "1" ]]; then
  suffix=""
  [[ "$PLATFORM" == win32-* ]] && suffix=".exe"
  "$BUILD_DIR/unittests/Support/SupportTests$suffix" --gtest_filter='VirtualFileSystemTest.*'
fi

echo "build.sh: --version output:"
"$BUILD_DIR/bin/clangd" --version
