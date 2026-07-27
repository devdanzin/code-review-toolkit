# Tech-debt inventory — coverage.py (informed pass)

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Briefing read:** `reports/coveragepy_v3/briefings/tech-debt-inventory.md` — 60 catalogued findings confirmed-not-relitigated.
**Pre-collected data used:** `reports/coveragepy_v3/collect_debt.json` (51 markers / 17 files).

**Did I edit the tree? No.** Every command against `/home/danzin/projects/coveragepy` was read-only (`grep`, `sed -n`, `git blame`, `git log`, `git show`). All execution happened in `/tmp/covrepro`, created with
`git -C /home/danzin/projects/coveragepy archive HEAD | tar -x -C /tmp/covrepro`, plus a throwaway config dir `/tmp/covglob`. The subagent dispatched for the pins audit was given the same prohibition and reported read-only throughout.

---

## 0. Correction to the pre-collected data — read this first

Two corrections change what the 51 markers mean.

### 0.1 The age distribution in `collect_debt.json` is an artifact of a `ruff format` sweep

coverage.py ships `/home/danzin/projects/coveragepy/.git-blame-ignore-revs`, listing 13 mass-mechanical commits. One of them is `82467f72` — *"2025-08-21 chore: `ruff format .`"*. Plain `git blame` attributes 31 of the 51 markers to that single day. The collector used plain blame.

Re-blaming all 51 with `--ignore-revs-file .git-blame-ignore-revs -w`:

| bucket | collect_debt.json | corrected |
|---|---|---|
| fresh | 3 | **2** |
| growing | 0 | **0** |
| stale | 36 | **5** |
| ancient | 12 | **44** |

**32 of 51 markers land in a different bucket.** The dangerous direction appears too: `coverage/sysmon.py:466` is reported **fresh, 2026-07-12** and is actually **2025-03-20** — a 16-month-old suppression presented as this month's.

*Actionable for the toolkit, not for coverage.py:* `collect_debt.py` should honour `.git-blame-ignore-revs` when the repo has one. Any inventory that ranks by age is otherwise ranking formatting commits.

### 0.2 47 of the 51 markers are `type: ignore` — briefing FP class 35 applies, re-verified at HEAD

Not taken on faith:

- `pyproject.toml:26` — `warn_unused_ignores = true`, still set.
- `tox.ini:130` — `mypy --python-version=3.14 --strict {env:TYPEABLE}`.
- `.github/workflows/quality.yml:96,122-124` — a required `mypy` job runs that tox env.
- The tell that the maintainer actively curates ignores: `coverage/sqlitedb.py:72` reads `# type: ignore[attr-defined, unused-ignore]` — the second code exists precisely so the ignore is legal on the versions where it *is* unused.

**Verdict for all 47: wish-not-debt / machine-verified live.** Marker age carries zero signal here regardless of what the corrected dates say.

**The same argument extends to pylint,** which the briefing does not cover: `pyproject.toml:64` enables `useless-suppression`, so the 48 `# pylint: disable=` comments in the package are equally machine-gated. Suppression debt in this project is **0 items**, not 95.

### 0.3 The one `PRAGMA_NO_COVER` marker is a false positive

`coverage/annotate.py:33` — `-     if 0:   #pragma: no cover` — sits inside the `AnnotateReporter` class docstring, illustrating what a `.py,cover` file looks like. Not a pragma. (`coverage/config.py:151,158` are likewise regex *literals* in `DEFAULT_EXCLUDE`, correctly not collected.)

**The shipped package contains zero real `# pragma: no cover`.** It uses a private vocabulary defined in `metacov.ini` instead — see §3, which is where the pragma debt actually is.

### 0.4 What the collector missed

`grep` over `coverage/` finds two markers outside the collector's regexes, both false positives worth recording so nobody chases them: `coverage/html.py:487` (`\uXXXX` in prose) and `coverage/ctracer/tracer.c:835` (`const char * w = "XXX ";`, a log prefix).

---

## 1. Master table — age-sorted, corrected blame

