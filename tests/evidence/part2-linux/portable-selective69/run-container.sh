#!/usr/bin/env bash
set -euo pipefail
cd /repo
python3 - <<'CHECK'
import json
from pathlib import Path
base=Path('/prerequisite')
assert json.loads((base/'progress.json').read_text())['current_stage']=='complete', 'local clean consumer build/test must pass first'
matrix=json.loads((base/'matrix-control/summary.json').read_text())
assert len(matrix['results'])==12 and all(r['exit_code']==0 and r.get('semantic_pass') is True and r.get('all_selected_insertions_compiled') is not False for r in matrix['results'].values()), '12-context short correctness control must pass first'
native=json.loads((base/'native-settled-control/summary.json').read_text())
assert native.get('all_item_edit_fields_equal') is True and len(native['arms'])==3 and all(r.get('selected_native_insertions',0)>0 for r in native['arms'].values()), 'correct stock short control must pass first'
cold=json.loads((base/'native-candidate-control/candidate/report.json').read_text())
assert cold['all_semantic_requests_passed'] and cold['semantic_counts']['cold-open']['passed']==1, 'candidate cold correctness must pass; stock cold failure remains separately recorded'
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
