# test-coverage-analyzer — coverage.py (informed pass)

**Target:** `/home/danzin/projects/coveragepy` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main)
**Tree edited:** **No.** Nothing in the target was modified. All analysis was `git log`/`git show`/`grep`/read.
A read-only copy was extracted with `git archive HEAD | tar -x -C /tmp/covrepro` and every script was run
there. (Note: `ctracer_repros/`, `repro.py`, `ctracer_review_*.md` were already untracked in the working
tree when I arrived — pre-existing artifacts from an earlier session, not mine, not touched.)

**Scope split:** I own the structural gap map, the self-coverage/pragma audit, the no-test-commit hunt, and
the skip audit. Invariants and mutation testing belong to test-investigation-agent and are not duplicated here.

---

## 0. The 39.7% is wrong. Three separate defects, in both directions.

`correlate_tests.json` reports **29 of 73 source files with tests = 39.7%**. Every one of those three
numbers is wrong.

### Defect A — the denominator counts things that are not source (27 of 44 "untested" files)

`untested_sources` has 44 entries. Only **17** are shipped source (`coverage/*.py`). The other 27:

| Bucket | Count | What it actually is |
|---|---|---|
| `lab/*.py` | 13 | Ned's experiment scripts. Not shipped, not importable as a package. |
| `ctracer_repros/*.py` | 6 | **Untracked** crash reproducers left in the working tree by a prior review session. Not in git at all. |
| `ci/*.py` | 4 | GitHub-Actions helper scripts (`comment_on_fixes`, `session`, `trigger_action`, `update_rtfd`). |
| `doc/*.py` | 2 | `conf.py` (Sphinx) and `cog_helpers.py`. |
| `igor.py` | 1 | The project's own dev task runner. |
| `repro.py` | 1 | **Untracked** scratch file. |

So 61% of the "untested source" list is not source, and 7 of those files are not even tracked in git.
This is the same over-counting the briefing warned about from the last project, reproduced exactly.

### Defect B — the numerator credits test *fixtures* as test files (4 of 29 matches are phantom)

`test_files: 101` counts every `.py` under `tests/`. Only **42** are `tests/test_*.py`. The other 59 are
fixtures and support modules (`tests/modules/**`, `tests/moremodules/**`, `tests/zipsrc/**`,
`coveragetest.py`, `helpers.py`, `mixins.py`, `testenv.py`, `goldtest.py`, `plugin1.py`, …). Because they
are in the test-file pool, four source files were matched to a fixture with zero test methods:

| Source | "matched" test file | Reality |
|---|---|---|
| `coverage/__init__.py` | `tests/__init__.py` + 15 other `__init__.py` fixtures | package markers |
| `coverage/__main__.py` | `tests/modules/pkg1/__main__.py` | a fixture module used to test `python -m` |
| `__main__.py` (repo root) | same fixture | same |
| `lab/parser.py` | `tests/test_parser.py` | cross-directory basename collision — `test_parser.py` tests `coverage/parser.py` |

Note the direction: A deflates the number, B inflates it. They do not cancel; they just make the figure
uninterpretable.

### Defect C — the summary disagrees with its own detail rows, by 3.2x on skips and 1.7x on methods

| Summary field | Value | Detail rows say | Reality |
|---|---|---|---|
| `total_skipped_tests` | 13 | **42** (sum of every `classes[].skipped_methods`) | 1 unconditional `@pytest.mark.skip`, 58 `@pytest.mark.skipif`, 8 in-body `pytest.skip()` |
| `total_test_methods` | 669 | 32 (`test_details` inventory is near-empty) | **1170** `def test_` in `tests/test_*.py`, plus ~100 `@parametrize` decorators expanding them further |

Both summary figures are sums over the **29 matched source files only** — every test in
`test_process.py` (74), `test_arcs.py` (112), `test_coverage.py` (72), `test_api.py` (78),
`test_oddball.py` (21), `test_concurrency.py` (25), `test_venv.py`, `test_setup.py` and
`test_report_common.py` is silently outside the totals, because those files name-match no source module.
The prompt's "743 test functions" is also low; the real count is 1170 pre-parametrization.

### The corrected number

Define source = the 44 shipped `coverage/*.py` modules. Then:

