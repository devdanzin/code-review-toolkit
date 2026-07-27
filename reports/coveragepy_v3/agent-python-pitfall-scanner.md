# python-pitfall-scanner — informed triage of coverage.py

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Mode:** informed re-review. 60 findings already catalogued (CRF-COVPY-0001..0060); confirm-don't-re-litigate applied.
**Scanner input:** `reports/coveragepy_v3/scan_python_pitfalls.json` (26 candidates, not re-run) + the pinned-ruff `zip()` sweep (6 sites).

## Target-tree integrity

**I did not edit the target tree.** All reading, execution and reproduction was done against
`/tmp/covrepro` (created with `git -C /home/danzin/projects/coveragepy archive HEAD | tar -x -C /tmp/covrepro`)
and a scratch package under `/tmp/covwork`. Verified at end of run:

```
$ git -C /home/danzin/projects/coveragepy rev-parse HEAD
6b3259abb64a3cb80b4800f58fe1c71b24970110
$ git -C /home/danzin/projects/coveragepy status --porcelain
?? ctracer_repros/                       # pre-existing, not mine
?? ctracer_review_cext_toolkit.md        # pre-existing, not mine
?? ctracer_review_cext_toolkit_full.md   # pre-existing, not mine
?? ctracer_review_cpython_toolkit.md     # pre-existing, not mine
?? repro.py                              # pre-existing, not mine
```

No tracked file is modified. HEAD is unmoved.

## `by_directory` read (Phase 2)

`summary.by_directory` is `{"coverage": 26}` — 100% of findings in hand-written source, zero in
`tests/`, `lab/`, `doc/` or any generated tree. **No directory dominates for generated-content
reasons; no `--exclude` was warranted and none was applied.** The scanner scoped itself to the
package, which is why the four real `zip` candidates in `tests/` had to come from the ruff sweep and
a manual grep.

---

# PRIORITY 1 — the `zip-truncates-on-length-mismatch` sweep

**Verdict: all six pinned sites are false positives. One real instance exists, and the scanner never
saw it because it lives in `tests/`.**

I ran the full sibling hunt: `grep -rn "zip(" ` over the whole repo returns **6 sites in `coverage/`
and 7 in `tests/`**, and **`strict=` appears nowhere in the project**. So the catalogue's usual
"twin in the project's own tests" does not exist here — but a *better* twin does, described below.

### The four `report.py` sites — dismissed, one shared reason

| # | Location | Verdict | Operands |
|---|---|---|---|
| 1 | `report.py:106` | FP — deliberate truncation | `zip(header, values)` |
| 2 | `report.py:117` | FP — provably equal length | `zip(header, total_line)` |
| 3 | `report.py:176` | FP — deliberate truncation | `zip(header, values)` |
| 4 | `report.py:188` | FP — provably equal length | `zip(header, total_line)` |

All three operands are built in **one function**, `SummaryReporter.tabular_report()`
(`coverage/report.py:223-291`), from **the same two booleans** (`self.branches`,
`self.config.show_missing`) in **the same order**:

```python
header  = ["Name","Stmts","Miss"] + (["Branch","BrPart"] if branches) + ["Cover"] + (["Missing"] if show_missing)
args    = [name,   stmts,  miss ] + ([branch, brpart]    if branches) + [pc_str]  + ([missing]   if show_missing) + [nums.pc_covered]
total   = ["TOTAL",stmts,  miss ] + ([branch, brpart]    if branches) + [pc_str]  + ([""]        if show_missing)
```

There is no third source of length. I confirmed this by execution over all four
(`branch` × `show_missing`) configurations, instrumenting `report_text`:

```
branch=False show_missing=False   header(4)  values(5)  total(4)
branch=False show_missing=True    header(5)  values(6)  total(5)
branch=True  show_missing=False   header(6)  values(7)  total(6)
branch=True  show_missing=True    header(7)  values(8)  total(7)
```

`len(values) == len(header) + 1` in every configuration. **The surplus element is deliberate and
load-bearing**: it is `nums.pc_covered`, the raw float appended at `report.py:248` so that
`--sort=cover` sorts numerically rather than lexicographically (`column_order = dict(..., cover=-1)`
at `report.py:233`). The `zip` at `:106`/`:176` exists precisely to drop it before formatting.
`total_line` carries no sort key, so `:117`/`:188` are exactly balanced.

Per the shape's own differential ("Do NOT report when both operands are provably equal-length"),
these four are dismissed. **What makes them all the same:** they are not two computations over the
same data, they are two renderings of one branch decision made once in one scope.

*Robustness note (not a finding).* The truncation at `:106`/`:176` is undocumented. A second
appended sort key would be silently swallowed the same way. `values[: len(header)]` would express
the intent; `strict=True` on `:117`/`:188` costs nothing since those are already exact.

