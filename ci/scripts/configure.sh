#!/usr/bin/env bash
# configure.sh — cmake configure per ci/recipe.md (D3: upstream release paradigm).
source "$(dirname "$0")/env.sh"

CC="${CC:-}"
CXX="${CXX:-}"
COMPILER_FLAGS=()
[[ -n "$CC"  ]] && COMPILER_FLAGS+=(-DCMAKE_C_COMPILER="$CC")
[[ -n "$CXX" ]] && COMPILER_FLAGS+=(-DCMAKE_CXX_COMPILER="$CXX")

EXTRA=()
case "$PLATFORM" in
  linux-*)
    # recipe: old-glibc container is the compat floor; static libgcc + deps.
    # The static-deps part needs static system libs (CI container installs
    # them); local dev boxes opt in with FORCE_STATIC_DEPS=1.
    EXTRA+=(-DCMAKE_EXE_LINKER_FLAGS_RELEASE="-static-libgcc -static-libstdc++ -Wl,--compress-debug-sections=zlib")
    [[ "${FORCE_STATIC_DEPS:-0}" = "1" ]] && EXTRA+=(-DCMAKE_FIND_LIBRARY_SUFFIXES=".a")
    ;;
  darwin-x64)
    EXTRA+=(-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0 -DCMAKE_OSX_ARCHITECTURES=x86_64
            -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF)
    ;;
  darwin-arm64)
    EXTRA+=(-DCMAKE_OSX_DEPLOYMENT_TARGET=12.0 -DCMAKE_OSX_ARCHITECTURES=arm64
            -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF)
    ;;
  win32-x64)
    # Avoid a separately installed Visual C++ runtime on a clean Windows host.
    EXTRA+=(-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded
            -DLLVM_USE_CRT_RELEASE=MT -DLLVM_ENABLE_ZSTD=OFF
            -DLLVM_ENABLE_LIBXML2=OFF)
    if [[ "${SYMBOLS:-0}" = "1" ]]; then
      # sccache requires per-object debug information: /Zi's shared compiler
      # PDB fails under parallel cached CL invocations even with /FS. /Z7
      # embeds it in each object; /DEBUG still produces the linked PDB.
      EXTRA+=(-DCMAKE_POLICY_DEFAULT_CMP0141=NEW
              -DCMAKE_MSVC_DEBUG_INFORMATION_FORMAT=Embedded
              -DLLVM_ENABLE_PDB=OFF
              "-DCMAKE_EXE_LINKER_FLAGS=/DEBUG /OPT:REF /OPT:ICF")
    fi
    ;;
esac

# ccache when available (the CI lever: first build 1-3h, patch iterations minutes)
CCACHE_FLAGS=()
if command -v ccache >/dev/null 2>&1; then
  CCACHE_FLAGS+=(-DLLVM_CCACHE_BUILD=ON -DLLVM_CCACHE_DIR="${CCACHE_DIR:-$HOME/.ccache-mcppls-clangd}" -DLLVM_CCACHE_MAXSIZE=10G)
fi

# sanitizer builds for the soak job (LLVM's combined flag spelling)
SANITIZER_FLAGS=()
if [[ -n "${SANITIZERS:-}" ]]; then
  SANITIZER_FLAGS+=(-DLLVM_USE_SANITIZER="$SANITIZERS")
fi

cmake -G Ninja -S "$LLVM_DIR/llvm" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_APPEND_VC_REV=OFF \
  -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" \
  -DLLVM_TARGETS_TO_BUILD="${LLVM_TARGETS_TO_BUILD:-host;X86;AArch64}" \
  -DLLVM_ENABLE_PLUGINS=OFF \
  -DLLVM_ENABLE_WERROR=OFF \
  -DLLVM_VERSION_SUFFIX="$FORK_SUFFIX" \
  -DLLVM_INCLUDE_TESTS=ON \
  ${COMPILER_FLAGS[@]+"${COMPILER_FLAGS[@]}"} \
  ${EXTRA[@]+"${EXTRA[@]}"} \
  ${CCACHE_FLAGS[@]+"${CCACHE_FLAGS[@]}"} \
  ${SANITIZER_FLAGS[@]+"${SANITIZER_FLAGS[@]}"} \
  ${CMAKE_EXTRA:-}

echo "configure.sh: done ($BUILD_DIR, platform=$PLATFORM, version=$FORK_VERSION)"
