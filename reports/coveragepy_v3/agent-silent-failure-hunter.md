# silent-failure-hunter — coverage.py (informed run)

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Tree edited:** **NO.** The target tree was never written to. All reading and all reproduction
was done against `/tmp/covrepro` (`git archive HEAD | tar -x`) with `PYTHONPATH=/tmp/covrepro`,
and all scratch files were created under `/tmp/covlab`. Verify by SHA.

**Scope covered:** all 76 `except` handlers in `coverage/*.py` (enumerated by AST, not grep), all 18
`warn()`/`_warn()` call sites, and every path from a failure to a smaller measured number.

---

## Headline

The single most damaging asymmetry in this codebase is not in an `except` block. It is that
coverage.py's **denominator** — the set of files that *could* have run — is assembled by a different
predicate from the one that decides what to trace, and that predicate silently returns nothing for
whole classes of legitimate package layouts. One of those classes (PEP-420 namespace packages) is a
default layout for modern `src/` projects, and it takes a real 25% project to a reported **100%** with
`--fail-under=90` passing and exit 0.

Second: coverage.py's own diagnostic channel is `warnings.warn`, whose filter list is process-global
state that the **program being measured** is free to overwrite. Any codebase that calls
`warnings.simplefilter("ignore")` at import — routine in scientific/ML/legacy Python — silently
disables every coverage.py warning, including "Trace function changed, data is likely wrong".

Both are reproduced below.

---

## Confirmation of the 60 catalogued findings

