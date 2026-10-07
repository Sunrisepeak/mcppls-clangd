#!/usr/bin/env bash
# ci_build.sh — one CI build+test stage for a platform.
#   PLATFORM=linux-x64 [TEST=1] [RUN_TESTS=lit-subset] ./ci/ci_build.sh
# Used by the workflows; wraps the five-stage scripts with caching-friendly
# ordering (fetch -> apply -> configure -> build -> package).
set -euo pipefail
cd "$(dirname "$0")/.."

# Bring BUILD_DIR/LLVM_DIR/FORK_VERSION into this shell: the stage scripts run
# configure in a child process, and their exported values do not come back.
source ci/scripts/env.sh

./ci/scripts/fetch.sh
# CI always starts from the pinned tree; re-apply if the cache restored an
# already-patched tree this is a no-op (marker file).
./ci/scripts/apply.sh
./ci/scripts/configure.sh

if [[ "${TEST:-0}" = "1" ]]; then
  # clangd + the clang driver (module lit tests compile with it) + lit helpers
  cmake --build "$BUILD_DIR" --target clangd clang clang-tidy clang-format clangd-validation-overlay-probe FileCheck not count split-file llvm-config -j "${JOBS:-4}"
else
  cmake --build "$BUILD_DIR" --target clangd -j "${JOBS:-4}"
fi

if [[ "${SYMBOLS:-0}" = "1" ]]; then
  cmake --build "$BUILD_DIR" --target llvm-readobj llvm-pdbutil -j "${JOBS:-4}"
fi

"$BUILD_DIR/bin/clangd" --version
python3 ci/build_identity.py --build-dir "$BUILD_DIR" --llvm-dir "$LLVM_DIR" --platform "$PLATFORM"

if [[ "${RUN_TESTS:-}" = "lit-subset" ]]; then
  cd "$BUILD_DIR"
  # POSIX builds generate the llvm-lit shell wrapper, MSVC builds a .cmd.
  LIT=./bin/llvm-lit
  [[ -f "$LIT" ]] || LIT=./bin/llvm-lit.cmd
  "$LIT" -sv \
    tools/clang/tools/extra/clangd/test/module-directive-recovery.test \
    tools/clang/tools/extra/clangd/test/mcpp-format-style.test \
    tools/clang/tools/extra/clangd/test/mcpp-format-fallback.test \
    tools/clang/tools/extra/clangd/test/modules-validation-cache.test \
    tools/clang/tools/extra/clangd/test/modules-validation-overlay.test \
    tools/clang/tools/extra/clangd/test/modules-stale-lock.test \
    tools/clang/tools/extra/clangd/test/semantic-tokens-range.test \
    tools/clang/tools/extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-ranges.cpp \
    tools/clang/tools/extra/test/clang-tidy/checkers/misc/const-correctness-cxx20-range-constraints.cpp \
    tools/clang/tools/extra/clangd/test/modules-bounded-dag.test \
    tools/clang/tools/extra/clangd/test/modules.test \
    tools/clang/tools/extra/clangd/test/module_dependencies.test \
    tools/clang/tools/extra/clangd/test/modules_no_cdb.test \
    tools/clang/test/Modules/pr218152.cppm
fi

if [[ -n "${PACKAGE:-}" ]]; then
  ./ci/scripts/package.sh
fi