Only items with a verdict other than "machine-verified live suppression". The 47 `type: ignore` markers are aggregated in §6.

| # | file:line | corrected blame | age | kind | verdict |
|---|---|---|---|---|---|
| A | `coverage/parser.py:807` | 2017-01-18 | ancient | `pragma: debugging` | still true |
| B | `coverage/parser.py:193` | 2017-01-19 | ancient | `pragma: debugging` | still true |
| C | `metacov.ini:53` (`pragma: not testing`) | 2017-01-19 | ancient | dead exclusion rule | **resolved, delete the rule** |
| D | `metacov.ini:73` (`pragma: obscure`) | 2018-02-22 | ancient | dead exclusion rule | **resolved, delete the rule** |
| E | `coverage/parser.py:620` | 2018-10-05 | ancient | `TODO` | **still true but orphaned — see 2.1** |
| F | `coverage/control.py:794` | 2019-12-22 | ancient | `pragma: part started` | still true |
| G | `coverage/parser.py:980,986,998` | 2021-05-31 | ancient | `pragma: always breaks` | **inconsistent with sibling `:991` — see 3.3** |
| H | `coverage/misc.py:273` | 2021-10-08 | ancient | `pragma: always breaks` | still true (narrow) |
| I | `coverage/collector.py:425,428` | 2021-10-14 | ancient | `pragma: part covered` / `cant happen` | **NO LONGER TRUE — see 3.2** |
| J | `coverage/control.py:761,762` | 2022-01-23 | ancient | `pragma: not covered` | still true |
| K | `coverage/files.py:375` | 2022-11-08 | ancient | `pragma: always breaks` | **FALSE — reproduced infinite loop, see 3.1** |
| L | `coverage/collector.py:432` | 2023-01-01 | ancient | `pragma: cant happen` | **NO LONGER TRUE — see 3.2** |
| M | `coverage/parser.py:925` | 2023-02-09 | ancient | `pragma: only failure` | **NO LONGER TRUE — reproduced, see 3.4** |
| N | `coverage/report_core.py:68` | 2023-05-13 | ancient | `pragma: part covered` | still true |
| O | `coverage/sysmon.py:196-197` | 2023-11-10 | ancient | `TODO` | **still true — see 2.2** |
| P | `coverage/sysmon.py:202-203` | 2023-11-10 | ancient | `TODO` | **still true — see 2.3** |
| Q | `coverage/lcovreport.py:65-68,78` | 2024-10-02 | ancient | pinned workaround (PyPy 3.8) | **resolved — interpreter below the floor** |
| R | `coverage/env.py:39-41` (`PYPYVERSION`) | 2025-08-23 | stale | dead-ish constant | wish, not debt (debug-only) |
| S | `coverage/debug.py:123` | 2025-08-12 | stale | `pragma: never called` | still true |
| T | `coverage/execfile.py:94-99` | 2026-07-02 | fresh | version gate, self-dating | **exemplary — no action** |

---

## 2. Markers that name a real, still-live defect

### 2.1 `coverage/parser.py:620` — the last survivor of a 2018 TODO block, now orphaned  · **NOVEL** · shape `incomplete-fix-residue-at-an-answered-todo`

```
# TODO: Shouldn't the cause messages join with "and" instead of "or"?
```

Commit `04ff1883` (2018-10-05) added **three** TODOs as one block directly above `class AstArcAnalyzer`. Two have since been answered and removed, both on the same day:

- *"the cause messages have too many commas"* → `773f8da4` (2024-05-30) *fix(english): don't over-use commas in missing branch descriptions*
- *"some add_arcs methods here don't add arcs, they return them. Rename them."* → `6ae9363a` (2024-05-30) *refactor: rename functions and add docs to clarify parser.py*

The third was left. Then `cb7c59ae` (2026-07-06, Paul Kehrer) inserted `_STMT_CONTAINERS` / `walk_statement_nodes` immediately below it — pure AST-walking code with nothing to do with cause messages. **The comment now floats at module scope attached to unrelated code, 172 lines away from the thing it asks about** (`parser.py:448`, `return " or ".join(msgs)`).

