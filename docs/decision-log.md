# Decision log

Append-only record of decisions, plan changes, corrections and non-obvious findings for
`code-review-toolkit`. **Written for a reader with no memory of the session that produced it.**

## Why this file exists

Conversation context is compacted. Anything that lives only in a chat transcript is lost. A decision
whose *reasoning* is lost gets re-litigated, and a correction whose reasoning is lost gets re-made as a
mistake. This file is the durable half.

## Rules

1. **Append, never rewrite.** Superseding an entry means adding a new one that says so and links back.
2. **Record the reasoning, not just the outcome.** "We chose mypy" is worthless in three months;
   "we chose mypy because cross-tool consensus was measured to be dominated by shared blind spots"
   survives.
3. **Record corrections and refutations too** — they are the highest-value entries, because the
   plausible-but-wrong idea will otherwise come back.
4. **Numbers over adjectives.** Cite what was measured, on what corpus, at what commit.
5. One entry per decision. Date it. Give it a stable `D-nn` id so other docs can cite it.

## Where things live

| Artifact | Path | Purpose |
|---|---|---|
| The plan | `docs/improvement-plan.md` | What we intend to do and why, phased |
| This log | `docs/decision-log.md` | What we decided, changed, or got wrong |
| Benchmark reports | `reports/<target>_v<n>/` | Raw scanner JSON + the agent write-up per run |
| Findings | `github.com/devdanzin/code-review-findings` (private) | Per-project confirmed findings, wire-compatible with `informed-explore` |
| Shape catalog | `plugins/code-review-toolkit/data/python_bug_shapes.json` | Reusable bug shapes — the toolkit's memory |
| FP taxonomy | `plugins/code-review-toolkit/data/python_non_bugs.md` | What looks like a finding and is not |
| Known gaps | `CLAUDE.md` § *Known gaps* | Honest list of what does not work yet |

---

## D-01 · 2026-07-26 · The calibration loop is broken in the write-back direction

**Measured:** 43 of 64 shape names used across the findings repo are absent from
`python_bug_shapes.json`; only 40 of 111 findings map to a catalogued shape (36%). coverage.py
contributed 60 findings and 7 catalogued shapes.

**Cause:** shape names were invented ad-hoc while writing `findings.json` and never fed back. Their
`hunt` directives, differentials and guarded twins exist only as prose in three JSON files.

**Also:** `informed-explore.md` documents a `--catalog` flag `build_informed_briefing.py` does not
implement, so the read direction is half-wired too.

**Decision:** this becomes Phase 0 and blocks the rest of the plan. Shipping new shapes into a 36%-
connected catalog compounds the drift.

**Guard against recurrence:** every `findings.json` `shape` value must exist in the catalog. Enforce
mechanically (a test, or `gen_known_findings.py` failing on an unknown shape) rather than by intent.

---

## D-02 · 2026-07-26 · idlelib measures FP regression, not yield

**Measured:** current toolkit vs `reports/idlelib_v1` — 100 → 101 findings; `unchanged 100 | gone 0 |
added 1`. Fifteen shapes added since v1 produced one new idlelib finding.

**Decision:** two separate metrics. idlelib is the **fixed control** for false-positive regression,
crashes and runtime. **Yield** is measured only on targets the shapes were not derived from —
tkinter and asyncio.

**Consequence:** never score a wave on "new findings on idlelib". Every wave would look like a failure.

---

## D-03 · 2026-07-26 · Typing: one checker, its own config, one extra flag

**Measured** across idlelib / `_pyrepl` / coverage.py: mypy 61/0/0, pyright 1463/50/60, ty 1266/51/90,
pyrefly 53/25/18.

**Decision:** mypy, with the project's own config discovered and passed via `--config-file`, never
overridden. Plus `--disallow-any-unimported` as a labelled second pass.

