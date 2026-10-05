#!/usr/bin/env bash
# package.sh — assemble the mcppls payload "clangd part" (ci/recipe.md):
#   clangd/bin/clangd[.exe] + clangd/lib/clang/<major>/include + SHA256SUMS
source "$(dirname "$0")/env.sh"

CLANGD="$BUILD_DIR/bin/clangd"
[[ -x "$CLANGD" ]] || { echo "package.sh: $CLANGD not built" >&2; exit 1; }

OUT="$DIST_DIR/clangd-$FORK_VERSION-$PLATFORM"
rm -rf "$OUT"
mkdir -p "$OUT/clangd/bin" "$OUT/clangd/lib"

cp "$CLANGD" "$OUT/clangd/bin/"
case "$PLATFORM" in win32-*) mv "$OUT/clangd/bin/clangd" "$OUT/clangd/bin/clangd.exe";; esac
strip "$OUT/clangd/bin/clangd"* 2>/dev/null || true

MAJOR="$("$OUT/clangd/bin/clangd"* --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)"
if [[ -d "$BUILD_DIR/lib/clang/$MAJOR/include" ]]; then
  cp -a "$BUILD_DIR/lib/clang/$MAJOR/include" "$OUT/clangd/lib/clang/$MAJOR_include_tmp"
  mkdir -p "$OUT/clangd/lib/clang/$MAJOR"
  mv "$OUT/clangd/lib/clang/$MAJOR_include_tmp" "$OUT/clangd/lib/clang/$MAJOR/include"
fi

( cd "$OUT" && find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )

echo "package.sh: $OUT"
cat "$OUT/SHA256SUMS"