**Verdict: the question is still literally unanswered** (the join is still `" or "`), but it is a **wish, not debt** — a maintainer's open English question, not a defect. The *debt* is the orphaning: a reader at `parser.py:620` cannot tell what "the cause messages" refers to. **Action:** move it onto `missing_arc_description` at `parser.py:431`, or drop it as its two siblings were dropped.

### 2.2 `coverage/sysmon.py:196-197` — still true · **CATALOGUED**, confirms `CRF-COVPY-0046`

```
# TODO: should_start_context and switch_context are unused!
# Change tests/testenv.py:DYN_CONTEXTS when this is updated.
```

**Still exactly true at HEAD.** `grep` over `coverage/sysmon.py` finds `should_start_context` / `switch_context` at lines 198-199 only — assigned in `__init__`, never read. The guarded twin is `coverage/pytracer.py:190-196, 307-309`, which reads both and drives dynamic contexts from them. The confession clause is honoured: `tests/testenv.py:37` reads `DYN_CONTEXTS = C_TRACER or PY_TRACER`, switching the tests off for sysmon — which is the default core on 3.14+ (`coverage/env.py:56`).

Confirms `CRF-COVPY-0046` and abuts `CRF-COVPY-0050`. No new claim.

### 2.3 `coverage/sysmon.py:202-203` — still true, and it is the *root* of three catalogued findings · **NOVEL framing**, extends `CRF-COVPY-0003`

```
# TODO: warn is unused.
self.warn: TWarnFn
```

**Still exactly true.** `self.warn` is declared and never called anywhere in `sysmon.py`. `coverage/collector.py:258` assigns `tracer.warn = self.warn` unconditionally, so the channel is wired up and dead on arrival.

This is the third site of one root, and the briefing catalogues the other two separately without connecting them:

| backend | has a `warn` member | calls it |
|---|---|---|
| `PyTracer` | yes | yes — `pytracer.py:352-357`, `slug="trace-changed"` |
| `CTracer` | yes | **no** — `CRF-COVPY-0003`, `ctracer/tracer.c:1055` |
| `SysMonitor` | yes | **no** — this TODO, self-confessed since 2023-11-10 |

**Concrete failure scenarios enabled by the dead channel, both already catalogued as symptoms:**

1. `sysmon.py:253` — `raise RuntimeError("No sys.monitoring tool id is available")` when ids 0-5 are all taken. With a live `warn` this would be a warning plus a fallback to `PyTracer`; instead it is a hard crash outside the project exception hierarchy (`CRF-COVPY-0042`).
2. A second tool taking the id, or a nested `Coverage`, silently truncates data with no user-visible message (`CRF-COVPY-0005`) — precisely the condition `PyTracer` *does* warn about.

**Action:** `CRF-COVPY-0003` should be widened from "CTracer never calls warn" to "two of three backends never call warn"; the fix is one shape at two sites.

---

## 3. `no cover`-family pragma audit — the highest-yield section

coverage.py's own testability statements live in `metacov.ini` `[report] exclude_lines` / `partial_branches`, not in `# pragma: no cover`. 33 sites in the shipped package. Four verdicts of interest.

### 3.1 `coverage/files.py:375` — `pragma: always breaks` is FALSE; **reproduced infinite loop** · **NOVEL** · FIX

```python
while pos < len(pattern):
    for rx, sub in G2RX_TOKENS:  # pragma: always breaks
        if m := rx.match(pattern, pos=pos):
            ...
            pos = m.end()
            break
```

Blame **2022-11-08**. The claim rests on `G2RX_TOKENS`' final catch-all, `coverage/files.py:361`: `(r".", r"\\\g<0>")`. **`.` does not match `\n`** and the pattern is compiled without `re.DOTALL`. For a glob containing a newline, every token fails, the `for` completes without `break`, `pos` never advances, and the `while` spins forever. There is no error and no exit — a hang, not an exception.

Reproduced at HEAD in `/tmp/covrepro` (never in the target tree):