**Why not cross-reference checkers:** consensus was measured to be *anti-correlated with truth*. All 10
consensus sites in `_pyrepl` are the `if False:` TYPE_CHECKING idiom that only mypy special-cases;
7 of 10 in coverage.py are `hasattr()`-guarded assignment that only mypy narrows. Agreement among the
others means "mypy is right and they are misconfigured".

**Why the extra flag:** coverage.py is 0 errors under its own config; `--disallow-any-unimported`
surfaces exactly 3, all from `from coverage.plugins import FileReporter` — a module that does not
exist. The same flag adds 0 on `_pyrepl`, so it is a real finding, not a flag that fires everywhere.

**Landmines to encode:** `pyrefly` reports `0 errors` exit 0 when its config discovery excludes the
tree (idlelib: 0, or 53 from a staging root) — any integration must assert `files_checked > 0`. mypy
cannot analyze a stdlib-shadowing tree without symlink staging plus `--no-namespace-packages`.

---

## D-04 · 2026-07-26 · Stale `type: ignore` cannot be measured by grep

**Measured:** coverage.py has 47 `# type: ignore` comments, sets `warn_unused_ignores = true`, and
mypy exits clean — therefore **zero** are stale, whatever their commit age. `collect_debt` reported
"36 stale, 12 ancient" by counting the string and reading blame dates.

**Decision:** ignore-staleness is reported **only** from mypy's own `unused-ignore` diagnostics.
Marker age is not evidence. Where the count is 0, say so explicitly to pre-empt the grep-based alarm.

---

## D-05 · 2026-07-26 · Complexity is a poor ranker and a good lens

**Measured** on coverage.py: churn and complexity are *inverted*. `pytracer._trace` scores 10.0 with
2 fix-commits in two years; `sysmon.py` scores 7.5 with 11. High complexity marked **settled** code.

**Decision:** keep the complexity agent and scanner — on this run they found a live latent defect
(`sysmon.py:407-410`, a `.get()` dereferenced with no guard while its sibling at `:422-426` guards the
identical fetch) and correctly advised *against* refactoring `PyTracer._trace`, citing the code's own
evidence that per-event cost is binding.

**But:** never rank on complexity alone. Cross with fix-density. Per D-08, `measure_complexity` will
ingest history directly rather than leaving the crossing to an agent's memory.

**Also calibrate:** reported `nesting_depth` counts `try`/`else`/`finally` arms and `if 0:` debug
blocks as levels, overstating reader-facing depth.

---

## D-06 · 2026-07-26 · Prior-art search before any novelty claim

**Evidence:** the prior-art pass refuted one finding outright (a claim that a released `CHANGES.rst`
entry contradicted the code — 7.11.3 explicitly documents the restore; a changelog is a historical
record, not a live claim) and redirected three others from "file new" to "comment on existing",
including #1689, open since 2023, where our diagnosis is sharper than the reporter's.

**Decision:** prior-art becomes a standard phase, not opt-in. Vendor the `gh api search/issues` recipe
from `rust-ext-review-toolkit/docs/searching-trackers.md` — `gh search issues` has two footguns that
silently return empty (`--state all` errors; quoted multi-word terms are exact-adjacent phrases).

---

## D-07 · 2026-07-26 · Patch-test on a copy, never the live checkout

**Incident:** two patch-tests were left in the user's `coveragepy` checkout during the benchmark. One
agent claimed a byte-for-byte restore that had not happened. Three separate agents independently
flagged the contamination, and one noted that reading `collector.py` cold during that window yields a
**confident, wrong** finding — only the git history distinguishes a planted revert from the four
genuine bugs in that file.

**Decision:** all patch-testing happens on `git archive HEAD | tar -x -C <scratch>` or a
`git worktree`. A repro must also prove it exercised the tree it thinks it did (editable installs,
stale `__pycache__`, `sys.path` order). Verify the target tree yourself before reporting — do not
accept an agent's claim of restoration.

---

## D-08 · 2026-07-26 · Answers to the plan's open questions

Decided by the maintainer:

