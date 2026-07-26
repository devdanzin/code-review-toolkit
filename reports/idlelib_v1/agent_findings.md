# idlelib — agent-driven review (benchmark v1)

Companion to [`report.md`](report.md), which covers the scanner-only pass. This records what the
**defect-finding agents** found on the same target, and what their findings taught the shape catalog.

| | |
|---|---|
| **Target** | `Lib/idlelib`, CPython 3.14 @ `6080c8660961940929901d56d4809bc7a91c9282` |
| **Agents** | `silent-failure-hunter`; a test-invariant investigation over `idle_test/` |
| **Method** | both seeded with the five calibrated non-bug classes from the scanner pass, so neither re-litigated settled ground |
| **Verification** | several findings reproduced against the built `./python`; the non-GUI suite passes (623 tests) — **every bug below is one the suite cannot see** |

## Headline

The agents found substantially more than the scanner, including a **reproduced data-loss bug**. More
importantly for the toolkit, their *systemic* observations produced four new shapes — and one of those
shapes then found a bug the agents had missed.

## The strongest findings

### `config.py:135-139` — a failed config save deletes the user's config file

```python
try:
    cfgFile = open(fname, 'w')
except OSError:
    os.unlink(fname)            # unconditional, on ANY OSError
    cfgFile = open(fname, 'w')  # unguarded retry
```

Written for one errno (file exists but is read-only → delete and recreate), catches all of them, and
the recovery is itself unguarded. Reproduced two ways: under fd exhaustion the `unlink` **succeeds**
and the retry fails, destroying the file; with a non-writable `~/.idlerc` the `unlink` raises
`PermissionError` uncaught.

Blast radius: `ConfigChanges.save_all` calls this **first and unconditionally**, so the user presses
**OK** in Settings and their theme, keyset and extension changes are all silently discarded — the only
evidence is a Tk traceback on stderr, invisible when IDLE is launched from a desktop icon.

*Guarded twin:* `iomenu.writefile` — `with open(...)` plus `except OSError` → `showerror`. idlelib's
own file-write idiom never destroys and always tells the user.

### `pyshell.py:485` — one accept-timeout wedges IDLE permanently

`self.restarting = True`, then an early `return None` on `TimeoutError` from `rpcclt.accept()`, with
the only reset on the success path. Afterwards **Run Module**, **Restart Shell**, the debugger restart
and the auto-restart all hit the guard and return instantly, doing nothing and showing no error. IDLE
looks alive but can never run code again.

### `replace.py:213` — a guard that tests the wrong variable

```python
m = prog.match(chars, col)
if not prog:            # `prog` was already proven non-None at :201
    return False
new = self._replace_expand(m, ...)   # m may be None
```

Reproduced: Regular expression on, Find `\Z`, Replace → `AttributeError: 'NoneType' object has no
attribute 'expand'`. `replace_all` and `do_find` both guard their match correctly; only `do_replace`
misspells it.

### `autocomplete.py:117/134` — `not mode` where `ATTRS == 0`

`ATTRS, FILES = 0, 1`, and the mode filter is `(not mode or mode == FILES)`. `not 0` is `True`, so the
ATTRS restriction never applies while the FILES side works. Typing `f("data.` pops a **directory
listing inside a string literal**.

### `searchengine.py:146-151` — forward search abandons the rest of a line

After rejecting a zero-width match it advances to the next line instead of scanning on; the backward
twin delegates to `search_reverse`, which scans the whole prefix. Replace All `\w*`→`<>` on
`aaa bbb` yields `<> bbb`. The test suite *documents* this: `test_searchengine.py:309-311` has the
assertion **commented out** with "seems buggy - tjr".

## What this taught the catalog — four new shapes

The agents' value was less the individual bugs than the **systemic** observations behind them.

### 1. `flag-not-reset-on-early-exit` *(now `confirmed`)*

The silent-failure agent's headline was that idlelib's dominant defect family is **not** broad catches
— it has only three `except Exception:` in non-test code — but **state restored on the success path
instead of in `finally`**. The existing `cleanup-only-on-success-path` covered the resource-release
variant; this adds the guard-flag variant, which fails worse (permanent, silent, affects every later
call).

**The shape then found a bug the agents missed:** `autocomplete_w.py:238`, where
`if not self.is_active(): return` skips the reset of `self.is_configuring`, permanently disabling the
`<Configure>` handler for that completion window.

