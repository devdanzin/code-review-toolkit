# coverage.py — full-suite exploration (benchmark v3)

| | |
|---|---|
| **Target** | `~/projects/coveragepy/coverage` (44 files, ~16.4k lines) @ `d37859cdac002b49d8fe7aff8e7d9c675f70b0a7` (2026-07-26) |
| **Tests** | `~/projects/coveragepy/tests` (42 `test_*.py`, 1173 test functions) |
| **Scripts** | all 11 runnable (`scan_common.py` is a library; `build_informed_briefing.py` needs a prior run) |
| **Agents** | 16 dispatched |
| **Why this target** | First large **non-stdlib** benchmark. idlelib and `_pyrepl` are both CPython packages; coverage.py has a plugin API, three parallel tracer backends, a SQLite layer, and its own docs and CI — surface the previous two could not exercise. |

**Standing caveat:** nothing here has been reported upstream, and everything needs re-verification against
current `main` plus a tracker search before it goes anywhere. coverage.py is actively maintained and
several of these may be known.

---

## Part 1 — Toolkit bugs this run exposed

The headline result. coverage.py found **10 real defects in the toolkit**, six of them in one script.

### `find_dead_symbols` scored 0 of 51

Every high-confidence item was a false positive. Two agents reached this independently. Five causes:

| Cause | Share |
|---|---|
| `from __future__ import annotations` counted as an unused import — a **compiler directive** that binds no name, so a reference scanner always calls it unused | **42 of 42** unused imports |
| References scoped to the reviewed package, so helpers used only by `tests/`, an entry point in `setup.py`, or an API shown in `doc/` all read as dead | **9 of 9** unreferenced symbols |
| `__main__.py` flagged as an orphan — being unimported is what it is *for* | 1 of 2 orphans |
| A file read as **text** rather than imported (`pth_file.py`, embedded into the installed `.pth` by `setup.py`) flagged as an orphan | 1 of 2 orphans |
| Prose comments containing code examples read as commented-out code | **6 of 6** blocks |

After the fixes: **0 high-confidence items**, with no regression on idlelib or `_pyrepl`.

### `analyze_imports` — four bugs, two sharing a root cause

1. **`fan_in` prefix match** let a package `__init__` absorb every import of every module inside it —
   **209 reported for `coverage/__init__.py` vs 24 true**, in a 44-file package. This is the same
   prefix fallback `detect_cycles` dropped after the `_pyrepl` run; the fix was never propagated to its
   sibling, which is exactly the shape the toolkit's own `git-history-analyzer` hunts.
2. **Every reported cycle carried a duplicated node** — the reconstruction seeded the path with the
   closing node and then walked back onto it, so a 2-cycle printed as three. **All 26** affected.
3. **`TYPE_CHECKING`-only imports counted as runtime cycles.** The guard exists precisely to break the
   cycle. 20 such edges. `detect_cycles` already parsed the flag and ignored it.
4. **`from pkg import submodule` attributed to the package facade.** That statement binds the
   *submodule*; attributing it to `__init__.py` manufactures a cycle through the facade. **16 of the 20**
   remaining cycles were this one idiom (`from coverage import env`, at 12+ sites).

Cycles: **26 → 20 → 9**. Bugs 1 and 4 share a root cause worth naming — **the index was incomplete, not
the matching rule.** A leaf module with no imports of its own never appears as a graph key, so building
the module→file map from keys alone leaves it unresolvable and the bare-package fallback blames the
facade. The earlier `_pyrepl` fix treated the symptom.

**The strongest validation signal of the run:** after the fix the scanner reports 9 cycles, and those 9
are *exactly* the ones the architecture agent identified as real by reading the code —
`config↔tomlconfig`, `parser↔python`, `control↔patch`, and the `jsonreport`/`xmlreport`
`from coverage import __version__` pair. Two independent methods, same answer.

### `correlate_tests` — 0% for any package whose tests live in a sibling tree

**Second occurrence** (`_pyrepl` was the first, and was recorded as a known gap rather than fixed). It
reads as a finding about the project when it is an artefact of the scope.

| target | before | after | found in |
|---|---|---|---|
| `coverage/` | 0.0% | **61.4%** | `tests/` |
| `Lib/_pyrepl` | 0.0% | **36.0%** | `Lib/test/test_pyrepl` |
| `Lib/idlelib` | 84.8% | 84.8% | unchanged — no regression |

### Calibration insight, not a code bug: `type: ignore` age is not staleness

