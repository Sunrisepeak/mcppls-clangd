#!/usr/bin/env bash
# build-image.sh <arch> — clangd as an ok image of <arch>-openkal (probe).
#
#   1. openkal's compile conventions, read from mcpp's compile of a plain unit (hello/)
#   2. the host tools a cross build of LLVM runs (tablegen, the confusable-chars generator)
#   3. CMake builds the static libraries clangd links, with those conventions
#   4. mcpp links clangd's main over them and seals the image (make_link_project.py)
#
# Writes out/: clangd-<arch>.oke, compile-errors-<arch>.txt, sizes-<arch>.txt and the logs.
# Needs: mcpp on PATH, $LLVM_DIR patched (ci/scripts/apply.sh, then openkal-llvm.patch).
set -uo pipefail
arch="$1"
root="$(cd "$(dirname "$0")/../.." && pwd)"
P="$root/probe/openkal"
out="$root/out"
mkdir -p "$out"
jobs="${JOBS:-$(nproc)}"

echo "::group::conventions of $arch-openkal"
(cd "$P/hello" && mcpp build --target "$arch-openkal") 2>&1 | tail -20
cdb="$(ls "$P"/hello/target/"$arch"-openkal/*/compile_commands.json | head -1)"
python3 "$P/gen_toolchain.py" "$cdb" probe.cpp "$arch" "$root/openkal-$arch.cmake"
cp "$root/openkal-$arch.cmake" "$out/"
echo "::endgroup::"

echo "::group::host tools"
if [[ ! -x "$root/host-tools/bin/clang-tidy-confusable-chars-gen" ]]; then
  cmake -G Ninja -S "$LLVM_DIR/llvm" -B "$root/host-tools" -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_PROJECTS="clang;clang-tools-extra" -DLLVM_TARGETS_TO_BUILD=X86 \
    -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_ZLIB=OFF \
    -DLLVM_ENABLE_LIBXML2=OFF -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache > "$out/host-tools.cfg.log"
  ninja -C "$root/host-tools" -j "$jobs" llvm-tblgen llvm-min-tblgen clang-tblgen clang-tidy-confusable-chars-gen \
    > "$out/host-tools.build.log" 2>&1 || { tail -50 "$out/host-tools.build.log"; exit 1; }
fi
ls "$root/host-tools/bin"
echo "::endgroup::"

echo "::group::configure"
CMAKE_EXTRA="-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache" \
  "$P/configure-openkal.sh" "$LLVM_DIR" "$root/build-openkal-$arch" "$root/openkal-$arch.cmake" \
  "$root/host-tools/bin" "$arch" > "$out/configure-$arch.log" 2>&1 || { tail -60 "$out/configure-$arch.log"; exit 1; }
grep -E "^HAVE_[A-Z0-9_]*:INTERNAL=1" "$root/build-openkal-$arch/CMakeCache.txt" | sed 's/:INTERNAL=1//' > "$out/have-$arch.txt" || true
echo "::endgroup::"

echo "::group::static libraries"
python3 "$P/make_link_project.py" "$root/build-openkal-$arch" "$root/link-$arch" > "$root/libs-$arch.txt"
wc -l < "$root/libs-$arch.txt"
start=$(date +%s)
ninja -C "$root/build-openkal-$arch" -k 0 -j "$jobs" $(cat "$root/libs-$arch.txt") > "$out/compile-$arch.log" 2>&1
libs_rc=$?
echo "libraries: rc=$libs_rc in $(( $(date +%s) - start ))s"
grep -E "^FAILED: " "$out/compile-$arch.log" | sed 's/^FAILED: //' > "$out/failed-$arch.txt" || true
grep -E "error:" "$out/compile-$arch.log" | sed "s|$LLVM_DIR/||" | sort | uniq -c | sort -rn > "$out/compile-errors-$arch.txt" || true
echo "failed objects: $(wc -l < "$out/failed-$arch.txt")"
head -80 "$out/compile-errors-$arch.txt"
echo "::endgroup::"
[[ $libs_rc -eq 0 ]] || exit 2

echo "::group::link and seal with mcpp"
(cd "$root/link-$arch" && mcpp build --release --target "$arch-openkal") > "$out/link-$arch.log" 2>&1
link_rc=$?
tail -60 "$out/link-$arch.log"
echo "::endgroup::"
[[ $link_rc -eq 0 ]] || exit 3

img="$(ls "$root"/link-"$arch"/target/"$arch"-openkal/*/bin/clangd.oke | head -1)"
cp "$img" "$out/clangd-$arch.oke"
{
  echo "image $(stat -c %s "$img")"
  llvm_bin="$(dirname "$(grep -m1 'CMAKE_CXX_COMPILER ' "$root/openkal-$arch.cmake" | awk '{print $2}' | tr -d ')')")"
  "$llvm_bin/llvm-strip" --strip-debug -o "$out/clangd-$arch.stripped.oke" "$img" && echo "stripped-debug $(stat -c %s "$out/clangd-$arch.stripped.oke")"
  "$llvm_bin/llvm-size" "$img" | tail -1
} | tee "$out/sizes-$arch.txt"