I mechanically dumped the cited source region for the 44 catalogued findings with a code-level
`file:line` (excluding the doc/test/typing ones outside this agent's lane). **All are still present.**
Line numbers have drifted for nine of them; the code is unchanged:

| id | cited | actual now |
|---|---|---|
| 0002 | `control.py:1499-1503` | `control.py:1499-1503` (`_after_fork_in_child`) — unchanged |
| 0005 | `sysmon.py:335, 374-387` | `sysmon.py:335-347, 374-395` |
| 0006 | `sqldata.py:744-884` | `sqldata.py:744` onwards — unchanged |
| 0011 | `sqldata.py:468-475` | `sqldata.py:468-475` — unchanged |
| 0031 | `results.py:131-140` | `results.py:131-140` — unchanged |
| 0034 | `regions.py:53-55` | `regions.py:53-56` |
| 0035 | `files.py:508-509` | `files.py:507-512` |
| 0037 | `inorout.py:445-507 vs :599-621` | `inorout.py:445-504 vs :579-591, :599-620` |
| 0059 | `sqldata.py:912-927` | `sqldata.py:912-930` |

Spot-confirmed in detail, because they bear directly on findings below:

- **0007** `results.py:499-502` — `should_fail_under` still special-cases only `fail_under == 100.0`;
  every other threshold still uses `round(total, precision) < fail_under`, i.e. rounds *toward* the gate.
- **0016** `config.py:318-323` — `if not files_read: return False`; still cannot distinguish
  "no config file" from "config file unreadable".
- **0018** `html.py:42` — `from coverage.plugins import FileReporter` under `TYPE_CHECKING`. `coverage/plugins.py`
  still does not exist (only `plugin.py`).
- **0021** `report_core.py:105-115` — the `NotPython` + `should_be_python() is False` branch still
  falls through with no `warn`, no `raise` and no `yield`.
- **0022** `sysmon.py:407-412, :436, :451` — three callbacks still index `code_infos` unguarded.
- **0026** `pth_file.py:11-14` — bare `except: pass` still present.
- **0032** `results.py:336-340` returns `100.0` for a zero denominator, while `jsonreport.py:108` and
  `lcovreport.py:191` still return `self.total.n_statements and self.total.pc_covered`, i.e. `0`.
- **0040** — all six slugless warnings still slugless: `config.py:346`, `control.py:629`,
  `data.py:211`, `inorout.py:426`, `collector.py:409`, `html.py:131`.
- **0060** `inorout.py:115-118` — `except Exception: pass` around `find_spec`; the caller's guard at
  `inorout.py:318` (`except CoverageException`) is still dead code.

No catalogued finding appears to have been fixed at this SHA.

---

# NOVEL FINDINGS

Ranked by how silent the failure is.

---

## N1 — FIX — `--source=<package>` drops the whole un-executed denominator when the package has no `__file__`

> A 25% project reports **100%**. `--fail-under=90` **passes**, exit 0, nothing on stderr.

**Location:** `coverage/inorout.py:584-588`, gated by `coverage/inorout.py:97-102`.

```python
# inorout.py:579
def find_possibly_unexecuted_files(self) -> Iterable[tuple[str, str | None]]:
    for pkg in self.source_pkgs:
        if pkg not in sys.modules or not module_has_file(sys.modules[pkg]):
            continue                                    # <-- 585-586
        pkg_file = source_for_file(cast(str, sys.modules[pkg].__file__))
        yield from self._find_executable_files(canonical_path(pkg_file))

    for src in self.source_dirs:                        # <-- the guarded twin, 590-591
        yield from self._find_executable_files(src)
```

```python
# inorout.py:97
def module_has_file(mod: ModuleType) -> bool:
    mod__file__ = getattr(mod, "__file__", None)
    if mod__file__ is None:
        return False                                    # PEP-420 namespace package
    return os.path.exists(mod__file__)                  # zip/egg import
```

`find_possibly_unexecuted_files` is what feeds `Coverage._post_save_work` → `data.touch_files`
(`control.py:957-964`), i.e. it is the *only* thing that puts never-imported source files into the
report at 0%. When `module_has_file` is False the whole package subtree is skipped. Two independent
triggers, both reproduced:

**Trigger A — implicit namespace package (no `__init__.py`).** `mod.__file__` is `None`.

**Trigger B — package imported from a zip/egg.** `__file__` is `/…/src.zip/zpkg/__init__.py`, which
`os.path.exists` reports False.

### Reproduction (both verbatim, `/tmp/covlab/t3` and `/tmp/covlab/t7`)

Identical source, identical program, the only difference being whether `nspkg/__init__.py` exists:

```
$ coverage run --source=nspkg prog.py ; coverage report --fail-under=90     # NO __init__.py
Name                            Stmts   Miss  Cover
---------------------------------------------------
/tmp/covlab/t3/src/nspkg/a.py       2      0   100%
---------------------------------------------------
TOTAL                               2      0   100%
exit=0

$ touch nspkg/__init__.py ; <same two commands>                             # WITH __init__.py
Name                                   Stmts   Miss  Cover
----------------------------------------------------------
/tmp/covlab/t3/src/nspkg/__init__.py       0      0   100%
/tmp/covlab/t3/src/nspkg/a.py              2      0   100%
/tmp/covlab/t3/src/nspkg/b.py              6      6     0%
----------------------------------------------------------
TOTAL                                      8      6    25%
Coverage failure: total of 25 is less than fail-under=90
exit=2
```

Zip trigger, same shape:

```
$ PYTHONPATH=…/src.zip coverage run --source=zpkg prog.py ; coverage report --fail-under=90
src.zip/zpkg/__init__.py       0      0   100%
src.zip/zpkg/a.py              2      0   100%
TOTAL                          2      0   100%          # zpkg/b.py (6 stmts) silently absent
exit=0
```

**The setting that is supposed to fix this does nothing here.** `[report] include_namespace_packages`
was added for exactly this case — `CHANGES.rst:1764-1771`: *"When searching for completely un-executed
files, coverage.py uses the presence of `__init__.py` files… A new setting `[report]
include_namespace_packages` tells coverage.py to consider these directories during reporting."*
The setting is honoured at `inorout.py:609-612` (`find_python_files(src_dir, self.include_namespace_packages)`),
but control never reaches there because line 585 already `continue`d. Reproduced: setting
`include_namespace_packages = True` leaves the output at 100%, unchanged. This makes the finding a
contract violation against the project's own documented feature (`doc/config.rst:796-804`), not a
design choice.

### Guarded twins

1. **The other half of the same function**, `inorout.py:590-591`: the `source_dirs` branch has no
   anchor-file gate and enumerates correctly. `--source=nspkg` behaves *correctly* when `nspkg` happens
   to also be a directory relative to cwd (it goes to `source_dirs` via `inorout.py:218-222`) and
   *incorrectly* when it resolves as a module name. Same user-facing option, two code paths, opposite
   answers on the same tree — confirmed by running the same test from a different cwd.
2. `inorout.py:564-568` — `_warn_about_unmeasured_code` already reasons explicitly about namespace
   packages (`if module_is_namespace(mod): return`, comment *"there is no code directly in it"*). The
   codebase knows a namespace package has no code *directly in it*; the enumerator uses that same fact
   to skip the entire *subtree*.
3. The tracing side gets it right: `check_include_omit_etc` matches via `ModuleMatcher` on
   `source_pkgs`, so `nspkg.a` **is** measured when it runs. Only the un-executed enumerator disagrees.

### Fix

In `find_possibly_unexecuted_files`, when the module is a namespace package or has no on-disk
`__file__`, enumerate `mod.__path__` instead of bailing:

```python
for pkg in self.source_pkgs:
    mod = sys.modules.get(pkg)
    if mod is None:
        continue
    if module_has_file(mod):
        yield from self._find_executable_files(canonical_path(source_for_file(mod.__file__)))
    else:
        for pkg_dir in getattr(mod, "__path__", ()):
            if os.path.isdir(pkg_dir):
                yield from self._find_executable_files(canonical_path(pkg_dir))
```

Note this also makes `include_namespace_packages` actually reachable on this path.

### Relationship to CRF-COVPY-0037

Same file and same function pair as 0037 (`inorout.py:445-504` vs `:579-620`), but a **different root
and a different fix**. 0037 is "the enumerator applies only the omit rule while the gate applies
eight"; N1 is "the enumerator never runs at all because it is gated on an optional anchor file".
Fixing 0037 (teaching `_find_executable_files` the other rules) does not fix N1, and vice versa. Report
them as siblings, not duplicates.

### Proposed shape

```
subtree-enumeration-gated-on-an-optional-anchor-file
  Default severity: FIX · grounding: confirmed
  How you find it: agent-only — the sibling hunt below IS the method
  Pattern: Code that must enumerate a DIRECTORY TREE first tests for a single
    representative file (a package __init__, a manifest, an index) and returns empty
    when it is missing. The language or ecosystem permits the tree to exist without
    that file, so a legitimate layout yields nothing. Because the enumeration feeds a
    denominator, the failure makes a metric IMPROVE.
  Guarded twin: a sibling branch of the same function that takes a directory directly
    and does not apply the gate; and any configuration option written to handle the
    anchor-less layout, which will be dead on the gated path.
  Sibling hunt: for every "find everything under X" helper, find the existence test
    that precedes the walk and ask what legitimate arrangement fails it — namespace
    packages, zip/egg imports, symlink farms, editable installs, __init__-less test
    dirs. Then check whether an option exists that CLAIMS to handle it, and whether the
    gate runs before that option is consulted. A live option that changes nothing is
    the proof.
  Expected behaviour: the enumeration walks the tree whenever the tree exists.
  Surfaces as: SILENT and FAVOURABLE. Files vanish from the denominator, the
    percentage rises, the CI gate passes, exit 0, nothing on stderr.
  Do NOT flag when: the anchor file is genuinely required by the ecosystem for the
    tree to be meaningful. Check the relevant PEP/spec, not the common case.
```

---

## N2 — FIX — the measured program controls whether coverage.py's own warnings are visible

**Location:** `coverage/control.py:495` (`warnings.warn(msg, category=CoverageWarning, stacklevel=2)`).

Every coverage.py diagnostic — all 18 `warn()` call sites — funnels through `Coverage._warn`, which
emits via the `warnings` module. `warnings.filters` is process-global mutable state, and the program
under measurement runs in that same process, before and during collection.

### Reproduction (`/tmp/covlab/t4`)

```python
# loud.py
pass
```
```python
# quiet.py
import warnings
warnings.simplefilter("ignore")
```

```
$ coverage run --source=zzz_nonexistent loud.py
…inorout.py:561: CoverageWarning: Module zzz_nonexistent was never imported. (module-not-imported)
…control.py:955: CoverageWarning: No data was collected. (no-data-collected)

$ coverage run --source=zzz_nonexistent quiet.py
(no output at all)
```

Both runs exit 0. In the second, coverage.py measured nothing, was told to measure a package that
does not exist, and said nothing about either.

Two lines of one-time setup in the program under test — `warnings.simplefilter("ignore")`,
`warnings.filterwarnings("ignore")`, `-W ignore`, `PYTHONWARNINGS=ignore`, or a pytest
`filterwarnings = ignore` — silence the entire diagnostic surface. That includes the highest-stakes
one in the project: `pytracer.py:352-358`, *"Trace function changed, data is likely wrong"*.

### Guarded twins (both in-tree, both in the same class)

1. `control.py:501-504`:
   ```python
   def _message(self, msg: str) -> None:
       if self._messages:
           print(msg, file=sys.stderr)
   ```
   An unsuppressible second channel already exists on the same object. `combine`'s "Combined N files,
   1 file errored" goes through it; every correctness warning does not.
2. `cmdline.py:953` prints the `--fail-under` failure with `print(...)`, not `warnings.warn`.
3. `control.py:290-291, :490` — every warning is *already* accumulated into `self._warnings`.
   A repo-wide grep shows that list is read **only by `tests/test_oddball.py:157,162,165`**; no
   production code path ever surfaces it. The information survives suppression and is then discarded.

### Fix

Either wrap the emission so coverage's own category is always shown:

```python
with warnings.catch_warnings():
    warnings.simplefilter("always", CoverageWarning)
    warnings.warn(msg, category=CoverageWarning, stacklevel=2)
```

or, at minimum, have the CLI print `self._warnings` before exiting when the `warnings` machinery
swallowed them. The former is a three-line change and preserves `disable_warnings` (which is checked
earlier, at `control.py:486`, and is the *intended* suppression mechanism).

### Proposed shape

```
diagnostic-channel-controlled-by-the-subject-under-observation
  Default severity: FIX · grounding: confirmed
  How you find it: agent-only
  Pattern: A tool that observes or instruments another program emits its own
    diagnostics through a facility that lives in the observed program's process and
    that the observed program is free to reconfigure — the `warnings` filter list, the
    root logger, sys.stderr, an excepthook. The observed program's ordinary,
    well-intentioned configuration then blinds the observer.
  Guarded twin: the same tool almost always has a second, direct channel it uses for
    user-facing messages (a bare print to stderr, a CLI status line). Its existence is
    proof the author knew a suppressible channel was not always adequate.
  Sibling hunt: list every diagnostic emitter in the tool and ask which process-global
    the message passes through. Then grep the tool for a direct-write channel; any
    diagnostic that goes through the shared facility while a sibling goes direct is the
    finding. Reproduce by adding one line of ordinary configuration to the subject
    program.
  Expected behaviour: the observer's diagnostics reach the operator regardless of how
    the observed program configures itself; only the operator's OWN suppression
    setting silences them.
  Surfaces as: SILENT and TOTAL. Not one message is lost — all of them are, and only
    for the users whose codebases quiet warnings, which correlates with legacy and
    scientific code where measurement matters most.
  Do NOT flag when: the tool IS a library of the host program and shares its logging by
    design. The discriminator is whether the tool's correctness depends on the operator
    seeing the message.
```

---

## N3 — FIX — `ignore_errors` removes files from the denominator and reports no count anywhere

**Location:** `coverage/report_core.py:116-121`.

```python
except Exception as exc:
    if config.ignore_errors:
        msg = f"Couldn't parse '{fr.filename}': {exc}".rstrip()
        coverage._warn(msg, slug="couldnt-parse")
    else:
        raise
else:
    yield (fr, analysis)
```

A file that errors is not yielded. It disappears from both numerator *and* denominator, so the
percentage rises. There is a warning, but:

1. **there is no count of dropped files anywhere in the report output**, and
2. the slug `couldnt-parse` is one bucket for two unrelated causes — *"this is not parseable Python"*
   and *"this file no longer exists"* — so a project that legitimately silences the former (generated
   files, vendored templates) also silences the latter.

### Reproduction (`/tmp/covlab/t5`)

```
--- before deleting pkg/gone.py
pkg/gone.py           8      4    50%
TOTAL                10      4    60%

--- after `rm pkg/gone.py`, ignore_errors=False
No source for code: '/tmp/covlab/t5/pkg/gone.py'
exit=1                                             # correct, loud

--- after deletion, ignore_errors=True, fail_under=90
CoverageWarning: Couldn't parse '…/pkg/gone.py': No source for code: '…/pkg/gone.py'. (couldnt-parse)
TOTAL                 2      0   100%
exit=0                                             # gate passes at 100%

--- same, plus  [run] disable_warnings = couldnt-parse
TOTAL                 2      0   100%
exit=0                                             # zero output of any kind
```

60% → 100% because a source file moved. A stale `.coverage` after a refactor, a build that deletes
generated sources before reporting, or a `[paths]` remap that misses, all land here.

### Guarded twins (both in-tree)

1. **`report.py:279-285`** — the *same reporter*, in the *same output*, accounts for every **benign**
   omission by count:
   ```python
   end_lines = []
   if self.config.skip_covered and self.skipped_count:
       end_lines.append(f"\n{plural(self.skipped_count, 'file')} skipped due to complete coverage.")
   if self.config.skip_empty and self.empty_count:
       end_lines.append(f"\n{plural(self.empty_count, 'empty file')} skipped.")
   ```
   Files removed because they were *fine* are counted. Files removed because they **errored** are not.
2. **`data.py:234-240`** — the combine path already implements exactly the missing behaviour:
   `"Combined 3 files, skipped 1, 2 files errored"`. coverage.py knows how to tell a user how many
   inputs failed; the report path just doesn't.

### Fix

- Give the missing-source case its own slug (`no-source`) so `disable_warnings` can distinguish it.
  `report_core.py` already has the exception object; `except NoSource` before `except Exception`.
- Add `self.error_count` to `SummaryReporter`, incremented from `get_analysis_to_report`, and emit
  `"\nN files omitted due to errors."` in `end_lines` alongside the two existing lines.
- Consider making `--fail-under` a hard failure when `error_count > 0`, since the total is known to be
  computed over an incomplete file set.

### Relationship to CRF-COVPY-0021

0021 is the `except NotPython` + `should_be_python() is False` branch (`report_core.py:105-115`),
where a non-`.py` file is dropped with **no warning at all, ever**. N3 is the `except Exception`
branch below it, where the warning exists but the accounting does not and the slug is too coarse.
Adjacent, same function, different mechanisms — the complete fix is the same change, so land them
together.

---

## N4 — CONSIDER — PyTracer's frame-stack desync writes to a hardcoded `/tmp` path instead of warning

**Location:** `coverage/pytracer.py:176-182`, with `log()` at `coverage/pytracer.py:127-145`.

```python
# pytracer.py:172
try:
    self.cur_file_data, self.cur_file_name, self.last_line, self.started_context = (
        self.data_stack.pop()
    )
except IndexError:
    self.log("Empty stack!", frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)
return None
```

```python
# pytracer.py:127 — NOT gated on any debug flag
def log(self, marker: str, *args: Any) -> None:
    """For hard-core logging of what this tracer is doing."""
    with open("/tmp/debug_trace.txt", "a", encoding="utf-8") as f:
        ...
```

**Guarded twin — same class, same file, same kind of event.** `pytracer.py:352-358`:

```python
if self.warn and not suppress_warning:
    if tf != self._cached_bound_method_trace:
        self.warn("Trace function changed, data is likely wrong: …", slug="trace-changed")
```

Both handlers detect *"our bookkeeping about the frame stack is now wrong, so the data is not
trustworthy"*. One calls `self.warn` with a slug and a documented messages.html anchor. The other
appends a line to `/tmp/debug_trace.txt`, a file no user has ever looked at.

**Why it matters beyond the missing message.** After the failed `pop`, `cur_file_data`,
`cur_file_name` and `last_line` retain the *inner* frame's values. Subsequent events are then
attributed to the wrong file — this is mis-attribution, not merely loss, and mis-attribution can move
the number in either direction.

**Secondary hazard.** `log()` performs an unconditional `open("/tmp/debug_trace.txt", "a")` from
inside the trace function. On Windows, in a container with a read-only or absent `/tmp`, or under a
restrictive umask, that raises `OSError` *inside the trace function*, which CPython answers by
unsetting the trace function entirely — turning a diagnostic into a total measurement stop. Note also
that `/tmp/debug_trace.txt` is a fixed, world-writable-directory path.

Unlike other spots in this file, this branch carries no `# pragma: cant happen`.

**Fix:** replace the `log()` call with
`self.warn("Trace stack desynchronized, data is likely wrong", slug="stack-desync")`, and put `log()`
behind the project's existing `# pragma: debugging` / env-var convention (as `sysmon.py`'s `LOG` does)
so it cannot fire in production.

