#!/usr/bin/env python3
"""Replay nonempty, platform-specific crash corpora; forced termination fails.

Each JSON contains id, platform, project (relative to the manifest), baseline
(crash/hang/pass), timeout_seconds, and sequence. Each sequence step contains
method and params; requests additionally contain expect, a nonempty mapping
of JSON pointers to exact response values. Notifications set notify=true.
URI placeholders ${PROJECT_URI} are expanded recursively. A successful replay
requires initialize, at least one semantic assertion and a clean shutdown.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import platform
import re
import signal
import subprocess
import sys
import threading
import time


def executable(path):
    path = path.resolve()
    if not path.is_file() and path.with_suffix(".exe").is_file():
        path = path.with_suffix(".exe")
    if not path.is_file():
        raise ValueError(f"missing executable: {path}")
    return path


def platform_name():
    return {"win32": "win32-x64", "linux": "linux-x64", "darwin":
            "darwin-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "darwin-x64"}[sys.platform]


def pointer(value, path):
    if not path.startswith("/"):
        raise ValueError("assertions require JSON pointers")
    for key in path[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def replay(engine, manifest):
    case = json.loads(manifest.read_text())
    if case.get("platform") != platform_name():
        raise ValueError(f"{manifest}: wrong platform")
    if case.get("baseline") not in ("crash", "hang", "pass"):
        raise ValueError("missing baseline outcome")
    sequence = case["sequence"]
    if not sequence or sequence[0].get("method") != "initialize":
        raise ValueError("sequence must start with initialize")
    if not any((s.get("expect") or s.get("expected_symbols") or s.get("forbidden_symbols")) and s.get("method", "").startswith("textDocument/") for s in sequence):
        raise ValueError("sequence requires a semantic response assertion")
    project = (manifest.parent / case["project"]).resolve()
    if not project.is_dir():
        raise ValueError("missing project inputs")
    timeout = float(case["timeout_seconds"])
    if not 0 < timeout <= 600:
        raise ValueError("deadline must be in (0, 600]")
    # New process unit: POSIX group / Windows process tree, including helpers.
    proc = subprocess.Popen([str(engine), *case.get("flags", [])], cwd=project,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=os.name != "nt")
    messages = queue.Queue()
    log = bytearray()

    def stderr():
        while chunk := proc.stderr.read1(4096):
            if len(log) < 1048576:
                log.extend(chunk[:1048576-len(log)])

    def reader():
        try:
            while True:
                headers = {}
                while True:
                    line = proc.stdout.readline(8192)
                    if not line:
                        raise EOFError("server stdout closed")
                    if line in (b"\n", b"\r\n"):
                        break
                    key, value = line.decode().split(":", 1)
                    headers[key.lower()] = value.strip()
                length = int(headers["content-length"])
                if not 0 < length <= 16777216:
                    raise ValueError("invalid frame length")
                messages.put(json.loads(proc.stdout.read(length)))
        except Exception as exc:
            messages.put(exc)

    readers = [threading.Thread(target=reader, daemon=True),
               threading.Thread(target=stderr, daemon=True)]
    for thread in readers:
        thread.start()
    deadline = time.monotonic() + timeout
    rid = 0
    result = {"id": case["id"], "outcome": "error", "responses": [], "raw_responses": []}

    pending = {}
    aliases = {}

    def wait_reply(request_id, allow_error=False):
        while True:
            if request_id in pending:
                reply = pending.pop(request_id)
            else:
                if time.monotonic() >= deadline:
                    raise queue.Empty
                reply = messages.get(timeout=max(0.001, deadline-time.monotonic()))
                if isinstance(reply, Exception):
                    raise reply
                if "id" not in reply or not ("result" in reply or "error" in reply):
                    continue
                if reply["id"] != request_id:
                    pending[reply["id"]] = reply
                    continue
            if "error" in reply:
                if not allow_error or reply["error"].get("code") not in (-32800, -32801):
                    raise ValueError(f"request failed: {reply['error']}")
            return reply

    def send(method, params=None, notify=False, defer=False, allow_error=False):
        nonlocal rid
        rid += 1
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            msg["id"] = rid
        data = json.dumps(msg).encode()
        proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
        proc.stdin.flush()
        if notify:
            return None
        return rid if defer else wait_reply(rid, allow_error)

    def expand(value):
        if isinstance(value, str):
            if value.startswith("${REQUEST:") and value.endswith("}"):
                return aliases[value[10:-1]][0]
            if value.startswith("${FILE_TEXT:") and value.endswith("}"):
                source = (project / value[12:-1]).resolve()
                if not source.is_relative_to(project):
                    raise ValueError("fixture text escapes project")
                return source.read_text(encoding="utf-8-sig")
            return value.replace("${PROJECT_URI}", project.as_uri()).replace("${PROJECT_PATH}", project.as_posix())
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, dict):
            return {expand(k): expand(v) for k, v in value.items()}
        return value

    originals = {}
    try:
        for step in sequence:
            if step.get("action") == "sleep":
                slept_until = time.monotonic() + float(step["seconds"])
                while time.monotonic() < slept_until:
                    if time.monotonic() >= deadline:
                        raise queue.Empty
                    if proc.poll() is not None:
                        raise ValueError("engine exited during the requested sleep")
                    time.sleep(0.05)
                continue
            if step.get("action") == "await-log":
                expected = step["contains"].encode()
                while expected not in log:
                    if time.monotonic() >= deadline:
                        raise queue.Empty
                    if proc.poll() is not None:
                        raise ValueError("engine exited before the required log event")
                    time.sleep(0.01)
                continue
            if step.get("action") == "await":
                request_id, method, started = aliases.pop(step["request"])
                response = wait_reply(request_id, step.get("allow_error", False))
                result["raw_responses"].append({"method": method, "reply": response,
                                                "elapsed_ms": (time.monotonic()-started)*1000})
                for path, expected in step.get("expect", {}).items():
                    if pointer(response, path) != expand(expected):
                        raise ValueError(f"deferred response failed assertion {path}")
                continue
            if step.get("action") == "write-file":
                path = (project / step["file"]).resolve()
                if not path.is_relative_to(project):
                    raise ValueError("fixture edit escapes project")
                if path.exists():
                    stat = path.stat()
                    originals.setdefault(path, (path.read_bytes(), stat.st_atime_ns, stat.st_mtime_ns))
                else:
                    originals.setdefault(path, (None, None, None))
                path.write_text(expand(step["contents"]), encoding="utf-8")
                continue
            if step.get("action") == "replace-file":
                path = (project / step["file"]).resolve()
                if not path.is_relative_to(project):
                    raise ValueError("fixture edit escapes project")
                original = path.read_bytes()
                stat = path.stat()
                originals.setdefault(path, (original, stat.st_atime_ns, stat.st_mtime_ns))
                old, new = step["from"].encode(), step["with"].encode()
                if original.count(old) != 1:
                    raise ValueError("fixture replacement must match exactly once")
                updated = original.replace(old, new, 1)
                path.write_bytes(updated)
                if step.get("same-second"):
                    if len(updated) != len(original):
                        raise ValueError("same-second regression requires same size")
                    # A real change within the same second, with a different
                    # subsecond timestamp, rather than a preserved timestamp.
                    # NTFS represents timestamps in 100 ns ticks. A +1 ns
                    # request rounds back to the original stamp on Windows,
                    # accidentally testing a preserved-mtime edit instead.
                    delta = 1000000  # 1 ms, still within the same second
                    stamp = stat.st_mtime_ns + delta if stat.st_mtime_ns % 1000000000 < 1000000000 - delta else stat.st_mtime_ns - delta
                    os.utime(path, ns=(stat.st_atime_ns, stamp))
                    observed = path.stat().st_mtime_ns
                    if observed == stat.st_mtime_ns or observed // 1000000000 != stat.st_mtime_ns // 1000000000:
                        raise ValueError("filesystem cannot represent a changed timestamp within the same second")
                continue
            if step["method"] in ("shutdown", "exit"):
                raise ValueError("shutdown is managed by the replay harness")
            started = time.monotonic()
            response = send(step["method"], expand(step.get("params")), step.get("notify", False),
                            bool(step.get("defer")), step.get("allow_error", False))
            if step.get("defer"):
                if step.get("notify") or step["defer"] in aliases:
                    raise ValueError("deferred request requires a unique name")
                aliases[step["defer"]] = (response, step["method"], started)
                continue
            if response is not None:
                result["raw_responses"].append({"method": step["method"], "reply": response,
                                                "elapsed_ms": (time.monotonic()-started)*1000})
            if step.get("expected_symbols") or step.get("forbidden_symbols"):
                items = response.get("result") or []
                if isinstance(items, dict):
                    items = items.get("items", [])
                names = {re.split(r"[(<]", i.get("filterText", i.get("label", "")))[0].strip() for i in items}
                result["responses"].append({"method": step["method"], "symbols": sorted(names),
                                            "elapsed_ms": (time.monotonic()-started)*1000})
                missing = set(step.get("expected_symbols", [])) - names
                polluted = set(step.get("forbidden_symbols", [])) & names
                if missing or polluted:
                    raise ValueError(f"missing symbols {sorted(missing)}; forbidden symbols {sorted(polluted)}")
                selected = {}
                for item in items:
                    name = re.split(r"[(<]", item.get("filterText", item.get("label", "")))[0].strip()
                    if name in step.get("expected_symbols", []):
                        selected.setdefault(name, []).append(item)
                result["responses"][-1]["completion_items"] = selected
                for name, fragments in step.get("expected_snippet_fragments", {}).items():
                    candidates = selected.get(name, [])
                    texts = [i.get("textEdit", {}).get("newText", i.get("insertText", "")) for i in candidates]
                    if not any(all(fragment in text for fragment in fragments) for text in texts):
                        raise ValueError(f"{name}: missing snippet fragments {fragments!r}, observed {texts!r}")
            for path, expected in step.get("expect", {}).items():
                actual = pointer(response, path)
                if actual != expand(expected):
                    raise ValueError(f"{path}: expected {expected!r}, observed {actual!r}")
        if aliases:
            raise ValueError("deferred requests must be awaited before shutdown")
        send("shutdown")
        send("exit", notify=True)
        proc.stdin.close()
        proc.wait(timeout=max(0.001, deadline-time.monotonic()))
        result["outcome"] = "pass" if proc.returncode == 0 else "crash"
    except (queue.Empty, subprocess.TimeoutExpired):
        result["outcome"] = "timeout"
    except Exception as exc:
        result.update(outcome="crash" if proc.poll() not in (None, 0) else "error", detail=str(exc))
    finally:
        if os.name == "nt":
            if proc.poll() is None:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            # A crashed leader can leave live helpers holding its output pipes.
            # The owned group still exists, so clean it even after leader exit.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=15)
        for thread in readers:
            thread.join(timeout=2)
        result["readers_stopped"] = all(not thread.is_alive() for thread in readers)
        if not result["readers_stopped"]:
            result.update(outcome="error", detail="inherited output descriptors remain open")
        proc.stdin.close()
        if result["readers_stopped"]:
            # Closing a buffered stream held by a blocked reader can itself
            # block. A surviving pipe holder fails the gate above instead.
            proc.stdout.close()
            proc.stderr.close()
        for path, (content, atime, mtime) in originals.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
                os.utime(path, ns=(atime, mtime))
        result["exit_code"] = proc.returncode
        result["stderr"] = log.decode(errors="replace")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifests = sorted(args.corpus.glob("*.json"))
    if not manifests:
        parser.error("empty corpus cannot provide crash evidence")
    engine = executable(args.engine)
    results = []
    for manifest in manifests:
        try:
            results.append(replay(engine, manifest))
        except Exception as exc:
            results.append({"manifest": str(manifest), "outcome": "invalid", "detail": str(exc)})
    args.output.write_text(json.dumps({"engine_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
                                      "platform": platform_name(), "results": results}, indent=2))
    return int(any(r["outcome"] != "pass" for r in results))


if __name__ == "__main__":
    sys.exit(main())
