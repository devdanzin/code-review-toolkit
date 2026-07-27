# consistency-auditor — coverage.py (informed pass)

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259ab` (main, 2026-07-26), 44 files.
**Tree edited:** **No.** All work was done on `/tmp/covrepro` (`git archive HEAD | tar -x`) and scratch dirs
under `/tmp/covtest`. Verified after the run: `git -C /home/danzin/projects/coveragepy status --porcelain`
shows no modified tracked files and `HEAD` is still `6b3259ab`. The five untracked paths present
(`ctracer_repros/`, `repro.py`, three `ctracer_review_*.md`) predate this run and are not mine.

**Scope:** the narrow mechanical question — where does coverage.py disagree with *itself* on a convention,
with a behavioural consequence. Backend-vs-backend divergence is `pattern-consistency-checker`'s and is not
re-litigated here.

**Everything below with a "reproduced" tag was executed** against the `/tmp/covrepro` copy on CPython 3.14.4.

---

## Summary

Five novel findings, four of them FIX-class and three of them **silently wrong** rather than loud. The
headline is not on the path-handling axis the briefing predicted — path handling turned out to be well
covered by CRF-COVPY-0014/0015 and I found one new *site* rather than a new root. The sharpest novel finding
is on the data layer: **`CoverageData`'s read accessors are split down the middle over whether they run a
destructive initializer**, so a read-only reporting call on an unloaded data file *deletes the user's
`.coverage`* and then reports "No data to report." The second sharpest is that "which config options are
lists" is declared in two places that disagree, and one of the disagreements (`report_contexts`) makes
`Coverage.report()` return **wrong coverage numbers with no error**.

Both ruff hits named in the brief (`S608`, `S302`) are false positives, and their sibling sites *are*
consistent — but the `S608` line is, by coincidence, the exact line where novel finding N2 lands.

---

## Catalogued — confirmed still present, not re-litigated

Verified on my five axes only. Line numbers are current at `6b3259ab`.

| ID | Site now | Status |
|---|---|---|
| CRF-COVPY-0011 | `sqldata.py:468-475` (`INSERT OR REPLACE INTO file`) | present, verbatim |
| CRF-COVPY-0014 | `python.py:155-161` vs `inorout.py:401` | present; **new site found — see N3** |
| CRF-COVPY-0015 | `files.py:211-215` (`prep_patterns`, `abs_file` only for non-`*` patterns) | present |
| CRF-COVPY-0016 | `config.py:50-56`, `config.py:319-323` | present |
| CRF-COVPY-0023 | `files.py:133-139` (`except Exception: files = []`, cached) | present |
| CRF-COVPY-0027 | `config.py:494-529` (`set_option` bypasses `post_process`) | present |
| CRF-COVPY-0035 | `files.py:509` (`path.replace(m[0], result)`) | present |
| CRF-COVPY-0042 | `sysmon.py:253` (`raise RuntimeError("No sys.monitoring tool id is available")`) | present; **more sites found — see N5** |
| CRF-COVPY-0043 | `html.py:289-294` (two-level fallback) vs `xmlreport.py:176` / `lcovreport.py:207` (direct read) | present — owned by pattern-consistency, not expanded here |
| CRF-COVPY-0059 | `sqldata.py:912-929` (`write()` lacks the `no_disk` guard) | present |

Note that CRF-COVPY-0059 is the *same family* as novel finding N1: `sqldata.py` has an established habit of
one method in a sibling group omitting a guard the others have.

---

## N1 — `CoverageData`'s read accessors disagree about a destructive precondition; the majority erase your data file

**Classification: FIX.** **Novel — proposed shape `read-path-shares-a-destructive-initializer-with-the-write-path`.**

### The two sides

`sqldata.py:931-940`:

```python
def _start_using(self) -> None:
    """Call this before using the database at all."""
    if self._pid != os.getpid():
        self._reset(); self._choose_filename(); self._pid = os.getpid()
    if not self._have_used:
        self.erase()          # <-- file_be_gone(self._filename)  (sqldata.py:897)
    self._have_used = True
