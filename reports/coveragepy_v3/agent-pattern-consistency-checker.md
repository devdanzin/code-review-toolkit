# agent-pattern-consistency-checker — coverage.py

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Working copy:** `/tmp/covrepro` (`git archive HEAD | tar -x`). **I did NOT edit the target tree.** Every line number below was read from `/tmp/covrepro/coverage/...`, which is byte-identical to HEAD.
**Runtime evidence:** produced with `PYTHONPATH=/tmp/covrepro` under `~/venvs/coverage_venv/bin/python` (CPython 3.14t). All demo projects live in `/tmp/covdemo`, `/tmp/covmp`, `/tmp/covctx`, `/tmp/covreg`, `/tmp/covhash`. The C tracer is not built in the copy, so cross-core runtime comparison was done at source level; everything else is reproduced.
**Briefing read:** `briefings/pattern-consistency-checker.md` (14 shapes, 60 catalogued findings, 25 cross-project, 47 FP classes).

---

## Pattern Divergence Summary

coverage.py is a codebase of interchangeable backends and it is **pattern-consistent within each backend and inconsistent across them**. Three families carry almost all of the divergence: the six report renderers, the three tracer cores, and the three ways a child process gets measured. In every family the shared driver (`get_analysis_to_report`, `Collector`, `Coverage.__init__`) carries only the concerns that were there on day one; every concern added since (`skip_covered`, `skip_empty`, `[report] contexts`, region reporting, `--sort`, child-process warning suppression, forced parallel mode) was implemented *inside* the individual backends, so the matrices are full of holes. The catalogued shape `one-concern-implemented-per-backend` is not just confirmed — it is the dominant defect generator in this project, and eight of the sixty catalogued findings are instances of it.

The single most useful new observation is that this is now measurable end to end: **the same data file, the same config, and six report commands produce 1, 1, 3, 3, 4 and 4 rows respectively, and five different `--fail-under` verdicts** (§2, §3). Beyond confirming the catalogue I found **eight novel divergences** (§5), of which two are FIX-class: multiprocessing children emit warnings that every other child-process backend suppresses, and the "do two file-tracer assignments conflict?" predicate is implemented twice inside one file with rules that disagree.

---

## 1. Backend × concern matrix — tracer cores

The user selects among these with one knob (`COVERAGE_CORE` / `[run] core` / `[run] timid`), so they are interchangeable by the briefing's own test. Sources: `core.py:104-134`, `pytracer.py`, `sysmon.py`, `ctracer/tracer.c`.

Legend: ● implemented · ○ absent · ◐ present but inert · G guarded (the core is refused when the concern is requested)