`collect_debt` reported "36 stale, 12 ancient" of coverage.py's 47 suppressions. But `pyproject.toml`
sets `warn_unused_ignores = true` and `mypy` is clean — so **none is stale, whatever its commit age**.
Age measures commit date; `warn_unused_ignores` is the actual oracle. Two agents reached this
independently. Check for that setting before reporting ignore-debt as actionable.

### Known remaining gaps

- `correlate_tests` counts fixture packages under `tests/modules/` as test files and misses
  module-level test functions: it reported 101 files / 601 methods against an actual 42 / 1173.
- No dead-**constant** analysis. `env.py`'s constants are live by `globals()` reflection via
  `debug_info()`, so any future constant scan must whitelist that module.

---

## Part 2 — Target findings

Marks: `reproduced` = demonstrated running · `confirmed` = verified by reading code and tests ·
`candidate` = pattern match only.

### Wrong numbers that look right

The failure mode that matters for a measurement tool. A crash is benign by comparison — the user sees it.

| # | Location | Consequence | Status |
|---|---|---|---|
| 1 | `control.py:1499-1503` | **`patch = fork` makes coverage worse than not patching.** `process_startup` returns `None` when neither env var is set, and nothing checks; the child stops the inherited collector and never restarts. Same program: no patch → **100%**, `patch = fork` → **67%**, `fork, subprocess` → 87%. Exit 0, no warning. `doc/config.rst:495` promises the opposite. | reproduced |
| 2 | `results.py:502` vs `:411-418` | **`--fail-under` rounds toward 100 while the printed total rounds away.** `coverage report --fail-under=99.9` **passes** on a run whose own report prints `99%`. `display_covered` exists to clamp away from 100; `should_fail_under` does a plain `round()`. | reproduced |
| 3 | `ctracer/tracer.c:1055` | **CTracer never warns on a `sys.settrace` hijack** — data silently truncated on the default core (≤3.13). `PyTracer` raises "Trace function changed, data is likely wrong"; `CTracer` declares the same `warn` member and never invokes it. The warning fires only in the backend you would already have had to choose. | reproduced |
| 4 | `collector.py:334`, `core.py:120` | **The backends disagree about which threads exist.** A pool created before `coverage.start()`: **ctrace 20%, sysmon 60%** for identical code. Upgrading 3.13→3.14 changes numbers on any threaded codebase, unannounced. | reproduced |
| 5 | `xmlreport.py:33-38` | **XML publishes 99.997% as `line-rate="1"`.** `.4g` rounds up; a 30k-statement repo one line short reports as 100% to Sonar/Jenkins/Azure, while `lines-valid`/`lines-covered` in the same element disagree. Bypasses `display_covered`, whose docstring promises the opposite. | reproduced |
| 6 | `files.py:133-139` | **A transient `listdir` failure is cached for the process lifetime**, permanently disabling path case-correction. Two spellings of one file then get two rows with split coverage. | confirmed |
| 7 | `report_core.py:105-115` | An unparseable non-`.py` file leaves **both numerator and denominator**, inflating TOTAL. `ignore_errors` is not consulted. | reproduced |
| 8 | `bytecode.py:41` | A user-written `__annotate__` has its whole body dropped from `statements`, inflating the file's percentage. The filter matches `co_name` and cannot tell a compiler-generated PEP 649 block from a user method. | reproduced |
| 9 | `regions.py:53-55` | Region analysis never walks `orelse`/`handlers`/`finalbody`: **4 of 6** functions invisible in a fixture. LCOV `FNF`/`FNH` wrong. | reproduced |

### Data loss

| # | Location | Consequence | Status |
|---|---|---|---|
| 10 | `sqldata.py:744-884` | **`update()` never detaches**, so `Coverage(data_file=None).combine()` destroys the first data file and aborts. `combine_parallel_data` deletes each file after merging, so the data is permanently gone while the combine produced nothing. | reproduced |
| 11 | `patch.py:56-57,74-75` | `contextlib.suppress(Exception)` wraps `cov.save()` — the only call that persists the run — then `os._exit`/`execv`. Any `DataError` costs the whole process's measurement, silently, exit 0. | reproduced |
| 12 | `sqlitedb.py:102-112` | `__exit__` skips `close()` on a commit failure: `nest` already decremented to 0, connection still open, next `__enter__` reuses the stale connection with a failed transaction. | reproduced |
| 13 | `pth_file.py:11-16` | Bare `except:` around `import coverage` suppresses the **only** diagnostic — `site.addpackage` already contains the blast radius and prints a traceback without breaking startup. In a broken-install environment every subprocess contributes zero data. Also eats `KeyboardInterrupt`/`SystemExit`. | reproduced |

