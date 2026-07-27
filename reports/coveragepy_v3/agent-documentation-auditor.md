# documentation-auditor — coverage.py (informed re-review)

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Scope owned:** docstrings and inline comments inside `coverage/`. `doc/`, README and CHANGES belong to project-docs-auditor.
**Tree edits: NONE.** All reading and execution was done on a `git archive` copy at `/tmp/covrepro`. Verified after the run: HEAD unchanged, `git status --porcelain` shows **zero tracked modifications**, untracked set identical to session start.
**Runtime used for falsification:** Python 3.14.4, `env.SYSMON_DEFAULT` = True (default core = `SysMonitor`).

---

## Method

Per the briefing: **falsify the docstring by execution or by reading the body, don't just read it.** Concretely —

1. AST scan: every documented parameter name vs. the actual signature.
2. Scoped cross-reference resolution: every backticked identifier and `:func:`/`:meth:`/`:class:` role in every docstring, resolved against the scope a reader standing at that docstring would search (enclosing class → module → package public API → builtins/stdlib), with a flag for the dangerous *same-name-survives-elsewhere* variant. Repeated over **comments** as well as docstrings.
3. Return-claim falsification: docstring-stated return type vs. annotation vs. what the body actually returns.
4. Direct execution of every docstring containing a concrete example or a stated guarantee.
5. `.. versionadded::` / `.. versionchanged::` cross-checked against `CHANGES.rst`.
6. Process markers: every `# pragma:` in the repo mechanically tested against the regexes `metacov.ini` and coverage's own defaults actually apply; `PYVERSION(S)` marker spellings vs. what `howto.txt` tells the maintainer to grep for.

---

## Catalogued findings — CONFIRMED, not re-litigated

All six doc-shape entries I own are still present at `6b3259ab`.

| ID | Site | Status |
|---|---|---|
| CRF-COVPY-0051 | `collector.py:44-53` | **Present.** Class docstring still claims the Collector "installs a function to create Tracers for each new thread started". |
| CRF-COVPY-0052 | `collector.py:420-423`, `:453-459` | **Present.** Both GIL justifications intact ("the GIL protects the dictionary iterator", "the GIL is held for the duration of the C-level copy"). |
| CRF-COVPY-0053 | `control.py:448`, `parser.py:1039`, `regions.py:84`, `data.py:144/152/155`, `types.py:41`, `execfile.py:289`, `annotate.py:57`, `sqldata.py:39` | **Present**, spot-confirmed. |
| CRF-COVPY-0054 | `misc.py:364`, `files.py:204-205`, `files.py:498-500`, `patch.py:115` | **Present.** |
| CRF-COVPY-0055 | `control.py:197-199`, `control.py:1149-1150`, `plugin.py:537-539`, `lcovreport.py:202-203` | **Present.** The `format`/`output_format` mismatch was independently re-derived by the mechanical param scan. |
| CRF-COVPY-0058 | `execfile.py:95`, `phystokens.py:98` | **Present.** See N7 for a third site outside `coverage/`. |

---

## Novel findings

### N1 — `pytracer.py:59-65` — a stated prohibition the function it governs violates twice per run
**Shape:** `doc-describes-a-superseded-model` · **CONSIDER** · blame `808e6e332`, 2014-09-19

> "there must be only one function ever set as the trace function, both through `sys.settrace`, and as the return value from the trace function. Put another way, **the trace function must always return itself. It cannot swap in other functions, or return None to avoid tracing a particular frame.**"

**Evidence it is false — executed:** instrumenting `PyTracer._trace` under `Coverage(timid=True)` over a 3-line module: **228 calls, 2 of which returned `None`.**

Two in-tree sites do exactly what the comment forbids:
- `pytracer.py:156-157` — `if THIS_FILE in frame.f_code.co_filename: return None` (added 2021-02-21, commit message *"fix: avoid tracing pytracer.py"* — verbatim "return None to avoid tracing a particular frame").
- `pytracer.py:183` — `return None` on the stop path (2017-12-23).

A third opt-out mechanism the model predates: `frame.f_trace_lines = False` at `:240` and `:242` (2022).

**Guarded twin:** the signature was updated, the prose was not. `pytracer.py:153` is `-> TTraceFn | None`, and `types.py:101-102` documents `start()` as *"return a trace function **if based on sys.settrace**"* — the protocol was made conditional on the backend in 2023; this comment was not.