| Concern | PyTracer | CTracer | SysMonitor | Evidence |
|---|---|---|---|---|
| line coverage | ● | ● | ● | |
| branch/arc coverage | ● | ● (packed ints) | ● | `collector.py:462-484` unpacks only for CTracer |
| arcs on Python < 3.14 | ● | ● | G | `core.py:75-76` refuses sysmon |
| dynamic contexts (`should_start_context`) | ● `pytracer.py:190-201` | ● `tracer.c:344-360` | ○ **TODO** `sysmon.py:196-197` | G at `core.py:77-78` |
| static context switch (`Coverage.switch_context`) | ● | ● | ● (via `Collector`, not the tracer) | `collector.py:391-401` |
| plugin file tracers (`file_tracers`, `check_include`, `disable_plugin`) | ○ | ● | ○ | `core.py:118/124/130`; warned at `control.py:628-638` |
| `should_trace_cache` `None` = "excluded" sentinel | ○ **reads it as a miss** `pytracer.py:223-226` | ● `tracer.c:399-401`, writes at `:470` | ○ **reads it as a miss** `sysmon.py:337-338` | protocol documented `collector.py:205-212`, typed `types.py:92` — **novel N4** |
| `concur_id_func` (greenlet/eventlet/gevent) | ○ | ● `tracer.c:220-245` | ○ | hard error at `collector.py:149-155`; G at `core.py:79-80` |
| thread jump-start (`threading` member) | ● `pytracer.py:93,320-322` | ○ (no member in `CTracer_members[]`, `tracer.c:1048-1087`) | ○ (n/a — `sys.monitoring` is process-global) | **CRF-COVPY-0009** |
| `warn` on trace-function hijack | ● `pytracer.py:352-358` | ◐ member at `tracer.c:1055`, **zero call sites** | ◐ member set, **`# TODO: warn is unused.`** `sysmon.py:202-203` | **CRF-COVPY-0003**, still present; sysmon is the un-catalogued second empty cell |
| `post_fork` | ○ | ○ | ● `sysmon.py:299-302` | dispatched by `hasattr`, `collector.py:377-381` |
| `stop()` called from a foreign thread | ● early-returns `pytracer.py:338-345` | ◐ sets a flag only `tracer.c:996-1004` | ● global `set_events(0)` `sysmon.py:271-281` | |
| `get_stats()` | ○ always `None` `pytracer.py:368-370` | ● only if built with `COLLECT_STATS` `tracer.c:1026-1046` | ● env `COVERAGE_SYSMON_STATS` `sysmon.py:53,227-231` | three different opt-ins |
| skips `__annotate__` code objects | ○ | ○ | ● `sysmon.py:323-325` | **novel N8** — the analysis-side twin is `bytecode.py:41` (**CRF-COVPY-0033**) |
| empty-set read as "not traced" | ● **bug** `pytracer.py:241-242` | ○ (tests `PyDict_GetItem == NULL`, `tracer.c:497-499`) | ○ (caches `tracing` per code object) | **CRF-COVPY-0038**; CTracer is the guarded twin |
| `lock_data`/`unlock_data` around first-touch | ● `pytracer.py:232-237` | ● `tracer.c:492-533` | ● `sysmon.py:352-357` | consistent |

**Empty cells that are real user-visible divergence:** `warn` (2 of 3 cores can never report that measurement was truncated), thread jump-start (0009), the `None` cache sentinel (novel, latent), `post_fork`.

---

## 2. Backend × concern matrix — report formats

Sources: `report.py`, `html.py`, `xmlreport.py`, `jsonreport.py`, `lcovreport.py`, `annotate.py`, `cmdline.py:609-732`, `control.py:1088-1356`.

| Concern | `report` | `html` | `xml` | `json` | `lcov` | `annotate` |
|---|---|---|---|---|---|---|
| `[report] include` / `omit` | ● | ● | ● | ● | ● | ● (all via `report_core.py:85-91`) |
| `[report] skip_empty` | ● `report.py:303` | ● `html.py:459-463` | ● `xmlreport.py:176-178` | ○ | ● `lcovreport.py:206-208` | ○ |
| `--skip-empty` on the CLI | ● | ● | ● | ○ | ○ (config only) | ○ |
| `[report] skip_covered` | ● `report.py:300-302` | ● `html.py:451-457` | ○ | ○ | ○ | ○ |
| per-format skip override | — | ● `[html] skip_covered/skip_empty`, `html.py:289-294` | ○ | ○ | ○ | ○ |
| `[report] contexts` | ● `report.py:209` | ● `html.py:132` | ○ | ● `jsonreport.py:79` | ○ | ○ |
| `[report] sort` | ● `report.py:252-268` | ○ | ○ | ○ | ○ | ○ |
| row order when `sort` is ignored | `human_sorted` | emit order (`report_core.py:100-102`) | `human_sorted_items` `xmlreport.py:128,133` | emit order | **plain `str` sort** `lcovreport.py:185` | emit order |
| `[report] precision` | ● | ● | ○ (`%.4g`, `xmlreport.py:33-38`) | ● | n/a (counts only) | n/a |
| `[report] show_missing` | ● | n/a | n/a | n/a | n/a | n/a |
| region reporting (functions/classes) | ○ | ● regions + "(no *noun*)" row, skip-flags applied `html.py:584-636` | ○ | ● regions + synthetic `""` region, skip-flags **not** applied `jsonreport.py:134-161` | ● `function` only, zero-statement regions dropped unconditionally `lcovreport.py:78,93-94` | ○ |
| returns a total for `--fail-under` | ● `pc_covered` | ● `n_statements and pc_covered` `html.py:408-411` | ● `pct` `xmlreport.py:166-171` | ● `n_statements and pc_covered` `jsonreport.py:108` | ● `n_statements and pc_covered` `lcovreport.py:191` | ○ **returns `None`** `annotate.py:55` |
| `--fail-under` accepted on the CLI | ● | ● | ● | ● | ● | ○ `cmdline.py` has no `annotate` entry with `Opts.fail_under` |
| raises `NoDataError` when nothing to show | ● `report.py:213-214` | ● `html.py:378-379` | ○ | ○ | ○ | ○ |

