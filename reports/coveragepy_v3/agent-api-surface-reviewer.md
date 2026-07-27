# api-surface-reviewer — coverage.py (informed pass)

**Target:** `/home/danzin/projects/coveragepy/coverage` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Tree edited:** **No.** All analysis ran against `/tmp/covrepro` (`git archive HEAD | tar -x`) and a scratch project at `/tmp/covtest`. `git status` in the target shows no tracked file modified and HEAD unchanged; the untracked `ctracer_*` files predate this run and are not mine.
**Briefing:** read in full. 60 catalogued findings treated as settled — verified, not re-derived.

---

## 0. Method

The four surfaces were enumerated mechanically and differenced in both directions:

1. **Config** — the 53 entries of `CoverageConfig.CONFIG_FILE_OPTIONS` (`coverage/config.py:396-469`) plus `[paths]` and plugin sections.
2. **CLI** — the 33 registered option `dest`s across the 11 `COMMANDS` parsers, read by importing `coverage.cmdline` and walking `parser.option_list`.
3. **Python API** — `coverage/__init__.py` re-exports, `Coverage`/`CoverageData` public members, and what Sphinx publishes (`doc/api_*.rst`).
4. **Plugin API** — `CoveragePlugin` / `FileTracer` / `FileReporter` methods vs their call sites and their `Debug*Wrapper` mirrors.

Every claim below was either read at `file:line` on both sides or reproduced against a built coverage.py.

---

## 1. Directions checked and **EMPTY** (negative results)

These are the set-differences that came back clean. Recorded so the next reviewer does not re-derive them.

| # | Direction | Result |
|---|---|---|
| E1 | Config options defined in `CONFIG_FILE_OPTIONS` but read by **no** code path (dead option) | **EMPTY** — 53/53 have a consumer. The five with no literal `config.<attr>` reference (`exclude_list`, `exclude_also`, `partial_list`, `partial_also`, `partial_always_list`) are reached dynamically via `getattr(self.config, f"{which}_list")` at `control.py:825,836,847` and directly at `python.py:215`; `*_also` are folded in by `config.py:563-564`. |
| E2 | `config.<attr>` reads with no matching attribute on `CoverageConfig` (unreachable name) | **EMPTY** — the only three non-attribute hits are module-level (`tomlconfig.py:41,187,202` referencing `coverage.config.HandyConfigParser` / `process_file_value` / `process_regexlist`). |
| E3 | CLI option `dest`s registered on a command but never read in `cmdline.py` | **EMPTY** — 33/33 read. No silently-accepted CLI flag. |
| E4 | Long options in `doc/python-coverage.1.txt` (hand-maintained man page) absent from `cmdline.py` | **EMPTY** — man page is a strict subset; only `--module` and `--version` are missing from it, and both are documented there under their short forms / the global section. |
| E5 | `type_` values in `CONFIG_FILE_OPTIONS` with no matching `get<type>` on a parser | **EMPTY** — 7 types (`""`, `boolean`, `file`, `float`, `int`, `list`, `regexlist`) × 2 parsers, all 14 present. |
| E6 | `[section] option` documented in `doc/config.rst` but not implemented | **EMPTY** — 50/50 documented options exist. (The gap is the other way: see §2 CRF-COVPY-0057.) |
| E7 | `--debug` options documented in `doc/commands/cmd_debug.rst:74-127` but never tested by `DebugControl.should()` | **EMPTY** — all 21 documented options are checked. (Gap is the other way: N6.) |
| E8 | Warning slugs a user can put in `[run] disable_warnings` that no code emits | **EMPTY** — all 13 slugs anchored in `doc/messages.rst` are emitted by a `_warn(slug=...)` call. The two extra code slugs (`fork`, `pth`) belong to a *different* `slug` parameter — see N1. |
| E9 | `CoveragePlugin` / `FileTracer` methods not mirrored by `DebugPluginWrapper` / `DebugFileTracerWrapper` | **EMPTY** for both (6/6 and 4/4). Only `FileReporter` has the gap, and that is catalogued (0019). |
| E10 | Documented plugin hooks with no call site anywhere (`documented-recipe-not-wired-up`) | **EMPTY** — all six `CoveragePlugin` methods are invoked. Note `dynamic_context` is wired as a *bound-method reference* at `control.py:587`, so a `grep '\.dynamic_context('` returns zero hits and looks like a dead hook. It is not. |
| E11 | Names addressable by `set_option` but not `get_option`, or vice versa | **EMPTY** — both iterate the same `CONFIG_FILE_OPTIONS` list (`config.py:516`, `config.py:546`) and special-case `"paths"` identically. |
| E12 | Plugin `code_region_kinds()` nouns the HTML backend cannot express | **EMPTY** — `html.py:392-394` creates an index page per noun dynamically. (LCOV is the exception: N13.) |

