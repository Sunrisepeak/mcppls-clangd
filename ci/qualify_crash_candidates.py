#!/usr/bin/env python3
"""Measure candidate regressions against a pinned historical engine on its OS."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('replay', ROOT / 'tests/crash/replay.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def qualify(engine, candidates, output):
    cases = sorted(candidates.glob('*.json'))
    if not cases:
        raise ValueError('candidate corpus is empty')
    results = [replay.replay(engine, case) for case in cases]
    required = [json.loads(case.read_text())['baseline'] for case in cases]
    # Timeout only qualifies a hang. A protocol/semantic error or successful
    # replay cannot stand in for the historical crash we're trying to reduce.
    if any(baseline not in ('crash', 'hang') for baseline in required):
        raise ValueError('candidate qualification requires a real crash or hang baseline')
    eligible = all(result['outcome'] == ('timeout' if baseline == 'hang' else baseline)
                   for result, baseline in zip(results, required))
    output.write_text(json.dumps({'platform': replay.platform_name(),
        'baseline_engine_sha256': hashlib.sha256(engine.read_bytes()).hexdigest(),
        'qualified': eligible, 'results': results}, indent=2) + '\n')
    return eligible


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path)
    parser.add_argument('--download-windows-baseline', type=Path)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.download_windows_baseline:
        if sys.platform != 'win32':
            parser.error('Windows baseline must execute on Windows')
        directory = args.download_windows_baseline
        directory.mkdir(parents=True, exist_ok=True)
        archive = directory / 'clangd-windows-23.1.0.zip'
        urllib.request.urlretrieve('https://github.com/clangd/clangd/releases/download/23.1.0/clangd-windows-23.1.0.zip', archive)
        # Same reviewed release archive as mcppls packaging/payload.lock.json.
        expected = '23412a240756a162e7b98a282f36aa2a23a88db5ce16a0cbc4fef7253768c810'
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            parser.error('historical baseline archive digest mismatch')
        with zipfile.ZipFile(archive) as files:
            files.extractall(directory)
        engines = list(directory.glob('*/bin/clangd.exe'))
        if len(engines) != 1:
            parser.error('baseline archive must contain one clangd executable')
        args.engine = engines[0]
    if args.engine is None:
        parser.error('an engine or pinned Windows download is required')
    return 0 if qualify(args.engine.resolve(), args.candidates, args.output) else 1


if __name__ == '__main__':
    sys.exit(main())
