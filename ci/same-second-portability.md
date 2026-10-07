# Same-second edits must change a representable timestamp

Windows run 37654044049 linked and passed the carried lit subset, then failed
the asynchronous member test because `freshItem` did not appear after the disk
edit. The replay harness had requested an mtime increment of **one nanosecond**.
Windows FILETIME uses 100-nanosecond intervals ([Microsoft FILETIME reference](https://learn.microsoft.com/windows/win32/api/minwinbase/ns-minwinbase-filetime));
that request can round back to the original timestamp, changing the intended
same-second/different-subsecond scenario into same-size/preserved-timestamp.
The precise-stat cache does not claim content-hash invalidation for that case.

Replay now requests a one-millisecond change within the original second, then
reads stat back and requires both a changed timestamp and the unchanged whole
second. A filesystem that cannot represent this scenario fails explicitly.
The controlled NTFS-precision test rounds utime arguments to 100 ns, verifies
the timestamp really changes inside the same second and the input is restored.

The controlled regression passes on Linux; native Windows acceptance of the
new replay is still pending. This changes the scenario to its documented
premise without adding sleeps, retries or weakening symbol assertions. It
is not an engine fix or proof of arbitrary preserved-mtime edits.

## Native iteration cost

The failed Windows job spent about two hours building before the semantic test.
Its only installed build tool was Ninja; the restored `.ccache` directory had
no compiler cache executable behind it. PR Windows builds now install the
immutable `sccache-action` v0.0.11 commit and pin sccache v0.18.0, enabling its
GitHub Actions backend through the documented CMake C/C++ launcher options.
See [the official action instructions](https://github.com/mozilla-actions/sccache-action)
and [sccache's CMake/MSVC guidance](https://github.com/mozilla/sccache/blob/main/README.md).

The Release recipe and compiler remain the same. The action reports cache
statistics; actual native cache hits and iteration time require the next
Windows runs. This is not a measured speedup claim. Dedicated PDB workflows
have not been converted because their debug-info layout requires independent
cache/symbol validation.