1. **`code-review-findings` is now a private GitHub repo** — `github.com/devdanzin/code-review-findings`,
   default branch `main` to match the family. One artifact (`coveragepy/repros/f4/debug.out`) was
   removed before the first push because it embedded local venv and CPython paths; a `.gitignore` now
   excludes captured tool output.
2. **`measure_complexity` will ingest git history directly** and emit a fix-density-crossed ranking,
   rather than leaving the crossing to an agent. Promotes plan item 4.6 from a question to a build item.
3. **`migrate` is out of scope.** Removed from the plan entirely, not deferred.
4. **A `tools/` directory is wanted.** Home for `validate_precision.py`, `sample_scan.py`-style
   helpers, and the confidence-tier calibration harness (plan item 6.3).

---

## D-09 · 2026-07-26 · Everything important goes in a file

**Requirement from the maintainer:** every step, fix, change of plan, and anything else important is
recorded in a file so it survives compaction.

**Decision:** this log is the mechanism. Working rules:

- A **decision** or a **correction** → an entry here, with a `D-nn` id.
- A **plan change** → edit `docs/improvement-plan.md` *and* log the change here with the reason.
- A **benchmark run** → `reports/<target>_v<n>/` with the raw JSON and a write-up. Never leave results
  only in a transcript.
- A **confirmed finding** → the findings repo, with `status` and `prior_art`.
- A **toolkit gap we are not fixing yet** → `CLAUDE.md` § *Known gaps*, so it stays visible.
- Prefer committing a partial artifact over holding it in context. A committed draft survives
  compaction; a perfect unwritten one does not.

---

## D-10 · 2026-07-26 · ruff pinning policy — the default set moved 59 → 413 three days ago

**Verified independently** (not just reported): `B006` on a mutable-default fixture, `--isolated`, no
`--select`:

```
ruff 0.15.10: 0 findings -> []
ruff 0.16.0:  1 findings -> ['B006']
```

**Facts, from the changelog and measurement:**

- ruff **0.16.0** (2026-07-23) took the default rule set from **59 to 413**, listed under
  `### Breaking changes`. It shipped preview-gated in 0.15.2 (412) and was promoted to stable default.
- It is **not a superset** — 18 rules were *dropped* from the default (`E401 E402 E701 E702 E703 E711
  E712 E713 E714 E721 E731 E741 E742 E743 F403 F405 F406 F722`). Only `E722` and `E902` survive from
  the `E` family.
- **27 of the 59 codes in our tiered selection are NOT in the 0.16.0 default** — including every
  security rule (`S101 S301 S302 S307 S608`), every complexity rule (`C901 PLR0912 PLR0915`), plus
  `B904`, `B905`, `PGH003`, `PLR2004`, `PLC0415`. Exactly the rules a review tool wants.
- **Nothing in our list was renamed or removed.** The failure mode we feared did not fire.
- **Correction to the earlier design pass:** `PLW1641` was reported as preview-gated. It is
  **Stable since 0.12.0** and fires without `--preview`. Only 4 of our codes are preview-gated:
  `B909`, `PLE1141`, `RUF027`, `RUF069`.

**Decision — pin both version and rule list.**

1. Pin `ruff==0.16.0`; record `ruff --version` in every envelope. A ruff bump is a **calibration
   event** requiring a fixture-corpus re-run, not a routine dependency update.
2. Always pass an explicit `--select`. **Never `--extend-select`** — it composes with a default that
   just changed 7×.
3. Always `--output-format json`, read `code`. Concise output changed shape between versions *and*
   between preview modes, and **0.16.0 preview omits the rule code entirely**. JSON also gained a
   `name` field; note `filename`/`location` "may now be null".
4. **Capture stderr.** Two staleness classes are warning-only and appear nowhere else:
   `'PGH001' has been remapped to 'S307'` and
   `Selection 'B909' has no effect because preview is not enabled`.
