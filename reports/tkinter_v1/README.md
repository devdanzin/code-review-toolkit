# tkinter — Phase 5.1 yield run

`Lib/tkinter` @ CPython 3.14, toolkit v1.9.0. **13 files.**

Purpose: measure YIELD on a corpus the shapes were not derived from. idlelib
cannot serve that role (D-02) because every shape since v1 was calibrated against it.

## Results

| Tool | Result |
|---|---|
| `scan_python_pitfalls` | 62 findings (10 high, 52 medium) |
| `run_lint_rules --tier 1` | 52 findings, **49 overlapping a catalogued shape** |
| `measure_complexity` | 0 hotspots at score >= 5.0 |

**The corpus is dominated by one idiom.** 46 of 62 scanner findings and 46 of 52 tier-1 lint findings
are the same thing: `def method(self, cnf={}, **kw)`, tkinter's option-dict convention, repeated
across the widget API. Scanner and ruff `B006` agree exactly on all 46 — which is the clearest
validation the merge design has had, and also means this corpus contributes **one** finding, not 46.

**Verdict on the idiom: ACCEPTABLE.** `_cnfmerge` builds a fresh dict rather than mutating its input,
and `_options(cnf, kw)` routes through it, so the shared default is read-only on the ordinary path.
The scanner correctly rates 43 of 46 `medium` with "no mutation seen; may be read-only".

The three `high` survivors (`__init__` at 2793, 2834, 3354) do reach `del cnf[k]`. They are true
positives for the mechanism and harmless in practice: the deletion is driven by
`[(k, v) for k, v in cnf.items() if isinstance(k, type)]`, which is empty for the empty default, so
the shared dict is never actually reached. A caller who passes their own dict *does* have it mutated
— that is `wrapper-mutates-foreign-collection`, a different catalogued shape.

## Toolkit defects this corpus found

- **`_returns` matched any occurrence of the name inside a returned expression.**
  `return self._grid_configure('columnconfigure', index, cnf, kw)` was read as returning `cnf`.
  Seven tkinter methods were reported at HIGH confidence with "the shared object is returned to
  callers", a claim the code does not support. Fixed and tested; high-confidence
  mutable-default findings on tkinter went **7 → 3**, and idlelib was unchanged at 101.

## What tkinter did NOT stress

The plan expected tkinter to stress reachability tiering and the dead-code false-positive classes
hardest. It did not, because this run did not include `find_dead_symbols` — that pairing needs
Phase 4 item 4.3 (reachability tiering), which is not built. Recorded rather than claimed.