### Silently ignored configuration

| # | Location | Consequence | Status |
|---|---|---|---|
| 14 | `xmlreport.py`, `lcovreport.py`, `annotate.py` | **`[report] contexts` silently ignored** by three of six backends — 75% in report/json/html vs 100% in xml/lcov. Worse, `set_query_contexts` mutates `CoverageData` and is never reset, so a prior json call **filters a later xml call**: XML output depends on what ran before it. | reproduced |
| 15 | `python.py:155-161` vs `inorout.py:401` | **`relative_files = True` reports 0%** for any file reached through a symlink — write path canonicalizes, read path deliberately skips it. Bare `coverage report` is unaffected, which is why the suite misses it. | reproduced |
| 16 | `files.py:211-215` | **`omit`/`include` patterns starting with `*` are not symlink-resolved** — `omit=src/*` works, `omit=*/src/*` does not. The wildcard form is the one the docs encourage. Vendored code gets measured. | reproduced |
| 17 | `config.py:494-529` | `set_option()` bypasses `post_process()`: `exclude_also` never merged, `patch = subprocess` does not imply `parallel`, bogus `concurrency` accepted silently. Documented public API claiming parity with the config file. | reproduced |
| 18 | `tomlconfig.py:91` | A plugin whose name contains a dot cannot be configured from TOML — `split(".")` treats the plugin name as table nesting. INI works. Silent. | reproduced |
| 19 | `tomlconfig.py:146-148` | `$VAR` substitution applies to plugin options in INI but not TOML. Migrating `.coveragerc` → `pyproject.toml` silently changes plugin behaviour. | reproduced |
| 20 | `config.py:55-59`, `:319` | An unreadable config file reads as "no config" — `source`, `omit`, `include`, `parallel`, `patch` all revert to defaults, exit 0. The explicitly-named path *does* raise. | confirmed |

### Type and API surface

| # | Location | Consequence | Status |
|---|---|---|---|
| 21 | `html.py:42` | `from coverage.plugins import FileReporter` — **module does not exist** (it is `coverage.plugin`). Under `TYPE_CHECKING` so no runtime error, and `ignore_missing_imports` swallows it, so **3 annotations silently became `Any`**. Proven with `--disallow-any-unimported`. One-word fix. | reproduced |
| 22 | `plugin_support.py:243` | `DebugFileReporterWrapper` mirrors **10 of 14** `FileReporter` methods. The four missing ones inherit the base's no-op defaults instead of delegating, so **setting `debug = plugin` silently changes report content** — regions vanish, arc descriptions degrade. Found independently by two agents. | confirmed |
| 23 | `report_core.py:110` | `should_be_python()` exists only on `PythonFileReporter`; a third-party `FileReporter` raising the public `NotPython` gets `AttributeError`. The `type: ignore` is the wrong resolution — mypy was right. | confirmed |
| 24 | `plugin.py:610-614` | `__eq__`/`__lt__` return `False` rather than `NotImplemented` for foreign types; with `@total_ordering` this makes `fr > 5` → `True` and `sorted([fr, 5])` succeed. | reproduced |

### Test-suite integrity

| # | Location | Consequence | Status |
|---|---|---|---|
| 25 | `env.py:118`, `igor.py:55-96`, `conftest.py:74` | **On Python 3.12/3.13 the nominal "sysmon" test leg silently runs PyTracer.** All 184 arcs/coverage tests use `branch=True`; sysmon can't measure branches below 3.14, so the core falls back — and the warning that would reveal it is filtered out in `conftest.py`. The three-way sweep is a two-way sweep on those versions. | confirmed |
| 26 | — | **No in-process backend conformance suite.** Cores are frozen once per process from `COVERAGE_CORE`; the sweep is three separate `pytest.main()` runs via tox, and `COVERAGE_CORE` appears in **no CI workflow file**. No test instantiates `PyTracer` or `CTracer`, or compares two cores in one process. | confirmed |
| 27 | `pytracer.py`, `inorout.py` | The **highest-complexity function in the project** (`PyTracer._trace`, score 10.0) has no dedicated test file — only string comparisons of the core name. `inorout.py` (654 lines deciding what gets measured at all) has one reference in the whole suite. | confirmed |

### Docs

