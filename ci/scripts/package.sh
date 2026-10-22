#!/usr/bin/env bash
# package.sh — assemble the mcppls payload "clangd part" (ci/recipe.md):
#   clangd/bin/clangd[.exe] + clangd/lib/clang/<major>/include + SHA256SUMS
source "$(dirname "$0")/env.sh"

CLANGD="$BUILD_DIR/bin/clangd"
[[ -x "$CLANGD" ]] || CLANGD="$BUILD_DIR/bin/clangd.exe"   # windows artifact name
[[ -x "$CLANGD" ]] || { echo "package.sh: $BUILD_DIR/bin/clangd[.exe] not built" >&2; exit 1; }

OUT="$DIST_DIR/clangd-$FORK_VERSION-$PLATFORM"
rm -rf "$OUT"
mkdir -p "$OUT/clangd/bin" "$OUT/clangd/lib"

# copy under the platform's artifact name directly; on windows MSYS resolves
# both `clangd` and `clangd.exe` to the same file, so a rename would refuse
case "$PLATFORM" in
  win32-*) TARGET="clangd.exe" ;;
  *)       TARGET="clangd" ;;
esac
cp "$CLANGD" "$OUT/clangd/bin/$TARGET"
# The release ships clangd stripped. Its symbol table, which costs no build time (the build has no
# debug information to keep), goes beside the part as the unstripped binary: a crash's module
# offsets in a mcpp-language-server incident (the stack clangd printed, with "??" for every frame)
# are named with `llvm-symbolizer --obj=<symbols>/clangd/bin/clangd`. Windows has its PDB instead
# (ci/windows-symbols.md). The part, and so engine.json, is unchanged by it.
SYMBOLS="$OUT-symbols"
rm -rf "$SYMBOLS"
if [[ "$PLATFORM" != win32-* ]]; then
  mkdir -p "$SYMBOLS/clangd/bin"
  cp "$CLANGD" "$SYMBOLS/clangd/bin/clangd"
fi
if command -v strip >/dev/null 2>&1; then
  strip "$OUT/clangd/bin/clangd"* 2>/dev/null || true
fi
# Stripping a Mach-O invalidates its signature, and Apple Silicon refuses to run an unsigned arm64
# executable. The part is shipped byte for byte (mcpp-language-server never re-signs it), so it is
# signed here, before engine.json records its SHA-256.
if [[ "$PLATFORM" == darwin-* ]]; then
  codesign --force --sign - "$OUT/clangd/bin/clangd"
fi

MAJOR="$("$OUT/clangd/bin/clangd"* --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)"
if [[ -d "$BUILD_DIR/lib/clang/$MAJOR/include" ]]; then
  mkdir -p "$OUT/clangd/lib/clang/$MAJOR"
  cp -a "$BUILD_DIR/lib/clang/$MAJOR/include" "$OUT/clangd/lib/clang/$MAJOR/include"
fi

# Both the upstream license and distribution notice accompany the engine.
cp "$LLVM_DIR/llvm/LICENSE.TXT" "$OUT/clangd/LICENSE.TXT"
cat > "$OUT/clangd/NOTICE.txt" <<EOF
mcppls-clangd is based on LLVM/Clang $UPSTREAM_VERSION.
Upstream: https://github.com/llvm/llvm-project
Modifications: https://github.com/Sunrisepeak/mcppls-clangd
LLVM is distributed under Apache-2.0 WITH LLVM-exception; see LICENSE.TXT.
Engine source and ordered patch identities are recorded in engine.json.
EOF
if [[ -n "${RUNTIME_LICENSE_DIR:-}" ]]; then
  mkdir -p "$OUT/clangd/licenses"
  cp -a "$RUNTIME_LICENSE_DIR/." "$OUT/clangd/licenses/"
fi
python3 "$REPO_DIR/ci/package_identity.py" --build-dir "$BUILD_DIR" --llvm-dir "$LLVM_DIR" --directory "$OUT/clangd" \
  --version "$FORK_VERSION" --platform "$PLATFORM" --checksums "$OUT"
if [[ -d "$SYMBOLS" ]]; then
  # Which shipped binary these symbols are of: its SHA-256, as engine.json and the incident record it.
  if command -v sha256sum >/dev/null 2>&1; then SHIPPED=$(sha256sum "$OUT/clangd/bin/clangd" | cut -d' ' -f1)
  else SHIPPED=$(shasum -a 256 "$OUT/clangd/bin/clangd" | cut -d' ' -f1); fi
  printf 'The unstripped clangd %s (%s) whose stripped binary has SHA-256 %s.\n' "$FORK_VERSION" "$PLATFORM" "$SHIPPED" > "$SYMBOLS/README.txt"
fi

echo "package.sh: $OUT"
