# asyncio — Phase 5.2 yield run

`Lib/asyncio` @ CPython 3.14, toolkit v1.9.0. **35 files.**

Purpose: the only corpus that exercises the async shapes and the `ASYNC` ruff rules, which shipped
in Phase 1 **entirely unvalidated**.

## Results

| Tool | Result |
|---|---|
| `scan_python_pitfalls` | 97 findings (10 high, 87 medium) |
| `run_lint_rules --tier 1` | 14 findings |
| `measure_complexity` | 11 hotspots — 2 `active-risk`, 3 `settled`, 6 `quiet` |

Top scanner shapes: `bare-except-swallows-control-flow` (45), `exception-in-del-or-finalizer` (13),
`raise-without-from-in-except` (12), `falsy-check-for-none-default` (9).

**`asyncio-fire-and-forget-task` fires twice** — the async *shape* family validated on the async
corpus, which is what this run existed to do.

## The ASYNC rules: validated, and nearly missed

The first run reported **zero** ASYNC findings. That was not the corpus — it was this toolkit.

`--isolated` is on by default so a project's ruff config cannot silently change the rule selection.
But it also discards `requires-python`, and ruff then assumes its oldest supported version. With
`--target-version` derived from the project (or, absent a declaration, the running interpreter):

- **`ASYNC109` fires 4 times** (`base_events.py:595`, `tasks.py:405/440/490`) — async functions
  taking a `timeout` parameter where `asyncio.timeout` is the modern construct.
- **Four `F821` false positives vanished** — `ExceptionGroup` / `BaseExceptionGroup`, builtins since
  3.11 that ruff flagged as undefined under its assumed floor.

**Isolation should control the rule set, not the language level.** That distinction was worth one
run of the corpus it was designed to validate.

Independently confirmed the rules are live: three of them (`ASYNC220`, `ASYNC230`, `ASYNC251`) fire
on a synthetic blocking-call fixture, and all 12 selected codes report `Stable` in `rule_validation`.

## Remaining false positives

Six `F821` on `staggered.py` (`parent_task`, `unhandled_exceptions`, `exceptions`) are a **ruff
closure-scope limitation**: all three are bound at lines 67-72 of the enclosing function and read
inside the nested `task_done`. F821 stays in tier 1 — it catches real `NameError`s and tier 1 is
explicitly agent-triaged at 50-70% precision — but this FP class is now recorded.
