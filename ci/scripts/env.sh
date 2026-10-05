#!/usr/bin/env bash
# Shared environment for ci/scripts/*.sh. Source, do not execute.
#   $(dirname $0)/env.sh
set -euo pipefail

CI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$CI_DIR/.." && pwd)"

# UPSTREAM: the pin. Parse repo/ref from the three-line file.
UPSTREAM_REF="$(awk -F': *' '/^ref:/{print $2}' "$REPO_DIR/UPSTREAM")"
UPSTREAM_REPO="$(awk -F': *' '/^repo:/{print $2}' "$REPO_DIR/UPSTREAM")"
# llvmorg-23.1.0 -> 23.1.0
UPSTREAM_VERSION="${UPSTREAM_REF#llvmorg-}"

# The fork version: upstream version + our suffix (D4).
FORK_SUFFIX="${FORK_SUFFIX:--mcppls.0}"
FORK_VERSION="${UPSTREAM_VERSION}${FORK_SUFFIX}"

# Working tree (gitignored), build dir, dist dir.
LLVM_DIR="${LLVM_DIR:-$REPO_DIR/llvm-project}"
BUILD_DIR="${BUILD_DIR:-$REPO_DIR/build-${PLATFORM:-linux-x64}}"
DIST_DIR="${DIST_DIR:-$REPO_DIR/dist}"
TARBALL="${TARBALL:-$REPO_DIR/llvm-src.tar.gz}"
TARBALL_SHA256="$(awk '{print $1}' "$REPO_DIR/ci/tarball.sha256" 2>/dev/null || true)"

# Platform: linux-x64 | linux-arm64 | darwin-arm64 | win32-x64
if [[ -z "${PLATFORM:-}" ]]; then
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)  PLATFORM=linux-x64 ;;
    Linux-aarch64) PLATFORM=linux-arm64 ;;
    Darwin-arm64)  PLATFORM=darwin-arm64 ;;
    MINGW*|MSYS*)  PLATFORM=win32-x64 ;;
    *) echo "env.sh: unknown platform $(uname -s)-$(uname -m); set PLATFORM" >&2; exit 1 ;;
  esac
fi

export LLVM_DIR BUILD_DIR DIST_DIR PLATFORM FORK_VERSION FORK_SUFFIX UPSTREAM_REF UPSTREAM_VERSION