---

## 2. Catalogued findings — **confirmed still present**, not re-litigated

| ID | Verified at | Note |
|---|---|---|
| CRF-COVPY-0010 | `xmlreport.py`, `lcovreport.py`, `annotate.py` | `report_contexts` is consumed only by `report.py:209`, `html.py:132`, `jsonreport.py:79`. The API still accepts `contexts=` on `xml_report`/`lcov_report`/`annotate` (`control.py:1287,1355,1183`) where it is inert. |
| CRF-COVPY-0019 | `plugin_support.py:243-299` | Mirrors 10 of 14. Missing exactly: `arc_description`, `code_region_kinds`, `code_regions`, `missing_arc_description`. |
| CRF-COVPY-0020 | `report_core.py:110` | Unguarded `fr.should_be_python()`. **Its guarded twin is in the same codebase**: `html.py:149` does `if hasattr(fr, "multiline_map")` before calling the other `PythonFileReporter`-only method. Two `PythonFileReporter`-only methods, one guarded, one not. |
| CRF-COVPY-0027 | `config.py:494-529` vs `:559-578` | `set_option` still bypasses `post_process()`. |
| CRF-COVPY-0028 | `tomlconfig.py:91` | `real_section.split(".")` still splits dotted plugin names. |
| CRF-COVPY-0029 | `tomlconfig.py:146-148` | `get_section` returns raw data; `HandyConfigParser.get_section` (`config.py:82-87`) routes through `get()` which substitutes. |
| CRF-COVPY-0040 | `control.py:474-499` | Six slug-less warnings confirmed, incl. `control.py:629` ("Plugin file tracers … aren't supported") and `inorout.py:426`. |
| CRF-COVPY-0043 | six report backends | Confirmed; **N2 below is the complementary surface-side gap**, not a re-derivation. |
| CRF-COVPY-0055 | `control.py:197-199`, `control.py:1149-1150` | `.. versionadded:: 7.0 The \`format\` parameter` still names a parameter that is spelled `output_format` (`control.py:1097`). |
| CRF-COVPY-0056 | `cmdline.py:299-303` | `--rcfile` help still omits `.coveragerc.toml`, which `config.py:661` does try. |
| CRF-COVPY-0057 | `config.py:437`, `config.py:441` | Set-difference confirms exactly two undocumented public options: `[report] partial_branches_always` and `[report] contexts` (`[run] _crash` is deliberately private). |

---

## 3. Novel findings

### N1 — `coverage.process_startup(slug=...)` is a public, documented parameter that no code reads · **CONSIDER**

- **Producer:** `coverage/control.py:1433-1437`
  ```python
  def process_startup(
      *,
      force: bool = False,
      slug: str = "default",  # pylint: disable=unused-argument
  ) -> Coverage | None:
  ```
