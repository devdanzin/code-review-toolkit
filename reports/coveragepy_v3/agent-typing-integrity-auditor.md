# Type integrity — coverage.py @ `6b3259ab`

**Agent:** `typing-integrity-auditor` (informed pass) · **Target:** `/home/danzin/projects/coveragepy` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110`

**Tree edits: NONE.** The target tree was never written to. Verified after the run: `git log -1` is still
`6b3259ab`, `git diff --stat` is empty, and the only untracked paths (`ctracer_repros/`, `repro.py`,
`ctracer_review_*.md`) predate this agent and belong to other agents in the pipeline. All experiments ran on
private `git archive` copies under `/tmp/covrepro_typing`, `/tmp/cov_noignore`, `/tmp/cov_fixed`,
`/tmp/cov_tomlfix`, `/tmp/cov_staleprobe`.

> **Environment note (one collision, disclosed):** the briefing named `/tmp/covrepro` as the scratch path. I
> `rm -rf`'d and re-extracted it at the start of this run, and a `build/` tree appeared and vanished inside it
> during the session — that directory is in **concurrent use by another agent**. I moved to a private path
> immediately. If another agent reports a mid-run file disappearance in `/tmp/covrepro`, that was me.

---

## Headline

**The `check_typing.json` on file for this project is a vacuous clean result, and I can prove it.**

The recorded run reports `status: OK`, `45 files_checked`, `phantom_imports: 0`, `strict_pass_ran: true`.
Re-running the identical command with one environment variable removed yields **3 phantom-import errors**, all in
`coverage/html.py`. The catalogued defect **CRF-COVPY-0018 is not gone — it is still live at `coverage/html.py:42`,
and the tool that exists to find it reported zero.**

Root cause: `FORCE_COLOR=3` is set in this shell environment. mypy honours `FORCE_COLOR` and emits ANSI escapes
even into a pipe. `check_typing.py`'s per-line regex (`_LINE`, line 93) anchors on `^(?P<file>.+?):(\d+)...:
(error|warning|note): ` and does not survive an escape sequence before `error:`, so **every finding is silently
dropped** — while `_SUMMARY`/`_CLEAN` use `.search()` and still match inside the coloured line, so
`files_checked` is populated and `status` stays `OK`. The failure is invisible by construction: a run that
analysed everything and reported nothing.

```
$ mypy --config-file pyproject.toml --disallow-any-unimported coverage      # 3 errors, always
$ python check_typing.py coverage                                          # phantom_imports: 0   <-- FORCE_COLOR=3
$ env -u FORCE_COLOR python check_typing.py coverage                       # phantom_imports: 3
```

This is exactly the failure mode the agent exists to prevent (`pyrefly` reporting `0 errors` on a tree its config
excluded), occurring inside the agent's own tooling. **Fix for the toolkit:** `_run_mypy` should pass
`env={**os.environ, "MYPY_FORCE_COLOR": "0", "FORCE_COLOR": "0", "TERM": "dumb"}`, or `_LINE` should strip
`\x1b\[[0-9;]*m` before matching. A cheap invariant is stronger still: if `stats["errors"] > 0` and
`len(findings) == 0`, that is a FAILED run, not a clean one.

---

## Phase 1 — Is the clean result real, and what does the config exclude?

**Yes, the baseline is real — but the audited scope was 31% of what the project itself gates.**

`/home/danzin/projects/coveragepy/pyproject.toml:10` `[tool.mypy]`, used as-is:

| Setting | Value | Consequence for this audit |
|---|---|---|
| `exclude` | `^tests/.*_plugin\.py$` | Matches exactly **one** file: `tests/select_plugin.py`. Nothing else is excluded. |
| `ignore_missing_imports` | `true` | **The enabler.** An import that resolves to nothing becomes `Any` with no diagnostic. |
| `follow_imports` | `"silent"` | Errors *inside* a followed-but-not-targeted module are suppressed. Harmless when the whole package is a direct target; it is what makes a narrowed scan under-report. |
| `warn_unused_ignores` | `true` | **Stale ignores ARE measurable here.** See Phase 4. |
| `ignore_errors` | *absent* | No module is silently skipped. |
| per-module `[[tool.mypy.overrides]]` | *none* | No hidden relaxations. |
| `check_untyped_defs`, `disallow_untyped_defs`, `disallow_incomplete_defs`, `disallow_untyped_calls`, `disallow_untyped_decorators`, `disallow_any_generics`, `disallow_subclassing_any`, `no_implicit_optional`, `warn_redundant_casts`, `warn_return_any`, `warn_unreachable` | all `true` | Annotation coverage is enforced, not optional. |

- **`45 files` is honest.** `coverage/` holds 44 `.py` files plus `coverage/tracer.pyi`. Nothing was skipped.
- **`45` is also not the project's gate.** `tox.ini:117-130` runs
  `mypy --python-version=3.14 --strict coverage tests setup.py` (`TYPEABLE=coverage tests setup.py`). That is
  **145 source files**. The recorded audit covered `coverage/` only — 100 gated files were never looked at.
  I ran the project's own command: **`Success: no issues found in 145 source files`.** Genuinely clean.
- **`--strict` is stricter than the config file.** `--strict` adds `no_implicit_reexport`, `strict_equality` and
  `extra_checks`, which are *not* in `[tool.mypy]`. A config-only run is therefore *weaker* than the project's CI
  bar. (Here it makes no difference — both are clean — but the toolkit's "use the project config as-is" rule
  under-approximates any project whose CI adds flags on the command line. Worth reading `tox.ini` before
  claiming the config is the baseline.)
- **Version skew, disclosed:** `requirements/mypy.pip` pins **`mypy==2.1.0`**; every number in this report was
  produced with **mypy 1.20.2** (the only build available here). Findings that depend on a specific diagnostic
  firing should be re-confirmed under 2.1.0.
- **The whole-repo `status: FAILED` was a scratch-directory artefact, not a project defect.** The
  `Duplicate module named "coverage"` came from an untracked, `.gitignore`d `build/lib.linux-x86_64-cpython-314/`
  left by a local `setup.py build`. The project never hits it because its own invocation names explicit targets.
  Reproduced and confirmed; no action for coverage.py.

---

## Phase 2 — Type defects the checker can prove (2)

Under the project's own gate the baseline is **0 errors**. These two are defects the checker *would* prove but is
prevented from reporting — the whole point of this pass.

| File:line | Code | What is actually wrong |
|---|---|---|
| `coverage/sysmon.py:410, :413, :440, :466, :476` | `union-attr` ×6 (suppressed) | mypy proves `code_info` is `CodeInfo \| None` and is dereferenced unguarded. A bare `# type: ignore` erases the proof. **Machine confirmation of CRF-COVPY-0022.** See F3. |
| `coverage/tomlconfig.py:150-152` | `no-any-return` (masked by `-> Any`) | The only getter in `TomlConfigParser` that neither validates nor is type-checked. Reproduced end-to-end as an `AttributeError` traceback. See F5. |

---

## Phase 3 — Phantom imports (3 errors, 1 import) — annotations that stopped checking

| File:line | Import | Correct name | Annotations affected |
|---|---|---|---|
| `coverage/html.py:42` | `from coverage.plugins import FileReporter` | `coverage.plugin` (singular) | `html.py:134` `data_for_file(self, fr: FileReporter, ...)`, `html.py:231` `FileToReport.__init__(self, fr: FileReporter, ...)`, `html.py:815` `can_skip_file(self, data, fr: FileReporter, rootname)` |

**F2 · CRF-COVPY-0018 — CONFIRMED STILL LIVE.** [FIX]

`coverage/plugins` does not exist; the module is `coverage/plugin.py`. The import sits inside `if TYPE_CHECKING:`
so there is no runtime error, and `ignore_missing_imports = true` swallows the diagnostic, so the name silently
becomes `Any`. Three annotations stopped checking anything.

**Guarded twin — 14 of them.** Every other module in the package spells it correctly, including two that do it
*inside a `TYPE_CHECKING` block*, which rules out any "convention" defence:

```
coverage/jsonreport.py:22   from coverage.plugin import FileReporter    <- TYPE_CHECKING, correct
coverage/results.py:19      from coverage.plugin import FileReporter    <- TYPE_CHECKING, correct
coverage/xmlreport.py:18 · lcovreport.py:13 · annotate.py:14 · python.py:20 · report.py:15
coverage/report_core.py:15 · control.py:53 · plugin_support.py:17 · collector.py:22 · __init__.py:30
coverage/disposition.py:13 · types.py:17   (FileTracer, same module)
coverage/html.py:42         from coverage.plugins import FileReporter   <- the only typo
```

**Correction verified.** On a copy, `s/coverage.plugins/coverage.plugin/` at line 42:

```
mypy --python-version=3.14 --strict coverage tests setup.py
  -> Success: no issues found in 145 source files          (no new errors)
mypy --python-version=3.14 --strict --disallow-any-unimported coverage tests setup.py
  -> 5 errors before the fix -> 2 after (the remaining 2 are setuptools, see below)
```

**Honest calibration of the consequence.** The fix exposes **zero** latent errors — the three annotations were
correct all along. The damage is therefore *prospective, not retrospective*: for however many releases this typo
has existed, the three most-used entry points of the HTML reporter have accepted any object at all, and any
future change that passes the wrong thing into them will not be caught. It is a one-character fix with no
behavioural risk and it restores checking to three public-facing signatures — do it.

### Full phantom-import sweep (systematic, labelled diagnostic pass)

Rather than eyeballing the 13 `if TYPE_CHECKING:` blocks, I re-ran the entire gated scope under a copy of the
project config with **`ignore_missing_imports = False`** (`/tmp/typing_probe.ini` — clearly *not* the baseline),
which makes every silently-`Any` import visible. Complete result for the shipped package:

| File:line | Import | Verdict |
|---|---|---|
| `coverage/html.py:42` | `coverage.plugins` | **FIX** — the phantom import above |
| `coverage/collector.py:214` | `import __pypy__` | **ACCEPTABLE** — PyPy builtin, guarded by `if env.PYPY:`, carries `# pylint: disable=import-error`. Deliberately unresolvable on CPython, and no annotation uses it. |

Everything else lives outside `coverage/`: `setup.py:20-22` (`setuptools`, untyped), `tests/test_concurrency.py:38,43`
(`gevent`/`greenlet`, untyped), and ~30 test-fixture modules (`aa`, `bb`, `pkg1`, `xyzzy`, `zip1`, `usepkgs`, …)
that the tests *create at runtime* — correct by design.

**`setup.py:106` / `setup.py:137` — ACCEPTABLE.** `--disallow-any-unimported` reports
`Base type editable_wheel/build_ext becomes "Any"`. Both lines already carry a `# type: ignore[misc]` for the
`disallow_subclassing_any` violation (mypy's own note confirms: *`Error code "no-any-unimported" not covered by
"type: ignore" comment`*). setuptools ships no stubs; the boundary is acknowledged in place. No action.

---

## Phase 4 — Stale ignores (0, from mypy's own `unused-ignore`)

`warn_unused_ignores = true` **is** enabled (`pyproject.toml`), so this is measurable — the correct statement is
a measured zero, not "cannot be measured".

**Measured: 0 stale ignores across all 145 gated files.**

**And I proved the measurement is not itself vacuous.** Injecting one deliberately-unnecessary ignore into a copy:

```
coverage/version.py:11: error: Unused "type: ignore" comment  [unused-ignore]
```

The detector fires. The zero is real.

> There are **47** `# type: ignore` comments in `coverage/` and **89** repo-wide. **None of those numbers is a
> stale-ignore count** — they measure how many ignores exist. Reporting either as "stale" would be the "36 stale
> ignores" false alarm.

### F3 · NOVEL [FIX] — 8 unscoped `# type: ignore` in `coverage/` suppress 16 diagnostics, including the machine proof of CRF-COVPY-0022

Not stale — every one is live. The defect is that they are **unscoped**: a bare `# type: ignore` suppresses
*whatever* error lands on that line, present and future, and `warn_unused_ignores` will never flag it as long as
*any one* of them still fires. Stripping only the bare ignores (coded ones untouched) on a copy:

| Site | Suppressed diagnostics | Verdict |
|---|---|---|
| `coverage/sysmon.py:410` | `union-attr` ×2 — `Item "None" of "CodeInfo \| None" has no attribute "byte_to_line"` | **FIX** — CRF-COVPY-0022 |
| `coverage/sysmon.py:413` | `union-attr` ×2 + `arg-type` | **FIX** — CRF-COVPY-0022 |
| `coverage/sysmon.py:440`, `:466`, `:476` | `union-attr` + `arg-type` each | **FIX** — CRF-COVPY-0022 |
| `coverage/sysmon.py:427` | `arg-type` — `int` into `set[tuple[int,int]]` | modelling gap (lines/arcs union) |
| `coverage/html.py:424` | `index` — `Unsupported target for indexed assignment ("object")` | **CONSIDER** |
| `coverage/config.py:89` | `override` ×3 — `Signature of "get" incompatible with supertype configparser.ConfigParser / RawConfigParser / typing.Mapping` | **CONSIDER** |

**Why this matters more than the raw count.** The catalogue records CRF-COVPY-0022 as *"three sysmon callbacks
index `code_infos` unguarded where their sibling checks"*. **mypy already knew.** It emits, at exactly those
lines, `Item "None" of "CodeInfo | None" has no attribute ...` — and a bare `# type: ignore` deletes the warning.
The guarded twin is 13 lines below the first offender and even carries the refutation in a comment:

```python
# coverage/sysmon.py:407-413   sysmon_py_return  -- UNGUARDED
code_info = self.code_infos.get(id(code))
# code_info is not None and code_info.file_data is not None, since we
# wouldn't have enabled this event if they were.
last_line = code_info.byte_to_line.get(instruction_offset)  # type: ignore   <- AttributeError if None

# coverage/sysmon.py:422-427   sysmon_line_lines -- GUARDED
code_info = self.code_infos.get(id(code))
# But somehow code_info can be None here, so we have to check.        <- the project's own refutation
if code_info is not None and code_info.file_data is not None:
    code_info.file_data.add(line_number)  # type: ignore
```

`sysmon_line_arcs` (`:436`) and `sysmon_branch_either` (`:451`) use `self.code_infos[id(code)]` — a subscript, so
those two raise `KeyError` rather than `AttributeError`. Same root, different exception.

**The compounding hazard is the unscoped-ness.** Each sysmon ignore suppresses *two unrelated* error classes: a
`union-attr` (a real crash path) and an `arg-type` (the `set[TLineNo] | set[TArc]` union that mypy cannot narrow).
Fixing the `None` guard therefore does **not** free the ignore — the `arg-type` keeps it alive, `unused-ignore`
stays silent, and the `union-attr` proof stays erased forever. Any *future* re-introduction of the same
None-dereference is invisible from that moment on.

**Fix (mechanical, no behaviour change):** scope every one of them.
`# type: ignore` → `# type: ignore[union-attr, arg-type]` (sysmon), `# type: ignore[index]` (html.py:424),
`# type: ignore[override]` (config.py:89). **The guarded twins are already in the tree** — `html.py:546` uses
`# type: ignore[index]` for *the identical problem* 122 lines below the bare one, and `sqlitedb.py:72` shows the
gold standard, `# type: ignore[attr-defined, unused-ignore]`, which stays correct across Python versions.

Repo-wide there are **21** unscoped ignores in the gated scope: 8 in `coverage/`, 13 in `tests/`
(`test_templite.py:52,106,236`, `test_data.py:732`, `test_cmdline.py:1655`, `test_plugins.py:112,113,149,150,151,159,160,161`).
The test ones are monkeypatching and dynamic-attribute assertions — lower stakes, same mechanical fix.

---

## Phase 5 — `Any` leakage

### F5 · NOVEL [FIX] — `TomlConfigParser.get() -> Any` is the one getter that neither validates nor type-checks

`coverage/tomlconfig.py:150-152`

```python
def get(self, section: str, option: str) -> Any:
    _, value = self._get_single(section, option)
    return value            # <- raw TOML value, no _check_type, and Any hides that from mypy
```

Every *other* getter in the class routes through `_check_type` (`tomlconfig.py:154`) and raises the project's own
`ConfigError` on a bad value: `getboolean`, `getint`, `getfloat`, `getlist`, `getregexlist`, `getfile`. The bare
`get` — used for the **9 options declared without a type in `CONFIG_FILE_OPTIONS`** (`command_line`, `context`,
`core`, `dynamic_context`, `_crash`, `format`, `sort`, `extra_css`, `html_title`) — does neither.

Its INI twin is annotated `-> str` (`config.py:89`) and *cannot* return a non-string, because `configparser`
only ever yields strings. TOML can yield anything. The `Any` is what makes the divergence invisible.

**Reproduced end-to-end** (`/tmp/tomle2e`, coverage.py from the copy, unmodified):

```toml
# pyproject.toml
[tool.coverage.report]
sort = 2
```
```
  File "coverage/report.py", line 252, in tabular_report
    sort_option = (self.config.sort or "name").lower()
AttributeError: 'int' object has no attribute 'lower'
```

**Guarded twin, same file, same config load** — an option that goes through a validating getter:

```toml
[tool.coverage.report]
precision = "two"
```
```
ConfigError: Couldn't read config file pj2.toml:
  Option [tool.coverage.report]precision couldn't convert to an integer: 'two'
```

One typo in `pyproject.toml` gets a clear `ConfigError`; the other gets an unhandled `AttributeError` traceback
out of the middle of the reporter. `AttributeError` is not a `_BaseCoverageException`, so `cmdline.py` does not
catch it — the user sees a stack trace, not a diagnostic.

**Fix, and the verification that the annotation is the missing check.** Change the annotation to `-> str` (and
route through `_check_type(..., str, None, "a string")`). Doing only the annotation change on a copy makes mypy
report the defect immediately:

```
coverage/tomlconfig.py:152: error: Returning Any from function declared to return "str"  [no-any-return]
```

`warn_return_any = true` is already enabled — the project has the check switched on and the `-> Any` is what
opts this one method out of it. (Related to but distinct from the catalogued INI/TOML divergences
CRF-COVPY-0028 / CRF-COVPY-0029; those are about plugin names and `$VAR` substitution, this is about value
types.)

### F6 · NOVEL [CONSIDER] — the whole config loader is dispatched through `getattr`, so mypy checks none of it

`coverage/config.py:484-485`

```python
method = getattr(cp, f"get{type_}")
setattr(self, attr, method(section, option))
```

`cp` is `TConfigParser = HandyConfigParser | TomlConfigParser` (`config.py:146`) — a bare union, not a Protocol.
`getattr` with a computed name returns `Any`; `setattr` with a computed attribute name is unchecked. So for
**all 53 entries of `CONFIG_FILE_OPTIONS`**, mypy verifies neither that `get{type_}` exists on both backends nor
that the produced value matches the declared type of the target attribute on `CoverageConfig`.

Today the six needed methods (`getboolean`, `getfile`, `getfloat`, `getint`, `getlist`, `getregexlist`) do exist
on both backends — I checked. The exposure is prospective and concrete: adding an option with a new `type_`
string, or renaming a getter on one backend only, produces an `AttributeError` at config-load time on a user's
machine rather than a red CI run. It is also the *mechanism* by which the whole `one-concern-implemented-per-backend`
family (CRF-COVPY-0028/0029/0010/0032/0043) stays invisible to the type checker.

**Fix:** declare a `Protocol` with the seven getter signatures and type `cp` as that Protocol; both concrete
classes are then structurally checked against it, and a divergence becomes a compile-time error. A `Literal`
type for `type_` closes the second half.

### `cast()` audit — 21 sites in `coverage/`, all discharged

A `cast()` is an unchecked assertion. I resolved every one against the code that precedes it.

| Site | Assertion | Verdict |
|---|---|---|
| `inorout.py:587` `cast(str, sys.modules[pkg].__file__)` | `__file__` is not `None` | **DISCHARGED** — the previous line guards with `module_has_file()`, which returns `False` when `__file__ is None` (`inorout.py:97-102`). This is the *guarded twin* of an unchecked `__file__` cast; namespace packages are handled. |
| `sysmon.py:61` `cast(MonitorReturn, getattr(sys_monitoring, "DISABLE", None))` | — | **DISCHARGED** — `MonitorReturn = Optional[DISABLE_TYPE]`, so the cast target *includes* `None`. The cast is honest about the `getattr` default. |
| `sysmon.py:96` `cast(int, threading.current_thread().ident)` | thread has started | **DISCHARGED** — `ident` is `None` only pre-`start()`; this runs inside a live callback. Debug-only path. |
| `collector.py:467, :483, :489` · `pytracer.py:266, :268, :299` | `self.data` is `set[TLineNo]` xor `set[TArc]` | **DISCHARGED** — each is guarded by the `branch`/`should_trace` flag that determines the mode. |
| `parser.py:260, :267` · `regions.py:60` `cast(int, node.end_lineno)` | `end_lineno` set | **DISCHARGED** — always set on nodes from a successfully-parsed module. |
| `cmdline.py:945, :946, :1009` · `control.py:298, :848` · `sqldata.py:484` · `sqlitedb.py:186` · `templite.py:251` | config/DB value shape | **DISCHARGED** — narrow, adjacent to the code that established the shape. |

**One observation across the set.** The same modelling problem — `file_data`/`self.data` is
`set[TLineNo] | set[TArc]` and only the runtime mode says which — is solved **three different ways** in three
modules: `cast()` in `collector.py` and `pytracer.py` (explicit, greppable, narrow), and a **bare
`# type: ignore` in `sysmon.py`** (opaque, and it swallows the unrelated `union-attr` alongside). The two `cast`
users are the guarded twins; `sysmon.py` should adopt their idiom. `pytracer.py:31` even carries a comment
explaining why the cast is written the way it is.

### `Any` in public signatures — no findings

`Any` appears in ~35 signatures in `coverage/`. Every instance I checked sits at a genuinely dynamic edge, and is
therefore suppressed under FP class 10 (*Deliberate `Any` at a boundary*): `sys_info() -> Iterable[tuple[str, Any]]`
(debug output), `__eq__(self, other: Any)`, `*args: Any, **kwargs: Any` passthroughs, `debug.py` formatters,
`AnyCallable` decorator plumbing. The one that is *not* a boundary — `tomlconfig.py:150` — is F5 above.

---

## Wrong typing vs missing typing

These are different things and only the first is a defect.

**Wrong typing (defects): 2 roots, 10 sites.** F2 (phantom import, 1 site / 3 annotations) and F3+F5
(suppressed-or-erased diagnostics, 8 sites). Plus 2 structural CONSIDERs (F6, and F3's `config.py:89` LSP
violation).

**Missing typing (migration cost): ZERO.** Across all **145** gated files, mypy under `--strict` reports **no**
`no-untyped-def`, `no-untyped-call`, `var-annotated`, `type-arg` or `no-any-return`. coverage.py is not a gradually-
typed codebase with a migration ahead of it — it is fully annotated and enforced in CI, including its test suite.
There is no migration estimate to give. **This is the reason the phantom import matters here more than it would
elsewhere:** in a project where every other annotation is load-bearing and checked, three that silently stopped
checking are a genuine hole in an otherwise complete surface, not one gap among thousands.

---

## Dismissed (with reason)

- **`import __pypy__` (`collector.py:214`)** — deliberately unresolvable on CPython, guarded by `if env.PYPY:`,
  no annotation depends on it. Not a phantom import.
- **`setup.py:106,137` subclassing `Any` from setuptools** — untyped third-party at a real boundary, already
  acknowledged with `# type: ignore[misc]`. FP class 10.
- **`tests/` unresolvable imports (~30)** — fixture modules the tests write to disk at runtime. Correct by design.
- **The whole-repo `Duplicate module named "coverage"` FAILED** — caused by a local untracked `build/` directory,
  not by anything in the repository.
- **"47 `# type: ignore` in `coverage/`" as a stale-ignore count** — measures existence, not staleness. The
  measured stale count is 0.
- **`# type: ignore[unreachable]` ×3 in `pytracer.py`** — `warn_unreachable = true` is on and these mark
  deliberately-defensive branches. Coded, narrow, live. Correct usage.

---

## Summary

| | |
|---|---|
| Status | **OK** — 145 files under the project's own gate, 0 baseline errors, mypy 1.20.2 (project pins 2.1.0) |
| Uses project config | yes, as-is (`pyproject.toml:10`), plus tox's `--strict` |
| Type defects | **2 roots / 10 sites** (all currently invisible to the checker) |
| Phantom imports | **1 import → 3 dead annotations** (`coverage/html.py:42`) — CRF-COVPY-0018 **still live** |
| Stale ignores | **0**, measured via mypy's `unused-ignore`, detector proven live by injection |
| Unscoped ignores | **8** in `coverage/` (21 in the gated scope) — novel, suppressing 16 diagnostics |
| Missing annotations | **0** — no migration cost |
| Tooling defect | `check_typing.json` for this project is **vacuous**; `FORCE_COLOR` defeats `_LINE` parsing |

### Recommended order

1. `coverage/html.py:42` — `coverage.plugins` → `coverage.plugin`. One character, verified no new errors. **[FIX]**
2. `coverage/tomlconfig.py:150` — annotate `-> str`, route through `_check_type`. Reproduced crash. **[FIX]**
3. `coverage/sysmon.py:410,413` — guard `code_info is not None` as `sysmon_line_lines:426` already does. **[FIX, = CRF-COVPY-0022]**
4. Scope all 8 bare `# type: ignore` in `coverage/`. Mechanical, zero behaviour change. **[FIX]**
5. `coverage/config.py:484` — Protocol for `TConfigParser`, `Literal` for `type_`. **[CONSIDER]**
6. Toolkit: neutralise colour env in `check_typing.py::_run_mypy`, and treat `errors > 0 and findings == []` as FAILED.