**Honesty note:** I did not construct an input that reaches the `IndexError`. The finding is the
diagnostic asymmetry and the unconditional `/tmp` write, both decidable from the source; the
consequence analysis assumes the branch is reachable, which the absence of a `cant happen` pragma
supports but does not prove.

---

## N5 — CONSIDER — an explicit `core = ctrace` that cannot be honoured falls back silently on non-wheel builds

**Location:** `coverage/core.py:104-109`.

```python
if core_name == "ctrace":
    if not CTRACER_FILE:
        if IMPORT_ERROR and env.SHIPPING_WHEELS:          # <-- gate
            warn(f"Couldn't import C tracer: {IMPORT_ERROR}", slug="no-ctracer", once=True)
        core_name = "pytrace"
```

**Guarded twin, thirteen lines above** (`core.py:91-94`): when the user explicitly asks for
`core = sysmon` and it is unusable, coverage warns **unconditionally**:

```python
if core_name == "sysmon" and reason_no_sysmon:
    warn(f"Can't use core=sysmon: {reason_no_sysmon}, using default core", slug="no-sysmon")
```

Two explicit core requests that cannot be honoured; one always tells the user, the other only when
`env.SHIPPING_WHEELS` (`env.py:51`) is set. A source install, a distro package, or a local build whose
C extension failed to compile takes the silent path.