**Why it costs:** a maintainer reading it will not add an early `return None` or an `f_trace_lines` opt-out, believing it breaks DecoratorTools compatibility — while the code already does both.

**Fix:** scope it to history. *"Historically (DecoratorTools, ~2007) the trace function had to always return itself. That constraint has been relaxed: `_trace` returns None for its own frames and after stop, and sets `frame.f_trace_lines = False` for untraced frames."*

---

### N2 — `collector.py:386` — direct sibling of CRF-COVPY-0051, same file, missed last run
**Shape:** `doc-describes-a-superseded-model` · **CONSIDER** · blame `d679d5442`, 2017-03-03

`Collector._activity()`:
> "Returns a boolean, **True if any trace function was invoked.**"

**Evidence it is false — executed on the default core:**
```
tracer_name       : SysMonitor
core.systrace     : False
sys.gettrace() during collection: None
_activity()       : True
```
No trace function is installed or invoked at any point on 3.14+. Activity is set by `SysMonitor._activity = True` at `sysmon.py:319`, inside the `sys.monitoring` `PY_START` callback.

This matters more than the class docstring it siblings: `_activity()` is the gate for `flush_data()` (`collector.py:450`) **and** for the "no data collected" warning. A maintainer debugging an empty report is pointed at a mechanism that does not exist on the default core.

**Guarded twin:** every sibling declaration of the same concept is core-neutral, and only this one was left behind — `types.py:107-108`, `sysmon.py:304-305`, `pytracer.py:360-361` all read simply `"""Has there been any activity?"""`.

**Fix:** `"""Returns a boolean, True if any tracer recorded activity."""`

---

### N3 — `inorout.py:346` — mechanism claim false under the default core
**Shape:** `doc-describes-a-superseded-model` · **CONSIDER** · blame `bd613312d`, 2018-02-25

`InOrOut.should_trace()`:
> "**This function is called from the trace function.** As each new file name is encountered, this function determines whether it is traced or not."

**Evidence it is false — captured caller chain, default core:**
```
sysmon.py:345 in sysmon_py_start
control.py:452 in _should_trace
```
with `sys.gettrace()` `None` for the whole run. The caller is a `sys.monitoring` `PY_START` callback registered at `sysmon.py:254-258`.

**Guarded twin:** the actual caller's own docstring, `sysmon.py:318` — `"""Handle sys.monitoring.events.PY_START events."""` — knows it is not a trace function. The `frame` argument this docstring implies is even reconstructed by hand via `inspect.currentframe().f_back` at `sysmon.py:339-344` *because* there is no trace-function frame argument — and is `None` when unavailable.

**Fix:** *"Called from the tracer's per-file hook — the trace function for the settrace-based cores, or the `sys.monitoring` PY_START callback for the sysmon core."*

---

### N4 — `plugin.py:575-576` — a public round-trip guarantee published without the caveats its own implementation documents
**Shape:** `refactor-changed-behaviour-doc-did-not` · **CONSIDER** · blame `9f8198556`, 2015-08-15

`FileReporter.source_token_lines`, a Sphinx-rendered plugin-API docstring:
> "If you concatenate all the token texts, and then join them with newlines, you should have your original source back."

**The guarded twin is in-tree and is the same sentence with the qualifier still attached** — `phystokens.py:122-125`, the internal function `python.py:262` delegates to:
> "…you should have your original `source` back, **with two differences: trailing white space is not preserved, and a final line with no newline is indistinguishable from a final line with a newline.**"

**Evidence the public claim is false — executed** against `PythonFileReporter`, the shipped implementation of this very interface:

| input | round-trips? |
|---|---|
| `'a = 1   \nb = 2\n'` (trailing whitespace) | **No** — rebuilt `'a = 1\nb = 2'` |
| `'def f():\n\treturn 1\n'` (tab indent) | **No** — rebuilt `'def f():\n        return 1'` |
| simple / f-string / `match` / unicode / backslash-continuation | yes |

**Second-order finding: even the guarded twin is now incomplete.** It names *two* differences. There is a third — `phystokens.py:133` does `source.expandtabs(8)`, so tabs are silently converted to 8 spaces. That line was added **2023-03-22**; the twin docstring was last touched **2022-11-28**. The caveat list has been stale for over three years.

**Fix:** replace the public sentence with the twin's wording, and add tab expansion to both.

---

