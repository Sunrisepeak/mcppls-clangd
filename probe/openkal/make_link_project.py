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

MAIN = r"""// clangd's own main (ClangdToolMain.cpp), as an ok image.
#include <pthread.h>
#include <stdlib.h>

namespace clang::clangd { int clangdMain(int argc, char* argv[]); }
int main(int argc, char* argv[]) { return clang::clangd::clangdMain(argc, argv); }

// PROBE WORKAROUND. openkal-llvm-runtime 0.16.6 exports __cxa_thread_atexit (a thread_local
// with a destructor) on __linux__, __Fuchsia__, OPENKAL_TARGET_WINDOWS and __APPLE__, and an ok
// image is none of them (libcxxabi/src/cxa_thread_atexit.cpp); okld check then refuses the import.
// The same per-thread list libc++abi keeps, here; the main thread's list is not run at exit.
namespace {
struct Dtor { void (*fn)(void*); void* obj; Dtor* next; };
pthread_key_t key;
pthread_once_t once = PTHREAD_ONCE_INIT;
void run(void* p) {
  for (auto* d = static_cast<Dtor*>(p); d;) { auto* n = d->next; d->fn(d->obj); free(d); d = n; }
}
void make() { pthread_key_create(&key, run); }
}
extern "C" int __cxa_thread_atexit(void (*fn)(void*), void* obj, void*) {
  pthread_once(&once, make);
  auto* d = static_cast<Dtor*>(malloc(sizeof(Dtor)));
  if (!d) return -1;
  *d = Dtor{fn, obj, static_cast<Dtor*>(pthread_getspecific(key))};
  return pthread_setspecific(key, d);
}
"""

os.makedirs(os.path.join(out, "src"), exist_ok=True)
with open(os.path.join(out, "src", "main.cpp"), "w") as f:
    f.write(MAIN)
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
