#!/usr/bin/env bash
# Run inside the pinned Ubuntu 20.04 rootfs, with the repository mounted.
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ "$(. /etc/os-release; echo "$VERSION_ID")" == "20.04" ]] || {
  echo "linux-floor: this recipe requires an actual Ubuntu 20.04 environment" >&2
  exit 1
}
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git g++ clang-12 ninja-build ccache python3 python3-pip zlib1g-dev binutils
python3 -m pip install 'cmake>=3.20,<4'
git config --global --add safe.directory "$PWD"
git config --global --add safe.directory "$PWD/llvm-project"
export PLATFORM=linux-x64 CC=/usr/bin/clang-12 CXX=/usr/bin/clang++-12 FORCE_STATIC_DEPS=1
export BUILD_DIR="${BUILD_DIR:-$PWD/build-linux-x64-ubuntu20}"
export DIST_DIR="${DIST_DIR:-$PWD/dist/linux-floor}"
export CCACHE_DIR="${CCACHE_DIR:-/tmp/mcppls-floor-ccache}"
export RUNTIME_LICENSE_DIR="$BUILD_DIR/runtime-licenses"
mkdir -p "$RUNTIME_LICENSE_DIR"
cp /usr/share/doc/gcc-9-base/copyright "$RUNTIME_LICENSE_DIR/GCC-RUNTIME-copyright.txt"
cp /usr/share/common-licenses/GPL-3 "$RUNTIME_LICENSE_DIR/GPL-3.txt"
cp /usr/share/doc/zlib1g-dev/copyright "$RUNTIME_LICENSE_DIR/zlib-copyright.txt"
source ci/scripts/env.sh
./ci/ci_build.sh
cmake --build "$BUILD_DIR" --target clang-resource-headers -j "${JOBS:-4}"
# Resource headers must be present before the final build stamp is recorded.
python3 ci/build_identity.py --build-dir "$BUILD_DIR" --llvm-dir "$PWD/llvm-project" --platform "$PLATFORM"
./ci/scripts/package.sh
python3 ci/portability_linux.py \
  "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.0}-$PLATFORM/clangd/bin/clangd" \
  --output "$DIST_DIR/portability-linux-x64.json"
python3 tests/e2e/completion_quality.py \
  --engine "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.0}-$PLATFORM/clangd/bin/clangd" \
  --clang /usr/bin/g++ --workdir "$BUILD_DIR/portable-module-quality" --unsaved-update --async-scheduling

python3 tests/e2e/compiler_extensions.py \
  --engine "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.0}-$PLATFORM/clangd/bin/clangd" \
  --clang /usr/bin/clang-12 --workdir "$BUILD_DIR/portable-compiler-extensions"

python3 tests/e2e/module_directive_recovery.py \
  --engine "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.0}-$PLATFORM/clangd/bin/clangd" \
  --clang /usr/bin/clang-12 --workdir "$BUILD_DIR/portable-module-directive-recovery"

python3 tests/e2e/module_lock_close.py \
  --engine "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.0}-$PLATFORM/clangd/bin/clangd" \
  --clang /usr/bin/clang-12 --workdir "$BUILD_DIR/portable-module-lock-close"
