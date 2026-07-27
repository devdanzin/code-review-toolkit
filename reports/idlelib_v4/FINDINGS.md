# idlelib informed-explore v4 — running findings

`Lib/idlelib` @ CPython `6080c866096` · toolkit v1.11.0 · 125 files · 18 agents + 12 scanners

## VERIFIED BY THE ORCHESTRATOR

### F1 · FIX · `pyshell.py:1020` + `pyshell.py:1002` — copy-with-prompts silently drops the last line

`copy_with_prompts_callback` normalises the selection end with

```python
sellast = text.index('sel.last')      # "line.col"
if sellast[-1] != '0':
    sellast = text.index("sel.last+1line linestart")
```

`sellast[-1] != '0'` is a **string-suffix test standing in for "column == 0"**. It is equivalent only
for single-digit columns; for column 10, 20, 30, 100 … the last character is `'0'` and the index is
left unextended. `get_prompt_text` then builds prompts from `range(int(float(first)), int(float(last)))`
and lines from `text.get(first, last).splitlines()`, and `zip()` truncates to the shorter — dropping
the final line.

**Verified against real Tk** (CPython 3.14 from this tree, `tkinter.Text` with 4 lines):

```
sel.last=4.5    guard->5.0    prompts=4 lines=4  ok
sel.last=4.10   guard->4.10   prompts=3 lines=4  DROPS LAST LINE
sel.last=4.20   guard->4.20   prompts=3 lines=4  DROPS LAST LINE
```

The docstring at `pyshell.py:1012-1013` promises the opposite: *"This always copies entire lines,
even if only part of the first and/or last lines is selected."*

Reachable from Edit menu, shell context menu (`sidebar.py:450`) and the `<<copy-with-prompts>>`
binding. Second failure mode at the same `zip`: `iomenu.py:261` save-shell-contents drops the
unsubmitted prompt line, which is the shell's normal resting state.

**History — this is fix residue.** `News3.txt:109` records gh-95511, *"Fix the Shell context menu
copy-with-prompts bug of copying an extra line"*. That fix introduced this guard.

**Guarded twin, in this project's own tests:** `idle_test/test_sidebar.py:764` pairs prompts with
lines using `zip(..., strict=True)`. The test demands strict pairing; the production code it tests
does not — and the test never catches it because its fixture selects to `'end-1c'`, which lands on
column 0.

Two independent one-line fixes: `if not sellast.endswith('.0'):` and `zip(..., strict=True)`.

## TOOLKIT DEFECTS FOUND BY THIS RUN

### T1 · `analyze_imports.py` reported a resolution failure as a clean result

On `Lib/idlelib` it emitted `cycles: []`, an empty `internal_graph`, and zero fan-in — and I
repeated that as "0 cycles" in my own status. It was not a finding. `project_root` resolved to the
CPython checkout, `project_packages` came out as `['python-config', 'python-gdb']`, and because
**idlelib IS the stdlib**, `_is_stdlib()` was consulted before `project_packages`, so every
`from idlelib.x import y` was classified `stdlib` and dropped.

Three fixes: the scanned package is now detected as a package in its own right; **project packages
win over the stdlib list**; and a `resolution` field reports `FAILED` / `PARTIAL` / `ok` so an empty
graph can never again read as "no coupling".

Result on idlelib: 0 → **113 resolved edges**, fan-out now correct (`editor.py` 21, `pyshell.py` 15).
**asyncio: 0 → 19 cycles**, so the Phase 5 asyncio run had the same silent failure.
coverage.py unchanged (9 cycles, 42 modules) — no regression.

**Still open:** fan-in and cycles remain 0 for idlelib. The graph keys sources on file paths and
targets on dotted module names; those agree only when the package root IS the project root.
`resolution: PARTIAL` now says so rather than reporting emptiness as a result.

### T2 · The 1.6.0/1.11.0 registry gap, live