```

`_have_used` is set to `True` by exactly one method — `read()` (`sqldata.py:906-910`). Every accessor that
runs `_start_using()` **without a prior `read()` deletes the database file.**

Of the seven public query methods, five call it and two do not:

| method | line | `_start_using()`? | behaviour on an unread `CoverageData` |
|---|---|---|---|
| `__bool__` | 403 | **no** | opens the DB, answers correctly, leaves file intact |
| `has_arcs` | 942 | **no** | returns in-memory `self._has_arcs`, file intact |
| `measured_files` | 946 | **no** | returns `set(self._file_map)`, file intact |
| `measured_contexts` | 955 → 961 | yes | **erases the file**, returns `set()` |
| `file_tracer` | 967 → 975 | yes | **erases the file**, returns `None` |
| `lines` | 1022 → 1032 | yes | **erases the file**, returns `None` |
| `arcs` | 1057 → 1074 | yes | **erases the file**, returns `None` |
| `contexts_by_lineno` | 1089 → 1098 | yes | **erases the file**, returns `{}` |

(`set_query_context` :985→996 and `set_query_contexts` :1001→1013 are in the destructive group too.)

### Which side is correct

The two non-callers are correct in *behaviour* (a query must not destroy its subject) and wrong in
*result* (they answer from stale in-memory state instead of the file). The five callers are wrong outright.
The real defect is that `_start_using()` conflates two different preconditions — "prepare to **write**, so
discard stale data" and "prepare to **read**" — and the read path was wired to the write path's initializer.

The class docstring (`sqldata.py:185-192`) groups `measured_files`, `has_arcs` and `bool()` together with
`lines`/`arcs`/`file_tracer` as the reading API, which is exactly the expectation the code violates.

### Reproduced

Interleaving the two groups on one object produces a self-contradiction *and* data loss:

```
size: 53248
bool(d)          -> True                       | file: 53248
d.has_arcs()     -> False                      | file: 53248
d.measured_files -> ['mk.py', 'prog.py']       | file: 53248
d.lines(known f) -> None                       | file: erased+recreated empty
d.measured_files -> []                         | file: empty
```

`measured_files()` names a file as measured; the very next `lines()` on that same file returns `None`
*and* destroys the database.

At the `Coverage` level the consequence is worse, because the error message blames the user:

```python
cov = coverage.Coverage(data_file=".coverage")   # forgot cov.load()
cov.report(file=buf)
# -> NoDataError: No data to report.
# and .coverage now contains nothing
```

Reproduced end to end: `BEFORE: ['/tmp/covtest/probe/mk.py', '/tmp/covtest/probe/prog.py']` →
`report()` raises `NoDataError` → `AFTER : []`.

`read()` is documented as required (`sqldata.py:185`), which is why this is a defect of *forgivingness*, not
of contract — but nothing documents that forgetting it is destructive, and the CLI is only safe because
`cmdline.py:870`, `:889`, `:1043` all call `load()` first. Any API user (pytest-cov-style integrations,
`coverage.CoverageData` consumers, notebook use) is one missing `read()` away from losing a run.

### Fix

Split the concern. `_start_using()` should keep the erase only for the mutating entry points
(`add_lines` :547, `add_arcs` :588, `add_file_tracers` :641, `touch_files` :676, `purge_files` :695,
`update` :737, `_context_id` :480); the query entry points should call a non-destructive
`_start_reading()` that opens the DB and populates `_file_map` — i.e. what `read()` already does. That also
fixes `measured_files()`/`has_arcs()` answering from stale state, so both halves of the split converge on
one behaviour rather than two wrong ones.

---

## N2 — "which options are lists" is declared twice, and the two declarations disagree; one gap makes `report()` return wrong numbers silently

**Classification: FIX.** Catalogued shape `same-fact-derived-from-two-sources` — **new site.**

### The two sources

1. `config.py:266-275` — `MUST_BE_LIST`, used by `from_args()` (`config.py:288-294`) to coerce a bare `str`
   into `[str]` for values arriving from the constructor, from `override_config()` (`control.py:77-89`), and
   from every `Coverage.report()`/`html_report()`/… keyword.
2. `config.py:396-469` — `CONFIG_FILE_OPTIONS`, whose `"list"` / `"regexlist"` type tag decides list
   treatment for values arriving from a config file.

Options tagged `"list"` in source 2 but **absent** from source 1:

`source`, `source_pkgs`, `source_dirs`, `report_contexts` (plus the five `"regexlist"` options, which are not
reachable as constructor kwargs).

### The silent one

`report_contexts` (`config.py:441`) flows to `sqldata.set_query_contexts()` from three call sites —
`report.py:209`, `html.py:132`, `jsonreport.py:79` — and lands on `sqldata.py:1015-1017`:

```python
context_clause = " or ".join(["context REGEXP ?"] * len(contexts))
with con.execute("SELECT id FROM context WHERE " + context_clause, contexts) as cur:
```

A bare `str` has a `len()` and *is* a sequence, so a string of N characters becomes **N single-character
regexes**, each matched with `re.search`. No exception is raised anywhere.

**Reproduced** through the public API, on data collected under a context named `abc`:

```
cov.report(contexts=['abcq'])   ->  prog.py   2   2    0%   TOTAL  10  10   0%    # correct
cov.report(contexts='abcq')     ->  prog.py   2   0  100%   TOTAL  10   8  20%    # WRONG
```

The bare string is split into `a`,`b`,`c`,`q`; `re.search("a", "abc")` matches, so a context the user
explicitly did not ask for is included. The report is wrong, the exit status is wrong, and nothing warns.

The **guarded twin is in the same call**: `cov.report(omit="*/t.py")` works correctly, because
`report_omit` *is* in `MUST_BE_LIST`. Two keyword arguments of one method, same str-instead-of-list mistake,
one normalised and one not.

### The loud ones

`source`, `source_pkgs`, `source_dirs` have the same gap but fail visibly. Reproduced:

```
Coverage(source_pkgs=['prog'])  -> prog.py 100%
Coverage(source_pkgs='prog')    -> NoDataError, plus
                                   "Module p was never imported."
                                   "Module r was never imported."
                                   "Module o was never imported."
                                   "Module g was never imported."