5. **Do not run `--preview` by default.** It is not additive — it mutates already-stable rules
   (`UP019` fires only under preview on 0.15.10, stabilised in 0.16.0), carries no deprecation policy,
   and breaks reproducibility. If `RUF069`/`B909` are wanted, run a **separate preview pass** with only
   those codes and label the findings preview-derived.

**The validation trap, verified:**

```
total rules in `ruff rule --all`: 968
  RUF076   present  status=Removed   <- naive membership test PASSES
  UP038    present  status=Removed   <- naive membership test PASSES
  ANN101   present  status=Removed   <- naive membership test PASSES
```

**Removed rules still appear in `ruff rule --all`.** A "is this code known?" membership check passes
for a rule that was deleted. Validation must inspect the `status` field:
`{"Removed": {"since": …}}` / `{"Preview": {"since": …}}` / `{"Stable": {"since": …}}`.

Emit the result as `rule_validation` in the envelope — `{unknown, removed, preview_gated, ok}` — so
every staleness class becomes a visible machine-readable fact rather than a missing finding. One
subprocess call per run. A prototype exists at `scratchpad/validate_rules.py`.

**Unresolved:** the 0.16.0 changelog claims `BLE001` is now suppressed when the exception is logged via
`logging` methods other than `critical`/`error`/`exception`; this could not be reproduced
(`logging.info(e)` still fires). Do not rely on `BLE001` suppression semantics without a local fixture.

---

## D-11 · 2026-07-26 · Session boundary — state at handoff, and how to resume

Written before a context compaction so Phase 0 can begin cold.

### State

| | |
|---|---|
| Toolkit | `main` @ `38b2d2f`, pushed. **v1.5.0** — 40 shapes (21 confirmed), 35 FP classes, 570 tests passing |
| Findings | `github.com/devdanzin/code-review-findings` (**private**) @ `8fc8cf8`, pushed. 3 projects, 111 findings |
| Benchmarks | `reports/idlelib_v1`, `idlelib_v2`, `pyrepl_v1`, `coveragepy_v1` |
| Targets | coveragepy @ `d37859cd` **clean**; CPython `~/projects/3.14` @ `6080c866096` unmodified |
| Venv | `~/venvs/cext-review-toolkit` (Python 3.14.3+ debug). Has ruff 0.15.10, mypy, pyright, ty, pyrefly. **coverage is an editable install of `~/projects/coveragepy`**, not PyPI 7.13.5 — restore with `pip install --force-reinstall coverage==7.13.5` if unwanted |
| ruff 0.16.0 | installed at `<scratch>/ruff016venv/bin/ruff` — scratch is session-local and **will not survive**; reinstall with `pip install ruff==0.16.0` |

### Start here

**Phase 0 of `docs/improvement-plan.md`. It blocks everything else.** Read that file and this log first
— between them they carry the reasoning, and the numbers are already measured so nothing needs re-deriving.

The first task is item **0.1**: reconcile the 43 stranded shapes. Reproduce the gap with:

```bash
cd ~/projects/code-review-findings && python - <<'PY'
import json, csv
from pathlib import Path
cat = json.loads(Path("../code-review-toolkit/plugins/code-review-toolkit/data/python_bug_shapes.json").read_text())
known = {s["id"] for s in cat["shapes"]}
used = {}
for tsv in Path(".").glob("*/catalog/known_findings.tsv"):
    for row in csv.reader(tsv.read_text().splitlines(), delimiter="\t"):
        if row and not row[0].startswith("#"):
            used.setdefault(row[2], []).append(tsv.parent.parent.name)
print(f"catalog={len(known)} used={len(used)} stranded={len({s for s in used if s not in known})}")
print(f"covered={sum(len(v) for s,v in used.items() if s in known)}/{sum(len(v) for v in used.values())}")
PY
```

Expected today: `catalog=40 used=64 stranded=43` and `covered=40/111`. **That ratio is Phase 0's
success metric** — not new findings.