**This is not only a speed change.** Switching to `pytrace` flips `supports_plugins` True→False
(`core.py:124` vs `:130`) and changes which threads are measured — the divergence catalogued as
CRF-COVPY-0009. The plugin half of that consequence *is* warned (`control.py:628-638`); the thread half
is not. So the user's measurement semantics change with no notice.

**Fix:** warn on any fallback away from an *explicitly configured* core, independent of
`SHIPPING_WHEELS`. The `once=True` slug already prevents noise. Keep the `SHIPPING_WHEELS` gate only
for the implicit-default path.

---

## N6 — CONSIDER — `coverage combine` exits 0 when input data files errored

**Location:** `coverage/cmdline.py:868-874`.

```python
elif options.action == "combine":
    …
    self.coverage.combine(data_paths, strict=True, keep=bool(options.keep))
    self.coverage.save()
    return OK                                      # unconditional
```

`combine_parallel_data` counts errored files (`data.py:207`) and reports the count
(`data.py:234-240`), but the count never reaches the exit status. `strict=True` only guards
"no files at all" / "no usable files"; a *partial* loss exits 0.

### Reproduction (`/tmp/covlab/t6`)

Two parallel data files, one overwritten with garbage:

```
$ coverage combine
CoverageWarning: Couldn't use data file '.coverage.…': file is not a database
Combined 1 file, 1 file errored
combine exit=0
```

