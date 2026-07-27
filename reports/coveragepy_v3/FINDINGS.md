# coverage.py informed-explore v3 — findings

`coverage/` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26) · 44 files / 16,426 lines
· toolkit v1.13.0 · 16 agents + 12 scanners · **12 of 16 agents landed at time of writing**

**This is a re-review at an unchanged tree.** `git diff d37859cd HEAD -- coverage/` is **empty** — only
CI workflow files moved since the v1/v2 review. So every new finding here is informed-pass yield, not
code churn, and the 60 catalogued findings are all still exactly where they were.

---

## ORCHESTRATOR-VERIFIED

### V1 · FIX · `files.py:375` — a newline in a config glob hangs coverage.py forever

`_glob_to_regex` walks the pattern with `while pos < len(pattern)`, trying each entry of
`G2RX_TOKENS` in turn. The catch-all is `re.compile(r".")` **without `DOTALL`**, so nothing matches a
newline, `pos` never advances, and the loop spins.

Reproduced end-to-end from a real config, not just the helper:

```toml
# pyproject.toml
[tool.coverage.run]
omit = ["a\nb"]
```
```
$ timeout 15 python -m coverage run m.py     # never returns
exit=143
```

**The `# pragma: always breaks` on that `for` is false** — the loop does not always break. That
pragma is also why the path has never been measured, on the project whose job is measuring paths.

Fix: add `DOTALL` to the catch-all, or raise `ConfigError` on an unmatched character (the branch
directly above already raises `ConfigError` for a disallowed token — the guarded twin is four lines up).

### V2 · FIX · `lcovreport.py` — no escaping anywhere, in a delimited format

`grep -n "escape\|replace\|quote" coverage/lcovreport.py` returns **nothing**. Filenames go into
`SF:{rel_fname}` and region names into `FN:{first},{last},{region.name}` verbatim. Reproduced with a
newline in a filename:

```
SF:lcovtest2/we
ird.py
DA:1,1
```

A line-oriented LCOV parser — genhtml, Coveralls, Codecov, Sonar — reads `lcovtest2/we` as the
filename and then hits a bare `ird.py` that is not a valid directive.

**Guarded twins, both from 2026:** `dd806350` "escape context labels in html report inline script
block" and `e06eb348` "escape filenames in markdown report". Two sibling reporters were fixed; the
one whose format is *most* delimiter-sensitive was not. `fix-not-propagated-to-sibling-path`.

### V3 · CONSIDER · `results.py` — 89.995% displays as 90.00% and passes `--fail-under=90`

```
total=89.995   display='90.00'   should_fail_under(total, 90, 2) = False
total=89.994   display='89.99'   should_fail_under(total, 90, 2) = True
```

Confirms catalogued CRF-COVPY-0007 (`asymmetric-rounding-between-display-and-gate`) at HEAD. The
display rounds half-up and the gate compares the rounded value, so a build at 89.995% passes a gate
set at 90 — and the report agrees with itself, which is what makes it invisible.

### V4 · CONSIDER · `multiproc.py:37` sets one of the three warning suppressions its twin sets

```python
# multiproc.py:37          # control.py:1490-1492
cov._warn_preimported_source = False    cov._warn_no_data = False
                                        cov._warn_unimported_source = False
                                        cov._warn_preimported_source = False
```
Same object, same purpose, two lines missing. Agent-measured: `concurrency=multiprocessing` emits 4
`CoverageWarning` lines from a `Pool(4)`; `patch=subprocess` on the identical program emits 0.

### V5 · CRF-COVPY-0018 is still live, and the toolkit had gone blind to it

`html.py:42` — `from coverage.plugins import FileReporter` inside `if TYPE_CHECKING:`. The module is
spelled `coverage.plugin`. `importlib.util.find_spec("coverage.plugins")` → `None`. It never runs,
nothing raises, and every annotation using `FileReporter` in that file degrades to `Any`.

---

## REFUTED OR DOWNGRADED BY THE ORCHESTRATOR

Four agent claims did not survive checking. Recording them so nobody re-derives them.