### 2.1 How many rows? — measured

`/tmp/covdemo`, four files (`allcov.py` 100 %, `empty.py` 0 statements, `full.py` 75 %, `main.py` 100 %), one data file, one config (`[report] skip_empty = True`, `skip_covered = True`):

| backend | file rows emitted | which |
|---|---|---|
| `report` | **1** | `full.py` |
| `html` | **1** | `full.py` |
| `lcov` | **3** | `allcov`, `full`, `main` |
| `xml` | **3** | `allcov`, `full`, `main` |
| `json` | **4** | all |
| `annotate` | **4** files written | all |

And at region granularity (`/tmp/covreg/mod.py`, three functions, one of them entirely `# pragma: no cover`):

| backend | function rows | function coverage published |
|---|---|---|
| `lcov` | **2** (`used`, `never_called`) | `FNF:2 FNH:1` → 50 % |
| `json` | **4** (`used`, `all_excluded`, `never_called`, `""`) | — |
| `html` | **4** (`used`, `all_excluded`, `never_called`, `(no function)`) | — |
| `report` / `xml` / `annotate` | **0** | — |

This is **CRF-COVPY-0043** with numbers attached. The lcov side is novel (§5, N3).

---

## 3. `--fail-under` across formats — measured

`/tmp/covdemo/zero`: one file with zero statements, `[report] fail_under = 50`. Identical data, identical config:

| command | value gated | exit |
|---|---|---|
| `coverage report` | `100.0` (`Numbers._percent` returns 100.0 for a 0/0 ratio, `results.py:336-340`) | **0 — passes** |
| `coverage xml` | `0.0` (`xmlreport.py:167-168`) | **2 — fails** |
| `coverage json` | `0` (`n_statements and …`, `jsonreport.py:108`) | **2 — fails** |
| `coverage lcov` | `0` (`lcovreport.py:191`) | **2 — fails** |
| `coverage html` | `0` (`html.py:408-411`) | **2 — fails** |
| `coverage annotate` | *never evaluated* (`annotate.py:55` returns `None`; `cmdline.py:937` `if total is not None`) | **0 — no gate** |

**CRF-COVPY-0032** confirmed, now with exit codes.

The **asymmetric-rounding** pair is also still live:

* **CRF-COVPY-0007** — `results.py:502` gates on `round(total, precision) < fail_under` while `display_covered` (`results.py:403-418`) clamps. Demonstrated: `total = 89.995`, `precision = 2` → **displayed `90.00%`, `fail_under = 90` passes**, on a run that is genuinely below 90.
* **CRF-COVPY-0008** — `xmlreport.py:33-38` `rate()` still formats with `%.4g`, so `99.997%` is published as `line-rate="1"` and `[report] precision` has no effect on any XML number.

---

## 4. Backend × concern matrix — child-process measurement

Three interchangeable mechanisms measure a child process. Sources: `multiproc.py`, `control.py:1433-1503`, `patch.py`, `pth_file.py`, `config.py:559-578`.

