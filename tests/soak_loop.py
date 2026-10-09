#!/usr/bin/env python3
"""Bounded module kill/restart evidence, with semantic and clean-exit checks.

Each cycle starts an independent engine over the same project/cache. Every
third cycle kills it after sending completion, reaps the process unit, then
starts a recovery engine which must return the project's exported functions.
Intentional kills are recorded separately from semantic successes. This short
lifecycle smoke is not the two-hour RC soak or a real crash corpus.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time


def stop_unit(proc):
    if os.name == "nt":
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15, check=True)
    else:
        # The leader may already have crashed while children hold inherited
        # descriptors. Kill its group even after the leader has exited.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=15)


def run_engine(engine, project, timeout, kill_mid=False, flags=None):
    text = (project / "Use.cpp").read_text()
    expected = {"fn" + n for n in re.findall(r"^import m(\d+);", text, re.M)}
    if not expected:
        raise ValueError("project must import generated modules with fnN exports")
    line = next(i for i, value in enumerate(text.splitlines()) if value.strip() == "fn")
    uri = (project / "Use.cpp").as_uri()
    arguments = flags if flags is not None else [
        "--experimental-modules-support", f"--compile-commands-dir={project}",
        "--background-index=false", "--pretty=false", "-j=2"]
    started = time.monotonic()
    deadline = started + timeout
    proc = subprocess.Popen([str(engine), *arguments], cwd=project,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=os.name != "nt")
    replies = queue.Queue()
    stderr = bytearray()
    reader_threads = []

    def read_stderr():
        while chunk := proc.stderr.read1(4096):
            if len(stderr) < 1048576:
                stderr.extend(chunk[:1048576 - len(stderr)])

    def read_stdout():
        try:
            while True:
                headers = {}
                while True:
                    header = proc.stdout.readline(8192)
                    if not header:
                        raise EOFError("engine stdout closed")
                    if header in (b"\n", b"\r\n"):
                        break
                    key, value = header.decode().split(":", 1)
                    headers[key.lower()] = value.strip()
                length = int(headers["content-length"])
                if not 0 < length <= 16777216:
                    raise ValueError("invalid LSP frame length")
                data = bytearray()
                while len(data) < length:
                    chunk = proc.stdout.read(length - len(data))
                    if not chunk:
                        raise EOFError("truncated LSP frame")
                    data.extend(chunk)
                replies.put(json.loads(data))
        except Exception as exc:
            replies.put(exc)

    for reader in (read_stdout, read_stderr):
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        reader_threads.append(thread)

    rid = 0
    raw = []
    result = {"outcome": "error", "pid": proc.pid, "intentional_kill": kill_mid,
              "expected_symbols": sorted(expected), "raw_responses": raw}

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise queue.Empty
        return value

    def send(method, params=None, notify=False):
        nonlocal rid
        rid += 1
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            message["id"] = rid
        data = json.dumps(message).encode()
        proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        proc.stdin.flush()
        return rid

    def wait(request_id):
        while True:
            response = replies.get(timeout=remaining())
            if isinstance(response, Exception):
                raise response
            if response.get("id") != request_id:
                continue
            raw.append(response)
            if "error" in response or "result" not in response:
                raise ValueError(f"invalid response: {response}")
            return response["result"]

    try:
        initialized = wait(send("initialize", {"processId": os.getpid(),
                           "rootUri": project.as_uri(), "capabilities": {}}))
        if not isinstance(initialized, dict) or "capabilities" not in initialized:
            raise ValueError("initialize requires server capabilities")
        send("initialized", {}, notify=True)
        send("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "cpp", "version": 1, "text": text}}, notify=True)
        if not kill_mid:
            # Initial fallback completion can arrive before any AST exists.
            # Wait for the AST operation rather than adding a timing sleep.
            wait(send("textDocument/documentSymbol", {"textDocument": {"uri": uri}}))
        completion = send("textDocument/completion", {
            "textDocument": {"uri": uri}, "position": {"line": line, "character": 6}})
        if kill_mid:
            time.sleep(min(0.05, remaining()))
            if proc.poll() is not None:
                raise ValueError("engine exited before the intentional kill")
            stop_unit(proc)
            result["outcome"] = "killed"
        else:
            items = wait(completion)
            if isinstance(items, dict):
                items = items.get("items", [])
            names = {re.split(r"[(<]", item.get("filterText", item.get("label", "")))[0].strip()
                     for item in (items or [])}
            callable_names = {re.split(r"[(<]", item.get("filterText", item.get("label", "")))[0].strip()
                              for item in (items or []) if item.get("kind") == 3}
            result["observed_symbols"] = sorted(names)
            missing = expected - callable_names
            if missing:
                raise ValueError(f"completion missing semantic function exports: {sorted(missing)}")
            send("textDocument/didClose", {"textDocument": {"uri": uri}}, notify=True)
            if wait(send("shutdown")) is not None:
                raise ValueError("shutdown must return null")
            send("exit", notify=True)
            proc.stdin.close()
            proc.wait(timeout=remaining())
            if proc.returncode != 0:
                raise ValueError(f"engine exited with {proc.returncode}")
            result["outcome"] = "pass"
    except (queue.Empty, subprocess.TimeoutExpired):
        result.update(outcome="timeout", detail="cycle deadline exceeded")
    except Exception as exc:
        result.update(outcome="error", detail=str(exc))
    finally:
        stop_unit(proc)
        for thread in reader_threads:
            thread.join(timeout=2)
        result["readers_stopped"] = all(not thread.is_alive() for thread in reader_threads)
        if not result["readers_stopped"]:
            result.update(outcome="error", detail="inherited output descriptors remain open")
        proc.stdin.close()
        if result["readers_stopped"]:
            # Closing a buffered stream held by a blocked reader can itself
            # block. A surviving pipe holder fails the gate above instead.
            proc.stdout.close()
            proc.stderr.close()
        result.update(exit_code=proc.returncode, stderr=stderr.decode(errors="replace"),
                      elapsed_ms=round((time.monotonic() - started) * 1000, 1))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", type=Path)
    parser.add_argument("project", type=Path)
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.cycles < 3 or not 0 < args.timeout_seconds <= 600:
        parser.error("need at least three cycles and a deadline in (0, 600]")
    engine, project = args.engine.resolve(), args.project.resolve()
    report = {"engine_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
              "cycles": [], "semantic_passes": 0, "intentional_kills": 0}
    for cycle in range(args.cycles):
        kill = cycle % 3 == 2
        outcome = run_engine(engine, project, args.timeout_seconds, kill)
        recovery = run_engine(engine, project, args.timeout_seconds) if outcome["outcome"] == "killed" else None
        ok = outcome["outcome"] == "pass" or (outcome["outcome"] == "killed" and recovery["outcome"] == "pass")
        report["cycles"].append({"cycle": cycle + 1, "engine": outcome, "recovery": recovery, "passed": ok})
        report["semantic_passes"] += int(outcome["outcome"] == "pass") + int(recovery is not None and recovery["outcome"] == "pass")
        report["intentional_kills"] += int(outcome["outcome"] == "killed")
        print(f"soak_loop: cycle {cycle+1}/{args.cycles}: {outcome['outcome']}"
              + (f", recovery {recovery['outcome']}" if recovery else ""), flush=True)
        if not ok:
            break
    report["passed"] = len(report["cycles"]) == args.cycles and all(c["passed"] for c in report["cycles"])
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"soak_loop: {report['semantic_passes']} semantic passes, {report['intentional_kills']} intentional kills")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