```
$ timeout 8 python3 -c "from coverage.files import _glob_to_regex; _glob_to_regex('a\nb')"
EXIT=124        # normal case: _glob_to_regex('a*.py') -> (.*[/\\])?a[^/\\]*\.py
```

Reachable from ordinary user config. With `pyproject.toml` containing `omit = ["a\nb"]`, `Coverage().start()` hangs, faulthandler stack:

```
File ".../coverage/files.py", line 375 in _glob_to_regex
File ".../coverage/misc.py", line 127 in join_regex
File ".../coverage/files.py", line 409 in globs_to_regex
File ".../coverage/files.py", line 328 in __init__          # GlobMatcher
File ".../coverage/inorout.py", line 282 in __init__
File ".../coverage/control.py", line 641 in _init_for_start
File ".../coverage/control.py", line 699 in start
```

Same via the public API: `globs_to_regex(['a\nb'])`. **The `always breaks` pragma is what kept the fallthrough from ever showing up as an unmeasured branch in coverage.py's own metacov.** Fix: add `re.DOTALL`, or `else: raise ConfigError(...)` on the `for`.

*Failure scenario:* a user hand-edits `omit` in `pyproject.toml` and a stray line break lands inside a quoted string. Every subsequent `coverage run` hangs with no output, no CPU-bound clue in the traceback, and no error. On CI this is a job timeout attributed to the test suite.

### 3.2 `coverage/collector.py:425-434` — `pragma: cant happen` on the free-threaded failure path · **NOVEL angle**, same root as `CRF-COVPY-0052` · CONSIDER

```python
# The call to list(items()) ensures that the GIL protects the dictionary
# iterator against concurrent modifications by tracers running
# in other threads. ...
for _ in range(3):                              # pragma: part covered
    try:
        items = list(d.items())
    except RuntimeError as ex:                  # pragma: cant happen
        runtime_err = ex
    else:
        break
else:                                           # pragma: cant happen
    assert isinstance(runtime_err, Exception)
    raise runtime_err
```

Blame **2021-10-14** / **2023-01-01** — both predate free-threading. `CRF-COVPY-0052` already flags the GIL comments at `collector.py:420-423, 453-459` as `doc-describes-a-superseded-model`. The new observation is that the superseded model is not only documented, it is **encoded as a coverage exclusion**: the project asserts to its own tooling that the free-threaded failure path cannot execute.

coverage.py ships free-threaded wheels (`setup.py:75`, `Programming Language :: Python :: Free Threading :: 3 - Stable`) and knows it (`coverage/env.py:48`, `FREE_THREADED`). On such a build `list(d.items())` is not atomic; `RuntimeError: dictionary changed size during iteration` is exactly what a concurrent tracer produces. `mapped_file_dict` is called from `flush_data` (`collector.py:485,491`) while tracers are live, reached from `Coverage.save()` (`control.py:932`).

*Failure scenario:* a free-threaded 3.14+ process with 8 worker threads calls `cov.save()` while they are still executing. Three consecutive `list(d.items())` all raise; the `else:` re-raises a bare `RuntimeError` out of `save()`. That path has never been measured, because `pragma: cant happen` excludes it. Same root as `CRF-COVPY-0012`.

**Action:** the two `cant happen` pragmas should become `pragma: cant happen` only under `if env.GIL`, or be dropped and the path tested.

### 3.3 `coverage/parser.py:980,986,991,998` — three of four siblings carry the pragma · **NOVEL** · CONSIDER

Four structurally identical functions:

```python
def process_break_exits(self, exits):    for block in self.nearest_blocks():  # pragma: always breaks
def process_continue_exits(self, exits): for block in self.nearest_blocks():  # pragma: always breaks
def process_raise_exits(self, exits):    for block in self.nearest_blocks():        <-- no pragma
def process_return_exits(self, exits):   for block in self.nearest_blocks():  # pragma: always breaks
```

All four added 2021-05-31. Either the loop always breaks — in which case `:991` is missing the pragma and permanently reports as a partial branch in metacov — or it does not, in which case the other three pragmas are wrong. It cannot be both. `fix-not-propagated-to-sibling-path`, in the coverage metadata rather than the code. Mechanically verifiable, one-line fix either way.

