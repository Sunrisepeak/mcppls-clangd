#!/usr/bin/env python3
"""Write the mcpp project that links clangd as an ok image from the static
libraries CMake built: clangd's own link line (ninja -t commands) names them.

usage: make_link_project.py <cmake-build-dir> <out-dir>
Prints the libraries, one per line, to stdout as well (the build's targets).
"""
import os, shlex, subprocess, sys

build, out = sys.argv[1:3]
cmds = subprocess.run(["ninja", "-C", build, "-t", "commands", "bin/clangd"],
                      check=True, capture_output=True, text=True).stdout.strip().splitlines()
link = shlex.split(cmds[-1])
libs = []
for w in link:
    if w.endswith(".a"):
        p = os.path.abspath(os.path.join(build, w))
        if p not in libs:
            libs.append(p)
if not libs:
    sys.exit("no static library in clangd's link line")

os.makedirs(os.path.join(out, "src"), exist_ok=True)
with open(os.path.join(out, "src", "main.cpp"), "w") as f:
    f.write("// clangd's own main (ClangdToolMain.cpp), as an ok image.\n"
            "namespace clang::clangd { int clangdMain(int argc, char* argv[]); }\n"
            "int main(int argc, char* argv[]) { return clang::clangd::clangdMain(argc, argv); }\n")
words = ", ".join(f'"{l}"' for l in libs)
with open(os.path.join(out, "mcpp.toml"), "w") as f:
    f.write(f"""# clangd as an ok image: mcpp links its main over the static libraries CMake
# built with openkal's compile conventions, and seals the image.
[package]
name    = "clangd"
version = "23.1.0"

[build]
sources = ["src/*.cpp"]
cxxflags = ["-fno-rtti", "-fno-exceptions"]
ldflags  = ["--start-group", {words}, "--end-group"]
""")
for l in libs:
    print(os.path.relpath(l, build))
