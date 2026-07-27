# Git history context — coverage.py (informed re-review, phase 1)

**Target** `/home/danzin/projects/coveragepy` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (`main`, 2026-07-26)
**Scope** the `coverage/` package
**History depth** full — 7500 commits, not shallow. 3283 commits have touched `coverage/`.
**Windows used** long = `--since=2021-01-01` (286 fix commits / 1015 total; conventional-commit prefixes begin in 2021), recent = last 24 months (`--since=2024-07-27`).

The pre-run `analyze_history.json` (98 commits) is a ~4-month window and is too short to rank
anything. Everything below is recomputed over the long window; the 98-commit file was used only
for cross-checking the most recent commits.

---

## 0. Re-review status — nothing has been fixed since the catalog was recorded

The catalog (`code-review-findings/coveragepy`, 60 findings) was recorded at
`d37859cdac002b49d8fe7aff8e7d9c675f70b0a7` (`main`, 2026-07-26). HEAD is `6b3259ab`. The delta is
**four commits, all CI-workflow-only**:

```
6b3259ab build: not my finest afternoon
4aa0ced2 build: get this right one of these days
aeb1922e build: oops, wrong test for target message
3afba332 build: show the text report earlier
```

`git diff d37859cd..HEAD -- coverage/` is **empty**. The reviewed package is byte-identical to the
catalog commit, so **no catalogued finding can have been fixed since recording**, and no line
number in the catalog has drifted. Agents should treat every catalogued `file:line` as exact.

The useful version of that question is *how old is the code each finding sits on*, which does
discriminate. Blaming all 58 single-line finding locations (two are multi-file) gives:

### Findings sitting on code changed in the last 90 days — re-read before trusting the catalog text