### N5 — `plugin.py:540-541` — documented default return string is not the one returned
**Shape:** `refactor-changed-behaviour-doc-did-not` · **CONSIDER** · blame `20033c710`, 2016-02-15

`FileReporter.missing_arc_description`:
> "By default, this simply returns the string **"Line {start} didn't jump to {end}"**."

Body at `plugin.py:544`: `return f"Line {start} didn't jump to line {end}"`.

**Evidence — executed:**
```
documented for (5,7): "Line 5 didn't jump to 7"
ACTUAL   for (5,7): "Line 5 didn't jump to line 7"
```
The word `line` is missing from the docstring. Blame shows both lines trace to the same 2016 commit, so this was wrong at birth rather than drift — but it is a public plugin-API docstring rendered to Sphinx, in the *same docstring* as catalogued CRF-COVPY-0055, and the returned string reaches users through `html.py:178`.

**Fix:** `"Line {start} didn't jump to line {end}"`.

---

### N6 — `collector.py:92` — dead cross-reference to a method deleted from this very class
**Shape:** `dead-cross-reference-in-a-docstring` · **CONSIDER** · blame `9a751db51`, 2009-11-08

`Collector.__init__`:
> "If `branch` is true, then branches will be measured. This involves collecting data on which statements followed each other (arcs). Use **`get_arc_data`** to get the arc data."

`Collector` has no `get_arc_data` — its full method list is `__init__, __repr__, use_data, tracer_name, _clear_data, reset, lock_data, unlock_data, _start_tracer, _installation_trace, start, stop, pause, resume, post_fork, _activity, switch_context, disable_plugin, cached_mapped_file, mapped_file_dict, plugin_was_disabled, flush_data`. Removed in `aa9af882` ("Refactor collector->data; data has only one of lines and arcs").

**This is the dangerous variant.** `arc_data` survives elsewhere as an unrelated entity: a local in `Collector.flush_data` (`collector.py:461`, `:481`) and the parameter name of `CoverageData.add_arcs` (`sqldata.py:573`). A reader chasing the reference lands on the wrong thing rather than on nothing.

Not among the eight sites in CRF-COVPY-0053 — this is a new site for that catalogued shape.

**Fix:** `"Use `flush_data()` to write the collected arcs to the CoverageData object."`

---

### N7 — `Makefile:126` — third `PYVERSION` marker, outside `coverage/`
**Shape:** `process-marker-invisible-to-its-own-checklist` · **CONSIDER** · *hand-off to project-docs-auditor*

`howto.txt:23` instructs the maintainer: *`Edit supported Python version numbers. Search for "PYVERSIONS".`*

`Makefile:126` carries a live claim spelled singular:
```make
# PYVERSION to use for kitting, based on cibuildwheel's requirements.
KITVER = py311
```
The pinned kitting interpreter is exactly the kind of value that must be revisited when supported versions change, and the documented search will not surface it. Same finding as CRF-COVPY-0058, third site — but the file is outside my scope, so flagging for the project-docs agent rather than claiming it.

Correctly-spelled marker siblings for reference: `collector.py:286`, `pytracer.py:40`, `setup.py:60`, `Makefile:24`, `doc/contributing.rst:78`, `tests/test_oddball.py:517`.

---

## Hypotheses — reported as such, not as findings

- **H1 `multiproc.py:98-103`** (blame 2016-01-10) — *"Windows only spawns, so this is needed to keep Windows working."* The literal sentence is still true; the implied **scope** is superseded. Verified at runtime: `multiprocessing.get_start_method()` is `'forkserver'` on Python 3.14/Linux, and `popen_forkserver` also routes through `spawn.get_preparation_data`, so the Stowaway hook at `multiproc.py:118` is on the **default Linux path**, not a Windows-only one. A maintainer would conclude the branch is Windows-specific and skippable when reasoning about Linux — now backwards.
- **H2 `collector.py:321`** — `# Install the tracer on this thread.` Under the sysmon core this reaches `sys.monitoring.set_events()`, which is interpreter-wide, not per-thread. Terse enough to read as loose phrasing.
- **H3 `control.py:182-184`** — the public `timid` docstring contrasts "a slower and simpler trace function" with "the faster trace function". On 3.14+ the default is `SysMonitor`, which is not a trace function at all and is unaffected by `sys.settrace` manipulation. Weaker because the sentence remains accurate on ≤3.13.

---

