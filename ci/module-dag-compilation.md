# Bounded prerequisite module compilation

Patch `0023-UP-03-bounded-module-dag-compilation.patch` replaces the serial
prerequisite loop with a single forest plan and a builder-owned worker pool.
It builds on the cycle, cancellation, generation and read-lease changes already
carried in the series. The patch is confined to ModulesBuilder.cpp and a focused
clangd lit test; the larger raw replay lives in tests/e2e/module_dag.py.

## Evidence and selected root cause

On the local Linux build, four independent module units, each with vector, map,
string and algorithm headers in its global module fragment, originally took
about 0.76 s for prerequisite construction. Their completion log showed four
successive BMI builds, taking roughly 154/218/171/173 ms. The importer initially
waited about 814 ms; its subsequent semantic completion took about 22 ms.
The cold cost is predominantly serial compiler work. This is a separate cost
from warm Sema completion and provider/dependency scanning.

The same cold semantic fixture after the change produced:

| mode | initial documentSymbol | maximum active module jobs |
| --- | ---: | ---: |
| preserved pre-change engine | 831.32 ms | serial baseline |
| candidate, one worker | 767.16 ms | 1 |
| candidate, two workers (default) | 485.37 ms | 2 |
| candidate, four workers | 381.10 ms | 4 |

These are single exploratory cold runs, not the joint release performance gate.
Every run required the four imported functions to appear in real completion.
The report stores raw timing samples, logs and both engine SHA-256 identities.
Local binaries were incrementally compiled and linked against existing libraries;
they are focused development evidence, not final packaged artifact identities.
The before binary was preserved before ModulesBuilder's object/archive changed.

## Scheduling and lifetime contract

The planner resolves all buildable direct roots on the calling document thread.
It traverses dependencies once, rejects active-stack cycles before dispatch and
records each node's dependency depth. ProjectModules scanning and provider state
are not shared with worker threads. Validated prebuilt modules are ready leaves:
a prebuilt dependency may legitimately have no provider source or CDB command.
Direct imports without a buildable provider retain the existing textual-import
behavior. A root depending on an unavailable toolchain module is also kept
textual without discarding a different resolvable root; concrete compilation,
cycle and cancellation failures still fail the prerequisite build.

A single pool belongs to ModulesBuilderImpl and is shared by its document
requests. `--modules-builder-workers` defaults to 2, clamps requests to 1–4 and
limits the result to available physical cores. Each request dispatches ready
nodes in batches no larger than that pool capacity. This bounds queueing per
request/wave; simultaneous scheduler requests can each enqueue a batch. The
pool still bounds active node jobs (compilation or cache validation) across those
requests. Initial prebuilt-BMI validation happens on the planning request thread.
Normal AST and background-index work are separate.

Each batch holds one immutable prerequisite snapshot. A worker performs exactly
one module task and takes only that source's existing publish lock. It never
submits a child job or waits for a dependency or sibling. The caller waits for
all dispatched jobs, collects every error, and only then merges successful BMIs
and advances to dependent nodes. A failing sibling prevents parent dispatch;
already running siblings drain before request state or read leases are released.
Cancellation and tracing Context travel to the pool workers. Live source-lock
waits are cancellable; an already executing Clang compilation remains
non-preemptible, as before this change. The pool is the
last Impl member, so its draining destructor runs before counters and caches die.

LLVM ThreadPool returns deferred shared futures. Waiting directly on such a
future can execute the job on the calling document thread and bypass the pool
limit under concurrent requests. This implementation instead waits on independent
promise futures, which are signalled only by the worker; callers cannot execute
those deferred jobs. A no-threads LLVM configuration explicitly drains its
SingleThreadExecutor before waiting on promise futures. Begin/end and active-job
counts use verbose logging.

## Verification and remaining work

The in-patch modules-bounded-dag.test proves a shared dependency is built once,
parents run after siblings finish, and all four imported functions survive. Its
shell/URI setup follows the existing module lit tests and is unsupported on
Windows; the Python raw replay uses native paths and URIs.

```sh
python3 tests/e2e/module_dag.py \
  --engine build-linux-x64/bin/clangd \
  --clang build-linux-x64/bin/clang++ \
  --baseline-engine /tmp/mcppls-dag-engine-before \
  --workdir /tmp/mcppls-module-dag
```

Use a fresh workdir, because cold cache is an assertion. The replay checks wide
DAGs with 1/2/4 workers, a nested diamond with 1/4 workers, failed siblings with
1/4 workers followed by a healthy edit, a prebuilt B whose provider is absent
from the CDB, and two simultaneously opened importers sharing the worker pool.
An additional A→unprovided-toolchain-module plus C case keeps A textual while
C remains semantically available. It asserts all task completions, dependency ordering, actual independent overlap,
worker bounds and clean shutdown. Cycle rejection, live-lock document close and
third-party textual-import regressions were also rerun successfully on Linux.
Linux CPU affinity probes restricted execution to one and four distinct physical
cores: the observed pool limits were 1 and 4 respectively. Four logical CPUs
representing two physical cores also correctly capped the pool at 2.

The change does not establish a hard RSS byte ceiling. Worker count bounds the
number of simultaneous prerequisite compiler instances, but their memory depends
on input complexity. Memory admission and high-water measurements remain open.
It does not add provider tables by CDB generation or dependency scan-result reuse;
those W2 tasks remain open too. No claim is made that warm latency or the complete
0.0.12 release performance/soak requirements have been satisfied.

For upstream submission, retain the scheduler refactor and its in-patch lit test
as one reviewable change; port the raw failure/concurrent-document fixtures to
upstream test infrastructure as needed. Drop this patch only when upstream has
bounded ready-node scheduling with equivalent dependency, failure and lifetime
semantics, rather than merely spawning one pool for every document.