Ranked below N1-N3 because the direction is toward *lower* coverage, so a configured `--fail-under`
catches it. But nothing catches it when `--fail-under` is unset, and both signals — the warning and
the message — are suppressible (the warning by N2, the message by `--no-messages`).

**Fix:** return `ERR` from the combine branch when `errored > 0`, or add an explicit
`[run] fail_on_errored_data` / `--strict` behaviour. `combine_parallel_data` would need to return or
raise on the counts it already has.

---

## N7 — CONSIDER — a non-UTF-8-encodable path is dropped from measurement with only a debug message

**Location:** `coverage/inorout.py:500-504`.

```python
# No point tracing a file we can't later write to SQLite.
try:
    filename.encode("utf-8")
except UnicodeEncodeError:
    return "non-encodable filename"
```

Every other reason `check_include_omit_etc` returns is a **user policy** — `"is inside an --omit
pattern"`, `"is in the stdlib"`, `"falls outside the --source spec"`. The user asked for those. This
one is coverage.py saying *"I am unable to measure this"*, and it is delivered through the same
silent channel: a `debug.write` at `control.py:465-470` that is off by default.

**Guarded twin:** the equivalent limitation at report time *does* warn —
`report_core.py:113` emits `couldnt-parse` when a file cannot be analysed. A file that cannot be
*measured* gets nothing.