| Rule | Result |
|---|---|
| As reported | 29 / 73 = **39.7%** |
| Same basename rule, correct denominators (source = `coverage/*.py`, tests = `tests/test_*.py`) | 25 / 44 = **56.8%** |
| **Correct rule — credit differently-named owning test files** (`test_xml.py`→`xmlreport.py`, `test_json.py`→`jsonreport.py`, `test_lcov.py`→`lcovreport.py`, `test_api.py`→`control.py`, `test_plugins.py`→`plugin.py`+`plugin_support.py`, `test_data.py`→`sqldata.py`) | **32 / 44 = 72.7%** |
| Weighted by statements (coverage.py's own parser, 7280 statements in `coverage/*.py`) | **6325 / 7280 = 86.9%** of shipped statements live in a module that has a dedicated test file |

**Report 72.7% of modules / 86.9% of statements, not 39.7%.** The 12 modules with no dedicated test file
account for 955 statements (13.1%), and only five of them are non-trivial.

---

## 1. Genuinely undertested modules, ranked by importance × gap

Two axes. **(a)** modules with no dedicated test file at all; **(b)** modules that have one but whose test
mass is negligible relative to the code. Axis (b) turns out to matter far more than axis (a) — and it is
invisible to the file-correlation script entirely, because those modules all score `has_tests: true`.

Importance is weighted by statement count (coverage.py's own `PythonParser`) and by **catalogued-finding
density** — the 60 findings in the briefing are the best available proxy for fan-in × fix-density, since
neither `agent-architecture-mapper.md` nor `agent-git-history-context.md` had been written when I ran.

### (b) The real gap: modules with a dedicated test file that tests almost nothing

Ratio = statements in the owning test file(s) ÷ statements in the source module.

| Rank | Module | Stmts | Owning test file | Test fns | Ratio | Catalogued findings |
|---|---|---|---|---|---|---|
| **1** | `collector.py` | 235 | `test_collector.py` | **1** | **0.06** | **5** (0009, 0012, 0013, 0051, 0052) |
| **2** | `sysmon.py` | 294 | `test_sysmon.py` | 6 | **0.14** | **6** (0004, 0005, 0017, 0022, 0042, 0044) |
| 3 | `bytecode.py` | 99 | `test_bytecode.py` | 2 | 0.17 | 1 (0033) |
| 4 | `results.py` | 240 | `test_results.py` | 10 | 0.25 | 3 (0007, 0031, 0032) |
| 5 | `python.py` | 148 | `test_python.py` | 4 | 0.29 | 1 (0014) |
| 6 | `regions.py` | 52 | `test_regions.py` | 2 | 0.50 | 1 (0034) |
| 7 | `sqlitedb.py` | 124 | `test_sqlitedb.py` | 8 | 0.52 | 1 (0025) |
| — | (median across the 32 mapped modules) | | | | 1.10 | |

**The correlation is the finding.** The two thinnest-tested modules in the project are exactly the two
that host the most catalogued defects — 11 of the 60 findings, 18%, in 529 of 7280 statements (7%).

**`collector.py` — FIX / rating 10.** `tests/test_collector.py` contains one test,
`CollectorTest.test_should_trace_cache`, and it does not test `Collector` at all: it asserts that
`Coverage._should_trace` is invoked once per filename, which is `inorout`/`control` behaviour observed
through a hook. **`Collector` itself has zero direct tests.** Untested: `flush_data()` (the
snapshot-under-concurrent-mutation logic, 235:450-490), `mapped_file_dict()`'s 3-retry loop,
`switch_context()`, `pause()`/`resume()`, `_start_tracer()`, the per-thread tracer registry, and the
`should_start_context` plumbing. Every one of the five catalogued findings in this file sits in code with
no dedicated test — 0012 (`file_tracers` iterated unguarded in `flush_data`) is a one-line sibling of a
race that was fixed two lines above it.
*Suggested tests:* a `Collector` unit test that (i) starts N tracer threads writing into `self.data`,
calls `flush_data()`, and asserts no `RuntimeError` and no lost lines; (ii) asserts `file_tracers` is
snapshotted the same way `arc_data`/`line_data` are; (iii) drives `resume()` on a thread other than the
one that called `pause()` and asserts the calling thread gets *its own* tracer back (0013).

**`sysmon.py` — FIX / rating 10.** `tests/test_sysmon.py` has six tests, and all six are about
`compute_multiline_map` and its cache (`ComputeMultilineMapTest`, `MultilineMapCacheTest`). **`SysMonitor`
— the default core on Python 3.14+ — has zero direct tests.** Untested: `start()` (including the tool-id
search loop added in `4b0fc8571`, see §3), `stop()`, and all five `sys.monitoring` callbacks
(`sysmon_py_start`, `sysmon_py_resume`, `sysmon_line`, `sysmon_branch*`, `sysmon_py_return`). Findings
0022 (three callbacks index `code_infos` unguarded where a fourth checks) and 0005 (nested `Coverage`
permanently stops measurement) are exactly the kind of thing a callback-level unit test finds and an
end-to-end run does not — an end-to-end run asserts line sets, and a dropped event on a file the test
does not assert about is invisible.
*Suggested tests:* instantiate `SysMonitor`, register it, and drive each callback directly with a code
object that is *not* in `code_infos`; assert a clean `DISABLE`/no-op rather than `KeyError`. Add a
start/stop/start cycle asserting events are re-registered (0005).

**`results.py` — CONSIDER / rating 7.** 240 statements, 10 tests, ratio 0.25 — and it is the module that
computes every number the tool prints, including `--fail-under`. Findings 0007 (rounding asymmetry
between the printed total and the gate), 0031 (`no_branch` desynchronizes counters from arc lists) and
0032 (zero-statement files) are all *arithmetic* defects, the single cheapest thing to unit-test, in a
module with almost no unit tests. `Numbers` is also load-bearing outside the package: `lab/goals.py`
imports it to implement the CI coverage gate.
*Suggested tests:* property-style tests over `Numbers` — `pc_covered_str` vs `pc_covered` agreement at
the 99.99x and 0.00x boundaries; `Analysis` with `n_statements == 0`; a file with `no branch` pragmas
asserting `n_branches`/`n_partial_branches` match the arc lists they are derived from.

### (a) Modules with no dedicated test file (955 statements, 13.1%)

| Module | Stmts | Verdict | Why |
|---|---|---|---|
| `inorout.py` | 347 | **CONSIDER / 7** | Largest unmapped module. Owns `should_trace`, `check_include_omit_etc`, `find_possibly_unexecuted_files`. Tested only obliquely through `test_api.py`'s source/include/omit cases and `test_venv.py`. Finding 0037 — *"the should-trace gate knows eight rules; the unexecuted-file enumerator knows one"* — is precisely a defect a `tests/test_inorout.py` that exercised both predicates on the same inputs would catch in one parametrized test. |
| `pytracer.py` | 169 | **CONSIDER / 6** | No dedicated tests, but *is* exercised end-to-end: `tox.ini` runs the whole suite three times (`igor.py test_with_core ctrace / pytrace / sysmon`). So line coverage is high and behavioural coverage is nil. Finding 0038 (an emptied set read as an untraced file, disabling line events for the frame) produces *missing data on a file the test does not assert about* — structurally invisible to end-to-end assertions. |
| `tomlconfig.py` | 128 | **CONSIDER / 6** | Tested inside `test_config.py` (15 of its 56 tests mention toml). See §5 for the specific cross-product gap that lets 0028/0029 survive. |
| `patch.py` | 67 | **FIX / 8** | No dedicated test file, and see §3: `patch = fork` shipped with **zero** tests and is catalogued as a FIX (0002). `patch = _exit` has one test (`test_process.py:478`); `patch = execv` and `patch = fork` have none. |
| `multiproc.py` | 67 | CONSIDER / 5 | Exercised by `test_concurrency.py::MultiprocessingTest`, no direct tests. |
| `types.py` (66), `env.py` (35), `disposition.py` (34), `exceptions.py` (24) | 159 | **ACCEPTABLE** | Type aliases/Protocols, environment constants, a `__repr__` dataclass, exception classes. No behaviour to test. `types.py` is imported by 14 test files, `exceptions.py` by 21 — they are exercised as vocabulary. |
| `pth_file.py` (7), `__init__.py` (7), `__main__.py` (4) | 18 | see §2 | `pth_file.py` is not a module — it is a text template embedded into the installed `.pth` by `setup.py`. It is also the one file the project excludes wholesale from its own coverage. |

---

## 2. The irony: coverage.py measures itself, and the gaps it tolerates are the interesting list

**Yes, there is a recorded self-coverage figure.** The project calls it *metacov*:

- `metacov.ini` — a full second config for measuring coverage.py with coverage.py.
- `.github/workflows/coverage.yml` — runs the whole suite under `COVERAGE_COVERAGE=yes` across 10 Python
  versions × 3 OSes (including `3.14t`/`3.15t` free-threaded), combines, and publishes.
- The number is published to a badge gist (`nedbat/8c6980f77988a327348f9b02bbaf67f5`) and rendered in
  `README.rst:17` as `|metacov|`, and the full HTML report is pushed to `coveragepy/metacov-reports`.
- It is **not** stored anywhere in the repository — no committed `coverage.json`, no threshold constant.
  The only in-repo commitment is the two gates below.

### NOVEL — the 90% self-coverage floor is really a ~76% floor on the product code

`.github/workflows/coverage.yml`, "Check targets" step:

```bash
if ! python lab/goals.py --group 90 "coverage/*.py" "tests/*.py"; then
    echo '***** Total coverage is less than 90%!'; exit 1; fi
if ! python lab/goals.py --file 100 "tests/test_*.py"; then
    echo '***** Coverage of test files must be 100%!'; exit 1; fi
```

`lab/goals.py --group` pools the selected files into **one** `Numbers` total. The pool is
`coverage/*.py` **plus** `tests/*.py`. Measured with coverage.py's own parser on this checkout:

| Group member | Statements | Share of the gate's denominator |
|---|---|---|
| `coverage/*.py` | 7 279 | **41.0%** |
| `tests/*.py` | 10 456 | **59.0%** |

The second gate independently pins `tests/test_*.py` (9 697 of those 10 456 statements) at **100%**. So
59% of the 90% gate's denominator is code another gate already forces to 100%. Solving for the product
code:

> `0.90 = (0.410·x + 0.590·~1.00)` → **x ≈ 0.76**

**`coverage/*.py` could fall to roughly 76% and the "Total coverage is less than 90%!" gate would still
pass silently.** The gate that reads as "our product is 90% covered" is arithmetically a ~76% floor with a
100% floor on the tests. Two `--group` invocations (one per directory, or `--group 90 "coverage/*.py"`
alone) would make the number mean what it says. **CONSIDER / rating 7** — no bug today (the actual
metacov number is presumably well above 76%), but the *guard rail* is 14 points looser than it reads, and
a slow erosion of product coverage would not trip it.

Secondary: the gate is implemented by `lab/goals.py`, a file that (i) prints
*"this is a proof-of-concept. Support is not promised"* on every CI run, (ii) `pip install wcmatch` on an
unpinned version at gate time, and (iii) imports `from coverage.results import Numbers  # Note: an
internal class!` — so the release gate depends on an internal API of the thing it is gating. It fails
*safe* (any non-zero exit is read as "below goal"), but it fails with a **wrong message**: an
`ImportError` or a `wcmatch` install failure both print "Total coverage is less than 90%!". **POLICY.**

Third: `select_files()` picks from the files **present in `coverage.json`**. A `coverage/*.py` file
missing from the report is silently dropped from the group rather than counted as 0%.

### NOVEL — the self-declared exclusions, audited

`coverage/*.py` carries 39 pragma sites. 15 are `pragma: debugging` (uninteresting — hand-invoked debug
tooling). The remaining 24 are the interesting list. Ranked by what a wrong assumption costs:

| Site | Pragma | Assessment |
|---|---|---|
| **`coverage/pth_file.py:5`** | `# pragma: exclude file from coverage` | **FIX / 9.** The *only* whole-file exclusion in the package — and it is the file that carries catalogued finding **CRF-COVPY-0026** (*"the .pth bare except hides a broken install, so every subprocess contributes nothing"*, `pth_file.py:11-16`). The one file coverage.py refuses to measure in itself contains a FIX-grade bug whose symptom is *silently collecting nothing*. It is genuinely hard to measure (it runs at interpreter start-up, before coverage exists) — but "hard to measure" is exactly why it needs a test, and there is none. |
| **`coverage/collector.py:425,428,432`** | `part covered` + **`cant happen` ×2** | **FIX / 9.** `mapped_file_dict()`: a 3-iteration retry loop whose `except RuntimeError` branch and whose loop-exhaustion `else: raise` branch are both declared **`cant happen`** — i.e. the project has told its own coverage tool never to report them as missing. The justifying comment (`:418-423`) is the "the GIL protects the dictionary iterator" claim catalogued as **CRF-COVPY-0052**, in a project that ships free-threaded wheels and runs `3.14t`/`3.15t` in this very workflow. Worse, commit `8cd392e3b` (May 2026) *disproved that claim* for the sibling function `flush_data()` — it replaced `list(...)` with `.copy()` snapshots precisely because `RuntimeError: Set changed size during iteration` was reachable. The disproven justification and its `cant happen` pragmas were left in place two functions up. This is `fix-not-propagated-to-sibling-path` with a coverage-suppression twist: the propagation gap cannot be detected by the coverage report, because the pragma removes the signal. |
| **`coverage/parser.py:980, :986, :998`** | `always breaks` ×3 | **CONSIDER / 7.** `process_break_exits`, `process_continue_exits` and `process_return_exits` each declare that `for block in self.nearest_blocks():` **always** hits its `break` — i.e. some enclosing block always claims the exit. `process_raise_exits` (`:990-994`) is the identical shape and carries **no pragma**. Either the fourth is missing a pragma (cosmetic) or the raise path genuinely *can* exhaust the block stack — in which case the arc is dropped silently and coverage.py reports wrong branch data with no error. The guarded-twin asymmetry is right there in four consecutive functions. No test asserts what happens when `nearest_blocks()` is exhausted for any of the four. |
| `coverage/control.py:761-762` | `not covered` ×2 | **CONSIDER / 6.** The SIGTERM handler's re-raise: `signal.signal(SIGTERM, self._old_sigterm)` then `os.kill(os.getpid(), SIGTERM)` — the lines that actually terminate the process after data is saved. Self-excluded and untested; if wrong, `coverage run` swallows SIGTERM. `test_process.py::test_save_signal_usr1` covers USR1, not the terminate path. |
| `coverage/parser.py:925` | `only failure` | CONSIDER / 5. `raise RuntimeError(f"*** Unhandled: {node}")` — the catch-all for an AST node type the handler table doesn't know. Declared "only happens if tests fail", i.e. an assertion that the node table is complete. This is the line a new Python grammar feature trips. Relevant because commit `cb7c59aeb` narrowed the AST walk (§3). |
| `coverage/misc.py:273`, `coverage/files.py:375` | `always breaks` | ACCEPTABLE-to-CONSIDER. `next(g for g in match.group(*dollar_groups) if g)` raises `StopIteration` if the assumption fails. Local, and the regex guarantees a group. |
| `coverage/core.py:34`, `html.py:192`, `collector.py:425`, `control.py:794`, `report_core.py:68` | `part covered`/`part started` | ACCEPTABLE. Partial-branch declarations, each with a stated reason. |
| `coverage/debug.py:123` | `never called` | ACCEPTABLE. A `yield` that exists to satisfy the type checker. |
| `coverage/annotate.py:33` | `#pragma: no cover` | **Not an exclusion.** It is inside the docstring's example of annotate output. The package contains **zero** real `pragma: no cover` — coverage.py does not use its own default marker on itself. Worth stating so nobody reports it. |

And one project-wide exclusion worth naming: `metacov.ini` `exclude_lines` contains **`def __repr__`**, which
excludes all **11** `__repr__` methods in `coverage/*.py` from self-measurement — including
`Coverage.__repr__` (`control.py:352`), which was added by commit `4143e7a73` with no test (§3). A
`__repr__` that raises on a partially-initialised object would be caught by neither the tests nor the
coverage report. **CONSIDER / rating 5.**

### NOVEL — metacov structurally cannot measure the trace-function machinery

Four tests are `@pytest.mark.skipif(env.METACOV, …)` — `test_timid`, `test_warning_trace_function_changed`,
`test_warnings_trace_function_changed_with_threads`, `test_subprocess_gets_nonfile_config` — because
coverage cannot measure itself while a test changes the trace function. `metacov.ini` then excludes those
test lines (`pytest.mark.skipif\(env.METACOV`, `if(.* and)? not env.METACOV:`) so the 100%-test-files gate
stays green. The consequence is on the *product* side: the `timid=True` path and the
trace-function-changed warning paths in `collector.py`/`core.py`/`control.py` are **never executed during
the metacov run at all**. The published self-coverage number is therefore not a complete self-audit — it
is structurally blind to exactly the code that manipulates the trace function, which is the code most
likely to break. **POLICY / rating 5** — inherent, but it should be stated next to the badge.

---

## 3. Commits that added code without tests (shape `coverage-claiming-commit-that-reduced-coverage`)

**Calibration first.** Over the last 600 non-merge commits (2025-07-10 → 2026-07-26), **187** touch
`coverage/*.py` excluding `version.py`. Of those, **97 (51.9%) also touch `tests/`** and **90 (48.1%) do
not.** So a no-test commit is not an anomaly here — it is a coin flip. Most of the 90 are genuinely
test-neutral (formatting sweeps, `ruff --fix`, docstring edits). After reading each diff and discarding
those, the following ship real behaviour with no test.

| # | Commit | Date | Module(s) | The behaviour that shipped untested | Rating |
|---|---|---|---|---|---|
| 1 | `6af8a5d13` **feat: patch=fork** | 2025-08-12 | `patch.py`, `control.py` | A whole new config value. `_patch_fork()` registers `os.register_at_fork(after_in_child=_after_fork_in_child)`; `_after_fork_in_child()` stops the inherited `Coverage` and calls `process_startup(force=True)`; `process_startup` gained a `force` keyword that bypasses the "already auto-started" guard. **Grep of all 42 test files: no test anywhere sets `patch = fork`.** `test_process.py::test_fork` tests forking *without* the patch; `test_os_exit` tests `patch = _exit`. The Windows rejection branch (`raise CoverageException("patch=fork isn't supported yet on Windows.")`) is also untested. This is the feature catalogued as **CRF-COVPY-0002 [FIX]** — *"patch = fork makes coverage worse than not patching at all"*. The untested feature is the broken one. | **10** |
| 2 | `8cd392e3b` **fix: snapshot data in Collector.flush_data to avoid threading race (#2165)** | 2026-05-09 | `collector.py` | A 40-line commit message describing a reproducible `RuntimeError: Set changed size during iteration` under `dynamic_context = test_function`, fixed by `.copy()` snapshots — and **zero** test files touched. No regression test for the race it fixes. The catalogued **CRF-COVPY-0012 [FIX]** says the very next statement in the same function (`file_tracers = {...}`, `collector.py:495`) did **not** get the same treatment. A regression test would have had to enumerate what `flush_data` iterates, and would plausibly have caught the miss. | **10** |
| 3 | `974486053` **perf: cache file reporters and analyses for the whole reporting phase (#2215)** | 2026-07-06 | `control.py` | Replaced `lru_cache(maxsize=1)` with two per-instance dicts (`_analysis_cache`, `_file_reporter_cache`) plus manual invalidation at **four** lifecycle points (`_init_data`/load, `erase`, `combine`, flush). Cache-invalidation logic, no tests. A missed invalidation is silent: coverage reports stale `Analysis` objects and the numbers are simply wrong. Sibling shape to catalogued **CRF-COVPY-0011** (stale `_file_map` in `sqldata`). | **9** |
| 4 | `4b0fc8571` **fix: find a usable sys.monitoring toolid instead of assuming COVERAGE_ID is available. #2187** | 2026-06-08 | `sysmon.py`, `core.py`, `control.py` | New `while self.myid <= 5: try use_tool_id … except ValueError: self.myid += 1` search loop with a `while…else: raise RuntimeError("No sys.monitoring tool id is available")`. No test exhausts tool ids; no test hits the `ValueError` retry; no test hits the `RuntimeError`. That `RuntimeError` is catalogued as **CRF-COVPY-0042 [CONSIDER]** (escapes the project exception hierarchy). The same commit removed `Core`'s `metacov` parameter and the `tool_id = 3 if metacov else 1` special case — i.e. it changed how coverage-measuring-coverage negotiates tool ids — with no test. `sysmon.py` is the default core on 3.14+. | **9** |
| 5 | `cb7c59aeb` **perf: only walk statement nodes when scanning for defs and classes (#2216)** | 2026-07-06 | `parser.py` | New `walk_statement_nodes()` replaces `ast.walk` in both `_raw_parse` and `AstArcAnalyzer.analyze`, descending only into `(ast.stmt, ast.excepthandler, ast.match_case)`; also replaced per-node `getattr` dispatch with `isinstance`. A narrowing of the core AST traversal in the largest module (599 statements), no tests. This project already carries **CRF-COVPY-0034 [FIX]** — *"Region analysis never walks orelse, handlers or finalbody"* — the exact same partial-traversal shape. The reasoning ("statements can never appear inside expression subtrees") is correct for today's grammar; the risk is that it is a *silent* failure mode (a missed `def` is a missing region, not an error) in code with no traversal-completeness test. | **8** |
| 6 | `81e01895d` **perf: move the core of the combine logic to be entirely in SQL (#2033)** | 2025-08-19 | `sqldata.py` | +128 lines rewriting `update()`/combine into SQL. No test change. `sqldata.py` hosts six catalogued findings, three of them in combine (**0006** update never DETACHes, **0030** lines-vs-arcs derived from two sources, **0011** stale `_file_map`). | **8** |
| 7 | `d8f88c765` **refactor: use SQLite URIs for in-memory databases (#2034)** | 2025-08-17 | `sqldata.py`, `sqlitedb.py` | Changed how in-memory DBs are opened, no test change. **CRF-COVPY-0001 [FIX]** (`_reap_dead_thread_dbs` destroys the in-memory database) and **0006** are both in-memory-DB defects. | **7** |
| 8 | `0d5a112fc` **perf: bulk narrowing to avoid N**2. #2048** | 2025-09-17 | `html.py`, `jsonreport.py`, `lcovreport.py`, `results.py` | +79 net across **four** report backends at once, no test change. The four-backend blast radius is the same surface as **CRF-COVPY-0010/0043** (`one-concern-implemented-per-backend`). | **7** |
| 9 | `a7224af73` **perf: pre-compute the mapping between other_db.context and main.context** | 2025-08-24 | `sqldata.py` | A precomputed identity mapping across two databases during combine, no test. Sibling shape of **CRF-COVPY-0011** (`identity-key-reallocated-under-a-cached-index`). | **7** |
| 10 | `36a14a02f` **perf: use per-instance caches in PythonParser (#2214)** | 2026-07-06 | `parser.py` | Per-instance caches in the parser, no test. Same untested-cache-invalidation shape as #3, landed the same day. | **6** |
| 11 | `322146a93` **debug: --debug=core** | 2025-11-05 | `control.py`, `core.py` | A new user-visible `--debug` option, no test. `test_debug.py` has 34 tests and tests other `--debug` options. | **5** |
| 12 | `f36248d7b` **fix: don't emit 'Couldn't import C tracer' warning for 3.13t (#2203)** | 2026-06-23 | `env.py` | A version-gated warning suppression, no test. Warning-suppression bugs are silent by construction. | **5** |

**Pragma-with-new-code:** no commit in the window added a `no cover`-family pragma to code it introduced in
the same commit. The self-exclusions in §2 are all long-standing. The related pattern that *does* occur is
#11's `Coverage.__repr__` (commit `4143e7a73`, +11, no test), which lands pre-excluded by the standing
`def __repr__` rule in `metacov.ini`.

**Systemic root, not 12 findings.** The pattern is: **performance and infrastructure work is exempt from
the project's test norm, and it is exactly where the catalogued defects cluster.** Seven of the twelve are
`perf:`/`refactor:`, four land in the two modules that already have the thinnest tests (`collector.py`,
`sysmon.py`) or the one with the most findings (`sqldata.py`). A single policy change — *a `perf:` or
`refactor:` PR touching `coverage/*.py` must either add a test or state in the PR why the existing tests
already pin the behaviour* — addresses all twelve.

---

## 4. The 13 (really 42, really 67) skipped tests

The reported 13 is a subset artifact (§0 Defect C). The real inventory across all of `tests/`:

- **58** `@pytest.mark.skipif(...)`
- **1** `@pytest.mark.skip(...)` — unconditional
- **8** in-body `pytest.skip(...)`
- **0** `xfail`

The 58 skipifs are almost entirely legitimate and *not* permanent: 12 are Windows-only / non-Windows, 8 are
Python-version gates, 8 are core gates (`testenv.C_TRACER` / `SYS_MON` / `DYN_CONTEXTS` / `PLUGINS`), 2 are
PyPy, 4 are `env.METACOV`. Crucially, **tox runs the suite three times per Python** (`igor.py
test_with_core ctrace / pytrace / sysmon`) across 10 Pythons × 3 OSes, so every core-gated and
platform-gated skip runs in *some* matrix cell. And the second CI gate — `lab/goals.py --file 100
"tests/test_*.py"` over the **combined** multi-cell data — mechanically fails if any test function's body
is never executed anywhere. **The project has a working detector for permanently-skipped tests.**

### NOVEL — the one skip form the detector cannot see is the unconditional one

`metacov.ini` `exclude_lines` contains `@pytest.mark.skip\(`. coverage.py excludes the whole decorated
function when an exclusion matches a decorator line. So an unconditionally-skipped test is **removed from
the denominator** of the very gate that would otherwise catch it. Two consequences, both confirmed live:

**S1 — `tests/test_concurrency.py:290` `test_bug_330` — permanent, invisible. [catalogued CRF-COVPY-0048]**
```python
@pytest.mark.skip(reason="We don't test eventlet; don't know how to rewrite this test.")
def test_bug_330(self) -> None:
```
The only `@pytest.mark.skip` in the suite. Cannot run in any configuration; excluded from metacov by the
rule above, so the 100% gate never notices. The comment above it says the C code it guards *"doesn't seem
particular to eventlet"* — i.e. a regression test for live `tracer.c` behaviour that has been switched off
indefinitely.

**S2 — `tests/test_oddball.py:256-259` `test_dropping_none` — belt, braces, and a pragma. [catalogued CRF-COVPY-0048]**
```python
@pytest.mark.skipif(not testenv.C_TRACER, reason="Only the C tracer has refcounting issues")
def test_dropping_none(self) -> None:  # pragma: not covered
    # TODO: Mark this so it will only be run sometimes.
    pytest.skip("This is too expensive for now (30s)")
```
Three independent suppressions stacked: a skipif, an unconditional in-body `pytest.skip` as the **first
statement**, and a `# pragma: not covered` on the `def` line. The in-body skip makes it unrunnable in
*every* matrix cell; the pragma hides that from the 100% gate. The next line even carries
`# type: ignore[unreachable]` — mypy knows it is dead. This is a `None`-refcount regression test for the C
tracer that has been fully neutralised, and the mechanism that would report it has been individually
disabled. **FIX / rating 7** to either delete it or wire it to an opt-in marker as its own TODO asks.

Everything else checks out. The other 7 in-body `pytest.skip()` calls are all conditional on a runtime fact
(`env.WINDOWS`, `gevent is None`, `start_method not in multiprocessing.get_all_start_methods()`, a
`cant_trace_msg` the test just asserted on) and run in the complementary matrix cells. `MemoryLeakTest`'s
two tests are `skipif(not testenv.C_TRACER)` and run in the ctrace pass.

Also confirmed still present: **CRF-COVPY-0045** — `tests/test_concurrency.py:635`
`test_thread_safe_save_data`, a module-level regression test for issue #581 whose body is a stress loop
with no assertion about the thing it regresses.

---

## 5. Additional novel coverage gaps found by cross-referencing catalogued findings

These are structural test-suite gaps, not re-litigations. Each explains *why* a catalogued finding survived.

**N1 — the config suite tests `$VAR` substitution and plugin options as disjoint axes and never crosses
them. CONSIDER / rating 6.**
`tests/test_config.py` has an INI env-var test (`:313-335`) and a TOML env-var test (`:336-370`); both
exercise `$VAR` only in `[run]` and `[report]` options. It also has plugin-option tests (`:98-111` TOML,
`:746/:816-820` INI) that use only **literal** values (`hello = "world"`, `names = Jane/John/Jenny`). No
test anywhere puts a `$VAR` inside a plugin-options section, for either backend. That is exactly the
uncovered cell that lets **CRF-COVPY-0029** (*"$VAR substitution applies to plugin options in INI but not
TOML"*) exist. *Fix:* one parametrized test over {INI, TOML} × {core option, plugin option} × {literal,
`$VAR`} — four new cells, and it closes 0029 and pins 0028's boundary at the same time.
*Cross-check for whoever owns 0028:* a TOML test with a **dotted** plugin section
(`[tool.coverage.plugins.a_plugin]` → `get_plugin_options("plugins.a_plugin")`) already exists and passes
at `test_config.py:98-111`, so 0028's failing input must be narrower than "any dot". No test distinguishes
the two cases — that distinction is the missing coverage.

**N2 — `process_raise_exits` is the un-pragma'd twin of three pragma'd siblings, and none of the four has a
block-stack-exhaustion test. CONSIDER / rating 6.** See §2, `parser.py:980-998`.

**N3 — the report backends have six test files and no cross-backend parity test. CONSIDER / rating 6.**
`test_report.py` (56) + `test_report_common.py` (14) + `test_html.py` (62) + `test_xml.py` (29) +
`test_lcov.py` (21) + `test_json.py` (5) + `test_annotate.py` (5) — 192 tests, each asserting one
backend's output in isolation. Three catalogued findings are *cross-backend disagreements*
(**0010** `[report] contexts` silently ignored by xml/lcov/annotate; **0032** two backends claim 100% on
zero statements; **0043** skip-flag and region support differ across six backends). A per-backend test can
never see a cross-backend divergence. *Fix:* one parametrized fixture that runs the same measured project
through all six backends and asserts the *same* totals, the same context handling, and the same
skip-flag behaviour. `test_report_common.py` (14 tests) is the existing seam to extend — it is the
guarded twin of this idea, already in the codebase, just under-used.

**N4 — `test_json.py` has 5 tests for an 86-statement public output format. CONSIDER / rating 5.**
Lowest absolute test count of any report backend (`test_lcov.py` has 21 for 95 statements,
`test_xml.py` 29 for 166). The JSON report is a documented, consumed API surface — `lab/goals.py`, the
project's own CI gate, parses it.

---

## Recommendations, by effort:impact

1. **Write `tests/test_collector.py` for real** (1 test → ~15). `Collector` is 235 statements, 5 catalogued
   findings, and the module where the last two concurrency fixes landed with no regression test. Highest
   ratio in the project.
2. **Add direct `SysMonitor` callback tests to `test_sysmon.py`.** It is the default core on 3.14+, has 6
   tests, all about a helper function, and 6 catalogued findings.
3. **Split the CI coverage gate:** `--group 90 "coverage/*.py"` and `--group 100 "tests/test_*.py"` as
   separate invocations. One line of YAML; recovers 14 points of real floor on the product code.
4. **Policy: a `perf:`/`refactor:` PR touching `coverage/*.py` must add a test or justify why not.** Seven
   of the twelve untested behaviour commits are perf/refactor, and they cluster in the highest-finding
   modules.
5. **Test `patch = fork` and `patch = execv`.** `patch = _exit` has a test; its two siblings do not, and one
   of them is a catalogued FIX.
6. **Re-examine the three `cant happen` / one whole-file pragma** (`collector.py:428,432`; `pth_file.py:5`).
   The `collector.py` justification was disproved by `8cd392e3b`; the `pth_file.py` exclusion hides a
   catalogued FIX.
7. **Add `tests/test_inorout.py`** exercising `should_trace` and `find_possibly_unexecuted_files` over the
   same inputs (closes the structural gap behind 0037).
8. **Cross-backend report parity test** (N3) — one parametrized test closes the seam behind three findings.
9. **Resolve the two permanently-skipped tests** (`test_bug_330`, `test_dropping_none`): delete, or wire to
   an opt-in marker and remove the pragma that hides them from the gate.
10. **Fix `correlate_tests.py`** before the next run: restrict source discovery to the package dir, restrict
    the test pool to `test_*.py`, forbid cross-directory basename matches, and compute the summary from all
    test files rather than only matched ones.