- **Consumers:** none. The function body (`control.py:1438-1495`) reads `force` at `:1470` and never mentions `slug`. Three call sites pass a value — `coverage/pth_file.py:16` (`slug="pth"`), `coverage/control.py:1503` (`slug="fork"`), `igor.py:187` (`slug='meta'`) — and all three are discarded.
- **Public surface:** `process_startup` is re-exported at `coverage/__init__.py:26` and published by `.. autofunction:: coverage.process_startup` (`doc/api_module.rst:38`). Sphinx renders the signature, so users see a keyword argument whose meaning is unknowable — the docstring documents neither `force` nor `slug`.
- **History:** introduced dead. `git log -L` shows `slug` added by `49a19928` ("fix: include a .pth file in the distribution"); it has never had a reader.
- **Consequence:** a documented API parameter that is silently accepted and does nothing — the API analogue of the briefing's target shape. Also a live trap: the name collides with `Coverage._warn(slug=)` and `CoverageException.slug`, both of which *are* load-bearing (`control.py:493`, `cmdline.py:1187-1188`), so a reader reasonably assumes `slug="pth"` reaches warning suppression. It does not.
- **Fix:** either wire it (pass through to the `Coverage(...)` construction at `control.py:1489` so `--debug=process` records which `.pth`/fork path started the collector — the evident intent), or delete the parameter and the three call sites. Deleting is `[breaking]` for anyone who copied the `pth_file.py` incantation; wiring it is `[additive]`.

### N2 — `precision` and `skip_empty` reach the json/lcov backends from the config file, but neither the CLI nor the API can set them there · **CONSIDER**

Surface-side complement to CRF-COVPY-0043 (which covers the *backend consumption* divergence). Here the backend **does** consume the option; the other two surfaces cannot reach it.

| option | consumed by | CLI flag | API parameter |
|---|---|---|---|
| `precision` | `report.py:47`, `html.py:349`, `jsonreport.py:42`, `lcovreport.py:167` | `report` ✔, `html` ✔, **`json` ✘, `lcov` ✘** | `report(precision=)` ✔, `html_report(precision=)` ✔, **`json_report` ✘, `lcov_report` ✘** |
| `skip_empty` | `report.py:284`, `html.py:292`, `xmlreport.py:176`, `lcovreport.py:207` | `report` ✔, `html` ✔, `xml` ✔, **`lcov` ✘** | `report` ✔, `html_report` ✔, `xml_report` ✔, **`lcov_report` ✘** |

**Reproduced** (built coverage.py, 9-statement file):

```
[report] precision = 3  ->  "percent_covered_display": "100.000"
[report] precision = 0  ->  "percent_covered_display": "100"
$ coverage json --precision=3   ->  no such option: --precision
$ coverage lcov --skip-empty    ->  no such option: --skip-empty
```

`precision` additionally gates the `--fail-under` comparison for **every** reporting command (`cmdline.py:946` reads `report:precision` unconditionally via `should_fail_under`), so `coverage json --fail-under=85.5` has a pass/fail boundary the invoker cannot adjust from the command line while `coverage report --fail-under=85.5 --precision=1` can.

- **Guarded twin:** `Opts.precision` and `Opts.skip_empty` already exist (`cmdline.py:275-287`, `:335-339`); adding them to the `json`/`lcov` option lists is a two-line change per command.
- **Fix:** `[additive]` — add `Opts.precision` to `COMMANDS["json"]` and `COMMANDS["lcov"]`, `Opts.skip_empty` to `COMMANDS["lcov"]`, and the matching `precision=` / `skip_empty=` parameters to `json_report()` / `lcov_report()`.

### N3 — `coverage report` and `coverage annotate` have no `-q/--quiet`, so the combine status line cannot be suppressed · **CONSIDER**

- `cmdline.py:890` runs an implicit combine for **all six** reporting commands; `data.py:233-240` emits `Combined N files, skipped M` through `Coverage._message` (`control.py:501-504`, stderr).
- `cmdline.py:855` computes `messages=not options.quiet`. `options.quiet` defaults to `None` (`cmdline.py:416`), so for `report` and `annotate` — which never register `Opts.quiet` — `messages` is **always `True`**.
- **Guarded twin:** `combine`, `html`, `json`, `lcov`, `xml` all carry `Opts.quiet` (`cmdline.py:563, 621, 650, 667, 726`).

**Reproduced:**
```
$ coverage run -p prog.py; coverage run -p prog.py
$ coverage report
Combined 1 file, skipped 1          <- stderr, unsuppressible
Name    Stmts   Miss  Cover
...
$ coverage report -q
no such option: -q
$ coverage annotate -q
no such option: -q
```