```

Also confirmed: `Coverage(omit='*.py')` → `run_omit == ['*.py']` (normalised), while
`Coverage(source_pkgs='mypkg')` → `source_pkgs == 'mypkg'` (not normalised).

### Fix

Derive one from the other rather than maintaining both: build `MUST_BE_LIST` from the `"list"`-tagged entries
of `CONFIG_FILE_OPTIONS` at class-definition time. That closes all four gaps at once and makes future
additions self-consistent. Minimum fix: add `report_contexts`, `source`, `source_pkgs`, `source_dirs` to
`config.py:266-275`.

---

## N3 — report-time `omit`/`include` compares a realpath-normalised pattern against an un-normalised filename

**Classification: FIX.** Catalogued shape `two-sides-of-a-comparison-normalized-differently` — **new site**
of the CRF-COVPY-0014 root.

### The two sides

- **Pattern side** — `report_core.py:85-91` builds the matcher from `prep_patterns(...)`, and
  `files.py:213-214` appends `abs_file(p)` for every pattern not starting with `*`/`?`. `abs_file`
  (`files.py:158`) is `actual_path(os.path.abspath(os.path.realpath(path)))` — **symlinks resolved.**
- **Value side** — `report_core.py:87` and `:91` match against `fr.filename`. For `PythonFileReporter`,
  `python.py:155-161` skips canonicalisation entirely when `relative_files` is set:

```python
fname = filename
canonicalize = True
if self.coverage is not None:
    if self.coverage.config.relative_files:
        canonicalize = False
if canonicalize:
    fname = canonical_filename(filename)
