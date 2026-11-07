#!/usr/bin/env python3
"""shard-exchange: the index shards one engine writes, the other reads (mcpp design 2026-11-07, §4.5 item 4).

usage: shard_exchange.py --workdir D [--std-args "..."] --native <clangd argv prefix> --image <clangd argv prefix>

Each direction is one project and two sessions with the background index on. The WRITER indexes every unit of
the project and leaves its shards in the project's own store (`.cache/clangd/index`); the READER then starts over
the same project and loads them. An engine without zlib cannot read a shard whose string table an engine with zlib
compressed ("Compressed string table, but zlib is unavailable"): it logs "Error while reading shard" and indexes
the unit again. The exchange holds when, in both directions, the reader logs no shard error and indexes no unit:
every unit is served by the writer's shard. The project's units do not change between the sessions, so a shard is
never stale.
"""
import argparse, json, os, re, shlex, shutil, subprocess, sys, threading, time

ap = argparse.ArgumentParser()
ap.add_argument("--workdir", required=True)
ap.add_argument("--std-args", default="")
ap.add_argument("--native", nargs="+", required=True)
ap.add_argument("--image", nargs="+", required=True)
ap.add_argument("--units", type=int, default=12)
ap.add_argument("--timeout", type=int, default=600)
a = ap.parse_args()


def project(at):
    shutil.rmtree(at, ignore_errors=True)
    os.makedirs(os.path.join(at, "src"))
    files = []
    for k in range(a.units):
        name = os.path.join(at, "src", f"unit{k}.cpp")
        with open(name, "w") as f:
            f.write("#include <string>\n#include <vector>\n"
                    f"namespace shard{k} {{\nstruct Record{k} {{ std::string name; std::vector<int> values; }};\n"
                    f"int sum{k}(const Record{k}& r) {{ int s = 0; for (int v : r.values) s += v; return s; }}\n}}\n")
        files.append(name)
    commands = [{"directory": at, "file": f,
                 "arguments": ["clang++", "-std=c++20", *shlex.split(a.std_args), "-c", f]} for f in files]
    with open(os.path.join(at, "compile_commands.json"), "w") as f:
        json.dump(commands, f, indent=1)
    return files


def uri(path):
    path = os.path.abspath(path).replace("\\", "/")
    return "file://" + ("/" + path if not path.startswith("/") else path)


class Engine:
    def __init__(self, argv, at):
        self.log = bytearray()
        self.p = subprocess.Popen([*argv, "--background-index=true", "--log=info", f"--compile-commands-dir={at}"],
                                  cwd=at, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.replies, self.cv, self.id = {}, threading.Condition(), 0
        for target in (self.read, self.err):
            threading.Thread(target=target, daemon=True).start()

    def err(self):
        while chunk := self.p.stderr.read1(65536):
            with self.cv:
                self.log.extend(chunk)
                self.cv.notify_all()

    def read(self):
        while True:
            n = 0
            while True:
                line = self.p.stdout.readline()
                if not line:
                    return
                if line in (b"\r\n", b"\n"):
                    break
                if line.lower().startswith(b"content-length:"):
                    n = int(line.split(b":")[1])
            m = json.loads(self.p.stdout.read(n))
            if "id" in m and "method" in m:
                self.send({"jsonrpc": "2.0", "id": m["id"], "result": None})
            elif "id" in m:
                with self.cv:
                    self.replies[m["id"]] = m
                    self.cv.notify_all()

    def send(self, m):
        body = json.dumps(m).encode()
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        self.p.stdin.flush()

    def request(self, method, params):
        self.id += 1
        self.send({"jsonrpc": "2.0", "id": self.id, "method": method, "params": params})
        with self.cv:
            self.cv.wait_for(lambda: self.id in self.replies, timeout=a.timeout)
        return self.replies.get(self.id)

    def text(self):
        with self.cv:
            return self.log.decode("utf-8", "replace")

    def wait_log(self, ready, timeout):
        end = time.monotonic() + timeout
        with self.cv:
            while not ready(self.log.decode("utf-8", "replace")):
                if not self.cv.wait(timeout=max(0.0, end - time.monotonic())):
                    return False
        return True

    def stop(self):
        try:
            self.request("shutdown", None)
            self.send({"jsonrpc": "2.0", "method": "exit"})
            self.p.wait(timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            self.p.kill()


def session(argv, at, files, until, settle):
    e = Engine(argv, at)
    e.request("initialize", {"processId": os.getpid(), "rootUri": uri(at), "capabilities": {}})
    e.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    with open(files[0]) as f:
        e.send({"jsonrpc": "2.0", "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri(files[0]), "languageId": "cpp", "version": 1, "text": f.read()}}})
    reached = e.wait_log(until, a.timeout)
    time.sleep(settle)
    e.stop()
    return reached, e.text()


def exchange(writer, reader, label):
    at = os.path.abspath(os.path.join(a.workdir, label))
    files = project(at)
    indexed = lambda log: len(set(re.findall(r"Indexed (\S+unit\d+\.cpp)", log))) >= len(files)
    ok, wlog = session(writer, at, files, indexed, 1)
    shards = [n for _, _, ns in os.walk(os.path.join(at, ".cache", "clangd", "index")) for n in ns if n.endswith(".idx")]
    enqueued = lambda log: "Enqueueing" in log
    seen, rlog = session(reader, at, files, enqueued, 15)
    for name, log in (("writer", wlog), ("reader", rlog)):
        with open(os.path.join(a.workdir, f"{label}-{name}.log"), "w", encoding="utf-8") as f:
            f.write(log)
    errors = re.findall(r"Error while reading shard[^\n]*", rlog)
    again = sorted(set(re.findall(r"Indexed (\S+unit\d+\.cpp)", rlog)))
    result = {"direction": label, "writer_indexed_all": ok, "shards": len(shards), "reader_started": seen,
              "reader_shard_errors": errors[:5], "reader_indexed_again": again}
    result["ok"] = ok and seen and len(shards) >= len(files) and not errors and not again
    return result


os.makedirs(a.workdir, exist_ok=True)
results = [exchange(a.native, a.image, "native-to-image"), exchange(a.image, a.native, "image-to-native")]
with open(os.path.join(a.workdir, "shard-exchange.json"), "w") as f:
    json.dump(results, f, indent=1)
print(json.dumps(results, indent=1))
sys.exit(0 if all(r["ok"] for r in results) else 1)