`--rcfile` help text omits `.coveragerc.toml`, and because it is cog-inlined the wrong list is checked
into **all 10** `doc/commands/cmd_*.rst` — re-running cog will not fix it. `[report] partial_branches_always`
and `[report] contexts` are implemented and tested but documented nowhere. Otherwise the docs are in
unusually good shape: **50/50 config options resolve, 0 phantom options, 52/52 defaults match, 0 broken
Sphinx refs, 10/10 cog blocks byte-identical.**

---

## Part 3 — What was NOT found

Recorded so it is not re-hunted.

- **The arc-normalisation layer is sound.** Across 47 stdlib modules under branch coverage, `ctrace` and
  `pytrace` produce byte-identical counts and `sysmon` differs on exactly one file (a `cover_pylib`
  artefact). Their raw arc representations are radically different — `ctrace` records real `(prev, this)`
  arcs, `sysmon` records `(l, l)` self-arcs plus resolved BRANCH events — yet every report agreed on
  generators, coroutines, comprehensions, `except*`, lambdas, `match`, `while/else`, `try/finally`, and
  exception exits. Mixed-core `combine` is also safe. **Do not go looking for bugs there.**
- **The codebase is consistent.** Clean against `ruff format`, `pylint`, and `mypy --strict`; Apache
  header 44/44; `from __future__ import annotations` 43/44 (the exception self-documents). No bypass of
  `files.py` canonicalization for source paths. Two bare `except:`, both examined.
- **The annotations are load-bearing.** 99.3% coverage, and `mypy` clean at 3.14. All 47 `type: ignore`
  are needed; none of the 40 `Any`s is harmful on the public boundary.
- **coverage.py is not complex.** Avg score 1.3; 18 of 698 functions score ≥5. `PyTracer._trace` at 10.0
  is **inherent** — the code itself documents caching a bound method and skipping a re-check for
  per-event cost. Do not refactor it.
- **None of the 13 skipped tests is always-true.** All are OS-, version-, or core-conditional and each
  runs in some CI cell.
- **`coverage/__init__.py` has no `__all__` and does not need one** — the `from X import Y as Y` idiom is
  the PEP 484 re-export convention and is equivalent for type checkers.

---

## Part 4 — Novel shapes proposed

Four reproduced end-to-end on coverage.py, none covered by the 40-shape catalog. Recorded in the
catalog's field structure so they can be implemented directly.

### N1 — Prefix rewrite done as a content search *(`files.py:508-509`, `:352`, `:354`, `:539`)*
- **Pattern:** a prefix rewrite expressed as `str.replace` (unbounded — hits every later occurrence)
  and/or bounded by a **greedy** quantifier (`m[0]` runs to the *last* match, swallowing intermediate
  path components), instead of a positional splice `result + path[m.end():]`. One regex does two jobs
  — "does it match?" and "how long is the prefix?" — and greedy matching is only correct for the first.
- **Guarded twin:** `relative_filename()` at `files.py:52-62` strips the same class of prefix correctly
  (`startswith` then `filename[len(RELATIVE_DIR):]`); `TreeMatcher.match` uses an explicit
  `fpath[len(p)] == os.sep` boundary. The *same* tokens are used safely by `GlobMatcher`, where only
  the boolean matters — the construct becomes a bug at exactly the one call site where length is
  load-bearing.
- **Hunt:** `.replace(` applied to regex-matched text; a leading greedy `(.*…)?` whose match *length*
  is consumed. Generic to `[paths]` root remapping, source maps, container→host path translation.
- **Caught as:** SILENT and plausible. `proj/sub/proj/mod2.py` vanishes from the report and its
  coverage is attributed to an unrelated, never-executed `proj/mod2.py`. Reproduced with **no user
  config beyond `relative_files = True`**; coverage's own `--debug=pathmap` prints the mis-mapping.
- **Differential:** invisible when the matched prefix occurs once (the ordinary unique-checkout-root
  case), and an `exists(new)` guard rejects mangled paths that don't name a real file — that
  plausibility guard is *why* it is silent rather than loud. The documented `/jenkins/build/*/src`
  idiom is safe (`*` compiles to `[^/\\]*`); `*/name` is not.

### N2 — Identity key derived from a proxy that is not a function of the artifact *(`data.py:99-129`, `sqldata.py:912-929`)*
- **Pattern:** a dedup/equality key derived from a *snapshot* or a proper subset of an artifact, while
  the consumer's contract is "equal key ⇒ identical artifact, safe to discard one". Here the hash is
  written once from a hasher fed only by some of the mutation paths, and misses both later writes and
  touched files.