```

So with `relative_files = True` the pattern is realpath-resolved and the value is not.

### Reproduced

`src/{a,b}.py`, symlink `lnk -> src`, `source=["lnk"]`, `omit=["lnk/b.py"]`:

```
relative_files=False  ->  src/a.py 100%                    TOTAL 2 stmts   # b.py omitted
relative_files=True   ->  src/a.py 100%, src/b.py 100%     TOTAL 4 stmts   # b.py NOT omitted
```

Identical config, identical data; `--omit` silently stops working the moment `relative_files` is on and the
path is reached through a symlink. Because it fails *open*, the user sees extra files in the report rather
than an error — and in a `--fail-under` gate the totals move in the permissive direction.

This is distinct from CRF-COVPY-0014 (which is about coverage attribution) and CRF-COVPY-0015 (which is
about `*`-prefixed patterns skipping `abs_file` entirely). Same root, third consequence surface.

### Fix

Same as CRF-COVPY-0014: `report_core.py` should match against a canonicalised value, or `python.py:155-161`
should canonicalise unconditionally and let `_file_mapper` do the relativising (which is what
`control.py:1009` already does for the *data* lookup one line later). The current arrangement has
`fr.filename` meaning two different things depending on a config flag, which is the underlying defect.

---

## N4 — `SqliteDb` wraps `sqlite3.Error` in three methods and not in four; the unwrapped ones are on the collection hot path

**Classification: FIX.** Catalogued shape `error-escapes-the-project-exception-hierarchy` — **new site,
with the guarded twin ten lines away in the same file.**

`sqlitedb.py:116-132` (`_execute`) and `sqlitedb.py:190-205` (`_executemany`) implement the *identical*
"retry once, see issue #1010" idiom. One wraps, one does not:

```python
# _execute — sqlitedb.py:119-132
try:
    try:              return self.con.execute(sql, parameters)
    except Exception: return self.con.execute(sql, parameters)   # issue #1010 retry
except sqlite3.Error as exc:
    raise DataError(f"Couldn't use data file {self.filename!r}: {msg}") from exc   # <-- present