`lint-rule-triager` and `typing-integrity-auditor` were not dispatchable — the installed plugin is
1.6.0, from before this session shipped 1.7.0-1.11.0. Both were routed through `general-purpose`
with their definition files. This is exactly the incident improvement-plan item 0.6 exists to
prevent, recurring in real time.

### F2 · FIX · `autocomplete_w.py:362-366` — `and` binds tighter than `or`, so the modifier guard covers one arm of two

```python
elif (self.mode == ATTRS and keysym in (...)) or \
     (self.mode == FILES and keysym in (...)) \
     and not (state & ~MC_SHIFT):
```

Parses as `ATTRS_arm or (FILES_arm and not_modified)` — **the ATTRS arm ignores the modifier guard.**
Verified:

```
ATTRS + space, no modifier  -> True
ATTRS + space, CONTROL held -> True   <- guard skipped
FILES + slash, CONTROL held -> False  (guard correctly applies)
```

**Guarded twin 20 lines above, same function** (`autocomplete_w.py:334-336`): the identical guard,
correctly parenthesised so every arm honours it.

**Reachable via IDLE's own default binding.** `config-keys.def:60,120,180,240` bind
`force-open-completions=<Control-Key-space>` in all four keysets. With the completion window open in
ATTRS mode, Control-Space commits the highlighted completion into the buffer instead of being
ignored — the function's own later branch (`:418`, *"A modifier key, so ignore"*) states the intent.

Fix: two parentheses.

### F3 · FIX · `hyperparser.py:298` — string-prefix scanner never learned `f` or `t`

```python
while pos > 0 and rawtext[pos - 1] in "rRbBuU":   # no f/F (3.6), no t/T (3.14)
```

**Guarded twin, same package:** `colorizer.py:50`
`stringprefix = r"(?i:r|u|f|fr|rf|b|br|rb|t|rt|tr)?"` — complete.