idlelib contains **five correct twins** of the idiom (`debugger.py:153`, `colorizer.py:265`,
`run.py:588`, `pyshell.py:1174`, `sidebar.py:57`) — which is what makes the omissions defects by the
project's own standard rather than a style preference.

### 2. `guard-rechecks-call-receiver` *(now `confirmed`)*

From `replace.py:213`. Highly specific: **zero false positives across all 125 files**, one true
positive. The kind of typo that survives review precisely because it *looks* like a guard.

### 3. `falsy-check-for-none-default`

From the `not mode` finding. Generalized to the common form: `def f(x=None)` tested with `if not x:`,
which also fires for `0`, `''`, `[]`.

**Known limitation, recorded honestly:** this check does *not* catch the idlelib instance that
inspired it, because `mode` is reassigned in the body and the check skips reassigned parameters. The
int-enum-containing-zero variant (`ATTRS, FILES = 0, 1`) needs constant tracking the checker does not
do. Recorded in the shape's `references` rather than papered over.

### 4. `raise-without-from-in-except` *(promoted to `confirmed`)*

All six raise-inside-except sites in idlelib lack `from`. `rpc.py:361`
(`except OSError: raise EOFError`) is the costly one: it discards the errno, so there is no record of
whether IDLE restarted because the peer exited or because the kernel ran out of buffers.

## Scanner vs agents — they are complementary, not redundant

| | Scanner | Agents |
|---|---|---|
| Coverage | exhaustive across 125 files | sampled, depth-first |
| Reasoning | pattern + differential | blast radius, guarded twins, reproduction |
| Missed | the config data-loss bug; `not mode`; the search-abandons-line bug | `autocomplete_w.py:238` |
| Cost | seconds | ~9 and ~24 minutes |

The agents reason about *consequence* — that a stuck `restarting` flag disables four separate menu
commands is not something a pattern matcher can conclude. The scanner sweeps *exhaustively* — it found
the third `flag-not-reset` instance neither agent reported. The productive loop is: agents find the
family, the family becomes a shape, the shape sweeps for the rest.

## Test-quality observations (not source bugs)

The invariant agent surfaced several tests that cannot fail, which is worth its own scanner later:

- `test_autocomplete.py:241` — `assertTrue(all(filter(lambda x: x.startswith('_'), s)))`. `filter`
  yields only matching names, so `all()` is `True` whether `s` has none or all. Intent was
  `assertFalse(any(...))`.
- `test_calltip.py:349-368` — two tests never call `open_calltip`; they assert on an attribute the
  harness set.
- `test_undo.py:108-123` — never generates `<<undo>>`; the assertion holds regardless.
- `test_window.py:23` — replaces `window.registry` with a plain `set()`, so the assertion exercises
  `set.add`, never `WindowList.add`.
- Empty or non-executing test bodies in `test_editor.py:236`, `test_configdialog.py:55`,
  `test_config.py:761`.

**Proposed follow-up shape family — `test-cannot-fail`:** assertions on constants, `all(filter(...))`,
test bodies that never call the module under test, and `test_`-prefixed methods with `pass` bodies.
These are mechanically detectable and directly undermine every other invariant the suite claims.

## Scanner state after this run

79 findings / 36 high-confidence across 125 files, from **22 shapes** (4 `confirmed`).

| Shape | Findings |
|---|---|
| bare-except-swallows-control-flow | 28 |
| class-level-mutable-attribute | 18 |
| raise-without-from-in-except | 7 |
| mutable-default-argument | 6 |
| except-exception-too-broad | 4 |
| exception-in-del-or-finalizer | 4 |
| cleanup-only-on-success-path | 3 |
| flag-not-reset-on-early-exit | 3 |
| falsy-check-for-none-default | 2 |
| eq-without-hash / error-reported-below-warning / guard-rechecks-call-receiver / late-binding-closure-in-loop | 1 each |

## Caveats

- **Nothing here has been reported upstream.** These are CPython findings produced as a toolkit
  benchmark; filing would need independent confirmation against `main` and a tracker search first.
- The agents were seeded with the prior pass's calibration, so their precision is partly inherited
  from that run rather than intrinsic.
- `except-exception-too-broad` has low yield *here* (4 sites) despite being ~50% of the CPython-stdlib
  audit's findings — idlelib is unusually free of that pattern. One target does not calibrate a shape.
