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
