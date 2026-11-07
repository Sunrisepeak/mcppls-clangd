#!/usr/bin/env python3
"""The engine's end-to-end regressions (tests/e2e) against one engine on this system.

usage: e2e_suite.py --engine E [--runner R] --clang C --platform P --workdir W [--matching-clang]

The engine is what users run, clangd.okb started by the system's runner (--runner, okrun), or a native build. Each
case is one script of tests/e2e with the arguments build-test gives it; the runner reaches the scripts through
MCPPLS_ENGINE_RUNNER (tests/crash/replay.py). --clang is a compiler the compile commands name. Two cases read a BMI
another compiler wrote, which the engine loads only when that compiler is the engine's own build (--matching-clang);
without one they are reported as not run, with that reason. The report is W/e2e-suite.json; any failed case exits 1.
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name, script, arguments after --engine/--clang/--workdir, the platforms it runs on (None: every one), and whether a
# BMI written by --clang is read.
CASES = [
    ("module-dag", "module_dag.py", [], None, True),
    ("module-response-inputs", "module_response_inputs.py", [], None, False),
    ("module-cold-completion", "module_cold_completion.py", [], None, False),
    ("module-preamble-mode", "module_preamble_mode.py", [], None, False),
    ("module-worker-default", "module_worker_default.py", ["--dependency-mode", "MMD"], "linux", False),
    ("module-worker-payloads", "module_worker_default.py",
     ["--engine-flag=--modules-builder-worker-output-mib=1", "--engine-flag=--modules-builder-worker-capture-mib=1"],
     "linux", False),
    ("module-worker-failure", "module_worker_failure.py", [], "linux", False),
    ("module-worker-diagnostics", "module_worker_diagnostics.py", [], "linux", False),
    ("module-provider-cache", "module_provider_cache.py", [], None, True),
    ("module-scan-memo", "module_scan_memo.py", [], "linux", False),
    ("module-scan-builtins", "module_scan_builtins.py", [], "linux", False),
    ("module-cache-lease", "module_cache_lease.py", [], None, False),
    ("module-cache-lease-legacy", "module_cache_lease.py", ["--cache-mode", "legacy"], "linux", False),
    ("module-request-inputs", "module_request_inputs.py", [], None, False),
    ("module-directive-diagnostics", "module_directive_diagnostics.py", [], None, False),
    ("module-quality", "completion_quality.py", ["--async-scheduling"], None, False),
    ("module-drafts", "completion_quality.py", ["--unsaved-update", "--async-scheduling"], None, False),
    ("module-cycle", "module_cycle.py", [], None, False),
    ("third-party-import", "third_party_import.py", [], None, False),
    ("module-lock-close", "module_lock_close.py", [], None, False),
    ("module-directive-recovery", "module_directive_recovery.py", [], None, False),
    ("compiler-extensions", "compiler_extensions.py", [], None, False),
]

ap = argparse.ArgumentParser()
ap.add_argument("--engine", required=True)
ap.add_argument("--runner")
ap.add_argument("--clang", required=True)
ap.add_argument("--platform", required=True)
ap.add_argument("--workdir", required=True)
ap.add_argument("--matching-clang", action="store_true")
ap.add_argument("--case", action="append", help="run only the named cases")
a = ap.parse_args()

work = Path(a.workdir).resolve()
work.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
if a.runner:
    env["MCPPLS_ENGINE_RUNNER"] = str(Path(a.runner).resolve())
engine, clang = str(Path(a.engine).resolve()), str(Path(a.clang).resolve())
system = a.platform.split("-")[0]
results = []
for name, script, extra, only, reads_bmi in CASES:
    if a.case and name not in a.case:
        continue
    if only and only != system:
        continue
    if reads_bmi and not a.matching_clang:
        results.append({"case": name, "status": "not_run", "reason": "reads a BMI only the engine's own clang writes"})
        continue
    if name == "module-worker-diagnostics" and a.runner:
        # The bounded FIFO transport is native Linux's; the image takes the portable one (issue 19).
        results.append({"case": name, "status": "not_run",
                        "reason": "the image's worker diagnostics take the portable transport, not native Linux's FIFO "
                                  "(https://github.com/Sunrisepeak/mcppls-clangd/issues/19)"})
        continue
    if script == "module_directive_diagnostics.py":   # its own runner option, and no compiler
        argv = [sys.executable, str(ROOT / "tests/e2e" / script), "--engine", engine,
                "--output", str(work / f"{name}.json"), *(["--runner", env["MCPPLS_ENGINE_RUNNER"]] if a.runner else [])]
    else:
        argv = [sys.executable, str(ROOT / "tests/e2e" / script), "--engine", engine, "--clang", clang,
                "--workdir", str(work / name), *extra]
    started = time.monotonic()
    run = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    seconds = round(time.monotonic() - started, 2)
    (work / f"{name}.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    status = "pass" if run.returncode == 0 else "fail"
    results.append({"case": name, "status": status, "exit": run.returncode, "seconds": seconds})
    print(f"{name}: {status} ({seconds}s)", flush=True)
    if status == "fail":
        print((run.stdout + run.stderr)[-4000:], flush=True)

report = {"engine": engine, "runner": a.runner, "platform": a.platform, "cases": results}
(work / "e2e-suite.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
for r in results:
    if r["status"] == "not_run":
        print(f"{r['case']}: not run ({r['reason']})")
sys.exit(1 if any(r["status"] == "fail" for r in results) else 0)