- **Consequence:** CI logs for the two most-used report commands carry an unsuppressible status line. Not corrupted machine output — `_message` correctly writes to stderr (`control.py:504`), so `coverage report --format=total` stdout stays clean; verified by separating the streams.
- **Fix:** `[additive]` — add `Opts.quiet` to `COMMANDS["report"]` and `COMMANDS["annotate"]`.
- **Related but distinct** from CRF-COVPY-0041 (which is about *which stream* messages go to); this is about the flag not existing.

### N4 — `[run] sigterm` is config-only, `--save-signal` is CLI-only: one feature, two disjoint surfaces, neither reachable from the API · **CONSIDER**

| | surface | signal | semantics | site |
|---|---|---|---|---|
| `[run] sigterm` | **config only** (no CLI flag, no API parameter, no env var) | SIGTERM | save, restore handler, re-raise to die | `config.py:423`, registered `control.py:655-665`, handler `control.py:756-762` |
| `--save-signal` | **CLI only** (no config option, no API parameter, no env var) | USR1/USR2 (`choices=`) | save and continue | `cmdline.py:306-318`, registered `cmdline.py:1045-1050` |

- Registration for `--save-signal` lives inside `CoverageScript.do_run`, so it is structurally unreachable from `Coverage`. Registration for `sigterm` lives inside `Coverage._init_for_start`, so it is structurally unreachable from the command line.
- **Reproduced:** `[run] save_signal = USR1` → `CoverageWarning: Unrecognized option '[run] save_signal='`; `coverage run --sigterm` → `no such option`.
- **Consequence:** a user whose invocation is fixed by tooling (tox, a Docker entrypoint, `[run] command_line`) cannot enable `--save-signal`; a user driving from the shell cannot enable SIGTERM handling. Documented independently (`doc/config.rst:539-556`, `doc/commands/cmd_run.rst:147-151`) so nothing tells a reader they are two halves of one concern.
- **Fix:** `[additive]` — add `[run] save_signal` (validated against the same `USR1|USR2` vocabulary) and move registration into `Coverage._init_for_start` beside the sigterm handler; optionally add `--sigterm`.

### N5 — the `which=` vocabulary of `exclude` / `clear_exclude` / `get_exclude_list` is unvalidated, undocumented at its third value, and fails outside the project exception hierarchy · **CONSIDER**

- **Sites:** `control.py:803` (`clear_exclude`), `control.py:809-827` (`exclude`), `control.py:840-848` (`get_exclude_list`), all resolving via `getattr(self.config, f"{which}_list")`. All three are published by `autoclass:: coverage.Coverage :members:` (`doc/api_coverage.rst:9-11`).
- **Documented vocabulary:** two values. `control.py:815-817` — *"The \"exclude\" list … The \"partial\" list …"*. `clear_exclude`'s docstring (`control.py:804`) mentions `which` not at all.
- **Actual vocabulary:** three. Verified at runtime:
  ```
  exclude          OK
  partial          OK
  partial_always   OK   <- undocumented, reaches [report] partial_branches_always
  excludes         AttributeError: 'CoverageConfig' object has no attribute 'excludes_list'
  exclude_also     AttributeError: 'CoverageConfig' object has no attribute 'exclude_also_list'
  ```
- **Two problems, one root:**
  1. `partial_always` is the API name for `[report] partial_branches_always` — which is *also* the option CRF-COVPY-0057 shows is undocumented in `doc/config.rst`. The list is therefore invisible from **both** the config docs and the API docs while being reachable from both.
  2. A typo raises `AttributeError`, which is not a `CoverageException` (verified: `issubclass(AttributeError, coverage.CoverageException)` is `False`). Same shape as catalogued CRF-COVPY-0042.
- **Guarded twin — and it is unanimous.** Every other closed vocabulary in coverage.py validates and raises `ConfigError`: `core` (`core.py:133`), `patch` (`patch.py:42-43`), `dynamic_context` (`control.py:583-584`), `sort` (`report.py:259-260`), `format` (`report.py:41-42`), `concurrency` (`config.py:571-574`), option names (`config.py:528-529`). `which=` is the only one with no check.
- **Fix:** `[additive]` — validate `which` against `{"exclude", "partial", "partial_always"}` and raise `ConfigError`; document all three values in `exclude()` and add a `which` sentence to `clear_exclude()`.