### 3.4 `coverage/parser.py:925` — `pragma: only failure` is FALSE; **reproduced** on PEP 695 source · **NOVEL** · CONSIDER

```python
if env.TESTING:
    if node_name not in self.OK_TO_DEFAULT:
        raise RuntimeError(f"*** Unhandled: {node}")  # pragma: only failure
```

`metacov.ini:59-61` glosses `only failure` as *"These lines only happen if tests fail."* That is no longer true. `ast.TypeAlias` (PEP 695, Python 3.12+) has **no `_handle__TypeAlias`** (`parser.py:1013-1211` lists handlers for Break/Continue/For/If/Match/Raise/Return/Try/TryStar/While/With) and is **not in `OK_TO_DEFAULT`** (`parser.py:881-893`).

Reproduced at HEAD in `/tmp/covrepro`, on `type Alias = int` at module level **and** inside a function:

```
RuntimeError: *** Unhandled: TypeAlias(name=Name(id='Alias', ctx=Store()), type_params=[], value=Name(id='int', ctx=Load()))
  coverage/parser.py:925 in node_exits  <- coverage/parser.py:967 in process_body <- :779 _code_object__Module
```

Without `COVERAGE_TESTING=True` the same file reports cleanly at 100% — the node silently falls through to `arc_starts = {ArcStart(self.line_for_node(node))}`.

**The guarded twin is in the same project:** `coverage/phystokens.py:104` handles `ast.TypeAlias` explicitly, version-gated. The AST arc analyzer never got the matching entry. The one PEP 695 fixture in the suite, `tests/test_phystokens.py:222` (`type Point = tuple[float, float]`), exercises the *tokenizer* path — the handled one — and never the analyzer. `grep` finds no other PEP 695 test anywhere in `tests/`.

*Failure scenario:* the self-check that is supposed to catch "we overlooked a node type" has been blind to it since Python 3.12 shipped (2023-10), and the `pragma: only failure` exclusion is what stopped the reachable-raise from ever registering as an unmeasured line. **Fix:** add `"TypeAlias"` to `OK_TO_DEFAULT`. One word.

### 3.5 The rest — still true

`pragma: debugging` ×15 (all behind `if LOG:` / `if self.debug:` / `if dump_ast:` / `COVERAGE_DEBUG_CALLS`), `control.py:761-762` `not covered` (post-`os.kill` SIGTERM re-raise), `control.py:743` `nested`, `control.py:794` `part started`, `core.py:34` `part covered`, `report_core.py:68` `part covered`, `html.py:192` `part covered`, `pth_file.py:5` `exclude file`, `misc.py:273` `always breaks`.

`coverage/debug.py:123` — `yield  # pragma: never called` on `NoDebugging.without_callers` — **still true**, checked rather than assumed: the sole caller is `control.py:422` inside `_write_startup_debug`, reached only from `_post_init` (`control.py:410-412`), which always runs after `_init()` has replaced `self._debug` (`control.py:295` → `:377`) with a real `DebugControl`.

### 3.6 Two exclusion rules are dead across the whole repo

| rule | defined | last use removed |
|---|---|---|
| `metacov.ini:53` `pragma: not testing` | 2017-01-19 | `9ea349a1` (2025-08-24) |
| `metacov.ini:73` `pragma: obscure` | 2018-02-22 | `c0921466` (2021-02-06) |

Zero occurrences repo-wide. `pragma: obscure`'s own comment — *"Obscure bugs in specific versions of interpreters, and so probably no longer tested"* — has outlived its last use by five years. `pragma: partial metacov` (`metacov.ini:95`) has 0 uses in the package and 2 in `tests/`.

---

## 4. Version-gated compatibility branches — floor is Python 3.10

`setup.py:225` — `python_requires=">=3.10"`. **No dead branch found.** Every gate in the package targets 3.11+, 3.12+, 3.14+ or 3.15+ and is live:

