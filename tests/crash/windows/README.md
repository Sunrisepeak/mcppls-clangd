# Windows crash corpus

Inputs that crashed the bundled clangd on Windows, with their compile
commands and the mcppls scenario that triggered them. Sources: the crash
files set aside in mcppls 0.0.5 (UP-12), the crash records with SHA-256s
from 0.0.8 (UP-13, UP-20), and any new reports.

Manifest entry (one JSON per case): input files, compile command, clangd
flags, the scenario to replay (see tests/e2e/lsp_driver.py), expected
behavior on clangd 23.1.0 (crash/hang/pass), register row.

The `win-crash-corpus` workflow replays every entry against the PDB
build under cdb with WER LocalDumps enabled; the run fails while any
entry still crashes, which IS that row's status. Currently empty - the
corpus files are collected from mcpp-language-server's crash records as
the first action of the C0 phase (windows-crash-plan document).

## Executable replay contract

`python3 tests/crash/replay.py --engine <clangd> --corpus tests/crash/windows
--output crash-outcomes.json` executes every JSON entry. Empty corpora fail.
Each entry supplies `id`, `platform`, `project` relative to the manifest,
`baseline` (`crash`, `hang`, or `pass`), `timeout_seconds` (at most 600), optional
`flags`, and `sequence`. Each step has `method` and `params`; notifications set
`notify: true`. Start with initialize and include a textDocument request with
`expect`, a mapping of JSON pointers in the response to exact expected values.
`${PROJECT_URI}` expands to the input directory URI. Shutdown is managed by
the harness. A clean exit and every assertion are required; timeout, forced
termination, protocol errors, and crashes all fail. The output records the
engine SHA and each observed outcome. This replay does not itself certify PDB
identity or symbolized stacks; those remain separate release requirements.