**Fix:** `self.warn(f"Can't measure {filename!r}: non-encodable filename",
slug="non-encodable-filename", once=True)` alongside the return. (Reachable on Linux with
surrogate-escaped filenames from a non-UTF-8 filesystem.)

---

## N8 — CONSIDER — `CoverageData.__bool__` answers False for a data file it could not read

**Location:** `coverage/sqldata.py:403-411`.

```python
def __bool__(self) -> bool:
    if threading.get_ident() not in self._dbs and not os.path.exists(self._filename):
        return False
    try:
        with self._connect() as con:
            with con.execute("SELECT * FROM file LIMIT 1") as cur:
                return bool(list(cur))
    except CoverageException:
        return False
```

Textbook `empty-result-conflated-with-absent` (CRF-COVPY-0016's shape). Line 404 correctly returns
False for a genuinely absent file; line 410-411 then returns the *same* answer for a file that exists
but is corrupt, has a wrong schema version, or cannot be opened. `DataError` is a `CoverageException`,
so `_read_db`'s carefully-worded errors (`sqldata.py:330-339`) are all collapsed to "no data".

The one production consumer is `control.py:954`:

```python
if not self._data and self._warn_no_data:
    self._warn("No data was collected.", slug="no-data-collected")
```

So the user is told *"No data was collected"* when the truth is *"your data file is damaged"* — a
warning that fires but names the wrong cause, which the shape's own guidance keeps in-shape at
reduced severity. It sends debugging in exactly the wrong direction: the user goes looking at their
`--source` configuration instead of at the file.

**Fix:** let `DataError` propagate out of `__bool__` (the callers are few), or have `_post_save_work`
call a `has_data()` that distinguishes the three states.

---

# Fix-propagation notes (not separate findings — same root as a catalogued one)

These are additional **sites** of already-catalogued roots. Reported so that the fix lands on all of
them, which is the whole value of listing them.

- **CRF-COVPY-0016 has a second parser.** The catalogued site is the INI reader
  (`config.py:318-323`). The TOML reader has the identical hole at **`tomlconfig.py:55-59`**:
  ```python
  try:
      with open(filename, encoding="utf-8") as fp:
          toml_text = fp.read()
  except OSError:
      return []
  ```
  An unreadable `pyproject.toml` / `.coveragerc.toml` (chmod 000, EACCES on a mounted volume, EIO)
  returns the same empty list as "file not present", and `config.py:322` then reads that as
  `return False` — no config. Any fix that only distinguishes `FileNotFoundError` from other `OSError`
  in `config.py` leaves TOML broken. Since `pyproject.toml` is now the dominant config location, this
  is arguably the *more* reachable of the two sites.

- **CRF-COVPY-0022 has a silent half.** 0022 covers the three sysmon callbacks that index
  `code_infos` unguarded (`sysmon.py:436`, `:451`, and the `# type: ignore` deref at `:410`). The
  *guarded* sibling, **`sysmon.py:422-427`**, is the other half of the same defect:
  ```python
  code_info = self.code_infos.get(id(code))
  # It should be true that code_info is not None … But somehow code_info can be
  # None here, so we have to check.
  if code_info is not None and code_info.file_data is not None:
      code_info.file_data.add(line_number)
  ```
  When the condition is False, an **executed line is silently discarded** — a direct under-count on
  the default 3.14 core, under a comment in which the maintainers state they do not know why the
  condition occurs. The unguarded siblings crash (visible); this one under-reports (invisible). Both
  need the same root investigation, so a fix for 0022 that only adds `.get()` guards to the other
  three converts three crashes into three more silent under-counts.

---

# Answers to the specific questions asked

### Q2 — every path that makes the percentage wrong in the *safe* (higher) direction

| path | diagnostic? | ranked |
|---|---|---|
| namespace / zip package drops its un-executed denominator | **none** | **N1** |
| `ignore_errors` drops an unreadable/missing file | warning, no count, coarse slug | **N3** |
| non-`.py` file raising `NotPython` is dropped | **none, ever** | CRF-COVPY-0021 |
| any of the above while the program quieted `warnings` | **none** | **N2** |
| zero-statement file counted as 100% (`results.py:336-340`) | none | CRF-COVPY-0032 |
| `--fail-under` rounds toward the gate (`results.py:502`) | none | CRF-COVPY-0007 |
| XML `line-rate` publishes 99.997% as `1` (`xmlreport.py:33-38`) | none | CRF-COVPY-0008 |
| user-written `__annotate__` body dropped from statements (`bytecode.py:41`) | none | CRF-COVPY-0033 |
| `sysmon_line_lines` discards a line event when `code_info` is None | none | see propagation note |
| `[report] omit` / `include` filtering (`report_core.py:85-91`) | none — but user-requested | not a finding |

The four un-catalogued entries are N1, N3, N2's amplification of all of them, and the `sysmon` half.

### Q4 — `warn()` sites and their silent siblings

18 `warn()` call sites; the silent siblings found are N4 (`pytracer` desync vs. `pytracer` trace-changed),
N5 (`core` ctrace fallback vs. `core` sysmon fallback), N7 (`inorout` unmeasurable-file vs.
`report_core` unreportable-file), N3 (report drop count vs. `report.py` skip counts and `data.py`
combine counts), and N1 (nothing warns that a whole package was skipped, while `inorout.py:561-577`
warns about three lesser variants of "we didn't measure your source").

Two `warn()` sites I checked and found **correctly guarded**, listed so they are not re-litigated:
`inorout.py:415-427` (plugin `file_tracer` exception → warn + disable, with `collector.py:403-411`
as the matching runtime path), and `data.py:203-214` (unreadable data file → warn, count, and do not
delete the file).

### Q5 — can a warning that matters be suppressed more broadly than intended?

Yes, three ways, in decreasing order of severity:

1. **N2** — not by `disable_warnings` at all, but by the `warnings` filter, which the measured program
   owns. This suppresses *everything*, including the un-sluggable ones.
2. **N3** — the slug `couldnt-parse` covers two unrelated failures, so `disable_warnings =
   couldnt-parse` (a reasonable setting for a project with vendored/generated files) also hides a
   missing source file that just inflated the total to 100%.
3. **`control.py:483-484`** — `if not self._no_warn_slugs: self._no_warn_slugs = set(...)`. The set is
   read from config lazily and **only while it is still empty**. Once any `once=True` warning has
   fired (line 497-499) the set is non-empty, so a later
   `set_option("run:disable_warnings", [...])` never takes effect. Small, but combined with
   CRF-COVPY-0027 (`set_option` bypasses `post_process`) it means the programmatic API for warning
   suppression is order-dependent in a way nothing documents. Fix: read `disable_warnings` in
   `_warn` unconditionally and keep the `once` slugs in a separate set.

`disable_warnings` itself is exact-slug matching with no globbing, so there is no over-broad *pattern*
in coverage's own machinery. CRF-COVPY-0040 (six slugless warnings unreachable by `disable_warnings`)
is confirmed still present and is the converse problem.

---

# Hypotheses tested and NOT confirmed — do not re-derive

- **`flush_data()` returning False suppresses `touch_files`.** `control.py:932-933` calls
  `_post_save_work()` — which does the un-executed-file touching *and* emits the "No data was
  collected" warning — only when `Collector.flush_data()` returns True, and `flush_data` returns
  False when no tracer reports activity (`collector.py:450-451`). I tried to reach it via
  `switch_context()` (which calls `flush_data()` then `_clear_data()` → `tracer.reset_activity()`,
  `collector.py:189-190`) immediately before `save()`. Not reproducible: `PyTracer._activity` is set
  on *every* `call` event (`pytracer.py:204`) and `SysMonitor._activity` on every `PY_START`
  (`sysmon.py:319`), before any should-trace decision, so the interpreter's own continued execution
  re-arms it. Recording the reasoning because the coupling is real and a future change to when
  `_activity` is set would open it.

- **`sqlitedb.py:119-132` / `:199-205` retry-once-on-any-`Exception`.** Looks like a swallow, but the
  retry re-raises on second failure and the SQL involved is `INSERT OR REPLACE` / `INSERT OR IGNORE`,
  so a partial first attempt is idempotent. Callers pass materialised lists, not generators, so the
  `executemany` retry cannot consume a half-drained iterator. Dismissed.

- **`data.py:117-129` `classify()` returning `"combine"` when hashing fails.** Fails toward *more*
  work, and coverage data union is idempotent. Dismissed as correct-by-design (the comment says so).

- **`html.py:754-770` status-file read failing → `usable = False`.** Fails toward regenerating
  everything. Dismissed.

---

# Statistics

| | |
|---|---|
| error-handling sites traversed | 76 `except` handlers + 18 `warn()` sites + 6 sentinel-return helpers |
| catalogued findings verified still present | 44 of 44 with a code-level `file:line` (9 with line drift) |
| catalogued findings observed fixed | 0 |
| **novel findings** | **8** (3 FIX, 5 CONSIDER) |
| reproduced end-to-end with a command and an exit code | 4 (N1, N2, N3, N6) |
| additional sites of catalogued roots (fix-propagation) | 2 |
| new shapes proposed | 2 |
| hypotheses tested and dropped | 4 |