### `html.py:385` — dismissed with the stated reason

```python
for ftr1, ftr2 in zip(files_to_report[:-1], files_to_report[1:]):
```

**A `zip` over two slices of the same list is not this shape.** Both operands are length `n-1` by
construction; the whole block is guarded by `if files_to_report:`. This is the standard pairwise
idiom for threading prev/next links. Dismissed.

### `sysmon.py:134` — dismissed (debug-only, and currently balanced)

```python
for name, arg in zip(names, args):
```

This *is* the shape structurally — `names` is authored per-decoration, `args` comes from CPython's
`sys.monitoring` callback ABI — but:

1. It lives inside `if LOG:` (`sysmon.py:64`), gated on `COVERAGE_SYSMON_LOG`, marked
   `# pragma: debugging`. The non-LOG `panopticon` (`sysmon.py:163-170`) is a no-op decorator.
2. I checked **every** decoration site against its method signature and all are exactly balanced:
   `@panopticon()` at `:240`, `:270`, `:299` decorate zero-arg methods (`start`, `stop`,
   `post_fork`); `@panopticon("code","@")` → `sysmon_py_start(self, code, instruction_offset)`;
   `@panopticon("code","@",None)` → `sysmon_py_return(self, code, offset, retval)`;
   `@panopticon("code","line")` → `sysmon_line_lines`/`sysmon_line_arcs`;
   `@panopticon("code","@","@")` → `sysmon_branch_either(self, code, offset, destination)`.

The only consequence of future drift (CPython adding a monitoring-callback argument) is a maintainer
debug log missing a field. ACCEPTABLE.

### The one real instance — `tests/test_data.py:1091`

### [CONSIDER] `zip-truncates-on-length-mismatch` — 1 instance

**What it is:** a parametrized test zips a list whose length is derived from one parametrize
argument against a *different* parametrize argument, with no length assertion.
**Why it is silent:** the test still passes, having asserted less than it claims. This is
`test-cannot-fail` arriving by another route, exactly as the shape's differential predicts.

| # | Location | Confidence | Notes |
|---|---|---|---|
| 1 | `tests/test_data.py:1091` | medium | `zip(datas, combine_or_skip)`; operands from two independently-authored strings |

```python
@pytest.mark.parametrize("spec, combine_or_skip", [
    ("abcdef", "cccccc"), ("aaaaaa", "csssss"),
    ("ababac", "ccsssc"), ("aaaaab", "cssssc"),
])
@pytest.mark.parametrize("arcs", [False, True])
def test_skipping_duplicates(self, spec, combine_or_skip, arcs):
    datas = self.make_data_files(spec, arcs=arcs)
    for data_file, c_or_s in zip(datas, combine_or_skip):
        file_action = classifier.classify(data_file.data_filename())
        assert file_action[0] == c_or_s
```

`make_data_files` (`tests/test_data.py:1056-1076`) emits **one `CoverageData` per character of
`spec`**, so `len(datas) == len(spec)`. `combine_or_skip` is a separate literal in the same table
row. The two are equal in all four current rows, so the shape is latent — but it is exactly the
"different computations over the same underlying data" pattern.

**Failure scenario:** a maintainer adds a row for a 7-file case and types
`("abcdefg", "cccccc")` — six `c`s instead of seven. `zip` stops at six. The seventh data file is
never classified, `DataFileClassifier` is never asked the question the row was added to ask, and the
test passes green. The same slip in the other direction (`("abcdef", "ccccccc")`) also passes.

**Guarded twin:** `tests/helpers.py:335-336`, in this project's own test-support module —

```python
assert len(msgs) == len(actuals)
for actual, expected in zip(actuals, msgs):
```

`assert_coverage_warnings` pairs actuals against expecteds and puts the length assertion
*immediately* above the `zip`. That is the project's own standard for this exact operation.

**Fix:** `zip(datas, combine_or_skip, strict=True)` (the project is 3.9+ … `strict=` needs 3.10;
coverage supports 3.9, so in `tests/` — which runs on the dev interpreter — `strict=True` is fine;
otherwise mirror `helpers.py` with `assert len(datas) == len(combine_or_skip)`).

**Siblings checked:** all 13 `zip()` in the repo. `tests/test_html.py:1496`, `:1518`, `:1541` pair
two three-element literals defined two lines above each `zip` — provably equal, dismissed.
`tests/test_coverage.py:1620` and `tests/test_arcs.py:1939` are equal-length-by-construction.
`tests/helpers.py:336` is the guarded twin. No `strict=` exists anywhere in the project.

---

# PRIORITY 2 — the environment-numeric cluster

