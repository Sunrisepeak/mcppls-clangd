#!/usr/bin/env bash
# probe-platform.sh DIR -- writes DIR, an empty project over the platform the images are built over.
#
# The platform is stated once, in openkal/clangd/mcpp.toml (its `[target.'cfg(os = "openkal")']`
# table); a step that needs that platform's okrun or okld builds this probe and asks
# `mcpp self env --target <arch>-openkal` in it. The probe repeats no version.
set -euo pipefail
dir=$1
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
platform="$(sed -n 's/^platform *= *"\(openkal-platform@[^"]*\)"$/\1/p' "$root/openkal/clangd/mcpp.toml")"
[ "$(printf '%s\n' "$platform" | grep -c .)" = 1 ] \
  || { echo "openkal/clangd/mcpp.toml states no single platform" >&2; exit 1; }
mkdir -p "$dir/src"
printf '[package]\nname = "%s"\nversion = "0.1.0"\n\n[target.'"'"'cfg(os = "openkal")'"'"']\nplatform = "%s"\n' \
  "$(basename "$dir")" "$platform" > "$dir/mcpp.toml"
printf 'int main() { return 0; }\n' > "$dir/src/main.cpp"
