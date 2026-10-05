#!/usr/bin/env python3
"""Generates a synthetic C++20 modules project for completion benches.

Run: %python gen_bench_project.py <dir> <num-modules>

Creates `m1.cppm .. mN.cppm` (module m_i exports one function and imports
m_{i-1}), a `Use.cpp` importing all of them with a completion point, and a
`compile_commands.json` wired to the clang binary given via $BENCH_CLANG
(default `clang`). The chain keeps every module in the prerequisite set of
Use.cpp, so the completion path exercises the whole BMI pipeline.
"""
import json
import os
import sys

out = os.path.abspath(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
clang = os.environ.get("BENCH_CLANG", "clang")

os.makedirs(out, exist_ok=True)
for i in range(1, n + 1):
    body = f"export module m{i};\n"
    if i > 1:
        body += f"import m{i-1};\n"
    body += f"export int fn{i}() {{ return {i}; }}\n"
    with open(os.path.join(out, f"m{i}.cppm"), "w") as F:
        F.write(body)

imports = "\n".join(f"import m{i};" for i in range(1, n + 1))
# The standalone `fn` token is the completion point: the module units export
# fn1..fnN, so a completion after `fn` must return module-exported symbols.
use = imports + "\nint main() {\n    fn\n    return fn1();\n}\n"
with open(os.path.join(out, "Use.cpp"), "w") as F:
    F.write(use)

cdb = [
    {"directory": out,
     "command": f"{clang} -std=c++20 -o {out}/Use.cpp.o -c {out}/Use.cpp",
     "file": f"{out}/Use.cpp"},
]
for i in range(1, n + 1):
    cdb.append({"directory": out,
                "command": f"{clang} -std=c++20 {out}/m{i}.cppm --precompile -o {out}/m{i}.pcm",
                "file": f"{out}/m{i}.cppm"})
with open(os.path.join(out, "compile_commands.json"), "w") as F:
    F.write(json.dumps(cdb, indent=2))
print(f"gen_bench_project: {out} with {n} modules")