### N6 — three things that are implemented, tested, and documented nowhere (siblings of CRF-COVPY-0057) · **CONSIDER**

| # | Thing | Implemented | Tested | Missing from |
|---|---|---|---|---|
| a | `--debug=sqlite` | `control.py:438-439` | `tests/test_debug.py:248` | the `--debug` option list in `doc/commands/cmd_debug.rst:74-127`. The list is strictly alphabetical; `sqlite` belongs between `sqldata` (:120) and `sys` (:123). *(`sqlite` **is** documented at :32 — but that is the `coverage debug <topic>` vocabulary, a different closed set that happens to share the word.)* |
| b | `sort = +Cover` (ascending prefix) | `report.py:257-258` | `tests/test_report.py:1277-1280` | `doc/config.rst:891` documents only the `-` prefix; `Opts.sort` help (`cmdline.py:344-349`) mentions neither prefix. |
| c | per-function / per-class **region reports** | `html.py:392-394,584-600`; `jsonreport.py:135-145`; `lcovreport.py:70-85`; `regions.py` | `tests/test_report.py`, `tests/test_json.py`, `tests/test_lcov.py` | all user documentation. Verified user-visible: `coverage html` emits `function_index.html` + `class_index.html`; `coverage json` emits per-file `"functions"` and `"classes"` keys. In `doc/` the strings appear **only inside the sample-HTML fixture** (`doc/sample_html/*.html`) and in two `CHANGES.rst` lines (:287, :1044). `doc/commands/cmd_html.rst` and `cmd_json.rst` contain neither word. The only prose is `doc/api_plugin.rst`, written for plugin *authors*. |

(c) is the largest of the three: a shipped, default-on feature that changes the HTML report's navigation and the JSON schema, with no user-facing documentation.

- **Fix:** `[additive]`, docs only.

### N7 — `COVERAGE_DEBUG` merges with the config file but is silently discarded by `--debug`, while its advertised sibling `COVERAGE_FILE` uses plain replace · **CONSIDER**

`config.py:704-718` applies env vars *between* the config file (step 2) and constructor/CLI arguments (step 4, `config.py:721`), with two different merge rules:

```python
env_data_file = os.getenv("COVERAGE_FILE")
if env_data_file:
    config.data_file = env_data_file        # replace
debugs = os.getenv("COVERAGE_DEBUG")
if debugs:
    config.debug.extend(...)                # append
env_core = os.getenv("COVERAGE_CORE")
if env_core:
    config.core = env_core                  # replace, and no CLI flag exists to beat it
```

**Reproduced** with `.coveragerc` containing `[run] debug = trace` and `COVERAGE_DEBUG=sys`:

```
config file + env      : ['trace', 'sys']     <- additive
with --debug=pid       : ['pid']              <- BOTH dropped
COVERAGE_FILE=envfile  : 'envfile'
+ --data-file=cli      : 'cli'
```

- **Consequence:** `COVERAGE_DEBUG` has two different precedence relationships depending on whether a CLI flag happens to be present, and a user who exports it for a whole CI job loses it the moment any command passes `--debug`. The help text advertises the two identically — `--data-file … [env: COVERAGE_FILE]` (`cmdline.py:101`) and `--debug … [env: COVERAGE_DEBUG]` (`cmdline.py:134`) — so nothing signals the difference. No documentation states any of these precedence rules.
- **Fix:** `[additive]` (docs) or `[breaking]` (make `--debug` additive too, matching the env var). Pick one and say so in `doc/commands/cmd_debug.rst`.

### N8 — the delegation target of five docstrings has an undocumented parameter of its own · **CONSIDER**

`annotate`, `html_report`, `json_report`, `lcov_report` and `xml_report` all say *"See :meth:`report` for other arguments."* (`control.py:1176, 1235, 1305, 1345`). That makes `Coverage.report`'s docstring the single source for the shared parameter set — and it is the one place a parameter is missing.