| site | gate | status |
|---|---|---|
| `coverage/tomlconfig.py:20` | `>= (3, 11, 0, "alpha", 7)` | live; expires with 3.10, paired with `setup.py:197` |
| `coverage/pytracer.py:40-48` | `RESUME is None` ⇒ pre-3.11 | live on 3.10 / PyPy only; `YIELD_VALUE`/`YIELD_FROM`/`YIELD_FROM_OFFSET` all die with 3.10 |
| `coverage/phystokens.py:104` | `>= (3, 12)` `ast.TypeAlias` | live |
| `coverage/phystokens.py:106` | `>= (3, 15)` lazy imports | live, forward-looking |
| `coverage/env.py:98,101,110,113,118` | 3.12.6 / 3.12 / ≠3.13 / 3.14 / >3.14.0a5 | all live |
| `coverage/execfile.py:94-99` | `safe_path` vs `isolated` | live |
| `coverage/collector.py:286` | note only, `settrace_all_threads` new in 3.12 | live note |

`coverage/phystokens.py:99` handles `ast.Match` with **no** gate — correct, since `ast.Match` is 3.10+; evidence the 3.9-era gate was cleaned up properly when the floor moved.

**One resolved gate to remove**, in-package: `coverage/lcovreport.py:65-68` + guard `and region.lines` at `:78`, blame 2024-10-02 — *"avoids a crash due to a bug in PyPy 3.8"*. PyPy 3.8 implements Python 3.8, below the 3.10 floor; it cannot install this coverage at all. **Verdict: resolved, delete the guard or requalify the comment.**

**Exemplary, keep as the house pattern:** `coverage/execfile.py:94-99` writes its own expiry into the comment — *"Remove the isolated fallback when coverage drops 3.10 support."* Note it is spelled `PYVERSION`, not `PYVERSIONS`, so the release checklist's grep misses it — `CRF-COVPY-0058`, confirmed still live here and at `coverage/phystokens.py:98`.

`coverage/env.py:39-41` `PYPYVERSION` and `:44` `GIL` have no logic consumer anywhere in the repo, but `env.debug_info()` (`env.py:132-135`) enumerates module globals, so both surface in `coverage debug sys`. **Wish, not debt** — debug-output values, and the `# type: ignore[attr-defined]` on `:39` is legitimate. The comment *"Minimum now is 7.3.16"* enforces nothing, which is the only soft spot.

---

## 5. Pinned workarounds whose upstream bug is fixed

`requirements/pins.pip` holds exactly **one** pin — the maintainer actively prunes (`git log`: "build: unpin tox", "build: remove gevent pin"). The debt lives in `.in` comments and skip reasons. In-package first, then the wider repo (outside the nominal `coverage/` scope, included because the brief asked for the category).

**In `coverage/`:**

| file:line | date | reason | verdict |
|---|---|---|---|
| `coverage/lcovreport.py:65-68,78` | 2024-10-02 | PyPy 3.8 empty-lines crash | **resolved — below the 3.10 floor** |
| `coverage/lcovreport.py:70,73,74` | 2024-10-02 | pylint#9923 spurious `nested-min-max` | still needed — issue **open** |
| `coverage/env.py:106-110` + `coverage/ctracer/util.h:59-63` | 2025-08-20 / 2024-08-08 | cpython#113728 `f_lasti` on 3.13 | still needed — closed as a *semantics clarification*, not backported; 3.13 is in `tox.ini:7` |

**Outside `coverage/` (repo-level, for completeness):**

