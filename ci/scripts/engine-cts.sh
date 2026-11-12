#!/usr/bin/env bash
# engine-cts.sh -- the engine's test program (tests/) against one engine on this system.
#
#   engine-cts.sh --tree T --engine E [--runner R] --clang C [--platform P] [--has a,b]
#                 [--tidy T --c-index-test X --clang-repl Y] [--control K] --out D [--jobs N]
#                 [-- <mtest run options>]
#
# T is what the job `program` of .github/workflows/engine-cts.yml built once: the directory that holds
# engine-cts-*.okb (the program as an ok image of both architectures) and engine-cts-*-openkal-bundle-all.zip
# (the same images with the runner of every system). mtest starts the okb under this system's runner from
# that tree, so a job needs neither mcpp nor a compiler to run the cases.
#
# E is the engine: clangd.okb with --runner (okrun, or `tree` for the tree's own), or a native build. C is
# the compiler the compile commands name. --has names what the subject has beyond what the program sees by
# itself (tests/cts/harness.cppm): matching-clang where C is the engine's own build. The three tools are a
# build tree's, and K is an engine without a fix that a case proves by it (started as E is); a case that needs
# one the subject lacks is reported as not run, with that reason.
#
# D receives the run: .mtest (mtest's store), junit.xml, report.md, and kept/ (each case's project and what
# its sessions answered). The exit status is mtest's: 0 when no case failed.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
tree="" engine="" runner="" clang="" platform="" has="" tidy="" cindex="" repl="" control="" out="" jobs=2
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) tree=$2; shift 2 ;;
    --engine) engine=$2; shift 2 ;;
    --runner) runner=$2; shift 2 ;;
    --clang) clang=$2; shift 2 ;;
    --platform) platform=$2; shift 2 ;;
    --has) has=$2; shift 2 ;;
    --tidy) tidy=$2; shift 2 ;;
    --c-index-test) cindex=$2; shift 2 ;;
    --clang-repl) repl=$2; shift 2 ;;
    --control) control=$2; shift 2 ;;
    --out) out=$2; shift 2 ;;
    --jobs) jobs=$2; shift 2 ;;
    --) shift; break ;;
    *) echo "engine-cts.sh: unknown argument $1" >&2; exit 2 ;;
  esac
done
[ -n "$tree" ] && [ -n "$engine" ] && [ -n "$clang" ] && [ -n "$out" ] || { sed -n '2,7p' "${BASH_SOURCE[0]}" >&2; exit 2; }

python=python3; command -v python3 > /dev/null 2>&1 || python=python
exe=""
case "$(uname -s)" in
  Linux) system=linux ;;
  Darwin) system=macos ;;
  MINGW*|MSYS*|CYGWIN*) system=windows; exe=.exe ;;
  *) echo "engine-cts.sh: no runner for $(uname -s)" >&2; exit 2 ;;
esac
case "$(uname -m)" in
  x86_64|amd64|AMD64) arch=x86_64 ;;
  aarch64|arm64|ARM64) arch=aarch64 ;;
  *) echo "engine-cts.sh: no image for $(uname -m)" >&2; exit 2 ;;
esac
# A name the programs of this system open: on Windows the shell's /d/a is not one.
native() { if [ "$system" = windows ]; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }
absolute() { case "$1" in /*|?:*) printf '%s\n' "$1" ;; *) printf '%s/%s\n' "$PWD" "$1" ;; esac; }

mkdir -p "$out"
out="$(cd "$out" && pwd)"
okb="$(ls "$tree"/engine-cts-*.okb | head -1)"
zip="$(ls "$tree"/engine-cts-*-openkal-bundle-all.zip | head -1)"
rm -rf "$out/tree" && mkdir -p "$out/tree"
"$python" -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$(native "$zip")" "$(native "$out/tree")"
okrun="$(ls -d "$out"/tree/*/libexec/okrun/"$system-$arch"/okrun"$exe")"
chmod +x "$okrun"

# mtest: the release bundle ci/mtest.env pins, its sha256 checked; MTEST names one already there.
. "$root/ci/mtest.env"
if [ -z "${MTEST:-}" ]; then
  archive="mtest-$MTEST_VERSION-openkal-bundle-all.tar.gz"
  cache="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/mtest-$MTEST_VERSION"
  [ "$system" = windows ] && cache="$(cygpath -u "$cache")"
  if [ ! -d "$cache/mtest-$MTEST_VERSION-openkal-bundle-all" ]; then
    mkdir -p "$cache"
    curl -fsSL --retry 5 --retry-all-errors --retry-delay 5 -o "$cache/$archive" \
      "https://github.com/mcpp-community/mtest/releases/download/v$MTEST_VERSION/$archive"
    actual="$("$python" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$(native "$cache/$archive")")"
    [ "$actual" = "$MTEST_SHA256" ] || { echo "engine-cts.sh: $archive has sha256 $actual, ci/mtest.env says $MTEST_SHA256" >&2; exit 1; }
    tar xzf "$cache/$archive" -C "$cache"
  fi
  MTEST="$cache/mtest-$MTEST_VERSION-openkal-bundle-all/bin/mtest$exe"
fi
"$MTEST" --version | grep -qF "$MTEST_VERSION" || { echo "engine-cts.sh: $MTEST is not mtest $MTEST_VERSION" >&2; exit 1; }

export MCPPLS_ENGINE="$(native "$(absolute "$engine")")"
[ "$runner" != tree ] || runner="$okrun"
if [ -n "$runner" ]; then export MCPPLS_ENGINE_RUNNER="$(native "$(absolute "$runner")")"; else unset MCPPLS_ENGINE_RUNNER; fi
export MCPPLS_ENGINE_CLANG="$(native "$(absolute "$clang")")"
export MCPPLS_ENGINE_HAS="$has"
if [ -n "$platform" ]; then export MCPPLS_ENGINE_PLATFORM="$platform"; else unset MCPPLS_ENGINE_PLATFORM; fi
if [ -n "$tidy" ]; then export MCPPLS_ENGINE_TIDY="$(native "$(absolute "$tidy")")"; else unset MCPPLS_ENGINE_TIDY; fi
if [ -n "$cindex" ]; then export MCPPLS_ENGINE_C_INDEX_TEST="$(native "$(absolute "$cindex")")"; else unset MCPPLS_ENGINE_C_INDEX_TEST; fi
if [ -n "$repl" ]; then export MCPPLS_ENGINE_CLANG_REPL="$(native "$(absolute "$repl")")"; else unset MCPPLS_ENGINE_CLANG_REPL; fi
if [ -n "$control" ]; then export MCPPLS_ENGINE_CONTROL="$(native "$(absolute "$control")")"; else unset MCPPLS_ENGINE_CONTROL; fi
mkdir -p "$out/kept"
export MCPPLS_ENGINE_KEEP="$(native "$out/kept")"

cd "$out"
status=0
"$MTEST" run --isolate --jobs "$jobs" --junit "$(native "$out/junit.xml")" "$@" --run-under "$(native "$okrun")" "$(native "$(absolute "$okb")")" || status=$?
"$MTEST" report --format md --run last --sections summary,failures,slowest --top 10 --out "$(native "$out/report.md")" || true
[ -z "${GITHUB_STEP_SUMMARY:-}" ] || [ ! -f "$out/report.md" ] || cat "$out/report.md" >> "$GITHUB_STEP_SUMMARY"
if [ "$status" != 0 ]; then "$MTEST" explain || true; fi
exit "$status"
