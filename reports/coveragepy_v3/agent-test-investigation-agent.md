# test-investigation-agent — coverage.py @ `6b3259ab`

**Target:** `/home/danzin/projects/coveragepy` @ `6b3259abb64a3cb80b4800f58fe1c71b24970110` (main, 2026-07-26)
**Method:** tests-as-specification + **mutation testing as arbiter**, 65 mutants over `coverage/`, each run against the **full 1613-test suite**, on **two core configurations** (default `sysmon` and `COVERAGE_CORE=ctrace`).

## Tree integrity

**I did not edit the reviewed tree.** Every mutation was applied to a `git archive` copy at `/tmp/covrepro`, with a second scratch copy at `/tmp/covdemo` for behavioural probes. Verified at the end of the run:

```
$ git -C /home/danzin/projects/coveragepy rev-parse HEAD
6b3259abb64a3cb80b4800f58fe1c71b24970110
$ git -C /home/danzin/projects/coveragepy diff --stat HEAD      # empty
$ git -C /home/danzin/projects/coveragepy status --porcelain    # only the 5 pre-existing untracked files
```

## Harness

- venv: `/tmp/covtestvenv` (CPython 3.14.3, uv build — chosen because the pre-existing `3.14_coverage_venv` has `sys.base_prefix=/usr/local` while its stdlib lives elsewhere, so coverage's stdlib detection mislabels stdlib files and 8 report tests fail for environmental reasons).
- `pip install -e /tmp/covrepro` + the built `tracer*.so` copied into `/tmp/covrepro/coverage/` so `COVERAGE_CORE=ctrace` is selectable (without it, `PLUGINS`, `DYN_CONTEXTS` and `CAN_MEASURE_THREADS` are all `False` and ~200 tests skip).
- Each mutant: 3 baseline runs → union of failures → mutate → full run → `new = fails − baseline`. A mutant with no new failures **SURVIVED**.
- Baseline: **20** pre-existing failures on the default core, **14** under ctrace (gevent/greenlet not installed, `setup.py` metadata, execv patch, excepthook). Stable across 3 runs each; no mutant's kill set overlaps them.
- The suite deletes `tests/*.zip` partway through a run, which silently disables 16 further tests; the harness re-runs `igor.py zip_mods` before every invocation.
- Excluded as flaky: `tests/test_testing.py::test_all_our_source_files` (fails under `-n` when another worker leaves a `.py` in the tree). One spurious kill from `tests/test_misc.py::HasherTest::test_equality_matches_hash` (a hypothesis `@given` test) was retracted on re-run.

---

# Mutation table

`—` means not re-run under ctrace (mutant already died on the default core).

| # | Site | Mutation | default (sysmon) | ctrace | Test that should have caught it |
|---|---|---|---|---|---|
| **S1** | `files.py:35` | `if not abs_curdir.endswith(os.sep):` → `if True:` | **SURVIVED** | **SURVIVED** | `test_files.py:93 test_relative_dir_for_root` — cannot: `normcase` frozen |
| S2 | `files.py:35` | same guard → `if False:` | DIED (92) | — | `test_api.py::RelativePathTest` + 91 more |
| F1 | `files.py:158` | `abs_file`: drop `os.path.realpath` | DIED (2) | — | `test_process.py::EnvironmentTest::test_bug_862` |
| F2 | `files.py:213` | `prep_patterns`: drop `"?"` from prefix test | DIED (1) | — | (only the flaky meta-test — effectively **unconstrained**) |
| F3 | `files.py:281` | TreeMatcher boundary `== os.sep` → `True` | DIED (4) | — | `test_files.py::MatcherTest::test_tree_matcher` |
| F4 | `files.py:309` | ModuleMatcher boundary `== "."` → `True` | DIED (2) | — | `test_files.py::MatcherTest::test_module_matcher` |
| F5 | `files.py:462` | `PathAliases.add`: drop `rstrip(r"\/")` | DIED (2) | — | `test_files.py::PathAliasesTest::test_cant_have_wildcard_at_end` |
| F6 | `files.py:510` | `map()`: drop separator swap | DIED (18) | — | `test_files.py::PathAliasesTest::test_linux_on_windows` |
| F7 | `files.py:514` | `map()`: drop `./` stripping | DIED (1) | — | `test_files.py::PathAliasesTest::test_no_dotslash[True]` |
| F8 | `files.py:580` | `find_python_files`: relax junk-char filter | DIED (2) | — | `test_files.py::FindPythonFilesTest::test_find_python_files` |
| F9 | `files.py:571` | `find_python_files`: drop `__init__.py` check | DIED (6) | — | `test_venv.py::VirtualenvTest::test_third_party_venv_isnt_measured` |
| F10 | `files.py:60` | `relative_filename`: never strip prefix | DIED (89) | — | `test_api.py::RelativePathTest` + 88 more |
| F11 | `files.py:74` | `canonical_filename`: drop `sys.path` search | DIED (7) | — | `test_api.py::ApiTest::test_stdlib` |
| **P1** | `report.py:106` | `zip(header, values)` → `values[:-1]` | SURVIVED | — | **equivalent mutant** (see dismissals) |
| **P12** | `report.py:248` | `args += [pc_covered]` → append it **twice** | **SURVIVED** | **SURVIVED** | nothing — `zip()` silently drops the extra |
| P1b | `report.py:106` | `zip(header[:-1], values)` | DIED (36) | — | `test_api.py::TestRunnerPluginTest` + 35 |
| P2 | `report.py:117` | TOTAL row `zip(header, total_line[:-1])` | DIED (26) | — | `test_api.py::ApiTest::test_completely_zero_reporting` |
| P3b | `report.py:176` | markdown rows `zip(header[:-1], values)` | DIED (7) | — | `test_report.py::SummaryTest::test_markdown_escape_filename` |
| P4 | `report.py:188` | markdown TOTAL `zip(header, total_line[:-1])` | DIED (4) | — | `test_report.py::SummaryTest::test_markdown_with_missing` |
| P5 | `report.py:30` | `escape_markdown` → identity | DIED (4) | — | `test_report.py::SummaryTest::test_markdown_escape_filename` |
| P6 | `report.py:213` | no-data guard → `if False:` | DIED (3) | — | `test_report.py::SummaryTest::test_dothtml_not_python` |
| P7 | `report.py:257` | `sort` `+` prefix not stripped | DIED (1) | — | `SummaryReporterConfigurationTest::test_sort_report_by_cover_plus` |
| P8 | `report.py:260` | invalid-sort guard → default to 0 | DIED (1) | — | `…::test_sort_report_by_invalid_option` |
| P9 | `report.py:300` | `skip_covered` ignores branches | DIED (2) | — | `test_report.py::SummaryTest::test_report_skip_covered_branches` |
| P10 | `report.py:42` | accept a bogus `format` value | DIED (1) | — | `…::test_report_with_invalid_format` |
| **I1** | `inorout.py:488/493` | swap third-party check and stdlib check | **SURVIVED** | **SURVIVED** | nothing — see N6 |
| I2 | `inorout.py:473` | drop `and not source_in_third_match` | DIED (6) | — | `test_venv.py::VirtualenvTest::test_us_in_venv_isnt_measured` |
| I3 | `inorout.py:503` | non-encodable filename → trace it anyway | DIED (1) | — | `test_oddball.py::ExecTest::test_unencodable_filename` |
| **A4** | `parser.py:274` | negative-lineno multiline map → `first = lineno` | SURVIVED | SURVIVED | **probably equivalent** (see dismissals) |
| **A5** | `parser.py:391` | `while start_next in fixers:` → `if` | **SURVIVED** | **SURVIVED** | nothing — deepest test nests 2 `with`s |
| A1 | `parser.py:351` | `_analyze_ast`: keep self-arcs (`fl1 != fl2` → `True`) | DIED (21) | — | `test_arcs.py::SimpleArcTest::test_compact_if` |
| A2 | `parser.py:410` | `exit_counts`: count excluded source lines | DIED (2) | — | `test_parser.py::test_missing_branch_to_excluded_code` |
| A3 | `parser.py:413` | `exit_counts`: count arcs into excluded lines | DIED (3) | — | `test_parser.py::test_excluded_classes` |
| A6 | `parser.py:266` | decorator exclusion does not carry to body | DIED (4) | — | `test_parser.py::ExclusionParserTest::test_decorator_pragmas` |
| A7 | `parser.py:424` | `_finish_action_msg`: `end < 0` → `end < -1e6` | DIED (4) | — | `test_arcs.py::WithTest::test_raise_through_with` |
| **C1** | `context.py:37` | iterate switchers in reverse | **SURVIVED** | DIED (1) | `test_plugins.py::DynamicContextPluginTest::test_plugin_with_test_function` — **skipped on the default core** |
| **C4** | `context.py:49` | drop `or co_name == "runTest"` | **SURVIVED** | **SURVIVED** | nothing, in any configuration |
| C2 | `context.py:32` | drop the `len == 1` fast path | SURVIVED | SURVIVED | **equivalent mutant** |
| C3 | `context.py:59` | drop `co_varnames[0] == "self"` | SURVIVED | SURVIVED | **near-equivalent**, low confidence |
| **D1** | `plugin_support.py:291` | `DebugFileReporterWrapper.source()` → `""` | **SURVIVED** | **SURVIVED** | nothing |
| **D2** | `plugin_support.py:256` | `DebugFileReporterWrapper.lines()` → `set()` | **SURVIVED** | **SURVIVED** | nothing |
| **J1** | `jsonreport.py:108` | zero-stmt total → `pc_covered` (100.0) | **SURVIVED** | **SURVIVED** | nothing |
| **J2** | `html.py:408` | zero-stmt total → `pc_covered` (100.0) | **SURVIVED** | **SURVIVED** | nothing |
| **XR3** | `xmlreport.py:167` | zero-denominator total `0.0` → `100.0` | **SURVIVED** | **SURVIVED** | nothing |
| J3 | `lcovreport.py:191` | zero-stmt total → `pc_covered` | DIED (2) | — | `test_lcov.py::LcovTest::test_empty_init_files` |
| **E2** | `results.py:138` | `arcs_missing`: drop excluded-destination filter | **SURVIVED** | **SURVIVED** | nothing — likely redundant, see N9 |
| E1 | `results.py:137` | `arcs_missing`: drop `no_branch` filter | DIED (5) | — | `test_arcs.py::ExcludeTest::test_default` |
| E3 | `results.py:100` | `n_partial_branches`: drop `k not in missing` | DIED (6) | — | `test_api.py::AnalysisTest::test_many_missing_branches` |
| E4 | `results.py:144` | `_branch_lines`: `count > 1` → `> 0` | DIED (55) | — | `test_arcs.py::AsyncTest::test_async_with` + 54 |
| E5 | `results.py:177` | `executed_branch_arcs`: drop possibilities filter | DIED (2) | — | `test_lcov.py::LcovTest::test_genexpr_exit_arcs_pruned_*` |
| E6 | `results.py:277` | `narrow()`: `no_branch` → `set()` | DIED (1) | — | `test_html.py::HtmlGoldTest::test_partial` |
| R1 | `results.py:412` | `display_covered`: drop near-0 clamp | DIED (2) | — | `test_results.py::NumbersTest::test_pc_covered_str[kwargs2-1]` |
| R2 | `results.py:414` | `display_covered`: drop near-100 clamp | DIED (4) | — | `test_results.py::NumbersTest::test_display_covered[0-99.995-99]` |
| R3 | `results.py:411` | `near0` off by one decimal | DIED (7) | — | `test_process.py::FailUnderTest::test_report_99p9_is_not_ok` |
| R4 | `results.py:499` | `should_fail_under`: drop exact-100 special case | DIED (37) | — | `test_results.py::test_should_fail_under[99.999-100-1-True]` |
| R5 | `results.py:502` | `should_fail_under`: drop the `round()` | DIED (4) | — | `test_results.py::test_should_fail_under[42.857-43-0-False]` |
| R6 | `results.py:494` | `should_fail_under`: widen the range check | DIED (2) | — | `test_results.py::test_should_fail_under_invalid_value` |
| R7 | `results.py:340` | `_percent`: empty → `0.0` instead of `100.0` | DIED (9) | — | `test_json.py::JsonReportTest::test_empty_file` |
| R8 | `results.py:381` | `ratio_covered`: drop branches from numerator | DIED (19) | — | `test_coverage.py::CompoundStatementTest::test_elif` |
| R9 | `results.py:475` | `format_lines`: weaken the arc filter | DIED (6) | — | `test_report.py::SummaryTest::test_report_show_missing_branches_and_lines` |
| **G1** | `regions.py:63` | class-context guard → `if self.context:` | SURVIVED | SURVIVED | **equivalent mutant** |
| G2 | `regions.py:66` | function bodies not subtracted from enclosing fn | DIED (2) | — | `test_regions.py` / `test_json.py::test_regions` |
| W1 | `control.py:486` | `disable_warnings` never suppresses | DIED (3) | — | `test_api.py::ApiTest::test_warnings_suppressed` |
| W2 | `control.py:497` | `once=True` no longer dedups | DIED (1) | — | `test_api.py::ApiTest::test_warn_once` |
| W3 | `control.py:483` | re-read `disable_warnings` every call | DIED (1) | — | `test_api.py::ApiTest::test_warn_once` |
| N1m | `numbits.py:87` | `numbits_intersection`: drop `rstrip(b"\0")` | DIED (1) | — | `test_numbits.py::NumbitsOpTest::test_intersection` |
| N2m | `numbits.py:34` | `nums_to_numbits`: one byte too many | DIED (5) | — | `test_numbits.py::NumbitsOpTest::test_conversion` |
| L1 | `lcovreport.py:45` | drop the per-line checksum | DIED (1) | — | `test_lcov.py::LcovTest::test_line_checksums` |
| L2 | `lcovreport.py:51` | emit `LF`/`LH` even with 0 statements | DIED (2) | — | `test_lcov.py::LcovTest::test_empty_init_files` |
| L3 | `lcovreport.py:139` | reverse the exit-arc sort key | DIED (5) | — | `test_lcov.py::LcovTest::test_exit_branches` |
| L4 | `lcovreport.py:157` | emit `BRF`/`BRH` when zero | DIED (2) | — | `test_lcov.py::LcovTest::test_branch_coverage_two_files` |
| L5 | `lcovreport.py:128` | drop the `taken == 0` special case | DIED (5) | — | `test_lcov.py::LcovTest::test_always_raise` |
| X1 | `xmlreport.py:36` | `rate(h, 0)` → `"0"` instead of `"1"` | DIED (2) | — | `test_xml.py::XmlReportTest::test_empty_file_is_100_not_0` |
| X2 | `xmlreport.py:38` | `rate` precision `.4g` → `.2g` | DIED (2) | — | `test_xml.py::XmlGoldTest::test_a_xml_1` |

**Score: 65 mutants run, 51 killed, 13 survived, 1 pattern error.** Of the 13 survivors, **4 are equivalent or near-equivalent** and **9 are genuine unconstrained guards**.

---

# NOVEL findings

## N1 — `files.py:35` The system-root separator guard is unconstrained; its only test freezes `os.path.normcase` — FIX

- **Shape:** `assertion-against-a-stub-that-cannot-fail` (the shape the briefing asked me to hunt).
- **Confidence:** HIGH. Mutant **S1 survives both cores**; the inverse mutant **S2 kills 92 tests**.

**The guard** (`coverage/files.py:33-40`):

```python
abs_curdir = abs_file(os.curdir)
if not abs_curdir.endswith(os.sep):
    # Suffix with separator only if not at the system root
    abs_curdir = abs_curdir + os.sep
RELATIVE_DIR = os.path.normcase(abs_curdir)
```

**The test that exists for exactly this case** (`tests/test_files.py:86-98`):

```python
@pytest.mark.parametrize("curdir, sep", [("/", "/"), ("X:\\", "\\")])
def test_relative_dir_for_root(self, curdir: str, sep: str) -> None:
    with mock.patch.object(files.os, "curdir", new=curdir):
        with mock.patch.object(files.os, "sep", new=sep):
            with mock.patch("coverage.files.os.path.normcase", return_value=curdir):
                files.set_relative_directory()
                assert files.relative_directory() == curdir
```

`normcase` is patched with `return_value=curdir` — it ignores its argument. `RELATIVE_DIR` is therefore `curdir` no matter what `abs_curdir` is, so the assertion is a tautology and cannot see the branch it was written for. Measured on the copy:

```
ORIGINAL + frozen normcase:  "/" -> '/'    assert passes
MUTANT   + frozen normcase:  "/" -> '/'    assert passes     <-- identical
MUTANT   + REAL   normcase:  "/" -> '//'
                             relative_filename('/a/b.py') -> '/a/b.py'   (unchanged!)
```

**Concrete wrong behaviour the test permits:** any regression that makes `RELATIVE_DIR` `'//'` at the filesystem root leaves `relative_filename()` returning absolute paths, so `relative_files=True`, `PathAliases` and every relative report path silently degrade for a process whose cwd is `/` (containers with `WORKDIR /`, some CI images). Nothing in the suite notices.

**Guarded twin:** the non-root branch, which S2 proves is pinned by 92 tests.

**Fix:** drop the `normcase` patch and assert on the real value (`files.relative_directory() == os.path.normcase(curdir)`), or assert the intermediate `abs_curdir` directly.

---

## N2 — `parser.py:391` The nested-`with` arc chain-walk is only ever exercised one level deep — CONSIDER

- **Confidence:** HIGH (non-equivalence proved by direct execution).
- Mutant **A5 survives both cores**.

`PythonParser.fix_with_jumps` walks a *chain* of with-jump fixers, and the docstring says so explicitly: *"With nested with-statements, we have to trace through a few levels to correct a longer chain of arcs."* Changing the `while` to an `if` — i.e. correcting only one level — is not noticed by any of the 1613 tests.

**Proof of non-equivalence** (three nested `with`s, run on a scratch copy):

```
ORIGINAL: [(1,2),(2,3),(3,6),(4,-2),(6,7),(7,8),(8,9),(8,10),(9,10),(10,-1)]
MUTANT  : [(1,2),(2,3),(3,6),(4,-2),(6,7),(7,8),(8,9),(8,10),(9,6), (10,-1)]
only in original: [(9, 10)]      only in mutant: [(9, 6)]
```

**Concrete wrong behaviour:** with a 3-deep `with` nest, the exit arc from the innermost body is recorded as jumping *backwards to the outermost `with` header* instead of forwards past the block. Branch reporting then shows a phantom missing branch out of that line and loses the real one.

**Guarded twin:** the 1- and 2-level paths are constrained — the deepest existing test is `tests/test_arcs.py:289 test_nested_with_return` (2 levels), and mutant A1 on the same file kills 21 tests.

**Suggested test:** clone `test_nested_with_return` with three `with` statements and assert `arcz` includes the arc from the innermost body straight to the statement after the outermost `with`.

---

## N3 — The empty-project total is a 4-way divergence, and only lcov's answer is pinned by a test — CONSIDER

- **Confidence:** HIGH. Reproduced end-to-end; **J1, J2, XR3 survive both cores**, **J3 dies**.
- **Relation to catalog:** confirms and extends **CRF-COVPY-0032** (which cites `results.py:336-340` and two backends). The mutation run adds the evidence and three more sites.

For a package containing only zero-statement files, the value each reporter returns — the number `--fail-under` compares against — differs per backend:

```
report(text)   -> 100.0   --fail-under=100 PASSES
json           -> 0       --fail-under=100 FAILS      (jsonreport.py:108)
xml            -> 0.0     --fail-under=100 FAILS      (xmlreport.py:167-168)
lcov           -> 0       --fail-under=100 FAILS      (lcovreport.py:191)
html           -> 0       --fail-under=100 FAILS      (html.py:408-411)
```

Mutating each of those to the *other* answer:

| site | mutation | result |
|---|---|---|
| `jsonreport.py:108` | `n_statements and pc_covered` → `pc_covered` | **SURVIVED** (both cores) |
| `html.py:408-411` | same | **SURVIVED** (both cores) |
| `xmlreport.py:167` | `pct = 0.0` → `pct = 100.0` | **SURVIVED** (both cores) |
| `lcovreport.py:191` | same as json | DIED — `test_lcov.py::test_empty_init_files` |

So three of the four backends are free to return whatever they like for the empty case; only lcov's answer is nailed down, and it disagrees with `coverage report`.

**Suggested test:** one parametrized test over all five report types asserting the same total for a package of empty modules — which will fail today and force the design decision.

---

## N4 — `context.py:49` The `runTest` clause is unconstrained in every configuration — CONSIDER

- **Confidence:** HIGH. Mutant **C4 survives on sysmon AND ctrace**.

```python
def should_start_context_test_function(frame: FrameType) -> str | None:
    if co_name.startswith("test") or co_name == "runTest":
        return qualname_from_frame(frame)
    return None
```

Deleting `or co_name == "runTest"` is not noticed by any test in any core configuration. Direct check on a scratch copy:

```
'test_one'  -> 'None.test_one'
'runTest'   -> 'None.runTest'      # None with the clause removed
'helper'    -> None
```

**Concrete wrong behaviour it permits:** `dynamic_context = test_function` silently produces no per-test contexts for suites that use unittest's `runTest` convention (`unittest.FunctionTestCase`, `TestCase` subclasses with a single `runTest`) — every line lands in the empty context and the HTML context filter shows nothing.

**Guarded twin:** the `startswith("test")` half is exercised by `DynamicContextTest`/`DynamicContextPluginTest`; the `runTest` half has no test at all.

---

## N5 — `context.py:37` Switcher precedence is completely unprotected on the default 3.14 core — CONSIDER

- **Confidence:** HIGH. Mutant **C1 SURVIVES on sysmon**, **DIES under ctrace against exactly one test**.
- **Relation to catalog:** this is the mutation-proof of the *cost* of **CRF-COVPY-0046 / 0049 / 0050** — previously argued structurally, now measured.

`combine_context_switchers` composes switchers in order, and the one test that pins the order is `tests/test_plugins.py::DynamicContextPluginTest::test_plugin_with_test_function` — whose comment reads *"test_function takes precedence over plugins"*. That class carries `@pytest.mark.skipif(not testenv.DYN_CONTEXTS, ...)`, and `DYN_CONTEXTS = C_TRACER or PY_TRACER` (`tests/testenv.py:36`). On Python 3.14 the default core is `sysmon`, so **the single test protecting the rule does not run in the project's default configuration**, and reversing the precedence is invisible to a developer running `pytest` bare.

Measured flag state in this environment on the default core:
`CORE=sysmon  PLUGINS=False  DYN_CONTEXTS=False  CAN_MEASURE_THREADS=False`.

---

## N6 — `inorout.py:484-494` The documented "third-party before stdlib" ordering is unconstrained — CONSIDER

- **Confidence:** HIGH that it is unconstrained; **LOW severity** (see impact).
- Mutant **I1 survives both cores**.

The code carries a comment stating the order is load-bearing:

```python
# Exclude anything in the third-party installation areas. Check this before
# the stdlib, since site-packages is nested inside the stdlib area. If we
# do it the other way around, third-party code will be labeled as stdlib
# in the debug output.
if self.third_match.match(filename):
    return "is a third-party module"
if self.pylib_match and self.pylib_match.match(filename):
    return "is in the stdlib"
```

Swapping the two blocks changes no test outcome. **Impact is confined to the reason string** — the caller (`control.py:457-472`) only tests truthiness — but that string is the `--debug=trace` diagnostic users are pointed at when files are unexpectedly unmeasured, and on a distro Python where `purelib` is nested under `stdlib` it would mislabel every third-party module.

**The stub that hides it:** the only test that drives the stdlib branch, `tests/test_api.py:188 test_stdlib_symlink`, installs

```python
class FakeSysconfig:
    def get_scheme_names(self): return ["xyzzy"]
    def get_paths(self, _):     return {"stdlib": os.path.abspath("myliblink")}
```

`get_paths` returns a dict with **no** `platlib`/`purelib`/`scripts` keys, so `_add_third_party_paths` (`inorout.py:142-146`) contributes nothing and `third_match` **cannot** match inside that test. Same shape as N1.

---

## N7 — `plugin_support.py` The debug FileReporter wrapper can return wrong data with no test noticing — CONSIDER

- **Confidence:** HIGH. **D1 and D2 survive both cores.**
- **Relation to catalog:** sharpens **CRF-COVPY-0019**. That finding says the wrapper mirrors 10 of 14 methods; the mutation adds that the 10 it *does* mirror are unverified too.

Making `DebugFileReporterWrapper.source()` return `""` (`plugin_support.py:291-294`) or `.lines()` return `set()` (`:256-259`) is invisible to the full suite on both cores. So `coverage --debug=plugin` is free to change report content silently in either direction — both by omitting methods (0019) and by corrupting the ones it forwards.

---

## N8 — `report.py:106,176` `zip()` silently absorbs an extra column, one-directionally — CONSIDER (low)

- **Confidence:** HIGH. **P12 survives both cores**; P1b/P3b (the opposite desync) die with 36 and 7 failures.

The four `zip()` calls named in the briefing split cleanly:

- `report.py:117` and `:188` (the TOTAL rows) are **constrained** — P2 and P4 die.
- `report.py:106` and `:176` (the data rows) rely on `len(values) == len(header) + 1`: `tabular_report` appends `nums.pc_covered` as a trailing **sort key** that `zip` is *designed* to truncate. Mutating `values[:-1]` there is an equivalent mutant (P1/P3 — dismissed below).
- The real gap: appending **a second** trailing value to `args` (`report.py:248`) — a header/values desync in the direction that actually happens when someone adds a column — is silently swallowed. **P12 survives.**

So the failure mode is asymmetric: *dropping* a column is caught by 36 tests; *adding* a value without a header entry is silently discarded. A `strict=`-style assertion (`assert len(values) == len(header) + 1`) would make it symmetric.

---

## N9 — `results.py:138` The excluded-destination filter in `arcs_missing()` is unconstrained and looks redundant — CONSIDER (low)

- **Confidence:** MEDIUM. Mutant **E2 survives both cores**; behaviour change proved, user-visible impact not reproducible.

Removing `and p[1] not in self.excluded` changes `Analysis.arcs_missing()` (measured: `[(3,5),(5,6),(6,9),(8,9)]` → `[(3,5),(5,6),(5,7),(6,9),(7,8),(8,9)]` on a `match` with an excluded case) but **not** `missing_branch_arcs()`, `numbers`, or `missing_formatted()`, because `PythonParser.exit_counts()` (`parser.py:413`) already drops arcs into excluded lines, so those lines never qualify as branch lines. Its sibling filter on the same expression (`p[0] not in self.no_branch`, E1) kills 5 tests.

This is the `same-fact-derived-from-two-sources` theme of **CRF-COVPY-0031** in filter form: the exclusion rule is applied in two places, and the second application is untested and possibly dead. Either delete it or add a test that distinguishes it.

---

# Test-infrastructure findings (`assertion-against-a-stub-that-cannot-fail`)

## T1 — `tests/coveragetest.py:263-323` `assert_warnings` replaces the function whose guards matter, for 25 call sites — CONSIDER

`CoverageTest.assert_warnings` monkeypatches `cov._warn` with a fake and states its own limits:

```python
"""...Warnings that are disabled are still considered issued by this function."""
def capture_warning(msg, slug=None, once=False):
    """A fake implementation of Coverage._warn, to capture warnings."""
    # NOTE: we don't implement `once`.
```

The real `Coverage._warn` (`control.py:474-499`) has exactly two guards — the `disable_warnings` filter and the `once` dedup — and the fake implements neither. Every one of the 25 tests using this helper is therefore blind to both. It also never produces the `; see …/messages.html#warning-<slug>` suffix, so no `assert_warnings` test can catch a broken slug URL.

**Guarded twin, and why this is CONSIDER rather than FIX:** `tests/test_api.py::ApiTest::test_warn_once` and `::test_warnings_suppressed` use `pytest.warns` + `assert_coverage_warnings` (which asserts an exact count) instead, and they do kill W1, W2 and W3. The finding is that the *shared* helper is strictly weaker than the idiom two tests already use, and that new tests reaching for the obvious helper will silently lose that coverage.

## T2 / T3

`tests/test_files.py:96` (frozen `normcase`) and `tests/test_api.py:198-207` (`FakeSysconfig.get_paths` returning a one-key dict) are written up under **N1** and **N6**.

---

# Equivalent / near-equivalent mutants — do NOT report these as gaps

| id | Site | Why it survives harmlessly |
|---|---|---|
| P1, P3 | `report.py:106,176` | `len(values) == len(header)+1` by design — the trailing `nums.pc_covered` sort key is *meant* to be truncated by `zip`. `values[:-1]` is a no-op. |
| G1 | `regions.py:63` | Relaxing `context[-1].kind == "class"` to `if self.context:` adds the nested function's lines to an enclosing **function**, and the very next loop (`ancestor.lines -= lines`) removes them again. Only two `kind` values exist. |
| C2 | `context.py:32` | The `len(...)==1` fast path is an optimisation; the general closure returns the same value for one switcher. |
| C3 | `context.py:59` | Dropping `co_varnames[0] == "self"` only differs if a frame has a local named `self` that is *not* the first parameter **and** that object has an attribute named after the running function. I could not construct one; treat as near-equivalent, low confidence. |
| A4 | `parser.py:274` | `-multiline_map.get(-lineno, -lineno)` differs from `lineno` only when the absolute value of a **negative** line number is a continuation line. Negative endpoints are always `-<code-object first line>`; across multiline signatures, multiline decorators and `match`, every negative endpoint mapped to itself. Likely a dead defensive branch — a simplification candidate, not a test gap. |

---

# Negative results — these areas are strongly constrained

Reported so other agents do not raise "untested" findings against them:

- **`files.py` path normalisation — 11 of 12 mutants die.** `abs_file`'s `realpath`, TreeMatcher/ModuleMatcher boundary characters, `PathAliases` `rstrip`/separator-swap/`./`-strip, `find_python_files`' junk filter and `__init__.py` check, `relative_filename`, and `canonical_filename`'s `sys.path` search are all pinned. The single exception is the root-separator guard (N1).
- **`results.py` percentage rounding and `--fail-under` — 9 of 9 mutants die.** Both `display_covered` clamps, the `near0` precision, the exact-100 special case, the `round(total, precision)`, and the range validation are all pinned by `tests/test_results.py`. The asymmetry described in **CRF-COVPY-0007** is a deliberate, tested design choice, not an untested one.
- **`report.py` — 9 of 10 non-equivalent mutants die**, including both TOTAL-row `zip`s, markdown escaping, sort-prefix handling, format validation, and the `skip_covered` branch condition.
- **`parser.py` arc handling — 5 of 7 die**, including self-arc filtering, both `exit_counts` exclusion filters, decorator-exclusion carry, and the exit-arc message branch.
- **`lcovreport.py` — 6 of 6 die.** LCOV output is the best-pinned reporter in the project.
- **`xmlreport.rate()` — both mutants die** (`test_empty_file_is_100_not_0`, the XML gold tests).
- **`control.py._warn` — all 3 mutants die** via `test_warn_once` / `test_warnings_suppressed`.
- **`numbits.py` — both die.**

---

# Catalogued findings touched by this run

| ID | Status |
|---|---|
| CRF-COVPY-0032 (zero statements, backends split) | **Confirmed and extended** — see N3; three additional unconstrained sites (`jsonreport.py:108`, `html.py:408`, `xmlreport.py:167`), reproduced end-to-end |
| CRF-COVPY-0046 / 0049 / 0050 (over-broad test flags mute tests) | **Confirmed with mutation evidence** — see N5; C1 survives on the default core and dies under ctrace against exactly the muted test |
| CRF-COVPY-0019 (DebugFileReporterWrapper mirrors 10 of 14) | **Confirmed and sharpened** — see N7; the 10 mirrored methods are unverified as well |
| CRF-COVPY-0031 (same fact from two sources) | **Related instance** — see N9, exclusion filtering applied twice |
| CRF-COVPY-0007 (asymmetric rounding display vs gate) | **Still present, but fully tested** — R1–R6 all die; it is a deliberate design choice, not a test gap |
| CRF-COVPY-0040 (warnings without slugs) | **Adjacent** — see T1; the shared `assert_warnings` helper cannot observe slug-based suppression at all |

---

# Caveats

1. **Single platform, single Python.** Linux, CPython 3.14.3. Windows-only code (`actual_path`, drive-letter handling) was not mutated. `CAN_MEASURE_BRANCHES` was `True`, so branch mutants were live.
2. **Two cores, not four.** `sysmon` (default) and `ctrace`. `pytrace` was not swept; `DYN_CONTEXTS` is true there too, so C1 would presumably die under it as well.
3. **20/14 pre-existing baseline failures** (see Harness) reduce discriminating power slightly. None of them lies in a module I found a survivor in, except the 8 CLI-driven `SummaryTest` cases that fail when `tests/zipmods.zip` is missing — mitigated by rebuilding the zips before every run.
4. **Survivor ≠ bug.** A surviving mutant proves the code is *free to be wrong there*, not that it *is* wrong. N1, N2, N3 and N4 are backed by an executed demonstration of the wrong behaviour; N6, N8 and N9 are backed by an argument about impact, and I have labelled their severity accordingly.