| Claim | Verdict |
|---|---|
| Six `zip()` calls without `strict=` are defects | **All six are FPs.** `report.py:106,176` zip against rows carrying a deliberate trailing sort key (`report.py:248`), so `len(values) == len(header)+1` always and `strict=True` would raise on **every text report**. `report.py:117,188` zip against `total_line`, which has no sort key — exact, and safe to strictify, but not defects. `html.py:385` is a pairwise zip of two slices of one list; `sysmon.py:134` is inside a `LOG`-only decorator. The only real instance in the repo is `tests/test_data.py:1091`, outside the scanned scope. |
| `--fail-under` silently no-ops for `coverage annotate` | **FP.** The block is guarded by `if total is not None:` (`cmdline.py:937`), and `annotate` does not accept the flag at all. |
| `ast.TypeAlias` raises `RuntimeError` on `type X = int` | **Downgraded to test-only.** The raise at `parser.py:925` is inside `if env.TESTING:`. Direct `PythonParser` runs on all three PEP 695 forms return clean arcs. Real gap in coverage.py's own test matrix; **not reachable by a user.** |
| Reading a data file calls `erase()` and destroys it | **Not reproduced.** The db stayed 53,248 bytes across `measured_files()` and `lines()`, and re-opening returned the same. Needs the agent's exact sequence before it can be restated. |

---

## STRONGEST AGENT-REPORTED, NOT YET ORCHESTRATOR-VERIFIED

Each carries a cited `file:line` and an agent-run reproduction. Ranked by how silently the failure
under-reports coverage, since that is the failure mode that matters most in this tool.

| Sev | Site | Failure |
|---|---|---|
| FIX | `inorout.py:584-588` | A `--source=` package with no on-disk `__file__` (PEP-420 namespace package, zip/egg import) skips the **entire** un-executed-file enumeration. Measured: identical tree, only `__init__.py` differing → **100% / exit 0** vs **25% / exit 2** under `--fail-under=90`. `include_namespace_packages`, documented for exactly this case, is dead on the path because `:585` `continue`s first |
| FIX | `report_core.py:116-121` | `ignore_errors` drops a file from **both** numerator and denominator with no count anywhere. Measured: deleting one source file takes 60% → **100%**, flipping `fail_under=90` from fail to pass. Twin: `report.py:279-285` counts every *benign* omission |
| FIX | `control.py:495` | All 18 diagnostics go through `warnings.warn`, whose filter list **the measured program owns**. Two lines of `warnings.simplefilter("ignore")` in the subject silence "no data collected" *and* "Trace function changed, data is likely wrong". Twin: `_message()` writes straight to stderr |
| FIX | `config.py:266` vs `:396` | "Which options are lists" declared twice; gap set `report_contexts`, `source`, `source_pkgs`, `source_dirs`. Reproduced: `cov.report(contexts='abcq')` → 20% total; `contexts=['abcq']` → 0%. The bare string becomes 4 single-char regexes |
| FIX | `sqldata.py:647-653` vs `:778` | The file-tracer conflict predicate implemented twice with disagreeing rules for `""`. The same two facts are accepted in-process and raise `DataError` through `coverage combine` |
| FIX | `pytracer.py:177` | The tracer's `except IndexError` path calls `log()`, which opens a hardcoded `/tmp/debug_trace.txt` in append mode. Only live `log()` call in the module, no `# pragma: debugging`. If that path is a directory or another uid's, the error escapes `_trace` into the user's program |
| FIX | `collector.py:413` | `functools.cache` on a method retains every `Collector` forever — and measured `hits=0`, because `self` is in the key, so it never functions as a cache at all. Twin `data.py:175` uses a call-scoped local |
| FIX | 5 sites | `env-flag-parsed-as-strict-int`: `COVERAGE_SYSMON_LOG=true` — or **empty** — breaks `import coverage`, then `pth_file.py:13`'s bare `except:` swallows it, so subprocesses contribute zero data silently |
| CONSIDER | `jsonreport.py:83`, `sqldata.py:368` | Naive `datetime.now()` into a versioned JSON format and a documented SQLite schema. Two runs 3600s apart across a DST fall-back produce byte-identical timestamps; the HTML backend gets it right via `misc.py:288-290` |
| CONSIDER | `control.py:654` | `atexit.register(self._atexit)` with `atexit.unregister` nowhere; 5/5 `Coverage` objects survive `del` + `gc.collect()`. Twin eight lines below saves and restores the SIGTERM handler |
| CONSIDER | `control.py:803-848` | `clear_exclude(which="partial_branches")` silently creates a phantom `config.partial_branches_list`; you can add regexes and read them back and coverage.py never uses it — fully consistent fictional feedback |

