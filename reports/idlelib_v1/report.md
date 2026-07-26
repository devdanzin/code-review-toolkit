# idlelib — validation run v1

The toolkit's **first validation run**. Scope was deliberately small: exercise
`python-pitfall-scanner` against a real, mature, heavily-reviewed codebase and see what the raw
output actually looks like when triaged honestly.

| | |
|---|---|
| **Target** | `Lib/idlelib` from the CPython 3.14 branch |
| **Commit** | `6080c8660961940929901d56d4809bc7a91c9282` (2026-03-11) |
| **Files** | 125 Python files |
| **Agent / script** | `python-pitfall-scanner` / `scan_python_pitfalls.py` |
| **Raw output** | [`scan_python_pitfalls.json`](scan_python_pitfalls.json) |

> The target is an active local build tree, so it was **not** `git pull`ed — pulling could invalidate
> the user's builds. The commit above is what was scanned.

## Headline

Triaging the first run **found more about the scanner than about idlelib**, which is exactly what a
calibration run is for. Three false-positive classes were identified, fixed in the scanner, and
recorded in the taxonomy; high-confidence findings fell from **51 → 28** with no loss of true
positives.

| Stage | Findings | High confidence |
|---|---|---|
| Initial run | 62 | 51 |
| After fixing value-rewrite-during-iteration | 58 | 47 |
| After fixing declarative-class-config | 58 | 33 |
| After fixing earlier-clause-re-raise | 58 | 28 |

idlelib itself came out **well**: one genuinely over-broad exception handler, and otherwise
deliberate idioms — appropriate for a 25-year-old GUI codebase that has been reviewed many times.

## Calibration findings (the real output of this run)

### 1. Value rewrite during iteration is safe — 4 false positives

All four `mutation-during-iteration` hits were the same shape:

```python
# config.py:343, 549, 567, 674
for element in theme:
    theme[element] = cfgParser.Get(themeName, element, default=theme[element])
```

Assigning to a key **already present** does not change the container's size, and CPython raises only
on a size change. The scanner treated any subscript assignment as a mutation.

**Fixed:** `_resizes_during_iteration()` now distinguishes size-changing operations (`del`,
`append`/`remove`/`pop`/`update`, assignment to a *different* key) from in-place value rewrites where
the subscript is the loop variable. → taxonomy class 16.

### 2. Declarative class configuration — 14 false positives

```python
class EditorWindow:
    menu_specs = [("file", "_File"), ("edit", "_Edit"), ...]   # never mutated
class PyShell(OutputWindow):
    menu_specs = [...]                                          # overridden, not shared
```

Read-only declarative config overridden by subclasses — the `Meta`/widget-spec pattern. The scanner
flagged every class-level mutable literal at `high`.

**Fixed:** `_attribute_mutated_anywhere()` checks the whole module for an actual mutation. Mutated →
`high`; unmutated lowercase → `medium` (could be mutated elsewhere); unmutated ALL_CAPS → `low`.
High-confidence instances dropped 18 → 4. → taxonomy class 18.

### 3. Control-flow exception re-raised by an earlier clause — partial false positive

```python
# rpc.py:109
try:
    raise
except SystemExit:
    raise          # <- obligation discharged for SystemExit
except:
    ...            # still swallows KeyboardInterrupt
```

**Fixed:** `_guarded_by_earlier_reraise()` subtracts what earlier clauses re-raise. If every
control-flow exception is covered, the finding is dropped; otherwise it is downgraded and names
precisely which ones remain swallowed. → taxonomy class 20.

### 4. Two idioms recorded without a code change

- **Mutable default as a counter cell** (`multicall.py:426`): `def bindseq(seq, n=[0]): ... n[0] += 1`
  — a pre-`nonlocal` mutable cell. The persistence *is* the intent. → taxonomy class 17.
- **Documented boundary around user code** (`calltip.py:141`): `except BaseException:` around
  `eval()`, with a comment explaining that an uncaught exception would close the IDE. POLICY for the
  maintainer, not a defect. → taxonomy class 19.

## Findings in idlelib

### Confirmed — 1

**`autocomplete.py:175` — over-broad exception handler** *(FIX, low impact)*

```python
try:
    rpcclt = self.editwin.flist.pyshell.interp.rpcclt
except:
    rpcclt = None
```

A bare `except:` guarding an attribute chain. The intended narrow form is `except AttributeError:`.
As written it also swallows `KeyboardInterrupt` and `SystemExit`. Impact is low — an attribute lookup
is unlikely to be interrupted — but the narrow form is strictly better and costs one word.

*Guarded twin:* `calltip.py` uses `except BaseException` **with** a documented rationale; the many
`except AttributeError:` handlers elsewhere in idlelib are the idiom this site should match.

This instance promotes `bare-except-swallows-control-flow` from `validation: documented` to
**`confirmed`** — the first shape in the catalog to make that transition.

### Remaining, untriaged — 57

Not individually verified; this was a scoped run. The residue is dominated by
`bare-except-swallows-control-flow` (28), which in a GUI/RPC codebase mixes genuine over-breadth with
deliberate containment boundaries. A full pass should triage these against taxonomy classes 19 and
20 before reporting anything upstream.

## Assessment of the scanner

**Working well:**
- Zero crashes across 125 files, including on `idle_test` fixtures.
- The `by_directory` breakdown correctly showed a single flat distribution (no generated-content
  cluster), unlike earlier runs on toolkit repos.
- Every false-positive class found was *diagnosable from the finding text alone* — the `detail` field
  pointed at the right question each time.

**Needed fixing (all now fixed):** the three classes above. All were over-broad *differentials*,
not bad shapes — the shape catalog held up; the encoding of "when not to flag" did not.

**Honest caveat:** one confirmed true positive out of 62 raw findings is a low yield. That is partly
the target — idlelib is old, stable, and much-reviewed — and partly that the highest-yield shapes
(the asyncio family, `return`-in-`finally`, `except`-ordering) have **no instances at all** here,
since idlelib predates asyncio and is written in a careful style. A younger async-heavy codebase is
the right next validation target.

## Catalog changes from this run

- `python_bug_shapes.json`: `bare-except-swallows-control-flow` → `validation: confirmed`, with the
  instance cited.
- `python_non_bugs.md`: added classes **16–20** under *Learned from validation runs*.
- `scan_python_pitfalls.py`: three differential fixes, each with a regression test naming idlelib as
  the source.