- **Guarded twin:** the `else` branch of the very same function still hashes the real bytes — that was
  the whole implementation before the perf commit that introduced the proxy.
- **Hunt:** for any cached identity token, enumerate every path that mutates the artifact without
  updating the token.
- **Caught as:** SILENT and DESTRUCTIVE — the "duplicate" is deleted. Two independent triggers
  reproduced; one yields a report of **100%** with a never-executed 4-statement file absent entirely.
  Which file survives is decided by `sorted()` over names containing a random token, so **the same
  suite reports different totals run to run**.
- **Differential:** correct whenever the artifact is written once over a complete dataset. The existing
  test only feeds *identical* files, so it structurally cannot see this.

### N3 — One predicate, two implementations: gate vs enumerator *(`inorout.py:445-507` vs `:599-621`)*
- **Pattern:** a predicate implemented once to *gate* an action and again to *enumerate* "everything
  the action could have applied to", with no shared code. Every rule present only in the gate becomes
  a phantom entry in the enumeration.
- **Guarded twin:** in this very codebase one rule of eight (`--omit`) *is* threaded through both, with
  a comment stating the invariant: *"Turns out this file was omitted, so don't pull it back in as
  un-executed."* The project states the rule and then implements it once.
- **Hunt:** diff the two rule sets. Two of eight were missing here.
- **Caught as:** an executed file reported at **0%**, dragging TOTAL from 100% of what was in scope
  to 11%.
- **Differential:** hidden in typical layouts by an incidental accident (directory pruning), not by the
  scope logic.

### N4 — Empty container read as "absent" via truthiness *(`pytracer.py:241-242`)*
- **Pattern:** a truthiness test standing in for an identity test (`is None`) on a value that is
  legitimately **empty-but-present**. Related to the catalogued `falsy-check-for-none-default`, but the
  subject is a *container mutated in place elsewhere*, which is what makes it reachable.
- **Guarded twin:** the C implementation re-checks the cache on every call and never disables event
  delivery; the third backend keys off a per-code-object record.
- **Hunt:** any `if not <container>:` where the container is emptied **in place** by a different
  component — a flush, a reset, a swap — rather than rebound.
- **Caught as:** line events disabled for a whole frame lifetime; a generator that gets it never
  recovers. Requires the flush and the next call to be on the *same source line*.
- **Differential:** the call site's own `line` event normally re-populates the container first, so the
  ordinary multi-line case is safe. That narrowness is why it survives the suite.

### Also proposed, agent-reproduced (not independently re-run here)
- **Stale in-memory index beside an upsert that reallocates identity** — `INSERT OR REPLACE` deletes
  the row and mints a new rowid, orphaning every child row, while a cached `_file_map` still holds the
  old id. Declared FKs are never enforced because `PRAGMA foreign_keys` is not enabled. *Guarded twin:*
  the sibling `update()` path uses `INSERT OR IGNORE` plus a re-read instead of trusting `lastrowid`.
- **The same fact derived from two sources** — one code path decides lines-vs-arcs from *table
  contents*, another from a *meta key*. They diverge in exactly one reachable state (branch mode with
  zero arc rows).
- **External registration not re-established after teardown/re-setup** — a warm cache short-circuits
  the re-registration path, so everything seen before a pause is permanently unmeasured after it.

### Refuted, recorded so they are not re-hunted
The one-shot SQL retry cannot double-apply · `journal_mode=off` does not break rollback (tested with
forced page-cache spill) · sysmon's missing yield-check in `PY_RETURN` is correct by construction
(`PY_YIELD` is a separate unregistered event) · pytrace and ctrace produced **byte-identical arc sets
across 27 adversarial control-flow cases**.

---

## Part 5 — Documentation rot

**31 verified doc/code contradictions.** The hypothesis held: coverage.py is essentially fully
documented, and every real defect is **rot, not absence**. Three patterns dominate.

### Ships to users via Sphinx autodoc

| Location | Contradiction |
|---|---|
| `control.py:197-199` | `config_file` doc names **three** candidate files; the code tries **five** and consults `$COVERAGE_RCFILE` first. Last touched 2016; `pyproject.toml` support landed 2019, `.coveragerc.toml` in 2025. `config.py:677` delegates to this same text, so the error is load-bearing twice. |
| `control.py:1149-1150` | `.. versionadded:: 7.0 — The ``format`` parameter.` **There has never been a `format` parameter** — it is `output_format`, documented correctly 34 lines above. Wrong since birth. |
| `plugin.py:537-539` | Doc says `executed_arcs` *"is a set of line number pairs"*; the signature defaults it to `None`, so a plugin author following the docstring crashes. |
| `lcovreport.py:202-203` | *"function coverage is not supported"* — 17 lines below, the same method calls `lcov_functions()`. |

