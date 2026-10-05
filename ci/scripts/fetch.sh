#!/usr/bin/env bash
# fetch.sh — get the pinned llvm-project tree into $LLVM_DIR.
# Reuses an already-fetched tree (marker file records the ref and the tarball digest).
source "$(dirname "$0")/env.sh"

MARKER="$LLVM_DIR/.mcppls-clangd-fetched-$UPSTREAM_REF"

if [[ -f "$MARKER" ]]; then
  echo "fetch.sh: $LLVM_DIR already has $UPSTREAM_REF"
  exit 0
fi

mkdir -p "$LLVM_DIR" "$DIST_DIR"

if [[ ! -f "$TARBALL" ]]; then
  echo "fetch.sh: downloading $UPSTREAM_REF source tarball"
  URL="https://codeload.github.com/llvm/llvm-project/tar.gz/refs/tags/$UPSTREAM_REF"
  for i in 1 2 3 4 5; do
    curl -sfL --retry 3 --connect-timeout 30 -o "$TARBALL" "$URL" && break
    sleep 10
  done
  [[ -f "$TARBALL" ]] || { echo "fetch.sh: download failed" >&2; exit 1; }
fi

if [[ -n "$TARBALL_SHA256" ]]; then
  echo "fetch.sh: verifying tarball digest"
  if command -v sha256sum >/dev/null 2>&1; then
    echo "$TARBALL_SHA256  $TARBALL" | sha256sum -c -
  else
    echo "$TARBALL_SHA256  $TARBALL" | shasum -a 256 -c -
  fi
fi

echo "fetch.sh: extracting"
# Windows runners cannot create the test fixtures' symlinks; those files are
# irrelevant to the clangd build, so tolerate symlink errors and verify the
# tree landed by its anchor file instead.
tar xzf "$TARBALL" -C "$LLVM_DIR" --strip-components=1 2>&1 | \
  grep -v "Cannot create symlink" || true
[[ -f "$LLVM_DIR/llvm/CMakeLists.txt" ]] || {
  echo "fetch.sh: extraction failed (no llvm/CMakeLists.txt)" >&2
  exit 1
}
touch "$MARKER"
echo "fetch.sh: done ($LLVM_DIR)"