**Verdict: all five are real defects, but the catalogued shape is the wrong shape for them. I
propose a new shape (below) and report them under it.**

The catalogued `unvalidated-numeric-from-environment` is about a **dimension** — a size, count or
offset — reaching arithmetic unchecked, whose failure mode is "0 or negative propagates
downstream". **None of these five is a dimension.** All five are boolean debug toggles:

```python
coverage/sysmon.py:50   LOG           = bool(int(os.getenv("COVERAGE_SYSMON_LOG", 0)))
coverage/sysmon.py:53   COLLECT_STATS = bool(int(os.getenv("COVERAGE_SYSMON_STATS", 0)))
coverage/control.py:1424 if int(os.getenv("COVERAGE_DEBUG_CALLS", 0)):     # pragma: debugging
coverage/parser.py:711  dump_ast      = bool(int(os.getenv("COVERAGE_AST_DUMP", "0")))
coverage/parser.py:733  self.debug    = bool(int(os.getenv("COVERAGE_TRACK_ARCS", "0")))
```

0 and negative are harmless here; `int()` on a *non-numeric* value is not. **`int()` raises
`ValueError` for every value outside `{"0","1",...}` — including the empty string**, which is the
single most common way an environment variable is accidentally set.

### [FIX] `env-flag-parsed-as-strict-int` (NOVEL) — 5 instances

**What it is:** a boolean-valued environment variable parsed with a bare `int()`, with no try/except,
no empty-string default and no accepted vocabulary. Setting it to anything but a decimal integer —
including setting it to nothing — raises `ValueError` out of module import.
**Why it is silent:** three of the five raise during `import coverage`, and coverage's own `.pth`
bootstrap swallows import failure with a bare `except:` (`pth_file.py:13`, catalogued as
CRF-COVPY-0026). In a subprocess, the result is not a traceback — it is coverage silently not
running.

| # | Location | Confidence | When it fires | Reproduced |
|---|---|---|---|---|
| 1 | `coverage/sysmon.py:50` | high | `import coverage` | yes |
| 2 | `coverage/sysmon.py:53` | high | `import coverage` | yes |
| 3 | `coverage/control.py:1424` | high | `import coverage` | yes |
| 4 | `coverage/parser.py:711` | high | `AstArcAnalyzer.__init__`, i.e. report time under `branch` | yes |
| 5 | `coverage/parser.py:733` | high | same | yes |

All five reproduced against `/tmp/covrepro`:

```
$ COVERAGE_SYSMON_LOG=true  python3 -c "import coverage"
  File ".../coverage/sysmon.py", line 50, in <module>
    LOG = bool(int(os.getenv("COVERAGE_SYSMON_LOG", 0)))
ValueError: invalid literal for int() with base 10: 'true'

$ COVERAGE_SYSMON_LOG=      python3 -c "import coverage"     # set but EMPTY
ValueError: invalid literal for int() with base 10: ''

$ COVERAGE_SYSMON_STATS=yes python3 -c "import coverage"
ValueError: invalid literal for int() with base 10: 'yes'     # sysmon.py:53

$ COVERAGE_DEBUG_CALLS=on   python3 -c "import coverage"
ValueError: invalid literal for int() with base 10: 'on'      # control.py:1424

$ COVERAGE_AST_DUMP=true    python3 <branch-coverage report>
  File ".../coverage/parser.py", line 711, in __init__
ValueError: invalid literal for int() with base 10: 'true'    # escapes _analyze_ast uncaught
```

**Failure scenario (the silent one).** A CI job or Dockerfile does
`ENV COVERAGE_SYSMON_LOG=${SYSMON_LOG}` where `SYSMON_LOG` is unset, or a shell exports
`COVERAGE_SYSMON_LOG=` to "turn it off". Every `import coverage` in that environment now raises
`ValueError`. In the parent process the operator sees a traceback and can act. In every subprocess
started under `COVERAGE_PROCESS_START`, `pth_file.py:11-16` runs `try: import coverage / except:
pass`, so the exception is discarded and `coverage.process_startup()` is never reached: **the
subprocess contributes zero data, with no warning, no log line, and a coverage report that is simply
lower than it should be.** That is CRF-COVPY-0026's failure mode reached through a new and entirely
plausible door.

**Failure scenario (the loud but confusing one).** `COVERAGE_AST_DUMP=true` measures fine and then
crashes `coverage report` (branch mode only) with a raw `ValueError` from `parser.py:711`, six frames
deep in AST analysis, naming neither the option nor the file being parsed.

**Guarded twin:** `coverage/tomlconfig.py:180-183` — the project's own boolean parser:

