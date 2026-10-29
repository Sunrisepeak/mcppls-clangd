# PROBE: clangd as an ok image (temporary, not to be merged)

Can this clangd be built once per architecture as an ok image (`<arch>-openkal`) that every
system's okrun starts, and what does that cost against the native clangd of the same source?

| File | Does |
|---|---|
| `hello/` | a plain unit mcpp compiles for `<arch>-openkal`: openkal's compile conventions are read from its compile command |
| `gen_toolchain.py` | that compile command → a CMake toolchain file (compile only; nothing is linked by CMake) |
| `configure-openkal.sh` | the cross configure of llvm-project with that file and the host's tablegen |
| `openkal-llvm.patch` | what llvm-project needs to compile and find itself as an ok image |
| `make_link_project.py` | clangd's link line → an mcpp project that links clangd's main over the static libraries and seals the image |
| `build-image.sh` | all of the above for one architecture |
| `run_check.py` | one clangd (native, or the image under okrun) through the cases; JSON out |

Workflow: `.github/workflows/probe-openkal.yml`. Results: the pull request.
