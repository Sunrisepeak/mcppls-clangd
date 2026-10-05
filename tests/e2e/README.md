# e2e and acceptance

Two layers of product-level verification, both driven through the mcppls
entry point (plan doc §4.3, `e2e` job):

## lsp_driver.py — scenario checks

Drives a server (clangd directly, or mcppls with the fork swapped in via
`--clangd`) over a generated modules project:

```
python3 tests/e2e/lsp_driver.py \
  <payload>/bin/mcppls "--clangd=$FORK" \
  --project /tmp/bench_proj --scenarios completion,diagnostics,latency \
  --budget-ms 8000
```

Scenarios: `completion` (module-exported symbols are returned), `hover`
(resolves through Sema), `diagnostics` (publishDiagnostics arrives),
`latency` (warm p95 gate). Exit 0 = all green.

## accept.py — latency measurement on real projects

Injects a completion point under a project's `import` block (didOpen only;
no file is modified) and times one completion per round, alternating the
injected prefix. This is the mcppls-side acceptance probe:

```
python3 tests/e2e/accept.py \
  <payload>/bin/mcppls "--clangd=$FORK" -- \
  --project ~/test/mcpp/qt-demo --file src/main.cpp \
  --marker "import nlohmann.json;" --pa "nlohmann::" --pb "nlohmann::j" \
  --rounds 12 --out acc.json
```

### Recorded matrix (2026-10-06, linux-x64, mcppls 0.0.11 payload)

Latency per completion request through the product, milliseconds
(`cold` = first request incl. module preparation; `p50`/`p95` over the
following rounds; each round is a body-only edit + completion):

| project | clangd | cold | p50 | p95 |
|---|---|---|---|---|
| qt-demo (`import std` + `nlohmann.json`) | vanilla 23.1.0 | 82 | 987 | 1005 |
| qt-demo | fork 23.1.0-mcppls.0 | 86 | 925 | 1002 |
| mcpp (large modules project, `src/home.cppm`) | vanilla | 17 | 11 | 188 |
| mcpp | fork | 653 | 11 | 170 |
| mcppls self-host (`modules/pack/src/lock.cppm`) | vanilla | 5 | 5 | 133 |
| mcppls self-host | fork | 1004 | 5 | 994 |

Reading:

- The product's fast rounds (5–90 ms) are mcppls's own engine and answer
  cache; they are the same with either clangd.
- Rounds that clangd answers cost ≈ 950 ms with vanilla and ≈ 60–100 ms less
  with the fork (the validation memo; trace attribution in the fix-register
  document §2.5). The remaining cost is the per-parse BMI load and the Sema
  completion collector — a clang-core problem (S2, `draft`).
- Cold figures are one-time per workspace (module preparation + BMI builds).