- `Coverage.report(..., sort=...)` — `control.py:1097`. Parameter exists, is wired (`control.py:1176` → `config.sort` → `report.py:252`), is CLI-exposed (`--sort`), and **its own method's docstring never mentions it** (`control.py:1099-1151` documents `show_missing`, `ignore_errors`, `file`, `output_format`, `include`, `omit`, `skip_covered`, `skip_empty`, `contexts`, `precision` — ten of eleven).
- Same family, smaller: `Coverage.clear_exclude(which=)` (`control.py:803-804`, docstring is `"Clear the exclude list."`) and `CoverageData.close(force=)` (`sqldata.py`, docstring is `"Really close all the database objects."`). Both are published by `:members:`.
- **Fix:** `[additive]`, docs only. A mechanical guard (docstring-parameter coverage check over the two `autoclass :members:` classes) would keep it closed; the full audit is in §5.

### N9 — `CoverageData.sys_info` is published as public API while the identically-purposed `Coverage.sys_info` is explicitly excluded · **CONSIDER**

- `doc/api_coverage.rst:9-12` — `autoclass:: coverage.Coverage` with `:exclude-members: sys_info`. Deliberate: the docstring is *"Return a list of (key, value) pairs showing internal information."*
- `doc/api_coveragedata.rst:11-13` — `autoclass:: coverage.CoverageData` with **no** `:exclude-members:`. `CoverageData.sys_info` is a public `@classmethod` whose docstring is *"Our information for `Coverage.sys_info`."* — i.e. it exists to feed the method that was deliberately hidden.
- **Consequence:** the CoverageData API page publishes an internal debug accessor as supported API. `doc/api.rst:41-49` explicitly warns that "if classes or functions are not documented in this published documentation, they are not supported" — the contrapositive is what bites here.
- **Fix:** `[additive]` — add `:exclude-members: sys_info` to `doc/api_coveragedata.rst`, mirroring the twin.

### N10 — eight of the nine documented public exception classes are not reachable as `coverage.X` · **CONSIDER**

- `doc/api_exceptions.rst:9-11` is `automodule:: coverage.exceptions :members:`, so `ConfigError`, `DataError`, `NoDataError`, `NoSource`, `NoCode`, `NotPython`, `PluginError` and `CoverageWarning` are all published as supported API (`_ExceptionDuringRun` is correctly excluded by its underscore).
- `coverage/__init__.py:29` re-exports **only** `CoverageException`. Verified: `hasattr(coverage, "NoSource")` is `False`.
- **Guarded twin, in the same `__init__.py`:** the four plugin classes are re-exported (`__init__.py:30-35`) and `doc/api_plugin.rst` addresses them by their short names (`autoclass:: coverage.CoveragePlugin`, etc.) even though it *also* has an `automodule:: coverage.plugin`. The exceptions page uses the long path throughout; the plugin page uses the short path. Two `automodule` pages, two conventions.
- **Consequence:** `doc/api.rst:29-30` tells a reader "Any of the methods can raise specialized exceptions described in :ref:`api_exceptions`", and the natural first attempt — `except coverage.NoSource:` — is an `AttributeError`. The working import (`from coverage.exceptions import NoSource`) appears in the rendered signatures but in no prose.
- **Fix:** `[additive]` — re-export the eight in `coverage/__init__.py` using the same `X as X` convention already used at `__init__.py:19-35`. Zero-risk; nothing is removed.

### N11 — LCOV hard-codes one noun out of the plugin-supplied region-kind vocabulary · **POLICY**

The closest thing in coverage.py to the briefing's `unreachable-name-in-a-closed-vocabulary`, at the plugin boundary.

- **Producer:** `FileReporter.code_region_kinds()` (`plugin.py:594-607`) — plugin-defined `(singular, plural)` pairs. Base returns `[]`; the docstring's example is `[("function","functions"), ("class","classes")]` and says only *"This will usually be hard-coded"*.
- **Consumers:** `html.py:392-394` and `jsonreport.py:136` accept **any** noun (HTML creates an index page per noun dynamically; JSON keys by the plural). `lcovreport.py:78` accepts **exactly one**: `if region.kind == "function"`.
- **Consequence:** a plugin whose kinds are, say, `[("rule","rules")]` or `[("procedure","procedures")]` gets region index pages in HTML and region blocks in JSON, and **zero** `FN`/`FNDA` records in LCOV, with no error and no warning. Nothing in `plugin.py` tells a plugin author that `"function"` is a magic string in one of the three consumers.
- **Why POLICY not FIX:** LCOV's `FN` record genuinely means "function", so the filter is semantically defensible — but the *contract* is undocumented. The decision (document the magic noun vs. widen the LCOV mapping) belongs to the maintainer.
- **Fix:** `[additive]` — state in `code_region_kinds`'s docstring that the LCOV backend emits `FN`/`FNDA` records only for the kind named `"function"`.