Each stranded shape already has a title, location, consequence, guarded twin and fix in the relevant
`project-local/findings.json`. What it needs is the catalog's `pattern` / `hunt` / `expected` /
`caught_as` / `differential` fields plus a call: **implement as a check, or mark `agent-only`**.

### Traps that cost real time this session

- **Never patch-test in a live checkout** (D-07) — `git archive HEAD | tar -x -C <scratch>`. Verify the
  target tree yourself; an agent claimed a restore that had not happened.
- **`gh search issues` silently returns empty** — use `gh api search/issues` (D-06).
- **A membership test against `ruff rule --all` passes for a removed rule** — read `status` (D-10).
- **Grep cannot measure stale `type: ignore`** (D-04).
- **Bump the plugin version whenever an agent is added**, or it stays invisible to the registry (item 0.6).
- `scan_python_pitfalls.py` has had **two quadratic walks** fixed; if a full-`Lib/` run exceeds ~5 min,
  suspect a third.

### Deliberately not doing

`migrate` (dropped), `reproduce`/OOM sweep, `recursion-guard-auditor`, `parity-checker` as an agent,
`data/playbooks/`, campaign slice manifests — reasons in plan §0.5. Upstream reporting of the 111
existing findings is out of scope by decision.

---

## D-12 · 2026-07-27 · Phase 0 items 0.1, 0.3 and 0.4 — the write-back direction is repaired

**Metric moved 40/111 (36%) → 111/111.** Catalog 40 → 89 shapes, schema 1 → 2, zero stranded.
Reproduce with the command in D-11; it now prints `catalog=89 used=71 stranded=0` / `covered=111/111`.

### What 0.1 actually consisted of

49 new catalog entries. Each stranded shape had a title, location, consequence, guarded twin and fix
in `findings.json`; what it needed was the reusable half — `pattern`, `hunt`, `expected`,
`caught_as`, `differential` — plus the implement-or-not decision. That decision is now a field.

**`detectability`, the new schema-2 field, is the deliverable as much as the prose is:**

| value | n | meaning |
|---|---|---|
| `implemented` | 38 | a check in `detected_by` emits candidates; the agent triages them |
| `implementable` | 19 | AST-decidable, not yet written — Phase 2's queue |
| `agent-only` | 32 | no scanner will ever produce it; the `hunt` directive **is** the method |

The plan predicted "roughly a third AST-decidable". For the 49 new shapes it is 19 (39%) — close
enough that the estimate can be trusted for the next corpus.

`aliases` is the second new field: a shape's earlier names, so findings and report prose written
before a merge still resolve. Added because the alternative — renaming across `findings.json`, three
TSVs, three INDEX.md files and a 685-line report — is how drift gets created while fixing drift.

### Two shape names were duplicates

- `divergent-capability-across-parallel-modules` (2 findings) → **`one-concern-implemented-per-backend`**
  (5). Identical hunt directive: enumerate the interchangeable implementations, build a
  feature × backend matrix, look at every cell that is not full. Now 7 findings — the corpus's most
  productive single shape.
- `guard-names-abbreviated-sibling` (1) → **`isinstance-on-container-not-element`**, which was
  already catalogued and whose own `guarded_twin` text *already cited that finding's twin*. The name
  had been invented for a shape that existed. This is the write-back gap in miniature.

### Ownership rule, adopted here

`python-pitfall-scanner` had ended up owning 58 of 89 shapes, giving it a 122 KB briefing. The rule
that fixed it, and that new shapes should follow:

> **A scanner-backed shape (`implemented`/`implementable`) belongs to `python-pitfall-scanner`,
> which runs the scanner and triages its output. An `agent-only` shape belongs to the agent whose
> METHOD finds it — its `hunt` directive is that agent's job description.**

Thirteen shapes moved. `python-pitfall-scanner` 58 → 45, `pattern-consistency-checker` → 14,
`silent-failure-hunter` → 7, `type-design-analyzer` → 5, and `api-surface-reviewer` got its first.

