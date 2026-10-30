#!/usr/bin/env bash
# apply.sh — apply the patch series in patches/ onto $LLVM_DIR with git am
# (authorship preserved; the tree keeps the upstream-facing commit history).
# A re-run on an already-applied tree is a no-op.
#
#   --openkal          then the openkal series (openkal/patches/series): the
#                      tree an ok image is built from, and no native engine is
#   --verify-openkal   apply the openkal series on top and reset to the tree
#                      before it (the series check, over a cached native tree)
source "$(dirname "$0")/env.sh"

MODE="${1:-}"
case "$MODE" in ""|--openkal|--verify-openkal) ;; *) echo "apply.sh: unknown option $MODE" >&2; exit 2 ;; esac

# The openkal series, applied with git am onto the tree the main series made.
apply_openkal() {
  local n=0 line
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"; line="${line%%#*}"; line="$(echo "$line" | xargs 2>/dev/null || echo "$line")"
    [[ -z "$line" ]] && continue
    echo "apply.sh: git am openkal/patches/$line"
    git -C "$LLVM_DIR" -c user.name=mcppls-clangd -c user.email=ci@mcppls.invalid \
        am -q -k "$REPO_DIR/openkal/patches/$line" \
      || { echo "apply.sh: FAILED on openkal/patches/$line" >&2; git -C "$LLVM_DIR" am --abort 2>/dev/null || true; return 1; }
    n=$((n+1))
  done < "$REPO_DIR/openkal/patches/series"
  echo "apply.sh: $n openkal patches applied"
}

IDENTITY="$(python3 "$REPO_DIR/ci/series_identity.py")"
OPENKAL_IDENTITY="$(python3 "$REPO_DIR/ci/series_identity.py" --openkal)"
MARKER="$LLVM_DIR/.mcppls-clangd-patched"
if [[ -f "$MARKER" ]]; then
  current="$(cat "$MARKER")"
  if [[ "$MODE" = --openkal && "$current" = "$OPENKAL_IDENTITY" ]]; then
    echo "apply.sh: identical series and openkal series already applied"; exit 0
  fi
  [[ "$current" = "$IDENTITY" ]] || {
    echo "apply.sh: stale patched tree; use a fresh LLVM_DIR for the changed series" >&2
    exit 1
  }
  echo "apply.sh: identical series already applied"
  if [[ "$MODE" = --openkal ]]; then
    apply_openkal && printf "%s\n" "$OPENKAL_IDENTITY" > "$MARKER"; exit
  elif [[ "$MODE" = --verify-openkal ]]; then
    base="$(git -C "$LLVM_DIR" rev-parse HEAD)"
    apply_openkal; rc=$?
    git -C "$LLVM_DIR" reset -q --hard "$base"
    exit $rc
  fi
  exit 0
fi

SERIES="$REPO_DIR/patches/series"
[[ -f "$SERIES" ]] || { echo "apply.sh: no patches/series" >&2; exit 0; }

cd "$LLVM_DIR"
if [[ ! -d .git ]]; then
  git init -q
  git add -A
  git -c user.name=mcppls-clangd -c user.email=ci@mcppls.invalid \
    commit -qm "llvm-project $UPSTREAM_REF (pinned base, unmodified)"
fi

applied=0
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"                 # tolerate CRLF checkouts on windows
  line="${line%%#*}"                   # tolerate trailing comments
  line="$(echo "$line" | xargs 2>/dev/null || echo "$line")"  # trim
  [[ -z "$line" ]] && continue
  p="$REPO_DIR/patches/$line"
  echo "apply.sh: git am $line"
  git -c user.name="$(git config user.name  || echo mcppls-clangd)" \
      -c user.email="$(git config user.email || echo ci@mcppls.invalid)" \
      am -q -k "$p" || { echo "apply.sh: FAILED on $line" >&2; git am --abort 2>/dev/null || true; exit 1; }
  applied=$((applied+1))
done < "$SERIES"

# overlay: new files, dropped in after the series (zero conflicts by design)
if [[ -d "$REPO_DIR/overlay" ]]; then
  echo "apply.sh: copying overlay/"
  cp -a "$REPO_DIR/overlay/." "$LLVM_DIR/"
fi

printf "%s\n" "$IDENTITY" > "$MARKER"
echo "apply.sh: $applied patches applied + overlay copied"
case "$MODE" in
  --openkal) apply_openkal && printf "%s\n" "$OPENKAL_IDENTITY" > "$MARKER" ;;
  --verify-openkal)
    base="$(git -C "$LLVM_DIR" rev-parse HEAD)"
    apply_openkal; rc=$?
    git -C "$LLVM_DIR" reset -q --hard "$base"
    exit $rc ;;
esac
