#!/usr/bin/env bash
set -euo pipefail
cd /repo
python3 - <<'CHECK'
import json,re
from pathlib import Path
assert json.loads(Path('/out/source-progress.json').read_text())['status']=='complete'
base=Path('/candidate')
assert json.loads((base/'progress.json').read_text())['status']=='complete'
assert json.loads((base/'existing-completion-controls.json').read_text())['exit_code']==0
assert re.search(r'\[\s+PASSED\s+\]\s+2 tests', (base/'new-controls.log').read_text())
for context in ['first-column','ordinary']:
 s=json.loads((base/'matched-index-settled'/context/'summary.json').read_text())
 assert s['all_returned_items_within_verified_reference']
 assert len(s['arms'])==3 and all(a['selected_gcc_insertions']>0 and not a['compiler_overlap'] and not a['sampler_errors'] and a['watcher_stopped'] for a in s['arms'].values())
CHECK
git config --global --add safe.directory /repo
git config --global --add safe.directory /source
export PLATFORM=linux-x64 LLVM_DIR=/source BUILD_DIR=/out/build DIST_DIR=/out/dist
export CC=/usr/bin/clang-12 CXX=/usr/bin/clang++-12 FORCE_STATIC_DEPS=1 JOBS=6
export TEST=1 RUN_TESTS=lit-subset TMPDIR=/compiler-temp
export CMAKE_EXTRA="-DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DLLVM_CCACHE_BUILD=OFF"
export RUNTIME_LICENSE_DIR=/out/build/runtime-licenses
mkdir -p "$RUNTIME_LICENSE_DIR"
cp /usr/share/doc/gcc-9-base/copyright "$RUNTIME_LICENSE_DIR/GCC-RUNTIME-copyright.txt"
cp /usr/share/common-licenses/GPL-3 "$RUNTIME_LICENSE_DIR/GPL-3.txt"
cp /usr/share/doc/zlib1g-dev/copyright "$RUNTIME_LICENSE_DIR/zlib-copyright.txt"
bash ci/ci_build.sh
bash ci/scripts/package.sh
python3 ci/portability_linux.py /out/dist/clangd-23.1.0-mcppls.0-linux-x64/clangd/bin/clangd --output /out/portability.json