| Concern | `concurrency = multiprocessing` | `patch = subprocess` / `COVERAGE_PROCESS_START` (`.pth` → `process_startup`) | `patch = fork` |
|---|---|---|---|
| entry point | `multiproc.py:30-63` | `pth_file.py:10-16` → `control.py:1433-1496` | `patch.py:103-111` → `control.py:1499-1503` |
| config source | `COVERAGE_RCFILE` env (`multiproc.py:96`) | `COVERAGE_PROCESS_CONFIG` / `COVERAGE_PROCESS_START` (`control.py:1478-1483`) | inherits whatever `process_startup` finds |
| forces `data_suffix` | ● explicit (`multiproc.py:36`) | ○ relies on `[run] parallel` | ○ |
| forces `parallel = True` | ● `control.py:381-384` | ● `config.py:565-566` (in `post_process`) | ○ **neither** |
| `_warn_preimported_source = False` | ● `multiproc.py:37` | ● `control.py:1492` | ● |
| `_warn_no_data = False` | ○ **missing** | ● `control.py:1490` | ● |
| `_warn_unimported_source = False` | ○ **missing** | ● `control.py:1491` | ● |
| stops a pre-existing Coverage first | ○ | ○ | ● `control.py:1501-1502` |
| re-entrancy guard | module marker `multiproc.py:89` | function attribute `control.py:1470` | bypassed (`force=True`) |
| works on Windows | ● | ● | ○ raises `patch.py:107-108` |

The two ○ cells in the first column are **novel finding N1** below. `patch = fork` forcing neither suffix nor parallel is **CRF-COVPY-0002**, confirmed at `control.py:1499-1503`.

---

## 5. Novel divergences (not in the catalogue)

### N1 — [FIX] `concurrency = multiprocessing` children emit warnings every other child-process backend suppresses
*Shape: `one-concern-implemented-per-backend`*

`process_startup()` turns off the three warnings that only make sense in the parent:

```python
# control.py:1490-1492
cov._warn_no_data = False
cov._warn_unimported_source = False
cov._warn_preimported_source = False
```

`ProcessWithCoverage._bootstrap` turns off **one**:

```python
# multiproc.py:36-37
cov = Coverage(data_suffix=True, auto_data=True)
cov._warn_preimported_source = False
```

so `_post_save_work` (`control.py:950-955`) fires in every worker.

**Reproduced** (`/tmp/covmp`, a `multiprocessing.Pool(4)` whose workers never import the `source` package):

```
[run] source_pkgs = mypkg, concurrency = multiprocessing  →  4 CoverageWarning lines on stderr
[run] source_pkgs = mypkg, patch = subprocess             →  0
```

The warning is `No data was collected. (no-data-collected)` from `control.py:955`, once per worker, interleaved with the program's own output. Both configurations measure the same children and produce the same combined data — only the noise differs. `no-data-collected` is suppressible via `[run] disable_warnings`, but doing so also silences it for the parent, which is where it is genuinely useful.

**Guarded twin / fix:** `control.py:1490-1492`. The three assignments should move into a `Coverage._configure_as_child()` helper (or a `Coverage(..., child=True)` flag) that both entry points call, so a fourth child-process mechanism cannot be added without them.

### N2 — [FIX] The file-tracer conflict predicate is implemented twice in one file, with rules that disagree
*Shape: `one-predicate-two-implementations`*

`CoverageData.file_tracer()` documents the sentinel (`sqldata.py:970-973`): `""` means *measured, no plugin*; `None` means *not measured*. The in-process writer honours it — `""` is falsy, so it is not a conflict:

```python
# sqldata.py:647-653
existing_plugin = self.file_tracer(filename)
if existing_plugin:
    if existing_plugin != plugin_name:
        raise DataError(f"Conflicting file tracer name for {filename!r}: ...")
elif plugin_name:
    con.execute_void("INSERT INTO TRACER ...")
```

The combine path does not — it `COALESCE`s a missing row to `''` and then compares for inequality:

```sql
-- sqldata.py:770-786
WHERE COALESCE(main.tracer.tracer, '') != COALESCE(other_db.tracer.tracer, '')
```