## Clean negatives — refuted candidates, recorded so they are not re-litigated

These all looked like the shape and are **not**. Each was checked by execution, not by reading.

| Candidate | Verdict |
|---|---|
| `results.py:448` `format_lines` documented example (`[1..5,10..14]` / `[1,2,5,10,11,13,14]` → `"1-2, 5-11, 13-14"`) | **Exact match.** |
| `files.py:97` `flat_rootname` documented example (`a/b/c.py` → `z_86bbcbe134d28fd2_c_py`) | **Exact match.** |
| `results.py:361-363` and `:406-408` — *"Rounding can never result in either "0" or "100""* | **Holds.** Brute-forced `display_covered` over precision 0-4 × 10⁶ values, and `Numbers.pc_covered_str` over precision 0-2 × denominators 1-400: **zero violations.** (The catalogued rounding defects CRF-COVPY-0007/0008 live in `--fail-under` and `xmlreport.py`, not in this guarantee.) |
| `numbits.py:54-55` — *"When registered as a SQLite function … this returns a string, a JSON-encoded list of ints"* | **Accurate** — `numbits.py:146` registers `lambda b: json.dumps(numbits_to_nums(b))`. |
| `sqldata.py:244` — `suffix` documented as *"same meaning as the `data_suffix` argument to `coverage.Coverage`"* | **Resolves** — `data_suffix` is a real `Coverage.__init__` parameter (`control.py:145`). |
| All `:ref:` targets used in `coverage/` docstrings (`api_exceptions`, `api_plugin`, `howitworks`, `config`, `dbschema`, `dynamic_contexts`) | **All resolve** to a definition in `doc/`. |
| Every `# pragma:` marker in `coverage/` | **All 12 distinct spellings match** a `metacov.ini` or built-in regex. No inert markers. The 4 apparently-inert hits are test fixtures in `tests/test_parser.py:1059-1084` that supply their own regex. |
| Documented-parameter-vs-signature scan across the package | Only the **2 already-catalogued** mismatches (`control.py` `format`→`output_format`, `execfile.py` `package`). No third. |
| Every `.. versionadded::` in `coverage/` vs `CHANGES.rst` | **All confirmed** — 7.7 `plugins` param, 7.8 `source_dirs`, 7.7 `branch_stats`, 7.2 `purge_files`, 7.3 `collect()`, 6.3 `lcov_report()`. No drift. |
| Base-class docstrings claiming a return where the body returns nothing (`plugin.py`, `types.py`, `pytracer.py:369`) | **Not the shape** — abstract methods and Protocol stubs; the docstring is the implementer contract. |

---

## Hand-off — a code finding surfaced while verifying N2, not a documentation defect

`collector.py:364-365`, `Collector.pause()`:
```python
if self.threading:
    self.threading.settrace(None)
```
`start()` (`:334`) and `resume()` (`:371`) were both gated on `self.core.systrace` in `1f08ea1cf` (2024-07-20); `pause()` (`8b3265d34`, 2014-09-17) was not. Under the sysmon core coverage never calls `threading.settrace`, but `pause()` — reached from every `Coverage.stop()` — clears it unconditionally, clobbering a third-party hook coverage never installed. Reproduced: a pre-existing `threading.settrace` hook survives `start()`, and is `None` after `stop()`.

Belongs to `fix-not-propagated-to-sibling-path` — routing to pattern-consistency-checker / silent-failure-hunter, not claimed here.

Minor, non-blocking: `env.py:34` reads *"version-specfic"* (typo).

---

## Summary

- **6 catalogued doc findings confirmed present**, none re-derived.
- **6 novel findings** (N1-N6) inside `coverage/`, all CONSIDER, all falsified by execution or by an in-tree guarded twin. Three are `doc-describes-a-superseded-model` around the sys.monitoring default core — the same drift as CRF-COVPY-0051, in three places that pass went past. Two are Sphinx-rendered public plugin-API contracts. One is a dead cross-reference of the dangerous same-name-survives variant.
- **1 hand-off** for the catalogued PYVERSION shape outside my scope (N7), **3 hypotheses**, **1 code finding** routed elsewhere.
- **9 candidate classes refuted by execution** — recorded above so the next pass does not spend the run on them.
- The highest-yield query this run was not the cross-reference scan but **executing the guarantee**: N1, N2, N3, N4 and N5 were all settled by running the code, and four of them read as entirely plausible on the page.