## Systemic root

**`one-concern-implemented-per-backend` is this codebase's dominant defect generator.** Two agents
inventoried it independently: 19 of 31 concerns are per-backend rather than shared, and only 2 of 13
report concerns live in the shared driver. Measured consequences at HEAD: six report formats emit
**1 / 1 / 3 / 3 / 4 / 4 rows** for one data file; `--fail-under` on a zero-statement project exits
**0** from `report` and **2** from xml/json/lcov/html and never gates for `annotate`; `--sort` is
honoured by 1 of 6.

The proposed fix is one change, not eleven: a `BaseReporter` lifecycle plus a single
`total_for_gate()` would retire CRF-COVPY-0010, -0032, -0043 and two novel findings across six files.

---

## TOOLKIT DEFECT FOUND BY THIS RUN — fixed and pushed (`36d0976`)

**`check_typing.py` reported `0 type errors` while mypy reported 3.**

`FORCE_COLOR=3` is set in this environment. mypy honours it even when stdout is a pipe, and the ANSI
codes land between the `file:line:` prefix and `error:` — so `_LINE` stopped matching and **every
finding was dropped**, while the summary line still parsed because its regex only needs the digits.

It lost precisely the defect the script exists to find (V5 above), on the project where that
capability was originally validated. Fixed four ways: `--no-color-output`, a `FORCE_COLOR=0`
subprocess environment, a defensive ANSI strip, and — the durable one — **a cross-check of the parsed
count against mypy's own "Found N errors", reported as `FAILED` with a `parse_mismatch` reason when
they disagree.** The script had the right number in `stats["errors"]` the whole time and reported the
smaller one. Same class as D-13, same fix.

## Other scanner defects reported by agents

- `collect_debt.py` ignores `.git-blame-ignore-revs`. coverage.py ships one, and `82467f72`
  (`ruff format .`) absorbs 31 blames — **32 of 51 markers were in the wrong age bucket**.
- `collect_debt.py` counts suppression comments as debt in a repo that gates
  `warn_unused_ignores` + `useless-suppression` in CI, where the true actionable suppression debt is 0.
- `correlate_tests.py`'s 39.7% is wrong three ways (non-source in the denominator, phantom matches in
  the numerator, summary disagreeing with its own detail rows: `13` vs `42` skips, `669` vs `1170`
  methods). Corrected: **72.7% of modules, 86.9% of statements.**
- `unvalidated-numeric-from-environment` needs a numeric-use test; its `detail` for `sysmon.py:50,53`
  is factually wrong.
- `scan_python_pitfalls`'s `coverage/`-only scope missed the run's only true `zip` instance, in `tests/`.

## PROCESS DEFECT — mine

I gave **all 16 agents the same scratch path**, `/tmp/covrepro`. One agent found another's
`builtins.EV` instrumentation inside it, rebaselined, and re-verified its citations — and warned in
its report that any "left-in debug code in pytracer.py" from another agent would be scratch
contamination, not a finding.

Triage rule 7 worked: the real tree is clean at `6b3259ab`, 0 modified, and all 12 agents so far
confirmed unprompted that they worked on a copy. But I recreated the exact hazard rule 7 exists to
prevent, one directory over. **The rule needs to be a per-agent scratch dir** — `/tmp/covrepro-$AGENT`
— not one shared path, and that belongs in the briefing next to the `git archive` recipe.

## Workflow note

The pattern-consistency agent reported that `agent-architecture-mapper.md` **did not exist at any
point during its run**. Phase 1 output is supposed to feed Phase 2, and dispatching them in parallel
to save wall-clock silently removed that input. Either serialise Phase 1, or stop telling Phase 2
agents to read it.
