# complexity-simplifier — coverage.py @ `6b3259ab`

**Tree edited: NO.** The target `/home/danzin/projects/coveragepy` was never written to. All
execution was done against a `git archive HEAD` copy at `/tmp/covrepro`. Verified after the run:
`git status --porcelain -- coverage/` is empty and HEAD is still `6b3259ab`.

Inputs used, not re-derived: `measure_complexity.json` (698 functions, 14 hotspots ≥5.0, 3 ≥8.0,
avg 1.3) and `analyze_history.json` (585 fix commits / 2y). `agent-git-history-context.md` was not
present at read time, so the fix-density cross uses `measure_complexity.json`'s own
`history_crossing` block plus `analyze_history.json`'s `function_churn` / `file_churn` lists.

---

## 1. Headline

Complexity is a poor ranker here and the data says so out loud: the script's own note records that
*"complexity alone ranked coverage.py's files in almost the reverse of their fix history."* Eleven
of the fourteen hotspots are inherent — tracer callbacks, a tokenizer walk, a template compiler, an
`optparse` dispatch. The three that are *reducible* are the three where the reducible part is also
where the bugs are.

The single most useful cut is not "score", it is **score × fix density**. `sysmon_py_start` scores
lower than `Templite.__init__` and has infinitely more risk: five fix commits in two years against
zero.

---

## 2. Hotspot table

`fix` = fix-commits in 2y (`measure_complexity.json`). `churn` = total commits touching the function
(`analyze_history.json::function_churn`). Verdicts are the script's, refined by reading the code.

| # | Function | file:line | Score | Inherent / Reducible | fix | churn | Verdict |
|---|----------|-----------|-------|----------------------|-----|-------|---------|
| 1 | `SysMonitor.sysmon_py_start` | `sysmon.py:317-395` | 7.5 | **Reducible** (see §4.1) | 5 | 2 | **active-risk — rank 1** |
| 2 | `PyTracer._trace` | `pytracer.py:147-311` | 9.0 | Inherent core, **reducible prologue** | 2 | 0 | **active-risk — carries NOVEL-1** |
| 3 | `PythonParser._raw_parse` | `parser.py:165-267` | 7.0 | **Inherent** (token state machine) | 1 | **3** | active — top of function_churn |
| 4 | `HtmlReporter.write_html_page` | `html.py:467-568` | 5.0 | **Reducible** (3 concerns) | 2 | 1 | **active-risk — rank 3** |
| 5 | `CoverageScript.command_line` | `cmdline.py:793-956` | 5.5 | Inherent (flat CLI dispatch) | 1 | **3** | quiet, high churn |
| 6 | `Templite.__init__` | `templite.py:125-257` | 8.0 | **Inherent** (template compiler) | 0 | 0 | settled — but carries NOVEL-2 |
| 7 | `combine_parallel_data` | `data.py:132-240` | 8.0 | **Reducible** (loop body extractable) | 1 | 0 | settled |
| 8 | `HtmlDataGeneration.data_for_file` | `html.py:134-225` | 7.0 | **Reducible** (category ladder) | 1 | 0 | quiet |
| 9 | `InOrOut.should_trace` | `inorout.py:343-443` | 7.0 | **Inherent** (guard-clause chain, already idiomatic) | 1 | 0 | quiet |
| 10 | `source_token_lines` | `phystokens.py:113-179` | 7.0 | **Inherent** (tokenizer) | 1 | 0 | quiet |
| 11 | `BranchArcResolver.resolve` | `bytecode.py:160-208` | 5.0 | **Inherent** (bytecode walker) | 1 | 1 | quiet — **verified correct, §5** |
| 12 | `CoverageConfig.from_file` | `config.py:296-379` | 5.0 | **Reducible** (mild) | 0 | 0 | quiet |
| 13 | `HtmlReporter.write_region_index_pages` | `html.py:584-641` | 5.0 | **Reducible** (mild) | 0 | 0 | quiet |
| 14 | `XmlReporter.xml_file` | `xmlreport.py:173-258` | 5.0 | **Inherent** (DOM assembly) | 0 | 0 | quiet |

