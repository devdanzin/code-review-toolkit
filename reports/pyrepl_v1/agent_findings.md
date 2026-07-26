# `_pyrepl` — agent-driven review (benchmark v2)

| | |
|---|---|
| **Target** | `Lib/_pyrepl` (25 files, ~6,900 lines), CPython 3.14 @ `6080c8660961940929901d56d4809bc7a91c9282` |
| **Tests** | `Lib/test/test_pyrepl/` (10 files, ~5,400 lines) — baseline green: 244 run, 40 skipped |
| **Agents** | `silent-failure-hunter`; a test-invariant investigation; a twin-parity check; a novel-shape hunt |
| **Why this target** | Young (133 commits), actively developed, takes risks: hand-rolled terminfo parser, byte-level event queue, raw terminal mode, parallel Unix/Windows implementations |

**Every finding below survives the full test suite.**

## Why `_pyrepl` was the right benchmark

idlelib is mature and careful; `_pyrepl` is new and adventurous. The defect profiles differ sharply, and that difference is the point — it exercised parts of the catalog idlelib never touched, and exposed **two bugs in the toolkit itself** that idlelib could not (see *Toolkit bugs found* below).

## Findings

### Reproduced

| # | Location | Consequence |
|---|---|---|
| 1 | `unix_console.py:335,780` | Unix emits `Event(evt, None)` where the Windows twin emits `Event(evt, "")`. `getpending()` then does `e.data += e2.data` → **`TypeError`**. Trigger: resize the terminal during a bracketed paste. Windows carries a defensive `if e2:` it doesn't need; Unix, which needs one, has none. |
| 2 | `input.py:94` | `unicodedata.category(key) == "C"` can never be true — the API returns two-letter subclasses (`Cc`, `Cf`). The guard is dead, so **unbound control characters self-insert into the buffer** (`a\x00b`, `a\x1cb`), and the misclassification is then cached permanently into the root keymap. |
| 3 | `terminfo.py:140` | `terminal_name[0].lower()` — ncurses stores entries under the *literal* first byte. Every uppercase-initial `TERM` (`Eterm`, `Apple_Terminal`; 36 of 2,903 system entries) silently degrades to a **3-capability stub**: no `cub`, no `cup`, no `clear`. `fallback=True` hides it. |
| 4 | `terminfo.py:479-481` | `tparm`'s `%p1%{n}%+%d` branch indexes 1-based into a 0-based tuple and drops `%i`. With `TERM=vt100-s`, **every absolute cursor move writes the column into the row field**. The correct sibling is ten lines above. |
| 5 | `reader.py:675` | `isinstance(cmd, commands.digit_arg)` tests the *spec tuple*, not the command object — always false. Kill-ring and yank-pop semantics break across a numeric argument. The correct idiom is `completing_reader.py:257`. |
| 6 | `simple_interact.py:124` | `reader.history.pop()` is unconditional; the append it inverts (`historical_reader.py:415`) is guarded by `should_auto_add_history`. With `readline.set_auto_history(False)` — public API — typing `clear` **destroys the user's manually-managed history entry**, or raises `IndexError` on empty. |
| 7 | `base_eventqueue.py:104` | One undecodable byte wedges the event queue permanently: `except UnicodeError: return` treats "invalid" as "incomplete", the buffer grows forever, and the REPL goes **deaf to all further input**. The next Backspace trips `assert len(self.buf) == 1`. `ENCODING` is `sys.getdefaultencoding()` regardless of locale, so a latin-1 paste suffices. |
| 8 | `terminfo.py:401`, `:373` | A bounds check copied without its operand (see *shape* below), **plus** header counts unpacked as *signed* (`<Hhhhhh`) with only upper-bound checks — a negative count walks `offset` backwards, every check passes, and **no exception is raised at all**, so `fallback=True` never fires. |
| 9 | `test_keymap.py:33-40` | `for key in []` — the test builds 60 cases and runs **zero**. `git blame` → commit `73ab83b27f1`, *"Increase test coverage for keymap"*, which **replaced three passing assertions with this**. Coverage of the whole `\C-` path went to zero and stayed there ~2 years. Hides a live `IndexError` at `keymap.py:124`. |
| — | `commands.py:496` | Unterminated bracketed paste busy-spins at **100% CPU**; `start = time.time()` is captured and used only for the trace message. |
| — | `commands.py` + `unix_console.py` | Ctrl-Z → `fg` → exit **leaves the terminal wedged**: `prepare()` snapshots termios *and* modifies it, and is called twice across the SIGCONT boundary, so the saved "original" is the raw state. |