```python
def getboolean(self, section: str, option: str) -> bool:
    name, value = self._get_single(section, option)
    bool_strings = {"true": True, "false": False}
    return self._check_type(name, option, value, bool, bool_strings.__getitem__, "a boolean")
```

`_check_type` (`tomlconfig.py:154-178`) wraps the conversion and re-raises a *contextualized*
`ValueError` naming the section, the option and the offending value. Configparser's `getboolean`,
used for the INI path, additionally accepts `1/0/yes/no/true/false/on/off`. **Coverage already knows
how to convert a boolean-ish string safely, with a named error and a documented vocabulary — the
five env reads do neither.**

**Fix,** in the project's own idiom — a single helper in `coverage/misc.py`, then five call sites:

```python
def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean debugging flag from the environment."""
    val = os.getenv(name)
    if val is None or val == "":
        return default
    if val.lower() in {"1", "true", "yes", "on"}:
        return True
    if val.lower() in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Environment variable {name} isn't a boolean: {val!r}")
```

Raising `ConfigError` (rather than `ValueError`) also puts these on the right side of
CRF-COVPY-0042's complaint that errors should stay inside the project exception hierarchy. If
raising at import is undesirable, `return default` on an unrecognized value is strictly better than
`ValueError`.

**Siblings checked:** every `os.getenv` / `os.environ[` in `coverage/` (22 sites). The other 17 read
strings and compare or split them (`core.py:34`, `config.py:651/705/710/716/724`,
`debug.py:439/490`, `control.py:1478/1479`, `patch.py:84/89/93`, `pth_file.py:10`) — none converts.
**The five `int()` calls are the complete set.** No environment read in `coverage/` is a size or
count, so the catalogued shape has zero true instances here.

### Novel shape, in `python_bug_shapes.json` field structure