| file:line | date | reason | verdict |
|---|---|---|---|
| `doc/conf.py:246-247` | 2020-08-18 | sphinx-tabs#54 | **dead** — project moved to `sphinx_code_tabs` (`doc/conf.py:44`, `7f71de6d`, 2023-05-30); `sphinx-tabs` is in no requirements file, so the setting configures an unloaded extension |
| `tests/test_process.py:1061-1065` | 2024-02-27 | packaging#678, "setuptools barfs on dev versions" | **upstream fixed** — packaging#802 shipped in **24.1 (2024-06-10)**; `test_bug_862` still skips on every `X.Y.Z+` build |
| `requirements/tox.in:12-16` | 2022-08-15 | copies tox's Windows-only colorama marker | **dead** — tox now depends on `colorama>=0.4.6` unconditionally |
| `.github/workflows/quality.yml:64-67` | 2020-12-31 | pylint#3489 OS-dependent results | still needed, but **WONTFIX** (closed 2022-06-30 "working as intended"); reword so nobody re-checks annually |
| `requirements/pytest.in:15-19`, `requirements/kit.in:16-20` | 2022-08-15 | colorama markers | still needed, **stale citations** — both cited `setup.cfg#Lnn` URLs now 404 |
| `tests/conftest.py:60-68` | 2023-10-03 | cpython#105539 | still needed — 105539 *added* the warning; there is no fix to wait for |
| `tox.ini:23` | 2021-11-23 | *(none)* | **reasonless** — undocumented `py3{10-14}` ceiling on gevent testing that drifts as envlist grows |
| `tests/test_process.py:700` | 2021-05-01 | "PyPy is unreliable with this test" | unverifiable — no ref, no bound, 5-year blanket skip |

Reasonless pins by count: 236 hash-pinned `.pip` lines (uv-generated, not debt), 4 `rev:` pins in `.pre-commit-config.yaml` (auto-updated, but pre-commit is **not** wired into CI — only `make precommit` — so they drift unobserved), 17 SHA-pinned GitHub actions (deliberate supply-chain policy).

---

## 6. Low-priority aggregate

| category | count | disposition |
|---|---|---|
| `type: ignore` | 47 / 17 files | **0 actionable** — `warn_unused_ignores` + gated `mypy --strict` (§0.2) |
| `pylint: disable` | 48 | **0 actionable** — `useless-suppression` enabled (`pyproject.toml:64`) |
| `noqa` | 0 | — |
| `fmt: skip` / `fmt: off` | 16 | formatting intent, not debt |
| `TODO` | 3 | all still true; 2 are live-defect markers (§2.2, §2.3), 1 orphaned wish (§2.1) |
| `FIXME` / `HACK` / `XXX` / `WORKAROUND` | 0 real | 2 grep false positives (§0.4) |
| real `# pragma: no cover` | 0 | vocabulary is private (§3) |

---

## 7. Recommendations, by impact

1. **`coverage/files.py:361`** — add `re.DOTALL` (or an `else: raise ConfigError`) to the glob tokenizer. A newline in an `omit`/`include` pattern hangs `Coverage.start()` forever, reproduced at HEAD. The `pragma: always breaks` at `:375` is why it was never visible; remove or correct it.
2. **`coverage/parser.py:893`** — add `"TypeAlias"` to `OK_TO_DEFAULT`. One word closes a self-check that has been blind to PEP 695 since 3.12 and whose `pragma: only failure` at `:925` is now a false claim.
3. **`coverage/collector.py:428,432`** — drop or `env.GIL`-condition the two `pragma: cant happen`. The project ships free-threaded wheels; the excluded path is the free-threaded failure path. Pairs with `CRF-COVPY-0052` / `CRF-COVPY-0012` as one change.
4. **Widen `CRF-COVPY-0003`** to cover `coverage/sysmon.py:202-203`. Two of three backends have a dead `warn` member; the self-confessed TODO has been accurate for 2.7 years and is the root of `CRF-COVPY-0005` and `CRF-COVPY-0042`.
5. **Delete four provably dead items in one sweep:** `metacov.ini:53` (`pragma: not testing`, 0 uses), `metacov.ini:73` (`pragma: obscure`, 0 uses since 2021), `coverage/lcovreport.py:78` PyPy-3.8 guard (below the 3.10 floor), and `doc/conf.py:246-247` (configures an extension no longer installed). Add `tests/test_process.py:1061-1065` once a `+`-suffixed dev-build run confirms packaging 24.1.

**POLICY:** the age signal in any future debt scan must honour `.git-blame-ignore-revs` (§0.1), and in a repo that gates `warn_unused_ignores` + `useless-suppression`, suppression count is not a debt metric at all.