### Confirmed by reading

`reader.py:604` (`issubclass` arguments reversed vs the `commands.py:98` twin) · `commands.py:159` (`kill_line` passes `eol + 1`, defeating its own empty-range guard) · `unix_eventqueue.py:33` (emits key name `'enter'`, which **no keyspec can express** — keypad Enter beeps instead of accepting) · `windows_console.py:152,156` (`GetConsoleMode`/`SetConsoleMode` return values ignored while every other Win32 call in the file is checked) · `_threading_handler.py:38-51` (restore→print→prepare on the success path, failure swallowed by `except Exception: pass` in a 10 Hz loop).

### Test-quality findings

`test_unix_console.py:336` — `test_restore_in_thread` **cannot fail** on the regression it guards (gh-139391): `Thread.join()` never re-raises. Patch-tested by reintroducing the pre-fix behaviour; the test still reports `ok`. · `MagicMock(lambda _: (h, w))` sets `spec`, not `side_effect` — inert at 7 sites, with the correct form two lines away in the same file. · `test_unix_console.py:33` mocks `getpending` out entirely, so the function containing finding 1 is **never executed by any test**, while `:216`/`:236` inject the wrong sentinel by hand.

## Novel shapes proposed

Two were implemented this session (see below); the rest are recorded for follow-up.

| Shape | Status |
|---|---|
| `self-referential-accumulate` — `x += x` beside a sibling using a different source | **implemented, confirmed** |
| `duplicated-guard-wrong-operand` — a guard copied without updating its operand | **implemented, confirmed** |
| `vacuous-loop-over-empty-literal` — `for x in []` in a test; builds cases, runs none | **implemented** (folded into `test-cannot-fail`) |
| **A** — divergent sentinel across a parallel pair, consumed by a per-side-duplicated helper | proposed |
| **B** — predicate compared against a coarser value than the API returns (`category(k) == "C"`) | proposed |
| **C** — dead guard from a same-prefix variable collision (`cmd` the tuple vs `command` the object) | proposed |
| **D** — unguarded inverse of a guarded operation (guarded append, unconditional pop) | proposed |
| **E** — mock-constructor arity confusion producing an inert stub | proposed |
| **F** — coverage-claiming commit that *reduced* coverage (diff assertion counts, not lines) | proposed |
| save-state clobber by a duplicated acquire across a signal boundary | proposed |
| decode-retry buffer with no incomplete/invalid discrimination | proposed |
| incomplete-fix residue at a TODO the fix answered (git-automatable) | proposed |
| return-value-ignored on the *save* half of an FFI pair | proposed |

Shape **A** deserves emphasis: the guarded-twin relation is *inverted*. The side emitting the safe value also carries a defensive guard it never needs, while the side that needs one has none — so looking for "which side has the guard" points at the wrong file.

## Toolkit bugs this run exposed

Running on a package with heavy relative-import use found two real bugs in the toolkit, both invisible on idlelib:

1. **`analyze_imports`: `from .X import Y` resolved one package too high**, so **`fan_in` was zero for every file** in any project using relative imports. 0 of 25 `_pyrepl` files had a fan-in; after the fix, 22 do.
2. **`detect_cycles` fabricated edges** via a prefix fallback, resolving import-free modules to the parent `__init__`. `_pyrepl`: 15 phantom cycles → 1 real.

The first was covered by four existing tests that **asserted the wrong values**, with a comment recording the author talking themselves out of the right answer. Rewritten against ground truth obtained by importing a real package layout.

