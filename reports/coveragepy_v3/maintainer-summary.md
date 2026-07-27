# coverage.py — review findings summary

`coverage/` at **`6b3259abb64`** (main, 2026-07-26). **74 findings** — 43 FIX, 30 CONSIDER, 1 POLICY.

Produced with [code-review-toolkit](https://github.com/devdanzin/code-review-toolkit) over two passes
(2026-07-26 and a 16-agent informed pass on 2026-07-27), drafted with AI assistance and then
re-verified by hand. **57 of 74 were reproduced against a running interpreter**; the rest were
confirmed by reading the code and its tests.

Nothing here has been filed. This is a heads-up before an umbrella issue, so you can tell me what is
wrong, what is intentional, and what is not worth the churn — I would rather cut the list than file it.

## Please read this before the table

**Prior art is not uniformly deep.** 42 findings had a per-symptom tracker search; the other 33 had
only a broad term pass, run today against a 2,235-item cache of the tracker. Those are marked
*(broad search only)* and are the ones most likely to be duplicates. Three of the 33 turned up real
prior art when looked at properly — **0032** is residue of #1470's fix, **0035** may be a duplicate of
PR #2120, **0043** was already asked for in #1878 — so the same is plausible for others.

**One finding is excluded as already filed:** the LCOV escaping bug is
[PR #2226](https://github.com/coveragepy/coveragepy/pull/2226) (rajath201, 2026-07-12). We found it
independently before spotting the PR, which is at least a vote of confidence in it.

**Severities are a reviewer's, not a maintainer's.** Several CONSIDER items are judgement calls.


## Tracer cores (17)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 4 | FIX | `sysmon.py:489-495` | SyntaxError from a bad coding cookie escapes compute_multiline_map | yes | — none found |
| 5 | FIX | `sysmon.py:335, 374-387` | Nested Coverage permanently stops measurement on the default 3.14 core | yes | — none found *(broad search only)* |
| 9 | FIX | `collector.py:334, core.py:120` | Tracer backends disagree about which threads are measured | yes | ↩︎ partially fixed |
| 12 | FIX | `collector.py:495` | file_tracers is iterated unguarded in flush_data while the C writer holds the lock | yes | ↩︎ partially fixed |
| 13 | FIX | `collector.py:369-370` | Collector.resume() installs other threads' tracers onto the calling thread | yes | ↔︎ known |
| 17 | FIX | `sysmon.py:489-503` | sysmon re-reads source from disk at measurement time and swallows tokenize errors | yes | — none found *(broad search only)* |
| 38 | FIX | `pytracer.py:241-242` | PyTracer reads an emptied set as an untraced file and disables line events for the frame | yes | — none found *(broad search only)* |
| 61 | FIX | `sysmon.py:50` | A debug env flag parsed with bare int(), so COVERAGE_SYSMON_LOG=true crashes `import coverage` | yes | ↔︎ open issue in the area |
| 22 | CONSIDER | `sysmon.py:410, :436, :451` | Three sysmon callbacks index code_infos unguarded where their sibling checks | read | — none found *(broad search only)* |
| 39 | CONSIDER | `core.py:83-89` | timid = True silently discards an explicit core = setting | yes | — none found *(broad search only)* |
| 42 | CONSIDER | `sysmon.py:253` | sysmon raises a bare RuntimeError on tool-id exhaustion with no fallback | yes | — none found *(broad search only)* |
| 44 | POLICY | `sysmon.py:213-215, :372` | sysmon retains every code object for the process lifetime | yes | ↔︎ known |
| 51 | CONSIDER | `collector.py:44-53` | Collector's class docstring is false for the default core on Python 3.14+ | read | — none found *(broad search only)* |
| 52 | CONSIDER | `collector.py:453-459, :420-423` | Two GIL justifications in a project shipping free-threaded wheels | read | — none found *(broad search only)* |
| 72 | CONSIDER | `collector.py:413` | functools.cache on a method retains every Collector for the process and never hits | read | — none found |
| 73 | CONSIDER | `pytracer.py:129` | The tracer's error path writes to a hardcoded /tmp/debug_trace.txt | read | ↩︎ residue of a merged fix |
| 74 | CONSIDER | `sysmon.py:410` | Unscoped type: ignore comments erase the machine proof of CRF-COVPY-0022 | yes | ↔︎ open issue in the area |

## Data & combine (7)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 1 | FIX | `sqldata.py:390` | _reap_dead_thread_dbs destroys the in-memory database and mis-attributes coverage | yes | — none found |
| 6 | FIX | `sqldata.py:744-884` | CoverageData.update() never DETACHes, so a second in-memory combine destroys the first data file | yes | — none found |
| 11 | FIX | `sqldata.py:468-475` | Stale _file_map plus INSERT OR REPLACE orphans every child row | yes | — none found *(broad search only)* |
| 25 | FIX | `sqlitedb.py:102-112` | SqliteDb.__exit__ skips close() on a commit failure and then reuses the stale connection | yes | — none found *(broad search only)* |
| 30 | FIX | `sqldata.py:804-809 vs :725-732` | update() derives lines-vs-arcs from table contents while the guard uses the meta key | yes | — none found *(broad search only)* |
| 36 | FIX | `data.py:99-129, sqldata.py:912-929` | The data-file hash is derived from a proxy that is not a function of the artifact | yes | — none found *(broad search only)* |
| 59 | CONSIDER | `sqldata.py:912-927` | write() lacks the no_disk guard its four siblings have | yes | — none found *(broad search only)* |

## Reporting (10)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 7 | FIX | `results.py:502` | --fail-under rounds toward 100 while the printed total rounds away from it | yes | ↩︎ partially fixed |
| 8 | FIX | `xmlreport.py:33-38` | XML line-rate publishes 99.997% as exactly 1 | yes | — none found |
| 18 | FIX | `html.py:42` | html.py imports coverage.plugins, a module that does not exist | yes | — none found |
| 20 | FIX | `report_core.py:110` | should_be_python() is called on plugin FileReporters that do not have it | yes | — none found |
| 21 | FIX | `report_core.py:105-115` | An unparseable non-.py file leaves both numerator and denominator, inflating TOTAL | yes | — none found *(broad search only)* |
| 31 | FIX | `results.py:131-140 vs :146-148, :183-197` | no_branch pragma desynchronizes the branch counters from the arc lists | yes | — none found *(broad search only)* |
| 32 | FIX | `results.py:336-340` | Zero statements: two backends claim 100% and --fail-under splits | yes | ↩︎ residue of a merged fix |
| 71 | FIX | `report_core.py:116-121` | ignore_errors drops a file from both numerator and denominator, so coverage RISES | yes | — none found |
| 62 | CONSIDER | `jsonreport.py:83` | Naive timestamps written into the versioned JSON report and the documented SQLite schema | yes | — none found |
| 69 | CONSIDER | `report.py:233-235` | --sort=branch is documented unconditionally and rejected without branch coverage | yes | — none found |

## Config & CLI (15)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 2 | FIX | `control.py:1499-1503` | patch = fork makes coverage worse than not patching at all | yes | — none found |
| 16 | FIX | `config.py:55-59, :319` | An unreadable config file reads as no config at all | yes | — none found *(broad search only)* |
| 27 | FIX | `config.py:494-529` | set_option() bypasses post_process(), silently no-opping several settings | yes | — none found |
| 28 | FIX | `tomlconfig.py:91` | A plugin whose name contains a dot cannot be configured from TOML | yes | — none found |
| 29 | FIX | `tomlconfig.py:146-148` | $VAR substitution applies to plugin options in INI but not TOML | yes | — none found |
| 63 | FIX | `control.py:495` | Every coverage.py diagnostic can be silenced by two lines in the program being measured | yes | — none found |
| 68 | FIX | `tomlconfig.py:150` | A wrong-typed TOML config value crashes with a traceback where its sibling reports cleanly | yes | — none found |
| 40 | CONSIDER | `control.py:474-499` | Six warnings carry no slug, so disable_warnings cannot reach them | yes | — none found *(broad search only)* |
| 41 | CONSIDER | `cmdline.py:953, :1188, :780` | CLI error and status messages are split across stdout and stderr | yes | ↩︎ partially fixed |
| 53 | CONSIDER | `control.py:448, parser.py:1039, regions.py:84, data.py:144/152/155, types.py:41, execfile.py:289, annotate.py:57, sqldata.py:39` | Eight docstrings cross-reference functions that were renamed or deleted | read | — none found *(broad search only)* |
| 55 | CONSIDER | `control.py:197-199, control.py:1149-1150, plugin.py:537-539, lcovreport.py:202-203` | Public API docstrings that ship to users via Sphinx are wrong | read | — none found *(broad search only)* |
| 56 | CONSIDER | `cmdline.py:299-303` | The --rcfile help text omits .coveragerc.toml, and cog has baked it into ten doc files | read | — none found |
| 57 | CONSIDER | `config.py:437, :441` | Two config options are implemented and tested but documented nowhere | read | — none found |
| 64 | CONSIDER | `control.py:654` | atexit.register(self._atexit) is never unregistered, pinning every Coverage object | yes | ↔︎ open issue in the area |
| 75 | CONSIDER | `control.py:803-848` | exclude(which=) is a closed vocabulary with no validation, unlike its seven siblings | yes | — none found |

## Paths & inclusion (16)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 14 | FIX | `python.py:155-161 vs inorout.py:401` | relative_files = True reports 0% for any file reached through a symlink | yes | ↔︎ known |
| 15 | FIX | `files.py:211-215` | omit/include patterns starting with * are not symlink-resolved | yes | — none found |
| 19 | FIX | `plugin_support.py:243-290` | DebugFileReporterWrapper mirrors 10 of 14 methods, so debug=plugin changes report content | yes | — none found |
| 24 | FIX | `patch.py:56-57, :74-75` | patch = _exit / execv discard the whole process's data with zero trace | yes | — none found *(broad search only)* |
| 26 | FIX | `pth_file.py:11-16` | The .pth bare except hides a broken install, so every subprocess contributes nothing | yes | — none found |
| 35 | FIX | `files.py:508-509, :352, :354, :539` | PathAliases rewrites a path prefix with str.replace and a greedy regex | yes | ↔︎ open issue in the area |
| 37 | FIX | `inorout.py:445-507 vs :599-621` | The should-trace gate knows eight rules; the unexecuted-file enumerator knows one | yes | — none found *(broad search only)* |
| 46 | FIX | `context.py:49, tests/testenv.py, pyproject.toml:121` | Dynamic-context detection is unguarded on the default 3.14 core | yes | — none found |
| 66 | FIX | `files.py:375` | A newline in a config glob makes coverage.py hang forever | yes | ↩︎ residue of a merged fix |
| 23 | CONSIDER | `files.py:133-139` | A transient listdir failure is cached for the process lifetime | yes | — none found *(broad search only)* |
| 47 | CONSIDER | `env.py:124 vs igor.py:247` | env.py and igor.py disagree on what METACOV means | read | — none found *(broad search only)* |
| 54 | CONSIDER | `misc.py:364, files.py:204-205, files.py:498-500, patch.py:115` | Four docstrings contradict what the function does, provable by calling it | yes | — none found *(broad search only)* |
| 58 | CONSIDER | `execfile.py:95, phystokens.py:98` | The release checklist greps for PYVERSIONS but two live markers are spelled PYVERSION | read | — none found *(broad search only)* |
| 60 | CONSIDER | `inorout.py:115-118` | find_spec failure is indistinguishable from module-not-found, and the caller's guard is dead code | read | — none found *(broad search only)* |
| 65 | CONSIDER | `files.py:35` | The system-root separator guard's only test patches the function it is asserting about | read | ↩︎ residue of a merged fix |
| 70 | CONSIDER | `multiproc.py:37` | multiproc sets one of the three warning suppressions its twin sets | read | — none found |

## Parsing (1)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 34 | FIX | `regions.py:53-55` | Region analysis never walks orelse, handlers or finalbody | yes | — none found *(broad search only)* |

## Other (8)

| # | Sev | Location | Finding | Repro | Prior art |
|---|---|---|---|---|---|
| 3 | FIX | `ctracer/tracer.c:1055` | CTracer never calls its warn member, so a settrace hijack silently truncates data | yes | — none found |
| 10 | FIX | `xmlreport.py, lcovreport.py, annotate.py` | [report] contexts is silently ignored by xml, lcov and annotate, and leaks across reports | yes | — none found |
| 33 | FIX | `bytecode.py:41` | A user-written __annotate__ has its whole body dropped from statements | yes | — none found *(broad search only)* |
| 45 | FIX | `tests/test_concurrency.py:635` | test_thread_safe_save_data has zero assertions and passes with its fix reverted | yes | ↩︎ partially fixed |
| 43 | CONSIDER | `report.py, html.py, xmlreport.py, lcovreport.py, jsonreport.py, annotate.py` | GetConsoleMode-style: skip-flag and region support differ across the six report backends | yes | ↔︎ open issue in the area |
| 48 | CONSIDER | `tests/test_oddball.py:256-259, tests/test_concurrency.py:290` | Two regression tests are switched off for every configuration | read | — none found *(broad search only)* |
| 49 | CONSIDER | `tests/testenv.py:43` | CAN_MEASURE_BRANCHES is a version fact applied as a core fact | read | — none found *(broad search only)* |
| 50 | CONSIDER | `tests/test_api.py:739` | SwitchContextTest is skipped wholesale on sysmon though two thirds of it is core-independent | read | — none found |

---

*Full write-ups, reproducers and guarded twins exist for every row; say which ones you want and I
will send those rather than all of them.*