`build_informed_briefing.py` now renders `detectability` in each entry, because the decision is
worthless if it does not reach the agent: an `agent-only` shape is explicitly labelled *"no scanner
will ever hand you this"*.

### 0.4 — the recorded diagnosis was wrong

The plan said "11 malformed rows … column mismatch". They were **not** malformed: all eleven were
well-formed 5-column rows carrying a literal `-` in the shape column. Eleven idlelib findings had
simply never been assigned a shape, because nine of them needed a shape that did not exist yet.
Those nine are now catalogued (`falsy-test-on-a-zero-valued-enum-member`,
`mirrored-direction-handles-fewer-cases`, `serialize-and-parse-use-different-grammars`,
`attribute-created-outside-init`, `handler-reads-a-name-the-try-may-not-have-bound`,
`recognizer-rejects-a-legal-variant-spelling`, `reinitializer-resets-a-subset-of-its-state`,
`index-computed-before-a-mutation-used-after-it`, `commit-side-effect-outside-the-success-guard`);
the other two mapped onto stranded shapes that now exist.

**Lesson worth keeping:** a data defect recorded from a summary statistic was mis-diagnosed. Eleven
rows failing to parse was inferred; it was never checked. Look at the rows.

### 0.3 — folded into the existing generator rather than a new script

