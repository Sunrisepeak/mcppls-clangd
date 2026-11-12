#!/usr/bin/env bash
# Run inside the pinned Ubuntu 20.04 rootfs, with the repository mounted.
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ "$(. /etc/os-release; echo "$VERSION_ID")" == "20.04" ]] || {
  echo "linux-floor: this recipe requires an actual Ubuntu 20.04 environment" >&2
  exit 1
}
export DEBIAN_FRONTEND=noninteractive
bash ci/scripts/apt-install.sh ca-certificates curl git g++ clang-12 ninja-build ccache python3 python3-pip zlib1g-dev binutils
python3 -m pip install 'cmake>=3.20,<4'
git config --global --add safe.directory "$PWD"
git config --global --add safe.directory "$PWD/llvm-project"
export PLATFORM="${PLATFORM:-linux-x64}" CC=/usr/bin/clang-12 CXX=/usr/bin/clang++-12 FORCE_STATIC_DEPS=1
export BUILD_DIR="${BUILD_DIR:-$PWD/build-$PLATFORM-ubuntu20}"
export DIST_DIR="${DIST_DIR:-$PWD/dist/linux-floor}"
export CCACHE_DIR="${CCACHE_DIR:-/tmp/mcppls-floor-ccache}"
export RUNTIME_LICENSE_DIR="$BUILD_DIR/runtime-licenses"
mkdir -p "$RUNTIME_LICENSE_DIR"
cp /usr/share/doc/gcc-9-base/copyright "$RUNTIME_LICENSE_DIR/GCC-RUNTIME-copyright.txt"
cp /usr/share/common-licenses/GPL-3 "$RUNTIME_LICENSE_DIR/GPL-3.txt"
cp /usr/share/doc/zlib1g-dev/copyright "$RUNTIME_LICENSE_DIR/zlib-copyright.txt"
source ci/scripts/env.sh
git config --global --add safe.directory "$LLVM_DIR"
./ci/ci_build.sh
# The installed-engine semantic gates below need this same-source driver;
# the non-test ci_build stage builds only clangd.
cmake --build "$BUILD_DIR" --target clang clang-resource-headers -j "${JOBS:-4}"
# Resource headers must be present before the final build stamp is recorded.
python3 ci/build_identity.py --build-dir "$BUILD_DIR" --llvm-dir "$LLVM_DIR" --platform "$PLATFORM"
./ci/scripts/package.sh
python3 ci/portability_linux.py \
  "$DIST_DIR/clangd-${FORK_VERSION:-23.1.0-mcppls.6}-$PLATFORM/clangd/bin/clangd" \
  --output "$DIST_DIR/portability-$PLATFORM.json"
# The series' regressions that say something about the packaged engine on this floor, by the test program the
# run built once (tests/cts/README.md): the tree is in engine-cts/ of the repository, put there before this
# container started (.github/actions/linux-floor). The compile commands name the build's own driver.
bash ci/scripts/engine-cts.sh --tree engine-cts \
  --engine "$DIST_DIR/clangd-$FORK_VERSION-$PLATFORM/clangd/bin/clangd" \
  --clang "$BUILD_DIR/bin/clang" --platform "$PLATFORM" --has matching-clang --out "$BUILD_DIR/cts" -- \
  --case 'module-request-inputs*' --case 'module-dag*' --case 'module-cold-completion*' --case 'module-scan-*' \
  --case 'module-drafts*' --case 'compiler-extensions*' --case 'module-directive-recovery*' \
  --case 'module-lock-close*' --case 'module-cycle*'