Also calibrated: `except-in-loop-without-exit` no longer fires on a loop whose handler reports loudly, and reserves `high` for a `while True:` whose entire body is the guarded operation (`_pyrepl`'s REPL loop tripped it twice).

## Scanner results

22 pitfall findings (7 high) across 25 files. Profile differs sharply from idlelib: `class-level-mutable-attribute` (10) and `except-exception-too-broad` (5) dominate; far fewer bare excepts. 87.2% annotation coverage. 18 debt markers, 13 of them `type: ignore`.

The two new shapes, run across **all 1,847 files of CPython's `Lib/`**, produce **3 findings — all real, all in `_pyrepl`**. These defect shapes are essentially absent from mature stdlib code.

## Known toolkit gap (not yet fixed)

`correlate_tests` reports 0% coverage for `_pyrepl` because CPython's tests live in `Lib/test/test_pyrepl/`, outside the scanned tree. The source↔test correlation assumes tests live inside the package. The invariant agent hit the same wall — its orientation script found 0 test files and it worked from the source directly.

## Caveats

- **Nothing here has been reported upstream.** Filing needs re-verification against current `main` plus a tracker search.
- Findings were produced while calibrating a review toolkit, not as a bug-reporting campaign.
- The agents were seeded with prior calibration, so their precision is partly inherited.

## Additional findings — parity agent and novel-shape agent

Both landed after the sections above. Highlights not already listed:

| Location | Consequence | Status |
|---|---|---|
| `readline.py:443` vs `:460` | History read decodes with `errors='replace'`, write is strict UTF-8. A latin-1 `~/.python_history` is **destroyed unrecoverably on first exit** — `b"caf\xe9"` → `b"caf\xef\xbf\xbd"`. `Modules/readline.c` uses `surrogateescape` on **both** sides and round-trips correctly. `site.register_readline` writes at exit, so one launch suffices. | reproduced |
| `commands.py:225-229` | **Ctrl-C persists the abandoned line to `~/.python_history`.** `ctrl_c`/`interrupt` call `reader.finish()` on the *abort* path, but `HistoricalReader.finish()` implements *line accepted* and appends. GNU readline discards on SIGINT. Verified: an abandoned `print(SECRET_TOKEN)` reaches disk. | reproduced |
| `unix_console.py:471` | `COLUMNS=0` → `ZeroDivisionError` at `reader.py:347`, inside `readline()`, so the REPL loop **retries forever spewing tracebacks** — unusable, never exits. `LINES=0` → `IndexError` the same way. The ioctl branch guards `if not height`; the env branch, which takes precedence and is user-controlled, validates nothing. | reproduced |
| `terminfo.py:373` | Five header counts unpacked **signed** (`<Hhhhhh`) with only upper-bound checks. A negative `name_size` drives `offset` negative; Python's negative slicing re-anchors instead of raising, so a 100-byte crafted file parses with **no error** and yields attacker-chosen `bel`/`clear` byte strings that `UnixConsole` writes straight to the terminal. ncurses range-checks all six fields and refuses `$TERMINFO` under setuid; this reimplementation does neither. | reproduced |
| `reader.py:241-246` | `RefreshCache.valid()` checks only `dimensions`, though the code's own comment names paste-mode as an invalidator. Entering paste mode mid-block yields **mixed prompts** (`>>>` / `...` / `(paste)`) on one screen. Three sibling mutators remember to set `invalidated`; `paste_mode` does not. | reproduced |
| `readline.py:592-617` | `sys.modules['readline']` is **never installed** — `_setup` replaces only `builtins.input`. The documented `rlcompleter` recipe is a no-op under the default 3.14 REPL and works under `PYTHON_BASIC_REPL=1`. | POLICY |

### Further shapes proposed

- **S8 — asymmetric encode/decode pair.** Three sub-shapes, all present: lenient decode + strict encode; escape at one granularity, unescape globally; a format marker the reader understands and the writer never emits. *Hunt:* for every `open(p,"r")`/`open(p,"w")` on the same path, diff `encoding=`/`errors=`, then property-test `unescape(escape(x)) == x` over a corpus containing the escape characters.
- **S9 — one lifecycle hook, two meanings.** A hook called on both the success and abort paths, where the subclass override implements only success semantics. *Hunt:* enumerate every call site of each overridden `finish`/`close`/`commit`/`cleanup`; flag any on an error/cancel path.
- **S10 — wrapper mutates the wrapped object's collection without its bookkeeping.** `readline.py` does `del history[:]` / `history.append(...)` directly while `historical_reader` maintains `historyi` and `transient_history` alongside.
- **Signed length from an untrusted header.** In C this is a classic signed-overflow read; in Python it is *harder* to detect, because negative bounds produce plausible data instead of an exception.
- **Validation in one branch of a multi-source value.** The unvalidated branch is usually the *untrusted* one (env/config), because the trusted one (syscall) is the failure mode the author actually hit.

### Refuted by the agents (recorded so they are not re-hunted)

`__write_changed_line` char-vs-column overrun (short-circuits before the index is taken) · `prefix()` infinite loop on an empty word list (caller guards `len > 1`) · `setpos_from_xy` unbounded `j` (callers clamp) · `_STRING_NAMES` ordering and the 32-bit number path (differential against `curses.tigetstr`: 183 capabilities, 0 mismatches) · 1-based/0-based history indexing (byte-for-byte identical to `Modules/readline.c`, including its own inconsistencies) · all 40 test skips (every one legitimately platform-gated).