```json
{
  "id": "env-flag-parsed-as-strict-int",
  "title": "A boolean env var parsed with bare int(), so any non-numeric value raises at import",
  "severity": "FIX",
  "grounding": "confirmed",
  "pattern": "`int(os.getenv(NAME, 0))` or `bool(int(os.getenv(NAME, \"0\")))` where the value is used only as a BOOLEAN (a debug toggle, a feature flag), not as a size or count. `int()` accepts only a decimal-integer literal, so `NAME=true`, `NAME=on`, `NAME=yes` and — most commonly — `NAME=` (set but empty) all raise ValueError. When the expression sits at module scope the exception escapes as an import failure of the whole package.",
  "guarded_twin": "The project's own config layer, which converts boolean-ish strings through a table and re-raises a contextualized error naming the option and the value (coverage.py: `TomlConfigParser.getboolean` + `_check_type`, `tomlconfig.py:180`; stdlib `configparser.getboolean`, which accepts 1/0/yes/no/true/false/on/off). A codebase that has a boolean config parser and does not use it for its env flags has the twin already written.",
  "hunt": "Grep every `int(os.getenv(` / `int(os.environ[`. Split them: a value used as a size/count belongs to `unvalidated-numeric-from-environment`; a value used only for truthiness is this shape. Then ask WHERE it evaluates -- module scope means import failure, and check whether any bootstrap on the import path (a .pth file, a sitecustomize, a plugin loader) swallows ImportError/Exception, which converts the loud failure into a silent no-op. Reproduce with the EMPTY value first: `NAME= python -c 'import pkg'`.",
  "expected": "An unrecognized value for a boolean flag is either ignored (falling back to the default) or rejected with an error naming the variable and the value; an empty value means 'unset'.",
  "caught_as": "ValueError: invalid literal for int() with base 10: '' -- raised from module scope, so it presents as an unimportable package rather than as a bad setting. Where a bootstrap swallows it, COMPLETELY SILENT: the feature the package provides simply does not happen.",
  "differential": "Not this shape when the value is genuinely numeric (a timeout, a worker count, a buffer size) -- that is `unvalidated-numeric-from-environment`. Not a defect when the conversion is already inside a try/except or uses a tolerant helper. The tell is that the result is immediately coerced with bool() or used directly in an `if`, which proves the author wanted a flag and reached for the wrong parser."
}
```

---

# PRIORITY 3 — `except Exception:` and `cleanup-only-on-success-path`

Ten candidates. **Three are already catalogued** (confirmed present, not re-derived), **one is part
of a catalogued finding**, and **six are the taxonomy's deliberate-best-effort / documented-boundary
FP classes.** Nothing new here.

### Confirmed still present (catalogued — no re-derivation)

| Catalog id | Scanner hit | Location | Status |
|---|---|---|---|
| CRF-COVPY-0001 | `cleanup-only-on-success-path` `sqldata.py:390` + `except-exception-too-broad` `sqldata.py:391` | `coverage/sqldata.py:388-394` | **still present** — `db.close(force=True)` in `_reap_dead_thread_dbs`; `force=True` still bypasses the `no_disk` guard at `sqlitedb.py:88` |
| CRF-COVPY-0025 | `cleanup-only-on-success-path` `sqlitedb.py:108` | `coverage/sqlitedb.py:101-112` | **still present** — `self.close()` is the last statement of `__exit__`'s `try`; a failing `con.__exit__` skips it and the stale connection is reused |
| CRF-COVPY-0026 | `bare-except-swallows-control-flow` `pth_file.py:13` | `coverage/pth_file.py:11-16` | **still present** — and see PRIORITY 2: it now also swallows the env-flag `ValueError` |
| CRF-COVPY-0023 | `except-exception-too-broad` `files.py:135` | `coverage/files.py:133-139` | **still present** — the breadth is documented (bpo-1776160); the catalogued defect is that `files = []` is then cached in `_ACTUAL_PATH_LIST_CACHE` for the process lifetime |
| CRF-COVPY-0060 | `except-exception-too-broad` `inorout.py:117` | `coverage/inorout.py:115-118` | **still present** — `except Exception: pass` around `find_spec`, making failure indistinguishable from not-found |

### Dismissed — FP taxonomy

| Location | Class | Reason |
|---|---|---|
| `data.py:121` | documented boundary (§5/§19) | `except Exception: return "combine"` around `hash_for_data_file`, with a comment stating the containment and naming the consequence ("Probably it will fail later, but that error will be handled"). The fallback is the *conservative* direction: worst case the dedup optimisation stops and coverage behaves as it did before `DataFileClassifier` existed. No correctness change. |
| `debug.py:232` | exception captured, not swallowed (calibration note) | `except Exception as e: summary = f"error: {e}"` — the exception text becomes the returned summary, and `FileNotFoundError` already has its own narrow clause above. Control flow does not continue as if nothing happened; the caller is told. |
| `sqlitedb.py:123` | retry, not swallow | `except Exception: return self.con.execute(sql, parameters)` — the handler *re-runs the same operation*, with a comment linking coveragepy#1010. A deterministic failure raises on the second attempt. Not a swallow. |
| `sqlitedb.py:201` | retry, not swallow | Identical idiom in `_executemany`, same issue link. |
| `sqldata.py:391` | deliberate best-effort teardown | `except Exception: pass` with `# Closing is best-effort; a failure here must not break collection. The entry has already been dropped.` The *defect* in this function is `force=True` (CRF-COVPY-0001), not the handler. |
| `sqlitedb.py:158` | **scanner false positive** | `self._execute(sql, parameters).close()` is a **single expression**: the cursor is created and closed in one statement, so there is no window in which it exists unclosed. Nothing to move to a `finally`. |

**Guarded twin for the real cleanup shape** (relevant to CRF-COVPY-0025): `sqlitedb.py:145-148`,
twelve lines above the defect —

```python
cur = self._execute(sql, parameters)
try:
    yield cur
finally:
    cur.close()
```

`SqliteDb.execute` releases in `finally`; `SqliteDb.__exit__` releases as the last statement of a
`try`. Same file, same class, same resource discipline — one right, one wrong.

**Siblings checked:** every `close(force=` in `coverage/` — `sqldata.py:301` (`_reset`, where
destroying the in-memory db is the point), `sqldata.py:390` (CRF-COVPY-0001), `control.py:754`
(`_atexit`, where the process is ending and destruction is harmless). Only `:390` is a defect, which
matches the catalogue.

---

# PRIORITY 4 — `class-level-mutable-attribute` (9 sites)

### Seven constants-by-convention — dismissed

Every one is ALL_CAPS and **read-only at every reference site** (membership test or iteration). I
grepped all references for each name; none is mutated anywhere in the package.

| Location | Name | Only uses |
|---|---|---|
| `config.py:266` | `MUST_BE_LIST` | `config.py:292` `if k in self.MUST_BE_LIST` |
| `config.py:279` | `SERIALIZE_ABSPATH` | `config.py:591` `for k, must_exist in ...` |
| `config.py:385` | `CONCURRENCY_CHOICES` | `config.py:571` set-difference; `cmdline.py:72` join (already `Final[set[str]]`) |
| `config.py:394` | `LIGHT_THREADS` | `config.py:575` set-intersection |
| `config.py:396` | `CONFIG_FILE_OPTIONS` | `config.py:329/338/516/546` iteration |
| `html.py:277` | `STATIC_FILES` | `html.py:430` iteration |
| `parser.py:881` | `OK_TO_DEFAULT` | `parser.py:924` `if node_name not in ...` |

Per the calibration note, this is correct and idiomatic. `frozenset`/`tuple` would express it, but
that is style, not a defect.

### The two registries — deliberate, and both *do* remove

**`Collector._collectors` (`collector.py:60`) — dismissed, well-disciplined.** It is a documented
stack ("The stack of active Collectors", `:57-59`). `start()` appends (`:330`); `stop()` pops
(`:351`) and resumes the one underneath. It additionally **self-heals across fork**: `start()`
filters out entries whose `pid` differs and calls `post_fork()` on them (`:307-313`), which is
strictly more careful than the sibling registry. `stop()` asserts LIFO order (`:339-346`).

**`Coverage._instances` (`control.py:126`) — dismissed as a shared-state defect, but see the
divergence below.** `start()` appends (`:720`); `stop()` pops (`:723-726`).

**Under repeated `Coverage()` construction in one process, both registries stay clean** as long as
start/stop are balanced and LIFO. I verified by execution: five sequential
construct→start→stop→save cycles leave `Coverage._instances == []` and
`Collector._collectors == []`. **pytest-cov's usage pattern does not leak either registry.**

That is the answer to the question asked. But the probe surfaced two things that *do* retain, below.

---

# Confirmed new findings

### [CONSIDER] `lru-cache-on-method` — 1 instance, reproduced

**What it is:** `@functools.cache` on an instance method, so the cache lives on the class and its
keys include `self`.
**Why it is silent:** nothing raises; RSS grows monotonically with the number of `Collector`
instances the process has ever created, and the cache can never hit across instances.

| # | Location | Confidence | Notes |
|---|---|---|---|
| 1 | `coverage/collector.py:413-416` | high | `@functools.cache` on `Collector.cached_mapped_file(self, filename)` |

```python
@functools.cache  # pylint: disable=method-cache-max-size-none
def cached_mapped_file(self, filename: str) -> str:
    """A locally cached version of file names mapped through file_mapper."""
    return self.file_mapper(filename)
```

The `# pylint: disable` on the line shows the author saw pylint object to the unbounded size and
suppressed it; the `self`-in-the-key consequence is the part that went unnoticed.

**Failure scenario, reproduced.** Five sequential `Coverage()` construct→start→trace 3 files→
stop→save cycles, with each `Coverage` deleted and `gc.collect()` run, **and with the independent
`atexit` retention explicitly removed via `atexit.unregister`**:

```
Collectors still alive after atexit.unregister: 5 / 5
cache_info: CacheInfo(hits=0, misses=15, maxsize=None, currsize=15)
gc.get_referrers(collector) -> cache-key tuple -> dict owned by:
    _lru_cache_wrapper Collector.cached_mapped_file
```

`currsize` is exactly `n_collectors × n_files` and grows without bound; **`hits` is 0**, because
`self` is part of the key so a second `Collector` can never reuse the first's entries. Each retained
`Collector` transitively retains its `Core`, its `CoverageData` (i.e. the entire measured dataset),
its tracers and its `file_mapper` closure. A long-lived process that measures many sub-runs — a test
harness, a notebook kernel, a server measuring per-request coverage — grows one full dataset per run
and never releases any of them.

**Guarded twin:** `coverage/data.py:175`, in this project —

```python
map_path = functools.cache(aliases.map)
```

A cache built as a **local**, scoped to one `combine_parallel_data` call and released with it. Same
decorator, same author, correct lifetime. The two module-level uses (`html.py:242` `encode_int`,
`misc.py:313` `_human_key`) are also correct: plain functions over immutable arguments, no `self`.
`collector.py:413` is the only one applied to a method.

**Fix,** in the project's idiom — a per-instance dict built where the mapper is stored:

```python
# in Collector.__init__
self._mapped_file_cache: dict[str, str] = {}

def cached_mapped_file(self, filename: str) -> str:
    """A locally cached version of file names mapped through file_mapper."""
    try:
        return self._mapped_file_cache[filename]
    except KeyError:
        mapped = self._mapped_file_cache[filename] = self.file_mapper(filename)
        return mapped
```

This also *improves* the hit rate, since it drops the useless `self` component from the key. The
`# pylint: disable` comment goes away with it.

**Siblings checked:** all four cache decorators in `coverage/` (`html.py:242`, `misc.py:313`,
`collector.py:413`, `data.py:175`). `collector.py:413` is the sole method instance. No
`cached_property` is used anywhere, so there is no third idiom to reconcile.

---

### [CONSIDER] `atexit-registration-never-unregistered` (NOVEL) — 1 instance, reproduced

**What it is:** a bound method registered with `atexit.register` and never unregistered, so the
`atexit` module's private list holds a strong reference to the object for the process lifetime.
**Why it is silent:** `atexit`'s registry is not reachable through any public API, so the object
does not appear "held" by anything a reader would think to check; and the handler still runs
correctly, so nothing misbehaves — memory simply never comes back.

| # | Location | Confidence | Notes |
|---|---|---|---|
| 1 | `coverage/control.py:654` | high | `atexit.register(self._atexit)`; `atexit.unregister` appears nowhere in the package |

**Failure scenario, reproduced.** Five construct→start→stop→save cycles with `del cov;
gc.collect()` between them leaves **5 of 5 `Coverage` objects alive**, and `gc.get_referrers`
identifies the holder directly:

```
Coverage objects created: 5   still alive: 5
Coverage._instances: 0        Collector._collectors: 0     # both registries are clean
   held by method Coverage._atexit
```

The registries the scanner flagged are innocent; `atexit` is the retainer. This is independent of
the `functools.cache` path above — each alone is sufficient to retain the object, which is why the
cache experiment had to `atexit.unregister` first to isolate it.

Second-order consequence worth a maintainer's judgement: at interpreter exit **every** stale handler
runs. `_atexit` (`control.py:745-753`) then calls `self.save()` when `_auto_save` is set and
`d.close(force=True)` on every entry of `_data_to_close`. For N long-dead `Coverage` objects that
is N redundant saves at shutdown. I did not find a case where this corrupts data, so I am reporting
it as retention, not as a data bug.

**Guarded twin:** the SIGTERM handler eight lines below, `control.py:656-663`, which **stores the
previous handler** (`self._old_sigterm = signal.signal(...)`) and **restores it**
(`control.py:761`). The same function registers two process-level hooks and only reverses one of
them.

**Fix:** `atexit.unregister(self._atexit)` in `Coverage._atexit` after the body runs, and/or in
`stop()` when the object is not going to be restarted. `atexit.unregister` is a no-op when the
callable is not registered, so it is safe to call unconditionally.

**Siblings checked:** every `atexit` reference in `coverage/` — `control.py:8` (import),
`control.py:654` (register), `control.py:745` (`_atexit` definition), `control.py:758` (SIGTERM
delegating to it). One registration, zero unregistrations.

### Novel shape, in `python_bug_shapes.json` field structure

```json
{
  "id": "atexit-registration-never-unregistered",
  "title": "atexit.register(self.method) with no unregister -- the object is retained for the process lifetime",
  "severity": "CONSIDER",
  "grounding": "confirmed",
  "pattern": "`atexit.register(self.<method>)` (or `weakref`-less `atexit.register(bound_method)`) inside `__init__` or a start/setup method, with no matching `atexit.unregister` anywhere in the package. The atexit module keeps a strong reference in a private list, so the instance -- and everything it transitively owns -- outlives every other reference to it. In a process that creates the object repeatedly, every generation is retained.",
  "guarded_twin": "A sibling process-level hook in the SAME function that IS reversed -- typically `signal.signal(...)` whose previous handler is saved and restored. A codebase that restores its signal handler and not its atexit handler has the twin literally adjacent. The other correct forms: `atexit.unregister(self._handler)` in the object's own teardown, or registering a module-level function that looks the object up weakly.",
  "hunt": "Grep every `atexit.register`. For each, grep the package for `atexit.unregister` -- if the count is zero, every registration leaks. Prioritize registrations of BOUND METHODS (a plain function leaks nothing) and objects that own large graphs (data buffers, connections, collectors). Confirm by constructing N objects, deleting each and running gc.collect(), then `gc.get_referrers(obj)` -- the retainer shows up as `method <Class>.<handler>`. Check for a sibling signal/setup hook in the same function that IS restored.",
  "expected": "The object becomes collectable once the caller drops it; the shutdown hook exists only while the object is live.",
  "caught_as": "SILENT. RSS grows monotonically with the number of instances ever created, and the object is invisible in ordinary referrer inspection because atexit's list is private. Every stale handler also still RUNS at shutdown, so a teardown side effect (a save, a flush, a close) is repeated once per dead generation.",
  "differential": "Not a defect for a singleton, a module-level function, or an object whose lifetime IS the process. Not a defect when the handler is registered with `weakref.finalize` or when a matching unregister exists on any teardown path. The finding requires (a) a bound method or closure over the instance, (b) zero unregister sites, and (c) a construction pattern that repeats within one process."
}
```

---

### [CONSIDER] Two parallel registries, two different failure disciplines

| # | Location | Confidence | Notes |
|---|---|---|---|
| 1 | `coverage/control.py:723-726` vs `coverage/collector.py:337-353` | medium | Same LIFO invariant; one asserts it, one silently declines to act |

```python
# Coverage.stop()  -- control.py:723
if self._instances:
    if self._instances[-1] is self:
        self._instances.pop()          # silently does nothing when not on top

# Collector.stop() -- collector.py:339
assert self._collectors[-1] is self, (
    f"Expected current collector to be {self!r}, but it's {self._collectors[-1]!r}"
)
```

**Failure scenario, reproduced.** Two overlapping `Coverage` objects stopped out of order:

```
c1.start(); c2.start(); c1.stop()
  -> c1.stop() raised: AssertionError (from Collector.stop)
  -> after c1.stop:  _instances: 2   _collectors: 2      # neither popped
c2.stop()
  -> after c2.stop:  _instances: 1   _collectors: 1
Coverage.current() is c1?  True      c1._started = True
```

`Coverage.current()` (public API since 5.0, `control.py:130`) returns `c1` — an object whose
`stop()` raised and which the caller believes is stopped. Its sole in-package consumer is
`control.py:1501` (`if cov := Coverage.current():` on the fork path, adjacent to CRF-COVPY-0002).

I am filing this as CONSIDER rather than FIX because the `AssertionError` from `Collector.stop()`
makes the misuse loud; the defect is that the two stacks disagree for the window in between, and
that the `_instances` half fails silently by design. **The guarded twin is `Collector.stop()`
itself** — one file over, the same invariant, stated as an assertion with a diagnostic. `Coverage`
should either assert the same thing or pop unconditionally by identity
(`if self in self._instances: self._instances.remove(self)`).

**Siblings checked:** both registries' full mutation sets (`_collectors` at `collector.py:307-353`,
`_instances` at `control.py:720-726`). `Collector.start()` additionally reconciles across fork;
`Coverage.start()` has no equivalent, and `Coverage.start()` called twice appends twice while one
`stop()` pops once.

---

# Suppressed

**26 scanner findings + 6 ruff `zip` sites = 32 candidates triaged. 0 suppressed as generated
content** (`by_directory` is 100% hand-written `coverage/`).

| Count | Disposition |
|---|---|
| 7 | `class-level-mutable-attribute` — constants-by-convention, verified read-only at every reference (calibration note: "fine for genuine constants") |
| 2 | `class-level-mutable-attribute` — `Collector._collectors`, `Coverage._instances`: deliberate registries, both pop on `stop()`, both verified clean after repeated construction |
| 6 | `except Exception:` / `cleanup-only-on-success-path` — FP taxonomy §5 documented boundary (`data.py:121`), calibration "exception captured" (`debug.py:232`), retry-not-swallow (`sqlitedb.py:123`, `:201`), deliberate best-effort teardown (`sqldata.py:391`), and one outright scanner FP (`sqlitedb.py:158`, single-expression create-and-close) |
| 5 | `except`/`cleanup`/`bare-except` — already catalogued (CRF-COVPY-0001, -0023, -0025, -0026, -0060); confirmed still present, not re-derived |
| 6 | `zip()` without `strict=` — 4 in `report.py` (operands coupled through one branch decision; the one-element surplus is the deliberate sort key, verified by execution over all 4 configurations), 1 in `html.py` (two slices of one list), 1 in `sysmon.py` (debug-only, all 8 decorations verified balanced) |
| 4 | `zip()` in tests — `helpers.py:336` (has the length assertion; this is the guarded twin), `test_html.py:1496/1518/1541` (two 3-element literals two lines above) |

**Reclassified, not suppressed:** the 5 `unvalidated-numeric-from-environment` hits are real defects
under a *different* shape. The scanner's `detail` for `sysmon.py:50/53` ("the same function validates
the value it gets from another source") is inaccurate — these are module-scope statements with no
sibling branch. The check is firing on the right code for the wrong reason, which is worth feeding
back into the scanner: split it on whether the parsed value is used numerically or for truthiness.

# Novel shapes proposed

1. **`env-flag-parsed-as-strict-int`** [FIX] — 5 confirmed instances, all reproduced. Full JSON above.
2. **`atexit-registration-never-unregistered`** [CONSIDER] — 1 confirmed instance, reproduced with
   `gc.get_referrers` evidence. Full JSON above.

# Scanner feedback

- **`unvalidated-numeric-from-environment` needs a numeric-use test.** All 5 coverage.py hits are
  boolean flags; 0 are dimensions. Gating on whether the result reaches arithmetic/indexing (vs.
  `bool()`/an `if`) would route them to the new shape and remove the misleading `detail` text.
- **`cleanup-only-on-success-path` fires on single-expression create-and-close.**
  `self._execute(sql, p).close()` (`sqlitedb.py:158`) has no window; requiring the resource to be
  bound to a name before the release would drop this FP class.
- **The scanner is scoped to `coverage/` and missed the only true `zip` instance**, which is in
  `tests/`. The catalogue's own note says the twin is often in the tests; here the *defect* was too.