**Reproduced** — the *same two facts*, once inside one `CoverageData` and once across two:

```
IN-PROCESS  add_lines(x.py); add_file_tracers({x.py: "myplugin"})
            -> ACCEPTED, tracer = 'myplugin'
COMBINE     data_a: add_lines(x.py)   |  data_b: add_lines(x.py) + tracer 'myplugin'
            data_a.update(data_b)
            -> DataError: Conflicting file tracer name for 'x.py': '' vs 'myplugin'
```

`update()` is what `coverage combine` runs (`data.py:combine_parallel_data` → `control.py:904`) **and** what `_prepare_data_for_reporting` runs whenever `[paths]` is configured (`control.py:1081-1086`). So a file that is plugin-traced in one data file and plain in another — or two distinct files that `[paths]` collapses onto one name, one of them plugin-traced — aborts the whole combine with a raw `DataError`, where merging the identical facts in a single process succeeds.

**Which is right:** the in-process one. It matches the documented meaning of `""`. **Fix:** `WHERE main.tracer.tracer IS NOT NULL AND other_db.tracer.tracer IS NOT NULL AND main.tracer.tracer != other_db.tracer.tracer` — or, better, hoist the predicate into one `_tracers_conflict(a, b)` used by both.

Reachability caveat, stated honestly: I reproduced this through the public `CoverageData` API (documented, and the API pytest-cov and coverage's own combine use). I did not build an end-to-end CLI repro, which additionally requires the plugin to be present for one data file and absent for the other.

### N3 — [CONSIDER] LCOV drops zero-statement regions unconditionally; HTML and JSON keep them
*Shape: `one-concern-implemented-per-backend`, at region granularity*

```python
# lcovreport.py:93-94
analysis = narrower.narrow(region.lines)
if analysis.numbers.n_statements == 0:
    continue
```

This is not gated on `skip_empty` — setting `skip_empty = False` does not bring the region back, even though the *file*-level empty skip immediately below it (`lcovreport.py:206-208`) is gated. `html.py:607-608` routes every region through `should_report`, which honours both skip flags; `jsonreport.py:147-161` emits every region unconditionally and adds a synthetic `""` region that lcov has no equivalent of.

**Reproduced** (`/tmp/covreg/mod.py`, three functions, one fully `# pragma: no cover`): lcov publishes `FNF:2 FNH:1` (50 % function coverage) while the HTML function index and the JSON `functions` map both list 4 entries. A CI dashboard reading lcov's function coverage and a developer reading the HTML function index are looking at different denominators for the same run.

### N4 — [CONSIDER] The `should_trace_cache` `None` sentinel is honoured by one core in three
*Shape: `one-concern-implemented-per-backend` × `empty-result-conflated-with-absent`*

The cache protocol is written down twice — in prose at `collector.py:205-212` ("the `FileDisposition` will be replaced by `None` in the cache") and in the type at `types.py:92` (`Mapping[str, TFileDisposition | None]`). Only CTracer implements it: it writes `Py_None` for a dynamically-excluded name (`tracer.c:470`) and reads it as *do not trace* (`tracer.c:399-401`). Both Python cores read a stored `None` as a cache **miss** and recompute:

```python
# pytracer.py:223-226 (identical shape at sysmon.py:337-338)
disp = self.should_trace_cache.get(filename)
if disp is None:
    disp = self.should_trace(filename, frame)
```

Latent today, because only CTracer writes `None` and only CTracer supports plugins (`core.py:118/124/130`). It is exactly the trap waiting for whoever adds plugin support to `sysmon` — the "this dynamic filename was excluded" memo would silently become "recompute", re-including every dynamically excluded file. **Fix:** a distinct `EXCLUDED` sentinel object, or `dict.get(filename, MISSING)`, so the two states cannot be confused by any reader.

### N5 — [CONSIDER] The combine dedup key is not stable across tracer cores
*Shape: `same-fact-derived-from-two-sources`; strengthens **CRF-COVPY-0036***

`Collector.flush_data` hands the hasher two different Python types for the same arc data depending on the core:

```python
# collector.py:462-479  (CTracer)          arc_data[fname] = tuples          -> list
# collector.py:480-484  (PyTracer/SysMon)  fname: arcs.copy()                 -> set
```

and `misc.Hasher.update` sorts sets but not lists, and mixes `str(type(v))` into the digest. Proven directly:

```
set       -> eadcda2fe2404760ac0e66cc9fd76776
list      -> 591b5471bd70de9f16ad6d91033a7e3b   (differs)
list(rev) -> 0847c9d707da65020cab11f84341149a   (order-dependent)
```

That digest becomes the `.H…h` filename suffix (`sqldata.py:912-927`) and is the dedup key in `DataFileClassifier.classify` (`data.py:111-129`). Consequence: identical measurements taken under different cores never dedup, and under the C tracer the digest depends on the iteration order of a `set[int]`. This direction only *weakens* dedup rather than losing data, hence CONSIDER — but it confirms the catalogued claim that the hash is not a function of the artifact, and points at the precise mechanism.

Related, same root: `touch_files` (`sqldata.py:668-685`) is the only writer that does **not** update `_hasher`, so two data files that differ only in their un-executed-file lists hash identically and one is skipped. (I checked and the obvious context case is *not* affected — `_set_context_id` does hash, `sqldata.py:502`; a two-context parallel run combines correctly. Verified in `/tmp/covhash`.)

### N6 — [CONSIDER] `--sort` is honoured by one of six backends, and the other five each choose a different order
`report.py:252-268` implements `--sort` and defaults to `human_sorted`. `xmlreport.py:128,133` uses `human_sorted_items` (not user-selectable). `lcovreport.py:185` uses a plain `to_report.sort()` on the relative filename — plain lexicographic, so `f10.py` precedes `f2.py` where the text and XML reports put `f2.py` first. `json`, `html` and `annotate` emit in `get_analysis_to_report` order (`report_core.py:100-102`). `[report] sort` lives in the shared `[report]` section (`config.py:447`), which advertises it as a reporting-wide option.

### N7 — [CONSIDER] "Force parallel mode so children don't clobber the parent" is implemented twice, and two patch modes get neither
`config.py:565-566` sets `parallel = True` for `patch = subprocess`, inside `post_process()`. `control.py:381-384` sets it for `concurrency = multiprocessing`, inside `_init()`. Because `post_process()` has exactly one caller (**CRF-COVPY-0027**), `cov.set_option("run:patch", ["subprocess"])` does **not** get parallel mode while `cov.set_option("run:concurrency", ["multiprocessing"])` does — the same concern, two implementations, one of which is bypassed by the programmatic entry point. `patch = execv` and `patch = fork` also create data-writing processes and force neither.

### N8 — [CONSIDER] `__annotate__` suppression exists on the measurement side of one core only
`sysmon.py:323-325` returns `DISABLE` for `code.co_name == "__annotate__"`; PyTracer and CTracer have no such check. The analysis-side twin is `bytecode.py:41`, which is **CRF-COVPY-0033**. Today the two cancel out (sysmon does not measure it, and no core analyses it, so every core reports the same nothing). **This is a fix-propagation trap:** fixing `bytecode.py:41` so a user-written `__annotate__` body counts as statements, without also removing `sysmon.py:323-325`, would make the same file report those lines as *covered* under `ctrace`/`pytrace` and *missing* under `sysmon` — which is the default core on 3.14.

### N9 — [note, not a finding] The two `zip()` calls in `report_text` have opposite length contracts
For the pitfall agent's `zip(..., strict=)` triage: in `SummaryReporter`, `lines_values` rows carry a **deliberate trailing sort key** (`report.py:248` appends `nums.pc_covered` after the last displayed column), so `zip(header, values)` at `report.py:106` and `:176` is *load-bearing truncation* — `strict=True` there would raise on every run. `total_line` carries no sort key (`report.py:271-276`), so `zip(header, total_line)` at `report.py:117` and `:188` is exact and `strict=True` is safe. `html.py:385` is an intentional pairwise `zip(xs[:-1], xs[1:])`; `sysmon.py:134` is inside the `LOG`-only `panopticon` decorator. So of the six flagged sites, four are intentional and two are safe to strictify — but not uniformly.

---

## 6. Catalogued findings — confirmation pass

Verified still present at HEAD; not re-litigated. Those marked **repro** I reproduced at runtime.

| ID | status | note |
|---|---|---|
| CRF-COVPY-0003 | present | `warn` member declared `tracer.c:1055`, only reference is the `Py_XDECREF` at `:92`. Second empty cell: `sysmon.py:202-203` (`# TODO: warn is unused.`) |
| CRF-COVPY-0007 | present, **repro** | `results.py:502`; `total=89.995, precision=2` displays `90.00%` and passes `fail_under = 90` |
| CRF-COVPY-0008 | present | `xmlreport.py:33-38`; `[report] precision` has no effect on any XML rate |
| CRF-COVPY-0009 | present | no `threading` member in `CTracer_members[]` (`tracer.c:1048-1087`); `collector.py:334` |
| CRF-COVPY-0010 | present, **repro** | `set_query_contexts` called at `report.py:209`, `html.py:132`, `jsonreport.py:79`; **not** in `xmlreport.py`, `lcovreport.py`, `annotate.py`. In `/tmp/covctx`, one process: `xml_report()` → all lines `hits="1"`; then `report(contexts=["test_a"])`; then the *same* `xml_report()` with no `contexts=` → nearly every line `hits="0"`. The filter leaks and there is no way to clear it from the XML path. |
| CRF-COVPY-0027 | present | `config.py:494-529` is a bare `setattr` loop; `post_process()` (`config.py:559-578`) has one caller — see N7 for a concrete symptom |
| CRF-COVPY-0030 | present | guard reads `_has_lines`/`_has_arcs` (`sqldata.py:725-732`), insert re-derives from `EXISTS(SELECT 1 FROM other_db.arc)` (`sqldata.py:804-809`) |
| CRF-COVPY-0032 | present, **repro** | exit codes in §3 |
| CRF-COVPY-0033 | present | `bytecode.py:41`; see N8 for the propagation trap |
| CRF-COVPY-0036 | present | `sqldata.py:912-927`, `data.py:99-129`; mechanism detailed in N5 |
| CRF-COVPY-0038 | present | `pytracer.py:241-242` tests `not self.cur_file_data` (true for an emptied set); CTracer tests key presence (`tracer.c:497-499`) and sysmon caches `tracing` per code object — both are guarded twins |
| CRF-COVPY-0040 | present | slug-less `_warn`/`warn` call sites: `control.py:629`, `collector.py:409`, `inorout.py:426`, `html.py:131`, `data.py:211`, `config.py:346` — six, as catalogued |
| CRF-COVPY-0043 | present, **repro** | row counts and region counts in §2.1 |
| CRF-COVPY-0002 | present | `control.py:1499-1503`; matrix row in §4 |

Cross-project shapes hunted here with **no hit**, reported as absence only because the briefing asks: `case-normalization-on-a-literal-key` (no `.lower()` on a store key in this tree), `mirrored-direction-handles-fewer-cases` (`add_lines`/`add_arcs` and `serialize`/`deserialize` are symmetric), `index-computed-before-a-mutation-used-after-it`.

---

## 7. Missing abstractions

1. **A report-lifecycle base class.** Every renderer re-implements the same five-step loop by hand: set query contexts → iterate `get_analysis_to_report` → decide whether the file is reportable → accumulate a `Numbers` total → return a gate value. There is a `Reporter` `Protocol` (`report_core.py:23-29`) but it declares only `report()`, so it enforces nothing. A `BaseReporter` with `prepare()` (which *always* calls `set_query_contexts`), `should_report(analysis)` (which *always* applies `skip_covered`/`skip_empty` with the per-format overrides), and `total()` (one definition of the gate value) would collapse rows 2-7 and 12-13 of the §2 matrix into one implementation. **Would unify:** `report.py`, `html.py`, `xmlreport.py`, `jsonreport.py`, `lcovreport.py`, `annotate.py` — six files, and closes CRF-COVPY-0010, 0032, 0043 and N3/N6 in one change.
2. **One `total_for_gate(numbers) -> float | None`.** Four call sites spell the same idea four ways (`pc_covered`; `n_statements and pc_covered` ×3; a hand-rolled `100.0*(hits)/(valid)`), and `annotate` has none. Put it on `Numbers` and make `annotate` return it too. **Would unify:** `report.py:221`, `html.py:408-411`, `xmlreport.py:166-171`, `jsonreport.py:108`, `lcovreport.py:191`, `annotate.py:55`. Closes CRF-COVPY-0032.
3. **`Coverage._configure_as_child()`.** One place that sets `data_suffix`, `parallel`, and the three `_warn_*` flags for any process coverage did not start interactively. **Would unify:** `multiproc.py:36-37`, `control.py:1490-1493`, `config.py:565-566`, `control.py:381-384`. Closes N1 and N7 and makes CRF-COVPY-0002 a one-line fix.
4. **`_tracers_conflict(a, b) -> bool`.** One predicate, called from `add_file_tracers` and generated into the combine SQL (or applied in Python over the joined rows). **Would unify:** `sqldata.py:647-653` and `sqldata.py:770-786`. Closes N2.
5. **A real `Tracer` ABC instead of `hasattr` duck-typing.** `Collector._start_tracer` (`collector.py:260-273`) probes six optional attributes with `hasattr`, and `Collector.post_fork` (`collector.py:377-381`) probes a seventh. That is why a core can silently lack `warn`, `post_fork` or `threading` without anything noticing. Making `Tracer` (`types.py:86-114`) declare every hook — with default no-op implementations and, critically, a default `warn`-on-hijack — turns each empty cell in §1 into a deliberate `pass` with a comment rather than an accident. **Would unify:** `pytracer.py`, `sysmon.py`, `ctracer/tracer.c`, `collector.py`, `core.py`.
6. **A distinct `EXCLUDED` sentinel for `should_trace_cache`.** Closes N4 and removes the `TFileDisposition | None` ambiguity from `types.py:92`.

---

## 8. Recommendations, prioritised

1. **N1** — add `_warn_no_data = False` and `_warn_unimported_source = False` at `multiproc.py:37` (one line each), then do it properly via abstraction 3. Highest value-per-byte: it is user-visible on every `concurrency = multiprocessing` run and the fix is two lines.
2. **N2** — fix the combine SQL's conflict predicate (`sqldata.py:778`) to require both sides non-empty. Currently aborts a whole `coverage combine` on a state the in-process writer accepts.
3. **Abstraction 1 + 2** — the report base class and the single gate value. This is the change that turns §2 from a matrix of holes into a matrix of ●, and it retires four catalogued findings at once. Largest effort, largest payoff.
4. **CRF-COVPY-0010** — even before the base class, move `set_query_contexts(self.config.report_contexts)` into `get_analysis_to_report` (`report_core.py:82`). Three lines deleted from three backends, three holes filled, and the leak between reports in one process disappears because every report sets it.
5. **N3** — gate `lcovreport.py:93-94` on `self.config.skip_empty` so lcov's `FNF`/`FNH` agree with the HTML and JSON function lists.
6. **Abstraction 5** — give `Tracer` real defaults so the §1 empty cells become explicit. Do this before anyone adds a fourth core.
7. **N4 / N8** — cheap, latent, and both are traps for the next person to touch plugins or `__annotate__`. Fix as part of whichever work touches them.
8. **N5 / N6 / N7** — record as known divergences; N5 only weakens dedup, N6 is cosmetic, N7 is a symptom of CRF-COVPY-0027 and will be fixed with it.