Per the briefing's "inherently-complex dispatch" and "parser / state machine" FP classes: **#3, #5,
#6, #9, #10, #11, #14 are dismissed as inherent and are not simplification targets.** `_raw_parse`
and `source_token_lines` are token state machines; `command_line` is a flat action dispatch where an
`if/elif` per subcommand is more readable than a registry; `resolve` is a raw-bytecode walker and I
verified it rather than restructured it.

---

## 3. The valuable cross-reference: complexity × fix density — top 5

Ranked by *where the next bug lives*, not by score.

1. **`sysmon.py::sysmon_py_start`** — score 7.5, **5 fix commits**, density 0.0633 (5× the next
   worst). This one function has absorbed the tool-id search (`4b0fc85`), the lazy branch resolver
   (`182b010`), and the `__annotate__` skip. It already owns four catalogued findings
   (**0005, 0022, 0042, 0044**). If one more bug lands in coverage.py this quarter, it lands here.
2. **`pytracer.py::_trace`** — score 9.0, 2 fix commits. Highest absolute complexity in the project
   and it is the *only* function I found a new, reproducible, user-reachable defect in (**NOVEL-1**).
3. **`html.py::write_html_page`** — score 5.0, density 0.0196, and its most recent commit
   (`dd80635`, 2026-07-11) is an **escaping** fix. Escaping fixes cluster; this is the highest-value
   place to look for a sibling of the `</script>`-in-a-context-label bug.
4. **`parser.py::_raw_parse`** — 3 commits, the top entry in `function_churn`, and `parser.py` is the
   *only* `coverage/` source file in the top-25 `file_churn` list (6 commits, +124/-49). Two of its
   neighbours (`_analyze_ast`, `fix_with_jumps`, `with_jump_fixers`) also churned twice each. The
   file is under active redesign.