### N12 — minor surface asymmetries, listed for completeness · **ACCEPTABLE / low CONSIDER**

- **`[html] extra_css` has config + API but no CLI.** `config.py:450`, `control.py:1207,1246`, consumed `html.py:436`. `coverage html --extra-css=x.css` → `no such option`. The only `[html]` option where the three surfaces disagree — `directory`, `title`, `show_contexts`, `skip_covered`, `skip_empty` all have all three.
- **`[run] relative_files` has config but no CLI flag** (`config.py:420`, consumed `control.py:390`, `xmlreport.py:70`). Verified: `coverage run --relative-files` → `no such option`. Notable because it is a very common CI need and forces a config file.
- **`CoverageConfig._include` / `_omit` are dead attributes.** `config.py:192-193` initialises both to `None` under the comment `# Defaults for [run] and [report]`. Repo-wide grep (including `tests/`, `doc/`, `lab/`, `igor.py`) finds no reader. Superseded by the four `run_*`/`report_*` attributes on the next lines.
- **`outfile` and `pretty_print` are missing from the alphabetized default list.** `cmdline.py:393-428` carries the comment *"Keep these arguments alphabetized by their names"* and lists 33 names; the two `dest`s introduced by `Opts.output_xml`/`output_json`/`output_lcov` and `Opts.json_pretty_print` are absent. **Not a bug** — optparse's `add_option` defaults an unseen `dest` to `None` — but the list no longer is the inventory the comment claims, and the file is otherwise scrupulously maintained with "alphabetize" markers (`cmdline.py:32-33, 46-47, 525-529`).
- **`[run] _crash` is settable through the public `set_option`.** `config.py:428` puts `run:_crash` in `CONFIG_FILE_OPTIONS`, so `cov.set_option("run:_crash", "foo")` is accepted and will raise `RuntimeError` from `control.py:416-417`. Underscore-prefixed and undocumented, so deliberate — recorded so it is not re-flagged.
- **Two names for one concept: `--keep` (combine) vs `--keep-combined` (six report commands).** `cmdline.py:182-193`. Same help sentence, same effect, different spelling depending on which command you are in; neither has a config equivalent.
- **Three names for one concept: CLI `--quiet` / API `messages=` / config: nothing.** Inverted polarity between the first two.

---

## 4. CLI ↔ config asymmetry table (both directions, complete)

**Config options with no CLI flag (25).** Deliberate ones are marked ✔.

| section | option | verdict |
|---|---|---|
| run | `command_line` | ✔ it *is* the CLI |
| run | `core` | oversight-adjacent — `--timid` selects one core (`core.py:83`) but the other two need config or `COVERAGE_CORE`; and see CRF-COVPY-0039 |
| run | `debug_file` | asymmetric — `--debug` exists, `--debug-file` does not, though `COVERAGE_DEBUG_FILE` does |
| run | `disable_warnings`, `dynamic_context`, `patch`, `plugins` | ✔ list/structured values |
| run | `relative_files` | **oversight** (N12) |
| run | `sigterm` | **oversight** (N4) |
| run | `source_pkgs`, `source_dirs` | ✔-ish — `--source` covers the ambiguous case; the disambiguating variants are config-only |
| run | `_crash` | ✔ private |
| report | `exclude_lines`, `exclude_also`, `partial_branches`, `partial_branches_always`, `partial_also` | ✔ regex lists |
| report | `include_namespace_packages` | ✔ |
| html | `extra_css` | **oversight** (N12) |
| xml | `package_depth` | ✔ config-only, consistently absent from the API too |
| json | — | complete |
| lcov | `line_checksums` | ✔ config-only, consistently absent from the API too |
| paths | (section) | ✔ structured |