# _executemany — sqlitedb.py:199-205
try:              return self.con.executemany(sql, data)
except Exception: return self.con.executemany(sql, data)         # issue #1010 retry
#                                                                # <-- no wrap at all
```

Unwrapped methods and their reachability:

| method | line | reached from |
|---|---|---|
| `_executemany` / `executemany_void` | 190-209 | `sqldata.py:601` (`add_arcs` — **the branch-coverage write path**), `sqldata.py:371` (`_init_db`) |
| `executescript` | 211-221 | `sqldata.py:353` (`_init_db` schema), `sqldata.py:458` (`loads`) |
| `dump` | 223-226 | `sqldata.py:432` (`dumps`) |
| `close` | 88-91 | `sqldata.py:391` (defused there by a local `except Exception`, exposed for any other caller) |

### Reproduced

Same failing statement through the three entry points:

```
execute_void      (wrapped)   -> coverage.exceptions.DataError: Couldn't use data file '...': no such table: nosuch
executemany_void  (UNWRAPPED) -> sqlite3.OperationalError: no such table: nosuch
executescript     (UNWRAPPED) -> sqlite3.OperationalError: no such table: nosuch
```

`DataError` is a `CoverageException`, so `cmdline.py:1184` turns it into a one-line error message and exit
code 1. A raw `sqlite3.OperationalError` bypasses that handler entirely and prints a traceback out of
`sqlitedb.py`.

Two downstream consequences of the gap, both from the same root:

- `CoverageData.__bool__` (`sqldata.py:403-410`) catches `CoverageException` and returns `False`, but its
  call chain reaches the **unwrapped** `executescript` via `_init_db` (`sqldata.py:350,353`). A dunder that
  is expected to be total can raise `sqlite3.Error`.
- `data.py:206` (`combine_parallel_data`) catches `CoverageException` per file and counts it as `errored`.
  A participant file that trips an unwrapped path aborts the whole `coverage combine` with a traceback
  instead of being skipped with a warning — while `sqldata.py:330-336` correctly converts the *neighbouring*
  "isn't a coverage data file" condition into `DataError`.

### Fix

Give `_executemany`, `executescript` and `dump` the same `except sqlite3.Error → DataError` wrapper
`_execute` has. Three lines each, and `execute_void`'s `fail_ok` (`sqlitedb.py:159-161`) already proves
`DataError` is the intended contract for this class.

---

## N5 — the same error *condition* is raised as a project exception in one place and a builtin/generic in its sibling

**Classification: CONSIDER.** Shape `error-escapes-the-project-exception-hierarchy` — new sites beyond
CRF-COVPY-0042.

The hierarchy is flat and clean: everything in `exceptions.py` descends from `CoverageException`
(`exceptions.py:11`), and `cmdline.py:1184` catches exactly that, so all 66 project raise sites produce a
clean message. The inconsistency is entirely in which conditions were given a project exception at all.

| pair | project-typed side | untyped side | consequence |
|---|---|---|---|
| `[run] patch` validation | `patch.py:44` `ConfigError("Unknown patch …")` | `patch.py:66` and `patch.py:108` `CoverageException("patch=execv/fork isn't supported yet on Windows.")` | `except ConfigError` around config setup catches one of three failures for the *same option*. `patch.py:14` already imports both names. |
| config value has the wrong type | `tomlconfig.py:107,112,143` and `config.py:80,104` `ConfigError` | `tomlconfig.py:173,176` bare `ValueError` | normalised only by `config.py:333-334`, which wraps *only* the `CONFIG_FILE_OPTIONS` loop; any other caller of the public `TomlConfigParser.getboolean/getint/…` (`tomlconfig.py:180-212`) leaks a raw `ValueError`. The wrapper also relabels a *value* error as "Couldn't read config file". |
| plugin contract violation | `plugin_support.py:50` `PluginError` (missing `coverage_init`) | `misc.py:217` `NotImplementedError` via `plugin.py:189,292,438` (missing `file_reporter`/`source_filename`/`lines`) | two neighbouring plugin defects, two different user experiences: clean message vs. traceback |
| "object not in a usable state" | `sqldata.py:679,702` `DataError` | `control.py:795` `CoverageException("Cannot switch context, coverage is not started")` | identical shape, one typed one not |
| "no source for this module" | `python.py:67` `NoSource(..., slug="no-source")` | `python.py:139` `CoverageException(f"Module {morf} has no file")` | **72 lines apart in one file**, and `NoSource` is already imported at `python.py:15` |
| config `$VAR` expansion failure | every other failure on that path is `ConfigError` | `misc.py:280` `CoverageException(f"Variable {word} is undefined")` | only reachable from config expansion (`config.py`, `tomlconfig.py:124`) |

Adjacent, same root: the `slug` mechanism (`exceptions.py:14-27`, consumed at `cmdline.py:1187-1188` to emit
a docs URL) is used by **4 of 66** raise sites. `python.py:67` passes `slug="no-source"` while the other six
`NoSource` raises (`execfile.py:51,53,60,162,305`, `parser.py:98`) do not — so whether the user gets a
documentation link depends on which code path noticed the missing source. Zero of the 26 `ConfigError` sites
carry one. This is the same shape as catalogued CRF-COVPY-0040 (six warnings with no slug), one layer down.

---

## N6 — encoding conventions at read/write boundaries

**Classification: POLICY / CONSIDER.** No FIX here; the divergences are real but two of the three are
documented or bounded.

The canonical source reader is `python.py:45-76`: binary read (`python.py:39`), PEP 263 / BOM sniff via
`tokenize.detect_encoding` (`phystokens.py:191-200`), then
`source_bytes.decode(source_encoding(source_bytes), "replace")` (`python.py:71`) — the only `errors=` on a
decode in the whole package.

1. **`plugin.py:426` vs `python.py:45` — POLICY, documented.** The base `FileReporter.source()` is
   `open(self.filename, encoding="utf-8")` — hard-wired codec, `errors="strict"`, no `\f` fix, no trailing-
   newline guarantee. The docstring (`plugin.py:421-423`) explicitly says "decodes it as UTF-8. Override
   this method if your file isn't readable as a text file", so the divergence is intended. Worth stating
   anyway because the *failure mode* is not bounded: `source()` is called from `annotate.py:87`,
   `html.py:826`, `lcovreport.py:213`, all **outside** `get_analysis_to_report`'s handler
   (`report_core.py:103-121`), so a `UnicodeDecodeError` from a plugin's default `source()` escapes even
   with `ignore_errors=True`. If the maintainer wants that bounded, the cheap fix is to widen the
   `report_core.py` handler rather than to change the documented default.

2. **`report_core.py:47-54` — CONSIDER.** `-o -` yields `sys.stdout` (locale / `PYTHONIOENCODING`);
   `-o file` yields `open(..., encoding="utf-8")`. XML is the only report that emits raw non-ASCII, and
   `xmlreport.py` calls `toprettyxml()` with no `encoding=` argument, so the document carries **no encoding
   declaration**. `coverage xml -o out.xml` and `coverage xml -o - > out.xml` can therefore produce
   different bytes for identical input, and only one of them is self-describing.

3. **`sysmon.py:110-114` vs `pytracer.py:129` / `debug.py:487,494` — ACCEPTABLE.** Three near-identical
   append-loggers; only `sysmon.py` guards `UnicodeError` and falls back to `ascii(msg)`. Debug-only path.

Also noted, no action: `files.py:104` spells the codec `"UTF-8"` where the other 20-odd sites spell it
`"utf-8"`; `config.py:599,604` and `sqldata.py:922` use bare `.encode()`/`.decode()` where the rest of the
package names the codec. The load-bearing invariant that keeps the strict encodes safe is
`inorout.py:500-504`, which rejects non-UTF-8-encodable filenames before they reach the DB — worth a comment
pointing at it, since removing that guard would break four unrelated sites.

---

## The two ruff hits — both dismissed, sibling sites are consistent

**`S608` at `sqldata.py:1017` — ACCEPTABLE (false positive).** The interpolated fragment is
`" or ".join(["context REGEXP ?"] * len(contexts))` — a repeated *literal* with `?` placeholders; the values
go through parameter binding. I checked all four dynamic-query builders and they use one convention:

| site | interpolated | bound |
|---|---|---|
| `sqldata.py:1016-1017` (`set_query_contexts`) | `"context REGEXP ?"` × N | `contexts` |
| `sqldata.py:1046-1048` (`lines`) | `", ".join("?" * N)` | `self._query_context_ids` |
| `sqldata.py:1080-1082` (`arcs`) | same | same |
| `sqldata.py:1114-1116`, `:1132-1134` (`contexts_by_lineno`) | same | same |

**No divergence — every site parameterises.** The irony is that this exact line *is* where a real defect
lives, just not an injection: the `len(contexts)` at `sqldata.py:1016` is what turns finding N2's bare string
into N single-character regexes.

**`S302` at `execfile.py:335` — ACCEPTABLE (false positive).** `marshal.load(fpyc)` is the only `marshal`
use in the package, and it is guarded: `execfile.py:320-321` rejects the file unless the first four bytes
equal `PYC_MAGIC_NUMBER`, and `execfile.py:336` asserts the result is a `CodeType`. Its sibling
`make_code_from_py` (`execfile.py:300-307`) compiles from source and needs no such guard. There is no
second unmarshalling site to be inconsistent with.

**Adjacent, ACCEPTABLE:** `sqlitedb.py:65` registers
`create_function("REGEXP", 2, lambda txt, pat: re.search(txt, pat) is not None)`. SQLite rewrites
`X REGEXP Y` as `regexp(Y, X)`, so the first argument is the *pattern* — the lambda's parameter names are
exactly backwards, while the body is correct. Cosmetic, but it invites a "fix" that would break the feature.

---

## Path handling — the enumeration the brief asked for

Every place a filename becomes a dict key or a DB key, with the normalisation applied on each side.

**The three normalisers.** `abs_file` (`files.py:158`) = `actual_path(abspath(realpath(p)))`, symlinks
resolved, case-corrected on Windows. `canonical_filename` (`files.py:65-87`) = resolve a relative path
against `os.curdir + sys.path` if it exists there, then `abs_file`; memoised in a module global cleared only
by `set_relative_directory()`. `relative_filename` (`files.py:52-62`) = strip the `RELATIVE_DIR` prefix after
`normcase`, **no** `abspath`/`realpath` on the input.

**The DB key** is `file.path`, reached only through `_file_map` / `_file_id` (`sqldata.py:462-475`).

| # | key site | write side normalisation | read side normalisation | agree? |
|---|---|---|---|---|
| 1 | `_file_map` ← tracer data | `collector.py:485,491,494` → `file_mapper(canonical_filename(traced))` | — | — |
| 2 | `_file_map` ← unexecuted files | `control.py:961` → `file_mapper(canonical_filename(f))` (`inorout.py:616`) | — | matches #1 |
| 3 | `data.lines/arcs(filename)` for reporting | as #1 | `control.py:1009` → `file_mapper(fr.filename)`, and `fr.filename` is `canonical_filename(...)` **only when `relative_files` is off** (`python.py:155-161`) | **NO** — CRF-COVPY-0014 |
| 4 | `data.file_tracer(mapped_morf)` | as #1 | `control.py:1034` → `file_mapper(morf)` on a **raw user string**, no `canonical_filename` | **NO** — diverges for a relative morf that resolves via `sys.path`, and for `./x.py` under `relative_files` (`relative_filename("./x.py")` is a no-op, write side yields `"x.py"`). Consequence: the plugin `FileReporter` is silently not found and the file falls back to `PythonFileReporter` (`control.py:1050`). |
| 5 | `main.file.path = other_file_mapped.mapped_path` (combine) | `sqldata.py:762-766` `map_path(other_file.path)`; `map_path` is `PathAliases.map` or **identity when no `[paths]` is configured** (`data.py:172-175`) | `main.file.path` from #1 | equal-string join in SQLite (BINARY collation); both sides were produced by the same `file_mapper`, so consistent — but see CRF-COVPY-0035 for how `map` itself rewrites |
| 6 | report `include`/`omit` matching | patterns: `prep_patterns` → `abs_file` (`files.py:214`) | values: `fr.filename` (`report_core.py:87,91`) | **NO** — finding N3 |
| 7 | run-time `include`/`omit` matching | patterns: `prep_patterns` → `abs_file` | values: `disp.source_filename` = `canonical_filename(...)` (`inorout.py:401,419`) | yes |
| 8 | HTML incremental cache | key = `flat_rootname(fr.relative_filename())` (`html.py:234`, `:830`) | same | yes, but `relname` is module-name-derived for a module morf and path-derived for a string morf (`python.py:164-171`), so the same file can key two ways across invocations |
| 9 | XML package derivation | `self.source_paths` = `canonical_filename(src)` or raw `src.rstrip("/")` under `relative_files` (`xmlreport.py:70-73`) | `fr.filename` (`xmlreport.py:183-188`) | consistent *within* each `relative_files` branch |

**Cache-invalidation asymmetry, ACCEPTABLE.** `files.py` holds three module-level caches —
`CANONICAL_FILENAME_CACHE` (:26), `_ACTUAL_PATH_CACHE` (:114) and `_ACTUAL_PATH_LIST_CACHE` (:115).
`set_relative_directory()` (:29-44) clears only the first. The other two are Windows-only and keyed on
absolute paths, so the practical exposure is small, but the invalidation hook covering one of three siblings
is the same omission pattern as CRF-COVPY-0059.

**Pointer, not my finding:** `collector.py:413-416` puts `functools.cache` on a *method*
(`cached_mapped_file`), so every `Collector` — and transitively its `CoverageData` and `Coverage` — is
retained for the process lifetime. That is `python-pitfall-scanner`'s `lru_cache-on-method` shape; flagging
it here only so it is not lost.

---

## Ranked recommendations

1. **N1** (`sqldata.py:931-940` + the 7-vs-2 accessor split) — a read that deletes the user's data. Split
   `_start_using()` into a mutating and a reading variant. Highest severity, and the fix is local.
2. **N2** (`config.py:266-275` vs `:396-469`) — derive `MUST_BE_LIST` from `CONFIG_FILE_OPTIONS`. One-line
   root fix; removes a silently-wrong report.
3. **N4** (`sqlitedb.py:190-226`) — copy `_execute`'s `except sqlite3.Error → DataError` into
   `_executemany`, `executescript`, `dump`. Mechanical, and it makes `combine` degrade per-file as designed.
4. **N3** (`report_core.py:87,91` + `python.py:155-161`) — make `fr.filename` mean one thing. Shares a root
   with CRF-COVPY-0014, so fix them together.
5. **N5** (`patch.py:66,108`; `tomlconfig.py:173,176`; `misc.py:217`; `python.py:139`; `control.py:795`;
   `misc.py:280`) — retype to the existing hierarchy. Low risk, no behaviour change for correct input.
6. **N6.2** (`report_core.py:47-54` + `xmlreport.py` `toprettyxml`) — decide one encoding policy for
   `-o -`, and emit an XML declaration that names it.

Not worth churn: the `"UTF-8"`/`"utf-8"` spelling split, the `REGEXP` parameter names, the `files.py` cache
invalidation, the `slug` coverage gap (fold into CRF-COVPY-0040).

Nothing in the report was inferred without either running it or reading both sides at the cited lines. Happy
to expand any single axis — the `_file_map` key table (§ Path handling) and the exception-type inventory both
have more sites than I reported here.