`b` was added to *both* sites in 2013 (#16819). The colorizer got `f` in 2017 and `t` on 2025-10-09
(gh-139742). `hyperparser.py:298` has not been touched since 2013. For `t'…'.strip` the completion
machinery evals a truncated expression, gets a `str`, and offers `str` methods — but the real object
is `string.templatelib.Template`, on which **none of them exist**.

## SYSTEMIC ROOT BEHIND F3

**idlelib maintains five independent hand-written recognizers for Python syntax with no shared
source of truth**: `pyparse._synchre`, `pyparse._junkre`, `hyperparser`'s prefix scan,
`codecontext.BLOCKOPENERS`, and `colorizer`. New syntax is taught to some and not others, and
`colorizer` is consistently the one that gets updated.

Confirmed drift, each with a twin inside the package:
- `hyperparser.py:298` missing `f`/`t` (F3)
- `codecontext.py:22` `BLOCKOPENERS` missing `match`/`case` — added to `colorizer` in 2021,
  `autocomplete.py:15` and `editor.py:1595` both have them; `BLOCKOPENERS` itself was extended for
  `async` in 2018, so the practice exists
- `pyparse._synchre` has `def` but cannot match `async def` (anchored `^[ \t]*`)
- `pyparse._junkre` `\#\S` — CRF-IDLELIB-0017, confirmed still present; its twin is
  `codecontext.py:39`, which treats any `#`-initial line as non-code

## MORE TOOLKIT DEFECTS

### T3 · Four scanner lists are silently capped, presented as counts

`count_types.unannotated_public_functions` reads 50 — the true figure for idlelib is **2079**
(`count_types.py:365` slices `[:50]`). Same shape at `extract_test_invariants.py:468` (`[:15]`) and
`:663` (`[:20]`) — **I quoted "20 untested similar functions" to an agent as if it were a count.**
All now emit `*_total` and `*_capped` beside the list.

### T4 · `correlate_tests.py` mis-measures idlelib three ways

Reported 84.8%; real product coverage is **93.3% (56/60)**. It counts six test-infrastructure files
under `idle_test/` as source; `summary.total_test_methods` (587) silently subtracts skipped tests and
unmapped files and so disagrees with its own `test_details` (613) by 26; and it sees only `@skip`
decorators, missing runtime `self.skipTest()` (2 sites in `test_configdialog.py`).

## THE COVERAGE ILLUSION, QUANTIFIED

Of 613 test methods: **43 assert only against a mock recorder, 11 assert nothing at all** — 8.8%
prove nothing about behaviour. 70% live in files importing `mock_tk`/`mock_idle`, and
**`mock_idle.py` — which defines the `Func` recorder used by 315 test methods — has no test of its
own.**

The exemplar is exact. CRF-IDLELIB-0025 says `Idb.user_exception` calls the GUI unguarded where its
twin `user_line` wraps the call in `try/except TclError`. Both are tested — with `self.gui = Mock()`.
**A `Mock()` never raises `TclError`**, so both tests pass identically whether or not the guard is
there. Line coverage is 100% on both; the assertion cannot discriminate the defect. One-line fix:
`Mock(side_effect=TclError)`.

Same shape, live bug: `test_zoomheight.py:33` calls `zoom_height_event()` and asserts **nothing**,
in the same function as CRF-IDLELIB-0009 (a `WmInfoGatheringError` leaves the window stuck maximized
because the restore is only on the success path).

## AGENT-REPORTED, NOT INDEPENDENTLY VERIFIED BY THE ORCHESTRATOR

Each carries a cited `file:line` and a stated failure scenario. Ranked by how silent the failure is.

| # | Sev | Site | Failure |
|---|---|---|---|
| A1 | FIX | `replace.py:151,220` `format.py:71,258` | `undo_block_start/stop` unpaired on the exception path. Leaks `UndoDelegator.undoblock`, freezing `pointer`/`saved`, so **Ctrl-Z dies AND `maybesave()` can return "yes" — window closes without prompting.** Twin: `pyshell.py:1329` uses try/finally |
| A2 | FIX | `codecontext.py:22` | `BLOCKOPENERS` lacks `match`/`case`; `colorizer` got them 2021, `autocomplete.py:15` and `editor.py:1595` have them |
| A3 | FIX | `config.py:243` | Invalid **default**-config value swallowed by `pass`; the user-config clause 11 lines up warns, and the docstring at `:225` has promised a warning since 2014 |
| A4 | FIX | `config.py:567` | Keybinding collision test is whole-list equality, so a partial overlap is undetected; and a dropped binding is silent where `config_key.py:261` shows a modal error for the same conflict |
| A5 | FIX | `pyshell.py:266` | `restore_file_breaks` appends without clearing → Save As carries the old file's breakpoints onto the new file and persists the union. `clear_file_breaks` exists and is never called on that path |
| A6 | FIX | `pyshell.py:243` | Breakpoints keyed by raw `io.filename`; `FileList` keys the same file `normcase(normpath(abspath()))`. On Windows a case change silently loses breakpoints and appends a duplicate entry forever |
| A7 | FIX | `filelist.py:88` | After a Name Conflict the displaced window gets `inversedict[w]=None` instead of a re-point; the **next** collision on that file is silent → two windows clobbering each other |
| A8 | FIX | `pyparse.py:245` | `_study1` has no f-string `{}` state; since PEP 701 a legal `f"{\n...}"` is read as two statements, so continuation lines indent to column 0 |
| A9 | FIX | `debugger_r.py:271` | `DictProxy.__getitem__` returns a *repr*; `debugger.py:569` strips the extra quotes, `stackviewer.py` does not |
| A10 | CONSIDER | `debugger_r.py:35` | Four `id()`-keyed tables never cleared. Measured 20k stops → 20k entries, 17MB → 56MB |
| A11 | CONSIDER | `tree.py:234` | 26-year-old `XXX` naming a real leak: `tag_bind` twice per node per redraw, Tcl commands never deleted, pinning every browsed object |
| A12 | CONSIDER | `pyparse.py:21` | `_synchre` matches `def` but not `async def`; measured 2.61 ms/call vs 0.00 on a 2000-function async module — per keystroke |
| A13 | CONSIDER | `config.py:196` | `GetUserCfgDir` falls back to `os.getcwd()`, so the whole IDLE profile is a function of the launch directory. Systemic root of the CRF-IDLELIB-0016 family |
| A14 | CONSIDER | 5 test files | `unittest.main(exit=2)` at 5 sites vs `exit=False` at 42. The 42 **return 0 even when their tests fail** |

## KNOWN-FINDINGS REGRESSION (`check_known_findings`)

`present 8 · absent_in_qualname 2 · absent 5 · not_scannable 11` of 26. The 11 are agent-only shapes a
scanner cannot see — **not checked**, not clear. Agents separately re-confirmed 0001, 0002, 0017,
0020, 0021, 0022, 0023, 0024, 0025 and 0026 as still present.

## F4 · FIX · the `-n` backend is a second execution engine missing five cross-cutting protections

VERIFIED by reading both sides. `use_subprocess` (`pyshell.py:48`) selects between two interchangeable
execution backends, and every protection lives *inside* the RPC backend rather than in a shared driver.

`SystemExit`, the sharpest cell — the two sides are opposites:

```python
# RPC backend, run.py:593-598          -> CONTAINED
except SystemExit as e:
    if e.args: ... print(...)
    # Return to the interactive prompt.

# -n backend, pyshell.py:778-789       -> ESCAPES mainloop()
except SystemExit:
    if messagebox.askyesno("Exit?", ..., default="yes"):
        raise
```

A script calling `sys.exit()` under `idle -n` prompts with **default="yes"** and, on Enter, raises out
of `root.mainloop()` (`pyshell.py:1691`) — no controlled shutdown, so **unsaved editor buffers get no
save prompt.**

Other empty cells in the same matrix: Ctrl-C has no interrupt path at all under `-n` (the guard at
`pyshell.py:1212` requires `self.interp.rpcclt`); Restart is never bound (`pyshell.py:911`); recursion
headroom (`run.py:551`) is never installed; `__file__` is not set for `-r`/`-s` (`pyshell.py:664`).
Plus a hard bug: `runcode` calls `restart_subprocess()` unconditionally (`pyshell.py:765`), which
dereferences `self.rpcclt.close()` — `None` under `-n`.

`gh-112936` already fixed **one** cell of this matrix. The rest were never swept.

## FURTHER AGENT FINDINGS (pattern-consistency; 9 of 12 reproduced by execution)

| Sev | Site | Failure |
|---|---|---|
| FIX | `iomenu.py:284-299` | Saving a file whose coding cookie cannot encode its text writes **a BOM and keeps the cookie**. Reproduced: the file then fails to import, run, or reopen, and IDLE's own "Specify file encoding" recovery cannot fix it |
| FIX | `pyshell.py:257` | `breakpoints.lst` delimits with `=`, which is legal in a path. A file named `a=b.py` silently drops another file's breakpoints, and `eval('b.py=[3,5]')` raises an **uncaught SyntaxError in the open path** |
| FIX | `configdialog.py:2204` / `config.py:695` | Help sources `;`-joined on write, `split(';')` on read, then sorted by the option **string** — so Doc 10 sorts before Doc 2, and `load_helplist` renumbers in the corrupted order, making it permanent past ten entries |
| FIX | `hyperparser.py:137-140` | Bracket matching: the backward scan checks bracket *type*, the forward scan does not. Reproduced: `x = (a]` reports `(` matched with `]`. `pyparse.py:120` deliberately erases identity; only one side compensates |
| FIX | `config_key.py:227` / `config.py:536` | Advanced key bindings stored as a Tk event **sequence**, read back as a whitespace-separated **list** — a chord `<Control-x> <Control-s>` becomes two independent bindings, and the dialog re-joins on display so the corruption is invisible |
| CONSIDER | `format.py:340` | Untabify rewrites the **whole line**; its tabify mirror rewrites only the indent. A literal tab inside a string is expanded, silently changing program output, and the test never round-trips |
| CONSIDER | `undo.py:104` | `undo_block_start` guards the `0` sentinel, `undo_block_stop` does not — `AttributeError` on an int. Compounds A1 |
| CONSIDER | `undo.py:268,294` | `DeleteCommand.undo` reinserts text **without tags**; the `Insert` mirror round-trips them. In the Shell nothing re-tags, and `pyshell.recall` / `ShellSidebar` read exactly that tag |

## CROSS-AGENT CORROBORATION

Five findings were reached independently by two agents working from different evidence. Convergence
from different methods is the strongest signal this run produced.

| Finding | Found by |
|---|---|
| `hyperparser.py:298` missing `f`/`t` prefixes | complexity-simplifier (as a syntax-recognizer sibling hunt) + pattern-consistency-checker (as a fix-propagation diff) — **and verified by the orchestrator** |
| `autocomplete_w.py:362` operator precedence | complexity-simplifier (`guarded-twin-with-false-reasoning`) + pattern-consistency-checker (`one-concern-per-backend`, ATTRS vs FILES) — **verified** |
| `codecontext.py:22` missing `match`/`case` | complexity-simplifier + pattern-consistency-checker |
| `config.py:243` default-config `ValueError` swallowed | tech-debt-inventory (`conflict-resolved-silently-where-siblings-warn`) + documentation-auditor (docstring falsified by execution) |
| `undo_block_start/stop` unpaired | silent-failure-hunter (leaked block freezes `saved`) + pattern-consistency-checker (`undo_block_stop` crashes on the `0` sentinel) |

## DOCUMENTATION FINDINGS (documentation-auditor; several falsified by execution)

- **`configdialog.py` × 5** — `create_page_highlight/font/keys/windows/shed` all open *"Return frame of
  widgets…"*; **all five return `None`**, confirmed by calling them under a display. One systemic root
  from the 2017-21 page-factoring series; `create_page_extensions` is the corrected twin.
- **`squeezer.py`** — four defects from two 2019 commits: a documented `tabwidth` parameter that no
  longer exists (`TypeError` when passed), a rationale describing a fetch that was deleted, a comment
  citing `get_line_width()` which is now **the only occurrence of that name in CPython** — and it is
  the sole thing making the orphaned `window_width_delta` assignment look purposeful. Plus
  `base_test` for `base_text`.
- **`query.py:18`** — cites `editor.EditorWindow.load_module` (renamed to `open_module`). The
  *dangerous* variant: four lines below is `import importlib.abc`, whose `Loader.load_module` is a
  real unrelated API, so the stale reference resolves to the wrong thing with confidence.
- **`tkinter_testing_utils.py:24`** — the decorator's own usage example names
  `run_test_with_tk_mainloop`, which exists nowhere; the decorator is `run_in_tk_mainloop`. All 11
  real uses spell it correctly.
- **Process markers** — three documents prescribe three different coverage-exclude regex sets, and
  the two under `idle_test/` are strict subsets of the repo's own `.coveragerc`. `htest.py`'s version
  omits the `_htest`/`_utest` lines entirely, so following it makes all nine live guards count against
  coverage.
- **`README.txt`**, shown in-app via About IDLE → Readme, lists four files that do not exist —
  `tabbedpages.py` (deleted 2017), `windows.py` (renamed 2018), `NEWS.txt`/`NEWS2.txt` (renamed 2023).
  The `NEWS.txt` row is actively misleading: it is annotated *"displayed by About IDLE"* while the
  News button actually reads `News3.txt`.

## PROCESS INCIDENT · D-07 violated again, caught and restored

Two agents patch-tested in the **live** CPython checkout during this run.

- `Lib/idlelib/colorizer.py` — `git-history-analyzer` reverted the t-string prefix fix to prove a
  test could not fail, and **did restore it**. Verified: working SHA == HEAD SHA, line 50 intact.
- `Lib/idlelib/sidebar.py` — a still-running agent left `a, b = start_line, lineno  # MUTANT: drop
  up-drag normalisation` at line 193. **Not restored by the agent.** I restored it with
  `git checkout --`; verified SHA identity afterwards.

The tree is clean. Both remaining agents have been messaged to stop and to work on a
`git archive` copy under `/tmp`.

**Why this matters more here than in a solo review:** a dozen agents were reading these files
concurrently. A mutation left in `sidebar.py` does not just corrupt its author's experiment — it
makes every other agent's read of that file wrong, and one of them reports a confident, false
finding about code that was never in the tree. That is exactly the failure D-07 was written for, and
it recurred despite `docs/reproduction-convention.md` existing.

**Toolkit action:** the convention doc is not enough — agent prompts do not read it. The
`git archive` instruction belongs in the informed briefing itself, which every agent does read.

## F5 · THE SYSTEMIC ROOT UNDER F1 — `redirector.py:116` swallows every TclError

```python
except TclError:
    return ""
```

`WidgetRedirector.dispatch` intercepts **every** subcommand of every percolated Text — i.e. every
EditorWindow, PyShell and OutputWindow. Verified on a live widget:

```
plain Text        index('sel.first') -> TclError
redirected Text   index('sel.first') -> ''
```

So on the widgets idlelib actually uses, `text.index()` **never raises and never returns `None`.**
That makes `pyshell.py:1016-1017` doubly wrong:

```python
selfirst = text.index('sel.first linestart')
if selfirst is None:  # Should not be possible.
    return
```

The guard **can never fire** — the comment is right for the wrong reason — and `sellast[-1]` on `''`
raises `IndexError`. F1 is the visible symptom; this is the cause.

The swallow also produced **three incompatible guard idioms** in one file:
`editor.py:360` tests `''` (correct here, wrong on a plain Text); `editor.py:558` catches TclError
**and** tests the value (the twin — correct on both); `editor.py:1261` catches TclError only, and its
own comment promises `(None, None)` while it measurably returns `('', '')`. Five callers survive only
because they all happen to write `if first and last:`.

It also makes four search/replace entry points (`search.py:35,129`, `replace.py:28`, `grep.py:39`)
work only *because* of the swallow — narrow it and Ctrl-F breaks with no selection. Fix
`redirector.py` first or not at all.

## FURTHER FINDINGS (consistency-auditor; 6 of 10 reproduced)

| Sev | Site | Failure |
|---|---|---|
| FIX | `config.py:486` | `activeKeys[event]` where two siblings use `GetOption(default='')`. Reproduced `KeyError: '<<z-in>>'` — stock 3.14 ships ZzDummy **disabled**, and `GetExtnNameForEvent` iterates `active_only=0`. Crashes Configure IDLE → Keys for any third-party extension |
| FIX | `runscript.py:185,190` | `io.save(None)` return ignored; `iomenu.py:198` re-checks `get_saved()`. A failed save (read-only file, full disk) still returns the filename, and F5 **runs the old code from disk** under a RESTART banner |
| FIX | `pyshell.py:666` | `__file__` set only under `use_subprocess`. Measured: `idle -n -r probe.py` gives `__file__ == '.../idlelib/__main__.py'` — not absent, *silently IDLE's own path*. `runscript.py:149` sets it in both modes |
| FIX | `autocomplete_w.py:454-491` | Popup teardown with no guard on 4 `event_delete` + 6 `unbind` + 3 `destroy`; `calltip_w.hidetip` guards each and even names `ValueError ... raised by MultiCall`. On abort, `autocompletewindow` is never `None`, so `is_active()` stays True and the list is **stranded on screen** |
| CONSIDER | `parenmatch.py:53`, `autocomplete.py:54` | Code fallback defaults disagree with the shipped `.def` (`opener` vs `expression`; `0` vs `2000` ms). Every other extension in the family matches |
| CONSIDER | `stackviewer.py:12` | Module-global `sc, item, node` pin every frame of the last exception for the process lifetime; `browser.py:98` is the sibling that destroys cleanly. `pyshell.py:652` already says `# XXX Should GC the remote tree` |

**Dismissed after measurement, do not re-derive:** "classes that schedule `after()` without `close()`
leak callbacks onto destroyed widgets" — measured zero callbacks fired in both the CodeContext and
ParenMatch scenarios, because `Misc.destroy` deletes the Tcl command. The whole class is a non-issue.

## TOOLKIT ACTION TAKEN

The reproduction discipline is now **triage rule 7 in the informed briefing itself**, which every
agent reads — `docs/reproduction-convention.md` was not enough, because agent prompts do not read it.

## F6 · FIX · `format.py:57-59` — Format Paragraph silently deletes characters from every non-comment line

VERIFIED BY EXECUTION against the 3.14 build:

```
in : '# Explain the next line.\nresult = compute(a, b)'
out: '# Explain the next line. esult = compute(a, b)'     <- 'r' gone

in : '    # Indented note.\n    value = 1'
out: '    # Indented note. alue = 1'                      <- 'v' gone
```

`get_comment_header` is `re.match(r"^([ \t]*#*)", line)` — **anchored**, so on a multi-line selection
it answers for line 1 only. `reformat_comment:161` then strips that width off **every** line:
`"\n".join(line[lc:] for line in data.split("\n"))`. The result is written back via
`text.delete`/`text.insert`, so the user's source is corrupted with nothing raised.

**Guarded twin:** the no-selection branch. `find_paragraph:101-112` walks outward only while
`get_comment_header(line) == comment_header`, so every line it passes on is guaranteed to carry the
header. The selection branch never establishes that invariant.

## F7 · FIX · `config.py:48` — a literal `%` in any setting raises on Apply, after keybindings are removed

VERIFIED:

```
SetOption('50%')                  -> ValueError: invalid interpolation syntax in '50%' at position 2
SetOption('C:\tmp\%USERPROFILE%') -> ValueError: invalid interpolation syntax
SetOption('a%%b')  -> Get() == 'a%b'    (a literal % cannot be stored at all)
```

`IdleConfParser.__init__` passes `strict=False` but never `interpolation=None`, so `BasicInterpolation`
stays on. `ConfigDialog.apply()` (`configdialog.py:179-184`) runs `deactivate_current_config()` →
`RemoveKeybindings()` on every open window **first**, then `save_all_changed_extensions()` raises, so
`ApplyKeybindings()` never runs. Agent-measured keybinding log: `['remove']` only —
**every open editor and shell is left with no keyboard shortcuts until IDLE restarts**, and the
`ValueError` goes to an invisible stderr.

This is `cleanup-only-on-success-path` at its most damaging: the teardown half of a teardown/rebuild
pair commits, and an exception from an unrelated step skips the rebuild.

## MUTATION TESTING — invariants proven unconstrained

The test-investigation agent used mutation as an arbiter rather than a guess. Against the full
**623-test GUI suite** (headless is only 296 run / 81 skipped — a developer running the suite bare
exercises less than half of it):

| Mutation | Result |
|---|---|
| `searchengine.py:182` `end-1c` → `end` | **survives** |
| `searchengine.py:185` `col = len(chars)-1` → `0` | **survives** |
| `searchengine.py:161` forward-wrap restart line | dies (5 failures) |
| `undo.py:218,279` drop both `end-1c` clamps | **survives** |
| `sidebar.py:193,194,195,202` drag/click logic | **all survive** |
| `iomenu.py:263` never append trailing newline | dies (2 failures) |
| `mock_tk.mark_set` made functional | **survives** — no mock test constrains cursor placement |

The forward/backward asymmetry is the sharp one: `search_forward`'s wrap is covered, `search_backward`'s
is not — because `test_searchengine.py:279` does `cls.text.index = lambda index: '4.0'`, freezing every
index expression to a constant. Same file and same asymmetry as CRF-IDLELIB-0005.

**The higher-value variant of `test-cannot-fail`** is not "no assertion" but **"assertion against a
stub that cannot express the failure"** — `mock_idle.Editor.get_selection_indices` returns a selection
unconditionally, so the no-selection branch of all five production consumers is unreachable under it.
That is the shape that hid CRF-IDLELIB-0025.

## PROCESS INCIDENT — resolved, with the cause

The test-investigation agent ran 13 mutation experiments **in the live checkout**, restoring from
`/tmp` copies each time. Every restore succeeded, but each test run left a file mutated for 60-90
seconds — and a concurrent reader had no way to distinguish a transient mutant from a real edit. It
reported this unprompted.

**Final state verified by the orchestrator:** `0` modified files, no `MUTANT` markers anywhere,
all SHAs match HEAD.

## F8 · FIX · `Doc/library/idle.rst:733` — the documented `sys.argv[0]` contract for `-r` is wrong

VERIFIED. Doc: *"`sys.argv[0]` is set to `''`, `'-c'`, or `'-r'` respectively."*
Code (`pyshell.py:1578-1583`): `elif script: sys.argv = [script] + args` — **the script path, never `'-r'`.**

The `''` and `'-c'` thirds are correct; only `-r` is wrong. **`idle -h` gets it right** —
`usage_msg` (`pyshell.py:1509`) says *"passing "foo.py" in sys.argv[0]"*. So the Library Reference
contradicts the tool's own help output, and the help output is the correct one.

Silent: code written against the doc reads `sys.argv[0] == '-r'`, gets `'foo.py'`, takes the wrong
branch, and nothing raises. Wrong since 2015.

## F9 · FIX · `Doc/library/idle.rst:754` — the network diagnostic names a port IDLE never listens on

VERIFIED. The doc tells a user to run `tcpconnect -irv 127.0.0.1 6543` to diagnose a failed
subprocess connection. `PORT = 0` (`pyshell.py:51`) — IDLE binds an **ephemeral** port.

`6543` appears in exactly two places in the entire tree: `idle.rst:754` and its generated copy
`help.html:619`. **Zero occurrences in idlelib source.** It was written into the docs in 2021 and was
never true.

The recipe cannot distinguish the two cases it exists to distinguish: a user hitting the documented
failure gets a refusal on a port nothing listens on, and concludes the wrong thing either way.

## GENERATED-DOC CHAIN: verified in sync, which is what makes it the shape

`Doc/library/idle.rst` → sphinx → `copy_strip()` (`help.py:251`) → `Lib/idlelib/help.html`, shown
in-app. All **35/35** rst section headings are present in `help.html`, both written by the same
commit. **The generator is working correctly** — so every error above is faithfully reproduced into
the shipped HTML and *regeneration cannot fix any of it*. That is precisely
`generated-doc-propagates-a-source-error`.

Also: **"the General tab" at 5 rst sites** — that tab was split into Windows and Shell/Ed in 3.11
(GH-26621) and help sources moved to Extensions. The guarded twin is hand-maintained and correct:
`README.txt:204-205` already says `Windows tab` / `Shell/Ed tab`. And **"IDLE Help" → "IDLE Doc"**
was renamed in 3.12 (`mainmenu.py:115`) and propagated to **none** of six live user-facing sites,
including two runtime error messages and `idle -h`.

## IMPLEMENTED-BUT-UNDOCUMENTED (4) + one phantom

`print-command-posix`, `print-command-win`, `delete-exitfunc`, `[History] cyclic` — all parsed,
defaulted and consumed, absent from both `idle.rst` and the Settings dialog. `print-command-*` is the
sharpest: `idle.rst:104` documents Print Window with no hint the command is configurable, the Linux
default is `lpr`, and `config-main.def:48` tells the user to change settings *through the dialog* —
which for these four is impossible.

Inverse direction: **`[EditorWindow] encoding`** (`config-main.def:67`) has **no consumer anywhere**.