**CLI options with no config equivalent (7).**

| flag | commands | verdict |
|---|---|---|
| `-a/--append` | combine, run | ✔ per-invocation action modifier |
| `--keep` / `--keep-combined` | combine / six report cmds | ✔ per-invocation, but two spellings (N12) |
| `-q/--quiet` | 5 of 7 output-producing cmds | see N3 |
| `-m/--module` | run | ✔ |
| `--save-signal` | run | **oversight** (N4) |
| `-d/--directory` | annotate | asymmetric — `html` has `[html] directory`, `annotate` has no config equivalent for its output dir |
| `-o` | xml/json/lcov | ✔ maps to `<fmt>:output` |

---

## 5. Learnability assessment

- **Pattern strength: 7/10.** The core rule — *every config option is `section:option`, addressable by `set_option`, and mirrored by a CLI flag and an API parameter* — holds for roughly 45 of 53 options, and the three-surface naming is mostly mechanical. The learnable exceptions a user must memorise: `cover_pylib`↔`--pylib`, `parallel`↔`--parallel-mode`↔`data_suffix=`, `report:format`↔`--format`↔`output_format=`, `html:directory`↔`--directory`↔`directory=`, `report:omit`↔`--omit`↔`omit=` (attribute `report_omit`). That is five, which is at the edge of memorable.
- **Surprise count: 12** (N1–N11 plus the `annotate()` return type below), of which 3 are silent (N1 `slug`, N2 unreachable-from-CLI options, N7 env precedence).
- **Return-type coherence:** five of the six report methods return `float` (the total percentage); `Coverage.annotate` returns `None` (`control.py:1172`, `annotate.py:55`). The CLI is internally consistent about this (`cmdline.py:903-904` does not assign `total`, and `annotate` correctly has no `--fail-under`), but a library user reading five sibling signatures will guess wrong on the sixth.
- **Overall learnability: 7/10.** The API is coherent enough that the failures are *predictable-shaped*: they cluster at the newest surfaces (regions, `--save-signal`, `precision`/`skip_empty` on the newer backends), which is the signature of features landed on one surface and never propagated to the other two.

---

## 6. Top recommendations

Ranked by impact on coherence. All are additive except where noted.

1. **[additive]** Add `Opts.precision` to `json` + `lcov`, `Opts.skip_empty` to `lcov`, and the matching `precision=`/`skip_empty=` parameters to `json_report()`/`lcov_report()` (**N2**). Highest ratio of user-visible fix to diff size: the backends already consume these values.
2. **[additive]** Re-export the eight documented exception classes from `coverage/__init__.py` (**N10**). One line each, zero risk, closes the largest documented-vs-importable gap.
3. **[additive]** Validate `which=` against `{"exclude", "partial", "partial_always"}` with a `ConfigError`, and document all three values (**N5**). Brings the last unvalidated closed vocabulary in line with the other seven.
4. **[additive]** Give `[run] sigterm` a CLI flag and `--save-signal` a config option, and register both in the same place (**N4**). Merges two half-features into one.
5. **[additive]** Add `Opts.quiet` to `report` and `annotate` (**N3**).
6. **[additive]** Document the region reports for users, `--debug=sqlite`, and the `+` sort prefix (**N6**); document `sort=` in `Coverage.report`'s docstring (**N8**); add `:exclude-members: sys_info` to `doc/api_coveragedata.rst` (**N9**). Docs-only batch.
7. **[deprecation]** or **[breaking]** — resolve `process_startup(slug=)` (**N1**). Preferred: wire it into the `--debug=process` output, which is `[additive]` and makes the three existing call sites meaningful. If deleting instead, deprecate for one release, since `pth_file.py`'s incantation is copied by third parties.
8. **[additive]** Document the env-var precedence rules, in particular that `COVERAGE_DEBUG` is additive to `[run] debug` but is replaced wholesale by `--debug` (**N7**), and that LCOV's `FN` records only honour the region kind literally named `"function"` (**N11**).