The plan called for a new `gen_known_findings.py`. The findings repo already had
`scripts/gen_index.py` carrying exactly the right convention ("single source of truth is
`findings.json`; never hand-edit the generated tables") — and regenerating everything **except** the
TSVs, which is precisely why they drifted. TSV emission now lives there. Verified idempotent: it
reproduces all three INDEX.md files byte-identically.

It also prints `N without a shape` per project and a warning line when any are found — item 4.5's
"report the denominator with every zero", applied at the point the zero is created.

### Open, and now measurable

- **Briefing size.** `python-pitfall-scanner`'s briefing is ~95 KB (~24k tokens) even after the
  rebalance, because it legitimately owns 38 implemented checks. Inherent, not a defect — but
  `implemented` shapes could render a short form (the agent needs the *differential* far more than
  the pattern, since the scanner already emits the message). Worth doing before Phase 5's big runs.
- **The 19 `implementable` shapes need code, not design.** Cheapest four:
  `type-checking-import-of-a-nonexistent-module`, `dead-cross-reference-in-a-docstring`,
  `partial-traversal-of-a-node-family` (one grep string: `getattr(node, "body", ())`),
  `handler-reads-a-name-the-try-may-not-have-bound`.
- **Coverage is now 100% by construction and will decay the same way it did before** unless every
  new finding names a catalogued shape. `gen_index.py`'s warning is the tripwire; wiring it into
  `informed-explore`'s write-back is the durable fix.

---

## D-13 · 2026-07-27 · Phase 0 items 0.2, 0.5 and 0.6 — Phase 0 is complete, shipped as 1.6.0

### 0.5 `diff_findings.py` — the regression gate

**Findings are keyed WITHOUT line numbers.** Inserting a line above a finding must not read as one
regression plus one fix. A keyed match whose line changed is reported as `moved`.

**It emits a `verdict` string, not a pass/fail boolean.** Nothing mechanical can tell a new true
positive from a false-positive regression — that is exactly what a shape wave is *supposed* to
produce. An earlier draft had `"regression": added > 0`, which would have marked every successful
wave a failure. The tool reports what moved; triage decides.

**Every list it compares is registered explicitly** in `_FINDING_LISTS`, not sniffed. A heuristic
that silently stopped recognising a list would make a regression look like an improvement. Anything
unregistered, unreadable, missing, or present in only one run goes to `notes` — the denominator is
part of the answer (plan item 4.5, applied at the point the zero is produced).

Validated against the shipped benchmarks: idlelib v1 → v2 comes out as `100 → 101, added 1, gone 0,
unchanged 100`, matching D-02 exactly. `coveragepy_v1` against itself is stable across 248 findings.

### 0.2 `--catalog` — the external-catalog read path

`informed-explore.md` had documented this flag since the command was written; nothing implemented it.
It accepts a `findings.json`, a project directory, or a findings-repo root, and splits what it finds:

- **This project's findings** → "verify, then move on". **Never** narrowed by `--agent`: an entry
  dropped from the do-not-re-derive set is one the agent will cheerfully re-derive.
- **Other projects' findings** → explicitly *not* claims about this codebase; shapes confirmed
  elsewhere that are worth hunting here. A hit is a new finding, a miss is not a finding at all.
  This list **is** narrowed to the agent's shapes, with the dropped count stated.

Target-project matching is by name containment in either direction, so `coveragepy` matches a target
directory named `coverage` and `cpython-idlelib` matches `idlelib`. Catalog problems go to **stderr**,
so a `--catalog` that resolved to nothing cannot masquerade as a complete briefing on stdout.
`--catalog-dir` is accepted as a synonym because the plan named it that way and the command docs
named it `--catalog`; making both work is cheaper than deciding which document was wrong.

### 0.6 Release discipline — a tripwire, honestly scoped

Nothing in a repository can detect that a user has not updated their installed plugin. What it can do
is make adding an agent impossible to do *silently*. `tests/test_release_discipline.py` asserts the
agent/command/script inventory against explicit counts; adding one fails the suite, and the fix is to
update the count **and** bump `plugin.json`. Deliberately annoying, in proportion to a defect that
cost a session.

**It caught its own author within a minute of being written** — the script count was set to 14 when
the real count was 13.

It also checks the wiring that makes an agent reachable at all: frontmatter present, `name` matching
the filename (Claude Code dispatches on the frontmatter name, so a mismatch is an unreachable agent),
dispatch from some command, and that every agent and script the shape catalog points at exists. That
last check exists because D-12's ownership rebalance moved shapes onto agents by name.

**Shipped as 1.6.0**, since Phase 0 added a script, 49 shapes, a schema version and a CLI flag. The
`[Unreleased]` content was folded into a dated `## [1.6.0]` section.

### Three bugs found while building the above

- **`analyze_history.py` leaked its `git log` pipes.** The `ResourceWarning` is emitted at collection
  time — *after* the JSON is written — so it landed inside
  `reports/coveragepy_v1/analyze_history.json` and made that report unparseable. Found because
  `diff_findings.py` tried to read it. Fixed with a `with` block; the artifact is repaired.
- **The same function passed `stderr=PIPE` and never drained it.** Nothing read that pipe, so `git`
  would block writing stderr once it filled while the script blocked reading stdout — a latent
  deadlock on any repo whose `git log` is noisy enough. Now `DEVNULL`.
- **`duplicated-guard-wrong-operand` printed every simple name twice, unbounded** — *"though text,
  text, line, col, chars, chars, m, m, …"*. A plain assignment target was yielded both by
  `_dotted_name` and by the `ast.walk` beside it. Deduplicated in source order and capped. Detection
  unchanged: idlelib still reports 101.

Also: `CHANGELOG.md` had **two `[Unreleased]` sections** for the whole 1.4.0 and 1.5.0 cycles — the
heading was never renamed when 1.4.0 was cut, so released work sat under "Unreleased". The orphan is
now labelled as the earlier 1.4.0 batch, and a test enforces at most one.

**Lesson, consistent with D-12's:** every one of these was found by *using* the artifacts rather than
reading them. The corrupt report had been sitting in the repo since the coverage.py benchmark and no
one noticed, because nothing had ever tried to parse it back.

### Where Phase 0 leaves things

Phases 1, 2 and 3 are unblocked and independent of each other. The natural next step is the plan's
own minimum-viable slice, now reduced to **2.1** (`unformatted-format-string-literal`, measured at
0 FP across all of `Lib/`) and **3.1** (`prior-art`). 2.1 also produces the first idlelib **v3** run,
which is what finally exercises `diff_findings.py` as a regression gate rather than as a self-test.