5. **`cmdline.py::command_line`** — 3 commits, and the last one (`1cd47aa`, *"implicit
   combine-during-report now removes the combined data files"*) changed data-destroying behaviour in
   a 10-return function. It is inherent complexity, but it is *churning* inherent complexity.

Note the anti-correlation the script warned about: `Templite.__init__` (8.0) and
`combine_parallel_data` (8.0) — the joint #2 most complex functions in the project — have **0** and
**1** fix commits. They are settled. Do not spend a refactoring budget there.

---

## 4. Bugs found inside the hotspots

### NOVEL

#### NOVEL-1 — [FIX] A stopped `PyTracer` writes to a hard-coded `/tmp` path, and crashes the user's program if it cannot

- **Where:** `coverage/pytracer.py:176-182` (the handler) → `coverage/pytracer.py:127-145` (`log`),
  specifically the `open("/tmp/debug_trace.txt", "a", …)` at **`coverage/pytracer.py:129`**.
- **Shape:** novel. Closest catalogued relative is `guarded-twin` — `data_stack.pop()` is wrapped in
  `except IndexError` at `pytracer.py:172-182` and is **unguarded** at its sibling
  `pytracer.py:302-304`.
- **What it is:** `log()` is a debugging helper (`"For hard-core logging of what this tracer is
  doing"`). Every other call to it in the file is dead — line 160 and 186 are commented out, lines
  167/169 sit under `if 0:`, line 344 is commented out. **`pytracer.py:177` is the only live call
  site in the module**, and it is on a production error path. It carries no `# pragma: debugging`.
- **Why it fires:** the deactivation branch at `pytracer.py:162` runs *before* the event dispatch and
  pops `data_stack` unconditionally, whatever the event type. If `stop()` was called from another
  thread (`pytracer.py:338-345` returns early without `sys.settrace(None)`), the flag is set but the
  tracer stays installed; the next event on the original thread can be a `"call"` raised from a frame
  that was never pushed — so the stack is empty and `pop()` raises.
- **Reproduced**, `Coverage(timid=True)` on Python 3.14.4 against a clean archive of `6b3259ab`:

  ```python
  cov = coverage.Coverage(timid=True, data_file=None)
  def stopper(): time.sleep(0.10); cov.stop()   # stop() from a different thread
  cov.start()
  threading.Thread(target=stopper).start()
  time.sleep(0.40)     # C builtin -> no trace events; main thread sits at <module> level
  foo()                # first event after stopped=True is a "call"; data_stack is EMPTY
  ```

  Result: `/tmp/debug_trace.txt` created, containing
  `Empty stack! 0[0] /tmp/covrepro/repro_empty_stack.py 11 foo`.
  Reproducer kept at `/tmp/covrepro/repro_empty_stack.py`.
- **Failure scenario (the part that matters):** `open(path, "a")` is not a best-effort write. Re-run
  the same script with `/tmp/debug_trace.txt` pre-existing as a **directory** and the program dies:

  ```
  IsADirectoryError: [Errno 21] Is a directory: '/tmp/debug_trace.txt'
  ```

  raised out of `_trace` at the `foo()` call site, killing the user's process at an arbitrary point
  with a coverage-internals traceback. On any shared or CI machine where that path already exists
  owned by another uid, the same happens with `PermissionError`. And because `"a"` follows symlinks,
  a local user can pre-create `/tmp/debug_trace.txt` as a symlink to any file the coverage-running
  user can write, and coverage will append to it — an unprivileged local write primitive in a tool
  that routinely runs in CI as a build user.
- **Fix (behaviour-preserving for every non-error path):** delete the `self.log(...)` call at
  `pytracer.py:177` and leave the handler as `except IndexError: pass`, or route it through
  `self.warn(..., slug=...)` which the class already holds (`pytracer.py:90`, used at
  `pytracer.py:352-358`). Separately, mark `log()` `# pragma: debugging` and move its path to
  `tempfile.gettempdir()` + `os.getpid()` so the surviving `if 0:` call sites cannot resurrect the
  hazard.
- **Would the tests catch a mistake in this fix?** **No.** `grep` finds no test that exercises
  `PyTracer.log`, and no test asserts on `/tmp/debug_trace.txt`. Removing the call is untested in
  both directions; the fix is safe precisely because the call is provably dead-except-on-error.
  A regression test is cheap: the reproducer above, asserting no file appears.

#### NOVEL-2 — [CONSIDER] `Templite` raises a raw `IndexError` for two malformed-template shapes where every sibling raises `TempliteSyntaxError`

- **Where:** `coverage/templite.py:171` (`squash = (token[-3] == "-")`) and
  `coverage/templite.py:187-188` (`words = …split()` then `words[0]`).
- **Shape:** catalogued — `error-escapes-the-project-exception-hierarchy` (same shape as
  **CRF-COVPY-0042**, `sysmon.py:253`).
- **Guarded twin:** the eight sibling error paths in the same function — lines 191, 197, 199, 206,
  219, 222, 225, 231 — all call `self._syntax_error(...)`, which raises `TempliteSyntaxError`. These
  two do not.
- **Verified** on the `6b3259ab` archive:

  | template | result |
  |---|---|
  | `Templite("{x}")` | `IndexError: list index out of range` |
  | `Templite("{")` | `IndexError: string index out of range` |
  | `Templite("{}")` | `IndexError: string index out of range` |
  | `Templite("a {b} c")` | ok (the `{` is not at position 0, so `re.split` yields one literal) |

  Only a template whose **first character** is `{` without a closing tag reaches it: `re.split`
  produces a single unmatched literal, `token.startswith("{")` is true, and `token[2:-2]` is empty.
- **Reachability inside coverage: none.** Both `Templite` call sites (`html.py:338`, `html.py:340`)
  pass package data (`read_data("index.html")`, `pyfile_html_source`). This is why it is CONSIDER, not
  FIX. It matters because `templite.py` ships as a documented, independently-tested, reusable class
  (`tests/test_templite.py`) whose contract is "syntax errors raise `TempliteSyntaxError`".
- **Fix:** guard the length before the `token[-3]` probe and before `words[0]`, routing both to
  `self._syntax_error("Don't understand tag", token)`.
- **Would the tests catch a mistake?** **Partly.** `tests/test_templite.py` has a
  `try_render`/`assertSynErr` harness for exactly this class of input, so a fix is easy to test — but
  no existing case covers a leading unmatched `{`, so the bug is currently invisible to CI.

### CATALOGUED — confirmed present, not re-litigated

Verified by reading the code at `6b3259ab`; all still live.

| ID | Site | Confirmed at |
|---|---|---|
| CRF-COVPY-0038 | empty set read as untraced file, `frame.f_trace_lines = False` | `pytracer.py:241-242` |
| CRF-COVPY-0005 | nested Coverage stops measurement on the 3.14 core | `sysmon.py:335`, `:374-387` |
| CRF-COVPY-0022 | three sysmon callbacks index `code_infos` unguarded | `sysmon.py:410`, `:436`, `:451` — sibling `sysmon_line_lines` still checks at `:426` |
| CRF-COVPY-0042 | bare `RuntimeError` on tool-id exhaustion | `sysmon.py:253` |
| CRF-COVPY-0044 | code objects retained for the process lifetime | `sysmon.py:213-215`, `:371-372` |
| CRF-COVPY-0013 | `resume()` installs other threads' tracers on the caller | `collector.py:367-373` |
| CRF-COVPY-0034 | region analysis walks only `body` | `regions.py:53-56` |
| CRF-COVPY-0031 | `arcs_missing()` filters `no_branch`, `exit_counts()` does not | `results.py:131-138` vs `parser.py:400-419` |
| CRF-COVPY-0016 | unreadable config file reads as absent | `config.py:319-323` |
| CRF-COVPY-0043 | `skip_empty` early-return diverges across backends | `xmlreport.py:176-178` |
| CRF-COVPY-0027 | `set_option()` bypasses `post_process()` | called from `cmdline.py:941-943` |

---

## 5. Things that look like bugs inside the hotspots and are not — checked, dismissed

Recording these so the next pass does not spend the budget again.

- **`html.py:536`, `assert len(longs) == 1`.** Looks like a crash waiting for a 3-way branch line:
  the `else` arm at `html.py:171-179` appends one long annotation per missing arc, so a line with 3
  exits and 2 missing would trip it. **Dismissed by measurement:** `exit_counts()` never exceeds 2. I
  parsed the entire 3.14 stdlib (625 files) with `PythonParser` and found **zero** lines with more
  than two exits, including `match` statements — `_handle__Match` (`parser.py:1088`) chains cases
  pairwise rather than fanning out. The assert's own comment is true.
- **`html.py:165`, `branch_stats[lineno]` indexed from a `missing_branch_arcs` key.** Not a KeyError:
  both dicts are keyed off the same `_branch_lines()` derivation (`results.py:143`, `:189`).
- **`bytecode.py:160-208`, `BranchArcResolver.resolve`.** New code (`182b010`, 2026-07-12) doing raw
  `co_code` arithmetic with hand-rolled `EXTENDED_ARG` accumulation and manual `CACHE` skipping —
  the highest a-priori suspicion in the list. **Differentially verified against `dis`:** I replicated
  its jump-target arithmetic and compared it to `dis.get_instructions(...).jump_target` over the
  3.14 stdlib — **12,965 unconditional jumps, 0 mismatches.** The `EXTENDED_ARG` fold
  (`ext = (ext | b) << 8` at `bytecode.py:179`) is equivalent to CPython's `(oparg << 8) | b` for any
  chain length. Leave it alone.
- **`pytracer.py:351`, `env.PYPY and self.in_atexit and tf is None or env.METACOV`.** I ran an AST
  sweep over all of `coverage/` for an `Or` containing an unparenthesised `And` — this is the only
  hit in the package, and it *is* explicitly parenthesised in the source. **No instance of
  `guard-conjoined-with-a-preference-flag` exists in coverage.py.**
- **`pytracer.py:172-183` popping on a `"call"` event.** I instrumented an archive copy and traced
  a nested-`Coverage` restart: the pop compensates exactly for the frame whose `return` event is lost
  in the `settrace(None)` window (observed `DEACT-POP` at depth 6, then balanced returns 5→4→3→0).
  Frames keep their `f_trace` across a `settrace` swap, so the accounting closes. Not a defect — but
  it *is* what makes the empty-stack case in NOVEL-1 reachable.
- **`data_for_file`, `contexts_by_lineno` possibly-unbound** (`html.py:143-144` bound,
  `html.py:198-199` read). Both arms gate on the same `self.config.show_contexts`, and nothing
  mutates config mid-report. ACCEPTABLE; noted only because it is the kind of thing an extraction
  refactor breaks.
- **`combine_parallel_data`, files deleted before `strict and not combined_any` raises**
  (`data.py:226-232`). Not data loss: the only way `combined_any` stays False with files present is
  that every file errored, and the error arm sets `delete_this_one = False` at `data.py:214`.
- **`coverage annotate` ignores `[report] fail_under`** (`cmdline.py:903-904` leaves `total` as
  `None`). Not a finding: `annotate`'s parser (`cmdline.py:538`) does not include `Opts.fail_under`,
  and annotate produces no total to gate on.

---

## 6. Simplification roadmap

Ordered by effort:impact, with the test question answered for each.

1. **`pytracer.py` — delete the `self.log()` call at `:177`.** One line. Fixes NOVEL-1. Tests will
   not catch a mistake (no coverage of `log`), so pair it with the reproducer as a regression test.
   Do this first; it is the only item that fixes a user-visible crash.
2. **`sysmon_py_start` — extract `_classify_code(code) -> CodeInfo` (`sysmon.py:335-372`) and
   `_enable_local_events(code)` (`sysmon.py:374-393`).** Rank-1 risk, depth 6, and the two halves
   are genuinely independent: one decides *whether* to trace, the other tells `sys.monitoring`
   *what* to watch. The extraction makes CRF-COVPY-0005 (the "already-registered code object never
   re-registers" bug) a two-line read instead of a six-level nesting read. **Tests would catch a
   mistake** — `tests/test_coverage.py` and `tests/test_arcs.py` exercise this path on every 3.12+
   run, and a wrong `tracing_code` assignment fails loudly.
3. **`write_html_page` — split the three concerns** (`html.py:483-500` context-code table;
   `:502-548` per-line HTML rendering; `:550-568` write + index bookkeeping). The middle block is a
   40-line loop doing five unrelated jobs and it is where the last escaping fix landed. Extracting
   `_render_line_html(ldata, context_codes)` puts the escaping in one nameable, testable unit.
   **Tests would catch a mistake:** `tests/gold/html/**` are byte-exact golden files, so any
   rendering change fails immediately. This is the safest refactor in the list.
4. **`combine_parallel_data` — extract the loop body** (`data.py:189-229`) as
   `_combine_one_file(data, f, classifier, keep, map_path) -> Literal["combined","skipped","errored"]`.
   Turns a 4-deep nest into a counter update. Settled code (1 fix / 2y) so the payoff is readability
   only — schedule it behind 1-3. `tests/test_api.py::test_combine_parallel_data*` covers it.
5. **`data_for_file` — extract the category ladder** (`html.py:158-193`) as
   `_categorize(lineno) -> tuple[str, str]`. Mechanical. Golden files cover it.
6. **Do not touch** `_raw_parse`, `source_token_lines`, `command_line`, `Templite.__init__`,
   `resolve`, `xml_file`, `should_trace`. Inherent, and in the `resolve` case measured correct.

**Do together:** items 3 and 5 both live in `html.py` and both feed the same golden-file suite; a
single PR keeps the golden regeneration to one step.

---

## 7. Cross-cutting observations

- **The tracer backends disagree about their own shutdown discipline.** `PyTracer.stop()` defers
  `sys.settrace(None)` into the callback and leaves a partially-popped `data_stack`
  (`pytracer.py:327-358`); `SysMonitor.stop()` tears everything down synchronously under a lock and
  early-returns if `not self.sysmon_on` (`sysmon.py:270-281`), which means a failure between
  `use_tool_id` and `sysmon_on = True` in `start()` (`sysmon.py:243-268`) leaks the tool id with no
  way to free it. This is the same root as the catalogued `one-concern-implemented-per-backend`
  family (0003, 0009, 0010, 0028, 0029, 0032) reaching into lifecycle rather than data.
- **Debug-only machinery is not consistently fenced.** `sysmon.py` gates its logging behind `LOG` and
  `# pragma: debugging` throughout (`sysmon.py:158-169`, `:283-297`, `:342-344`, `:389-393`).
  `pytracer.py`'s equivalent uses commented-out call sites and `if 0:` — an unenforceable convention
  that already leaked one live call. A `LOG`-style flag in `pytracer.py` would make NOVEL-1
  structurally impossible.
- **Complexity concentrates in the two tracers and the HTML writer, and so does the fix history.**
  Five of the fourteen hotspots are in `html.py`/`xmlreport.py` reporting code, four are in
  measurement (`pytracer`, `sysmon`, `parser`, `phystokens`). Every catalogued finding inside a
  hotspot is in the measurement group. Reporting complexity is broad and shallow; measurement
  complexity is deep and dangerous.