| Finding | Location | Last touched | Commit |
|---|---|---|---|
| **CRF-COVPY-0004, 0017** | `sysmon.py:489` | 2026-07-12 | `ee271ee2` perf: compute multiline maps cheaply in the sysmon core (#2220) |
| **CRF-COVPY-0058** | `execfile.py:95` | 2026-07-02 | `6f9fa1e1` fix: preserve isolated sys.path on Python 3.10 (#2211) |
| **CRF-COVPY-0001** | `sqldata.py:390` | 2026-06-20 | `f960696b` Fix: close SQLite connections from terminated threads (#2193) |
| **CRF-COVPY-0042** | `sysmon.py:253` | 2026-06-08 | `4b0fc857` fix: find a usable sys.monitoring toolid (#2187) |
| **CRF-COVPY-0052** | `collector.py:453` | 2026-05-09 | `8cd392e3` fix: snapshot data in Collector.flush_data (#2165) |

Three of these are worth calling out specifically:

- **CRF-COVPY-0001 is a live regression, not an old bug.** Blame confirms the catalog's own
  `prior_art` note: `_reap_dead_thread_dbs` was *introduced* by `f960696b` (PR #2193, fixing #2192)
  on 2026-06-20 and has stood unmodified for five weeks. The new function also contains a fresh
  `except Exception: pass` (sqldata.py, inside the reaper) — **silent-failure-hunter should look at
  that swallow directly**; it is six weeks old and was added as part of a fix.
- **CRF-COVPY-0042 is fresh code.** The bare `RuntimeError("No sys.monitoring tool id is
  available")` was written on 2026-06-08 by `4b0fc857`, in the same release cycle that `84347926`
  (2025-11-09) *removed* a hard `ConfigError` in `core.py` and replaced it with `warn(..., slug=...)
  + fallback`. The project standardised on warn-with-slug and then, seven months later, added a
  bare `RuntimeError` in the same subsystem. `84347926` is the guarded twin for CRF-COVPY-0042.
- **CRF-COVPY-0004/0017 must be re-verified against post-#2220 code.** `compute_multiline_map` was
  rewritten for performance on 2026-07-12, i.e. *after* the two exception-guard fixes discussed in
  §3 but before the catalog was recorded. The finding text may describe the pre-#2220 shape.

Conversely, **21 of the 58 findings sit on code last touched before 2023**, five of them on code
older than 2015 (`CRF-COVPY-0003` ctracer/tracer.c:1055 — 2011; `CRF-COVPY-0051` collector.py:44 —
2009; `CRF-COVPY-0015` files.py:211 — 2013; `CRF-COVPY-0053` control.py:448 — 2014;
`CRF-COVPY-0019` plugin_support.py:243 — 2015). Those are stable-by-neglect: real if the analysis
was right, but nobody is about to collide with them.

---

## 1. Ranked watchlist — per-file bug-fix density

Ranked for the other 16 agents' attention. `FIX/TOT` counts distinct commits touching the file
whose subject matches `^(fix|bug|hotfix)`. `Cx` marks a `measure_complexity.json` hotspot (14
hotspots ≥5.0). `Cat` is the number of catalogued findings in the file.

| # | File | FIX/TOT 24m | FIX/TOT 5.5y | ratio | Cx | Cat | Why it is here |
|---|---|---|---|---|---|---|---|
| 1 | **`sysmon.py`** | 11/40 | 17/55 | 0.31 | **rank 1** (`sysmon_py_start`, 5 fixes/2y, fix_density 0.063 — 5× any other hotspot, nesting 6) | 6 | Newest of the three cores, default on 3.14+, and the single hottest function in the package. |
| 2 | **`parser.py`** | 13/47 | 36/131 | 0.27 | rank 7 (`_raw_parse`, cog 50) | **0** | Highest absolute fix count in both windows — **and zero catalogued findings across 60**. Either genuinely well-tested or under-covered by the first two passes. |
| 3 | **`control.py`** | 11/49 | 27/138 | 0.20 | — | 5 | The public façade; every subsystem change lands here. |
| 4 | **`core.py`** | 9/19 | 9/20 | **0.45** | — | 2 | Tiny file, *nearly every commit is a fix*. Backend-selection policy is not settled. |
| 5 | **`patch.py`** | 9/24 | 9/24 | 0.38 | — | 2 | All of its history is inside 24 months — a 2025 subsystem that has never stabilised. |
| 6 | **`files.py`** | 5/21 | 23/70 | 0.33 | — | 4 | Path normalisation; the recurring cluster of §2. |
| 7 | **`inorout.py`** | 5/15 | 20/60 | 0.33 | rank 6 (`should_trace`, cog 35) | 2 | The should-trace predicate; CRF-COVPY-0037 says it exists twice. |
| 8 | **`env.py`** | 8/25 | 19/76 | 0.25 | — | 1 | Version/build feature detection — churns on every new Python. |
| 9 | **`execfile.py`** | 6/13 | 10/38 | 0.26 | — | 2 | Two of the six most recent fixes are here. |
| 10 | **`collector.py`** | 3/16 | 15/57 | 0.26 | — | 5 | Threading surface; §3 has a confirmed unpropagated fix. |
| 11 | **`sqldata.py`** | 3/22 | 21/100 | 0.21 | — | **6** | Cooling in the recent window but carries the most findings and a live regression. |
| 12 | **`config.py`** | 7/29 | 12/82 | 0.15 | rank 12 (`from_file`) | 3 | |
| 13 | **`html.py`** | 4/16 | 14/75 | 0.19 | ranks 3, 5, 13 (three hotspots) | 3 | Most hotspots of any file; `write_html_page` is `active-risk`. |
| 14 | **`lcovreport.py`** | 4/11 | 9/29 | 0.31 | — | 2 | See §3 — the only report backend with no output escaping at all. |
| 15 | **`ctracer/tracer.c`** | 4/10 | 10/29 | 0.34 | n/a (C) | 1 | Free-threading atomics migration is in progress and incomplete. |
| 16 | **`phystokens.py`** | 4/14 | 8/37 | 0.22 | rank 8 (`source_token_lines`, nesting 6) | 1 | |
| 17 | **`python.py`** | 4/12 | 8/31 | 0.26 | — | 2 | |
| 18 | **`results.py`** | 4/19 | 7/43 | 0.16 | — | 4 | |

Deliberately **de**prioritised (§15 of the briefing — churn from mechanical change):
`version.py` tops raw churn at 233 commits with **2** fixes (ratio 0.01) — it is the release-bump
file and carries no signal. `htmlfiles/style.css` / `style.scss` / `coverage_html.js` show
ratios of 0.38–0.43 but are asset files where "fix" means a rendering tweak.

### Churn × complexity crossings (task item 5)

`measure_complexity.json` already crosses its 14 hotspots with a 2-year fix window. The crossings
that matter:

| Verdict | Function | Score | Fixes/2y | Note |
|---|---|---|---|---|
| **active-risk** | `sysmon.py::SysMonitor.sysmon_py_start:317` | 7.5 | 5 | nesting 6, cog 41. Highest fix density of any hotspot by 5×. **Top target.** |
| **active-risk** | `pytracer.py::PyTracer._trace:147` | **9.0** | 2 | cog 70 — the most complex function in the package, still being fixed. |
| **active-risk** | `html.py::HtmlReporter.write_html_page:467` | 5.0 | 2 | |
| settled | `data.py::combine_parallel_data:132` | 8.0 | 1 | complex but quiet — deprioritise |
| settled | `templite.py::Templite.__init__:125` | 8.0 | **0** | complex and untouched in 2 years — **deprioritise, say so** |

One discrepancy worth flagging: **`parser.py` is the #1 file by fix count in both windows, but its
only hotspot (`_raw_parse`) scores 1 fix in 2 years.** The fixes are landing in `parser.py`'s
*simple* functions and in `AstArcAnalyzer`'s handler methods (see `a90589c5` in §3), not in the
complex one. Complexity ranking points the wrong way here — as the toolkit's own history_crossing
note warns: *"complexity alone ranked coverage.py's files in almost the reverse of their fix
history."*

---

## 2. Recurring fix-keyword clusters

286 fix commits since 2021, clustered by subject (a commit may join more than one cluster). Sorted
by "standing weakness" — count × number of distinct years.

| Cluster | Fixes | Years spanned | Exemplar commits | Read as |
|---|---|---|---|---|
| **concurrency / threads / processes** | 35 | 2021-2026 (6) | `8cd392e3` snapshot data in flush_data to avoid threading race (#2165); `f960696b` close SQLite connections from terminated threads (#2193); `d9683239` use atomics for `started`/`activity` (#2019); `41a22569` **revert** "thread safe resume (#2018)" | **The standing weakness.** Every year for six years. Includes one *reverted* fix (`41a22569`, the origin of CRF-COVPY-0013) and one fix that *introduced* a regression (`f960696b` → CRF-COVPY-0001). |
| **paths / files / symlinks** | 31 | 2021-2026 (6) | `f4413c6c` set sys.path correctly when running through a symlink (#2157); `a2f248cf` stdlib might be through a symlink (#2115); `371fcc57` set fixed paths_list in TreeMatcher init (#2130); `6208c42e` find third-party packages in more locations (#2082) | Symlink resolution recurs specifically — two symlink fixes in 2026 alone. Corroborates CRF-COVPY-0014 / 0015. |
| **Python-version / build compat** | 30 | 2021-2026 (6) | `f36248d7` don't emit 'Couldn't import C tracer' warning for 3.13t (#2203); `6f9fa1e1` preserve isolated sys.path on Python 3.10 (#2211); `77954415` default to sys.monitoring on 3.14+ | Free-threading is now part of this cluster, not separate. |
| **branch / arc computation** | 27 | 2021-2025 (4) | `31f91f81` multiline statement branches with sysmon (#2070); `c177731d` see through nop bytecodes to get the right arcs (#1999); `88dcaa21` assume a missing line number is intra-line (#1991) | The silent-wrong-answer cluster — these produce wrong coverage, not crashes. |
| **html report** | 22 | 2021-2026 (5) | `dd806350` escape context labels in html report inline script block (#2224); `63a8a759` cache busting on HTML report support files | |
| **sysmon / core / tracer selection** | 21 | 2021-2026 (6) | `4b0fc857` find a usable sys.monitoring toolid (#2187); `84347926` sysmon conflicts no longer cause errors; `c2127c69` change how the core default adjusts (#2064); `a90589c5` handle except\* with sysmon (#2086) | Concentrated in 2025-2026 — this is the *currently* active weakness. |
| **sqlite / data file / combine** | 18 | 2020-2026 (7) | `507c19f8` don't leak in-memory databases (#2138); `3de66ee4` combining skips no-read data files gracefully (#2117); `1cd47aa6` implicit combine-during-report removes the combined files | The `no_disk` / `force`-close guard has been changed in *both directions* inside four months (`507c19f8` removed a guard; `f960696b` added a force-close). See §3. |
| **xml / lcov / json report** | 13 | 2022-2026 (5) | `65979cc0` skip excluded functions in LCOV function totals (#2206); `02990a24` JSON reports executed lines same as other reports (#2105); `21d3e31e`, `6118798a` lcov report fixes | Every one of these is *one backend disagreeing with the others* — the `one-concern-implemented-per-backend` shape, which owns 6 catalogued findings. |
| **config / TOML** | 13 | 2021-2025 (5) | `697d4bb3` subprocesses inherit the entire configuration (#2021); `882395f7` execve also gets the full configuration | Note `882395f7` lands one day after `697d4bb3` — a fix that missed a sibling path and needed a follow-up. |
| **parser / AST / bytecode** | 9 | 2021-2025 (5) | `a90589c5` handle `except*` with sysmon (#2086); `c3c91f1f` the bytecode for yields was only different for 3.13 | |
| **encoding / tokenize** | 5 | 2023-2025 (3) | `2f1da955` add encoding arguments, fixes #1966; `364282ea` catch TokenError on parse (#1788) | Small but non-zero, and directly adjacent to CRF-COVPY-0004 (coding-cookie `SyntaxError`). |
| plugin lifecycle | 1 | 2021 | `27d82554` | Essentially inert — **not** a standing weakness despite the plugin API's size. |

**Two clusters deserve escalation to every agent:**

1. **Concurrency (35 fixes / 6 years), which is also the cluster with the worst *fix quality*.**
   Of the four concurrency fixes examined in §3, one was reverted (`41a22569`), one introduced a
   regression (`f960696b`), and one was applied to `self.data` but not to `self.file_tracers`
   (`8cd392e3`). Three of five catalogued `collector.py` findings and the whole `fix-reverted-and-
   never-relanded` / `fix-not-propagated-to-sibling-path` shape family live here.

2. **Cross-backend divergence (13 report fixes + 22 html + the whole `xml/lcov/json` cluster).**
   Every one of these fixes is a report backend catching up to the others. The catalog already has
   six findings on this shape (0003, 0009, 0010, 0028, 0029, 0032, 0043). §3 supplies two fresh,
   concrete siblings that are still unfixed.

---

## 3. Recently fixed — check for siblings

Shapes extracted from the 25 most recent fix commits. **Hand these to the named agents; do not
chase them all here.** Ordered by strength of the sibling evidence.

### A. `8cd392e3` (2026-05-09) — snapshot a live shared collection before iterating it

> #2165: `Collector.flush_data` iterated `self.data` while tracer threads mutated it, raising
> `RuntimeError: Set changed size during iteration`. The fix takes `.copy()` of the outer dict and
> of every inner set, with a comment explaining that `dict.copy()`/`set.copy()` are atomic under
> the GIL.

**Sibling, already catalogued and now proven:** CRF-COVPY-0012 says `file_tracers` is iterated
unguarded in the same method. This commit is the **guarded twin** — the maintainer fixed
`self.data` in exactly this function and left `self.file_tracers` beside it untouched. That
upgrades 0012 from "asymmetry" to "the fix stopped one line short".
**Unhunted siblings:** anything else mutated by a tracer thread and iterated by the flush/report
thread — `Collector.tracers` (appended by `_start_tracer` per thread), `sysmon.py`'s `code_infos`,
`sqldata._dbs`. → *silent-failure-hunter, python-pitfall-scanner.*
Note also the GIL-atomicity comment added here vs **CRF-COVPY-0052** (two GIL justifications in a
project shipping free-threaded wheels) — this fix adds a *third*, in 2026.

### B. `65979cc0` (2026-06-27) + `02990a24` (2025-12-24) — numerator and denominator from different sources

> #2206: LCOV wrote `FNF:{len(functions)}` (all functions) while `FNH` counted only functions that
> survived narrowing — excluded functions inflated the denominator. Fix introduces `functions_found`.
> #2105: `analysis_from_file_reporter` reported `executed` lines straight from the data file; JSON
> therefore listed lines the other backends did not. Fix: `... & statements`.

**Concrete unfixed sibling, verified this run.** In `coverage/results.py:22-52`, `02990a24`
clamped the *lines* path:

```python
executed = file_reporter.translate_lines(data.lines(filename) or []) & statements   # results.py:32
```

The *arcs* path immediately below builds `new_arcs` from `data.arcs(filename)` and **never
intersects it with `arc_possibilities_set`** (results.py:35-52). Measured arcs that the analyzer
does not consider possible flow straight through. Same function, same commit's blast radius, one
of the two paths fixed. → *python-pitfall-scanner, consistency-auditor, test-investigation-agent.*

### C. `dd806350` (2026-07-11) + `e06eb348` (2026-03-08) — output escaping applied per backend

> #2224: context labels were `json.dumps`'d into an inline `<script>`; a label containing
> `</script>` closed the element. Fix escapes `<`, `>`, `&` as `\uXXXX`.
> #2141: the markdown report escaped only `_` via `.replace("_", "\\_")`. Fix introduces
> `escape_markdown()` with a full punctuation table.

Two backends, four months apart, same root: **each report backend invents its own escaping, and
each got it wrong once.**
**Concrete unfixed sibling, verified this run.** `coverage/lcovreport.py` writes
`FN:{first_line},{last_line},{region.name}` (line 100), `FNDA:{hit},{region.name}` (101) and
`SF:{rel_fname}` (210) into a comma-and-newline-delimited format with **no escaping anywhere in
the file**. XML uses minidom (safe by construction) and JSON uses `json.dumps` (safe); markdown and
HTML have now both been fixed; **lcov is the one backend that never escapes.** Region names come
from plugin `FileReporter`s, and POSIX filenames may contain commas and newlines.
→ *pattern-consistency-checker, python-pitfall-scanner.* Corroborates CRF-COVPY-0043.

### D. `9f0753bd` (2025-11-08) then `e18359c8` (2025-11-17) — a guard catching the wrong exception set, twice

> #2077 wrapped `parser.parse_source()` in `except NotPython: return {}`.
> #2091, nine days later, added `except NoSource: return {}` **and had to move
> `PythonParser(filename=...)` inside the `try`** — the first fix had left the constructor outside it.

Two fixes to one guard in nine days, each adding one more exception type it should have caught.
**CRF-COVPY-0004 says a third is still missing**: a `SyntaxError` from a bad coding cookie. The
history is the argument — this guard has never once been enumerated correctly on the first attempt.
**Caveat:** `ee271ee2` (2026-07-12, perf #2220) rewrote this region again. **Re-read
`sysmon.py:489-503` before restating 0004/0017.** → *silent-failure-hunter.*

### E. `a90589c5` (2025-11-14) — a node-family handler missing a member, and KeyError-hardening applied to one map only

> #2086 added `_handle__TryStar = _handle__Try` to `AstArcAnalyzer` — `except*` had no handler at
> all — **and** changed `code_info.byte_to_line[offset]` to `.get(offset)` at two sysmon call sites
> (sysmon.py:384 and :458).

Two distinct siblings from one commit:
- The missing-node-family-member shape is exactly **CRF-COVPY-0034** (`regions.py:53-55` never
  walks `orelse`, `handlers`, `finalbody`). The `TryStar` gap proves the project ships analyzers
  with silently absent node handlers. → *python-pitfall-scanner, dead-code-finder.*
- The unguarded-subscript hardening was applied to `byte_to_line` but **not** to `code_infos` —
  which is **CRF-COVPY-0022** (three sysmon callbacks index `code_infos` unguarded where their
  sibling checks). Same file, same commit, same shape, half-propagated. → *python-pitfall-scanner.*

### F. `78cab6e1` (2026-07-15) — a manually-invalidated identity-keyed cache, deleted rather than fixed

> #2229: `_analysis_cache` and `_file_reporter_cache` were keyed on `TMorf` and hand-invalidated at
> four call sites via `_clear_analysis_caches()`. The whole mechanism was **removed** for memory reasons.

The maintainer's own verdict on hand-invalidated identity-keyed caches in this codebase. Two
survive: **CRF-COVPY-0011** (`sqldata.py:468-475`, stale `_file_map` + `INSERT OR REPLACE`) and
**CRF-COVPY-0023** (`files.py:133-139`, a failed `listdir` cached for the process lifetime). Both
are the shape that was just deleted from `control.py`. → *python-pitfall-scanner, silent-failure-hunter.*

### G. `507c19f8` (2026-03-12) vs `f960696b` (2026-06-20) — the `no_disk` / `force`-close guard is contested

> #2138 changed `CoverageData._reset` from `if not self._no_disk: self.close()` to
> `self.close(force=True)` — *removing* the no-disk guard.
> Three months later #2193 added `_reap_dead_thread_dbs`, which also calls `close(force=True)` —
> and that is CRF-COVPY-0001, where forcing the close destroys the shared-cache in-memory database.

The same guard was deliberately defeated in March and accidentally defeated in June. Add
**CRF-COVPY-0059** (`write()` lacks the `no_disk` guard its four siblings have) and this is a
three-site inconsistency in one class. → *consistency-auditor, pattern-consistency-checker.*
Enumerate every `close(force=...)` and every `self._no_disk` test in `sqldata.py`/`sqlitedb.py` as
one finding with N sites, per triage rule 2.

### H. `371fcc57` (2026-02-07) — an `Iterable` parameter iterated twice

> #2130: `TreeMatcher.__init__` iterated `paths` once for `human_sorted(paths)` and again in
> `for p in paths`. A generator argument left `self.paths` empty. Fix materialises `list(paths)` first.

Mechanically checkable sibling hunt: every function in `coverage/` taking `Iterable`/`Iterator` and
touching it more than once. The other `Matcher` subclasses in `files.py`, and any `morfs:
Iterable[...]` consumer in the report path, are the natural candidates. → *python-pitfall-scanner.*

### I. `f36248d7` (2026-06-23) — a runtime probe used where a build-time fact was meant

> #2203 added `FREE_THREADED = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))` with the comment
> *"Checks the build, not runtime GIL state, since the GIL can be re-enabled at runtime."*

`env.py` still exposes `GIL = getattr(sys, "_is_gil_enabled", lambda: True)()` — evaluated **once at
import time**, so it is a snapshot of runtime state, not a live query and not a build fact. Every
consumer of `env.GIL` needs auditing against which of the three things it actually wants.
`env.py` is #8 on the watchlist with 8 fixes in 24 months. → *consistency-auditor, python-pitfall-scanner.*

### J. `961fc5b4` (2025-11-15) — mock-hardening applied to one module

> #2083 added `open = open` at module level in `python.py` "so later mocks don't break us", beside
> the `os = isolate_module(os)` idiom.

`os = isolate_module(os)` appears in **19** modules; `open = open` appears in **exactly one**. Other
modules calling `open()` on a measurement-relevant path — `data.py:105` (`hash_for_data_file`),
`config.py:376`, `tomlconfig.py:56`, `debug.py:487/494` — have no such defense.
→ *consistency-auditor.* (Medium confidence: the mocking argument is strongest for measurement-time
reads, weakest for config-time ones. Judge per site.)

### K. `d9683239` (2025-08-09) — partial atomics migration in the C tracer

> #2019 converted `self->started` and `self->activity` to `atomic_load`/`atomic_store`.

`self->tracing_arcs` is still assigned plainly in `CTracer_start` and read from the trace callback.
The migration covered two flags of the struct, not the struct. `ctracer/tracer.c` carries 4 fixes
in 24 months and holds CRF-COVPY-0003. → *whoever covers the C tracer; python-pitfall-scanner cannot see this.*

### L. `3de66ee4` (2026-01-19), `f960696b` (2026-06-20) — broad excepts *added* as fixes

Two `except Exception:` handlers were introduced in 2026 as bug fixes: `DataFileClassifier.classify`
returns `"combine"` on any hash failure ("probably it will fail later, but that error will be
handled"), and `_reap_dead_thread_dbs` swallows every close failure. Both are fresh, both are in
the top-half watchlist files. → *silent-failure-hunter* — these are not legacy debt, they are this
year's.

### M. `8df0d5f0` (2026-02-04) — `listdir` used to test for one known name

> #2129 replaced `if "pyvenv.cfg" in os.listdir(d)` with `os.path.exists(os.path.join(d,
> "pyvenv.cfg"))` to avoid `PermissionError` on unreadable parent dirs.

`files.py:133-139` (**CRF-COVPY-0023**) still uses `os.listdir` in the actual-path cache, and caches
its failure. Same shape, same failure mode, unfixed. → *silent-failure-hunter.*

### N. `6f9fa1e1` (2026-07-02) — the `# PYVERSION` marker is still being spelled singular

`6f9fa1e1` added a fresh `# PYVERSION` comment at `execfile.py:95` — which is precisely
**CRF-COVPY-0058**'s location (the release checklist greps for `PYVERSIONS`). The finding is not
merely live; new instances of the invisible spelling are still being introduced, three weeks before
the review. → *project-docs-auditor, tech-debt-inventory.* Cheap, certain, and now dated.

### Lower-confidence, listed for completeness

- `4cf0f018`/`f8492317` (2025-12-21, two commits same day) — `Hasher.update` gained a `f"{len(v)}:"`
  delimiter for `str` and `bytes`; the `int()|float()` branch still writes bare `str(v)`. Probably
  fine (each `update()` also emits `str(type(v))` before and `b"."` after), but the maintainer
  needed two attempts, so it is worth one look. Relates to CRF-COVPY-0036.
- `9d920c39` (2025-08-09) — `.pth` filename made per-pid to stop collisions. Sibling: any other
  fixed filename written into a shared directory.
- `1ed39982` (2026-06-28) — `ModuleSpec` built with `loader=None` and the loader attached later;
  fix passes it to the constructor. Sibling: other partially-constructed objects whose fields are
  set post-hoc.
- `4b0fc857` (2026-06-08) — the tool-id search is `while self.myid <= 5`, a hardcoded bound over
  `sys.monitoring`'s id space that will claim `OPTIMIZER_ID` (5) if it gets that far.

---

## 4. Direct instructions to subsequent agents

- **silent-failure-hunter** — §3D (guard fixed twice, third exception still missing, region rewritten
  2026-07-12), §3L (two `except Exception:` added as fixes in 2026), §3M, §3F. Start in `sysmon.py`
  and `sqldata.py`.
- **python-pitfall-scanner** — §3B (arcs path unclamped, `results.py:35-52`, concrete), §3H
  (`Iterable` iterated twice — mechanical sweep), §3E (`code_infos` unguarded subscripts), §3A.
- **pattern-consistency-checker / consistency-auditor** — §3C (**lcovreport.py escapes nothing**,
  concrete), §3G (`no_disk`/`force` contested across three sites), §3I (`env.GIL` snapshot vs
  build fact), §3J. Report each as one root with N sites.
- **test-coverage-analyzer / test-investigation-agent** — `parser.py` is the #1 fix-density file in
  both windows with **zero** catalogued findings. Establish whether that is test strength or a
  coverage gap in the previous two passes. Also `patch.py`, whose entire history is inside 24 months.
- **complexity-simplifier** — the ranking is `sysmon_py_start` (rank 1, 5 fixes/2y) then
  `PyTracer._trace` (score 9.0, cog 70). **Deprioritise `templite.py::Templite.__init__`** (score
  8.0, zero fixes in 2 years) and `data.py::combine_parallel_data` — complex and settled.
- **tech-debt-inventory / project-docs-auditor** — §3N, `# PYVERSION` singular spelling is still
  being introduced as of 2026-07-02.
- **everyone** — the tree is byte-identical to the catalog commit. Catalogued line numbers are
  exact; do not re-derive the 60 settled findings, and re-read only the five in §0 whose code moved
  in the last 90 days.