### The `sys.monitoring` migration left the collector's mental model stale

Runtime-confirmed on 3.14.4: `SYSMON_DEFAULT = True`, `systrace = False`, `supports_plugins = False`.

`Collector`'s **class docstring** (`collector.py:44-53`) describes creating a tracer per thread and
installing a hook for new threads. Under the default 3.14+ core that gate is `False` and **exactly one
tracer exists for the whole process** — `sysmon.py:188` states the opposite invariant in-tree
(*"One of these will be used across threads. Be careful."*). Written 2009, 14 years before PEP 669.
Note `types.py:102` **was** updated for sysmon: the Protocol learned, the Collector didn't.

Same defect stated as universal fact at `collector.py:280-284`, `inorout.py:346`, and `control.py:182-184`
(`timid` "a slower and simpler trace function" — it now displaces `sys.monitoring`; the *CLI* help for
the same option was modernized, the docstring wasn't).

`plugin.py:60-71` never says file-tracer plugins **require the C core**, so a plugin author on 3.14
gets their file tracer silently disabled. Neither `plugin.py` nor `doc/plugins.rst` mentions cores.

### GIL justifications in a project shipping free-threaded wheels

`setup.py:75` carries `Free Threading :: 3 - Stable` and CI tests `py3{14-15}t`, but two comments
still reason from the GIL: `collector.py:453-459` (*"dict.copy() … the GIL is held for the duration"* —
conclusion probably still holds via per-object critical sections, **stated reason is false**; blame
2026-05-09, so this is *fresh* debt) and `collector.py:420-423`, where the prose justifies a
three-times retry that the `# pragma: cant happen` markers on the very next lines contradict.

### Dead cross-references — the single most productive query

Eight docstrings point at a function, attribute, or module that was renamed or deleted, up to ten years
ago: `control.py:448` (`_should_trace_internal`, no such function), `parser.py:1039` (`collect_arcs`,
deleted 2016 — and the surviving unrelated closure of that name makes it *actively* misleading),
`regions.py:84`, `data.py:144/152/155`, `types.py:41`, `execfile.py:289`, `annotate.py:57`,
`sqldata.py:39`. **A grep for "see `<name>`" plus an existence check finds all of them mechanically** —
that is a toolkit capability worth building.

### Refactor changed behaviour, docstring didn't

Four provable by calling the function: `misc.py:364` `plural()` (*"If n is 1, return thing"* →
returns `'1 item'`), `files.py:204-205` `prep_patterns()` (returns **two** entries, not a replacement),
`files.py:498-500` `PathAliases.map()` (both documented guarantees false when `relative=True`),
`patch.py:115` (*"Write .pth files"* — the `.pth` machinery was deleted 2025-11-29).

Two more on durable contracts: `sqldata.py:913` `write()` **also renames the data file**, so any cached
path is stale afterwards — undocumented in both the method and the class docstring; and
`cmdline.py:798` promises *"0 if all is well, 1 if something went wrong"* while line 954 returns
`FAIL_UNDER = 2`, which becomes the process exit status. Fourteen years of drift on the CLI's main
return contract.

### Process finding

`howto.txt:23` tells the releaser to grep for `PYVERSIONS`, but two live markers are spelled
**`PYVERSION`** singular (`execfile.py:95`, `phystokens.py:98`) and are therefore invisible to the
release checklist.

### Recorded as clean

`exceptions.py`, `numbits.py`, `disposition.py`, `plugin_support.py`, `report.py`, `jsonreport.py`,
`phystokens.py`, `bytecode.py`. Verified by execution rather than reading: the `SCHEMA` ↔
`doc/dbschema.rst` correspondence, `numbits` round-trip, `files.flat_rootname`'s SHA3 example
(recomputed exactly), `annotate.py`'s example output byte-for-byte, `results.format_lines`,
`phystokens.source_token_lines`' round-trip claim, and all 7 `:ref:` targets.

---

## Part 6 — Temporal analysis

**Seven live defects, four reproduced** — and they share one meta-shape: **a fix applied to one path and
not its sibling.** One backend but not the others; the disk path but not the in-memory path; three dicts
in a function but not the fourth. That is the toolkit's own fix-propagation shape, found in the wild.

| # | Site | Pattern | History | Status |
|---|---|---|---|---|
| 1 | `sqldata.py:390` | a lifecycle fix not carried to the in-memory path → **coverage data corruption** | `f960696b`, Jun 2026 | **reproduced** |
| 2 | `collector.py:369-370` | `resume()` installs *other threads'* tracers | `9533be81` fixed → `41a22569` reverted, never re-landed | **reproduced** |
| 3 | `sqldata.py:758`/`:881` | ATTACH never released; 2nd in-memory combine fails | `81e01895` silently un-fixed `84f70f69` | **reproduced** |
| 4 | `collector.py:495` | the 4th dict in `flush_data` never snapshotted | `08fc997b`, `8cd392e3` | confirmed |
| 5 | `sysmon.py:493` | trace-path guard catches the wrong exception set | `9f0753bd`, `e18359c8` | **reproduced** |
| 6 | `sysmon.py:410/:436/:451` | the guarded twin at `:422` proves the lookup can fail | `7ea1535f` | confirmed asymmetry |
| 7 | `sqldata.py:912-927` | `write()` lacks the `no_disk` guard its 4 siblings have | `160ad3b6` | confirmed |

**#1 is the one to fix first.** Introduced six weeks before this review. For `no_disk=True` every
per-thread `SqliteDb` shares one memory URI, so an unconditional `close(force=True)` **discards the
database**; the reconnect re-inits an empty schema while the stale path→rowid map survives. That is not
merely loss but **cross-file mis-attribution** — worker data reappears under the wrong filename. The
class docstring explicitly guarantees `add_lines` is thread-safe, and `no_disk` is public API.
**The test added by the very same commit asserts only `len(covdata._dbs) == 1`, so it passes while the
data is being destroyed.** The fd leak the fix was premised on did not reproduce (50 dead threads,
disk-backed: 0 open connections, 0 fd delta).

**#2 has been live ~11.5 months.** A fix landed, was correctly reverted for regressing the systrace
path, and **no replacement ever landed** — verified with `git log -L` over `resume()` from the revert to
HEAD: zero commits. On ctrace the thread swap is **silent**, because `CTracer` stores `warn` and never
calls it (the same root cause as target finding 3).

### Churn × complexity do NOT overlap — the useful inversion

| File | 2yr commits | 2yr fixes | Top complexity |
|---|---|---|---|
| `parser.py` | 47 | 13 | 8.0 |
| `sysmon.py` | 40 | 11 | 7.5 |
| `pytracer.py` | 12 | 2 | **10.0** |
| `templite.py` | 8 | 0 | 9.0 |

The two most complex functions are the two **least**-churned. Here high complexity marks *settled*
code — `pytracer._trace` is the frozen reference implementation of the tracer contract, while
`sysmon.py` churns to match it. The real risk zone is `parser.py` + `sysmon.py`, high on both axes, and
two of the seven findings are in `sysmon.py`. **Complexity-driven prioritisation would have pointed at
exactly the wrong files here** — worth remembering as a calibration lesson for the toolkit.

### Both git-shaped catalog shapes: absent, and that is a real negative result

- **`coverage-claiming-commit-that-reduced-coverage`** — net assertion delta scored across 3 years. Ten
  commits are negative and **every message honestly says** "remove"/"fold"/"no longer need"/
  "overtested". Zero vacuous test bodies, zero empty-iteration loops in the tree.
- **`incomplete-fix-residue-at-an-answered-todo`** — all three markers accurate and live.

Also verified clean: stale version guards (the sole guard is written as `hasattr`, so it degrades
correctly), combine schema validation (tested end-to-end with a forged schema-99 file), HTML escaping
completeness, and the `SHIPPING_WHEELS` free-threading matrix — where the expected 3.14t gap does *not*
exist, because cibuildwheel builds `cp314t` by default.

### Methodological note worth keeping

The working tree changed **twice** during this run from injected patch-tests. Reading `collector.py`
cold during that window yields a confident, **wrong** "unsnapshotted shared dict" finding — only the
history distinguishes the planted revert from the four genuine bugs. If a pipeline is being scored
against a live checkout, the checkout is not a stable baseline. Patch-tests belong on a
`git archive`/`git worktree` copy.

---

## Part 7 — Debt, and the shape that ties the run together

The marker inventory and the staged-removal backlog are **genuinely well-managed** — see Part 6's
negative results. Backend parity is not, and the governing insight is:

> **Every backend gap that someone thought about is guarded and warned. The costly ones are the gaps
> nobody wrote down.**

`sysmon.py:196` — the `# TODO: should_start_context and switch_context are unused!` marker — turns out
to be the **best-defended** gap in the codebase (`core.py:77-78` refuses sysmon when dynamic contexts
are configured; `tests/testenv.py:DYN_CONTEXTS` matches). A marker scan finds the guarded gaps and
misses every unguarded one.

### CTracer's `warn` is dead code — found independently by three agents

`warn` appears exactly **5 times** in the whole `coverage/ctracer/` tree: the struct member
(`tracer.h:22`), the `Py_XDECREF` (`tracer.c:92`), the member-table entry with
`PyDoc_STR("Function for issuing warnings.")` (`tracer.c:1055-1056`), and an unrelated comment.
**Zero call sites.** `Collector` assigns it, CTracer stores it, DECREFs it, and never calls it;
`CTracer_stop` only flips a flag where `pytracer.py:352-358` does a self-check.

Reproduced with `sys.settrace(None)` mid-run on 3.14.3 — ctrace and pytrace lose data **identically**,
only pytrace says so:

| core | result | warned |
|---|---|---|
| `ctrace` | 73%, missing 8/11/15 | **no** |
| `pytrace` | 73%, missing 8/11/15 | yes |
| `sysmon` | 100% (correct) | n/a — immune |

**Why it is worse than it looks:** on 3.14+ ctrace is the *automatic* fallback whenever sysmon is
disqualified — dynamic contexts, light-threads concurrency, or branch coverage on 3.12/3.13. Those
users land on the one core that is both displaceable and mute. `doc/messages.rst:72-79` documents
`(trace-changed)` generically, never saying it is pytrace-only. This is the same shape as the
`# TODO: warn is unused` at `sysmon.py:202` — **except nobody wrote the TODO**, so no marker scan and
no reading of `sysmon.py` could ever surface it.

### Two more sysmon-only exposures

- **`sysmon.py:213-215`** retains every code object *by design* (`"just to keep them alive so that
  id's are useful as identity"`). `tests/test_oddball.py:226-231` — the regression test for issue
  1924 — is skipped `not testenv.C_TRACER`, with the in-source admission *"sysmon explicitly holds
  onto all code objects, so this will definitely fail with sysmon."* A leak fixed for CTracer, silently
  re-accepted for the **default** core, with its own regression test switched off. Architectural
  (`id()`-as-identity), so not a quick fix — but it should be a documented limitation, not a comment in
  a skip decorator.
- **`sysmon.py:489-503`** re-opens and re-tokenizes the source **from disk at measurement time**,
  swallowing `OSError`/`NoSource` and `TokenError`/`IndentationError`/`SyntaxError` into `{}` — with
  the comment *"which might lead to slightly wrong branch coverage, but we don't have any better
  option."* **The one place a backend admits in its own comment that it may emit wrong data.** A `.py`
  edited after import yields wrong sysmon branch attribution. CTracer/PyTracer take line numbers from
  the frame and never touch disk.

### A shipped changelog entry describes behaviour the code does not have

`CHANGES.rst:447-449`, in **released 7.11.1** (2025-11-07): *"If the 'sysmon' core is explicitly
requested … but other settings conflict, **an error is now raised**. This used to produce a warning."*
The code warns and falls back (`core.py:91-95`), and `tests/test_core.py:108-114` asserts exactly that
warning. The adjacent bullet is correct.

### Over-broad test flags — muting a test instead of narrowing a condition

Three instances, all leaving the default core under-tested in the configurations most users run:

- `tests/testenv.py:40` `CAN_MEASURE_THREADS` — all three cores in fact score 13/13 on
  `--concurrency=thread`.
- `tests/test_api.py:739` skips **all** of `SwitchContextTest` on sysmon, but two of its three tests
  exercise the **manual** `Coverage.switch_context()` API, which is core-independent. The public
  `switch_context()` API is therefore untested on the default core.
- `tests/testenv.py:43` `CAN_MEASURE_BRANCHES` is a *Python-version* fact applied as a *core* fact, so
  on 3.12/3.13 with `COVERAGE_CORE=ctrace` — where CTracer measures branches fine — those tests skip
  anyway.

`core.py:83-89` also lets **`timid = True` silently discard an explicit `core =`**, checking `timid`
first with no warning, unlike every sysmon conflict.
