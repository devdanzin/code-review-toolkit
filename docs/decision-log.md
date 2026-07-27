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

---

## D-14 · 2026-07-27 · Phase 2 item 2.1 and Phase 1 — shipped as 1.7.0

### 2.1 `unformatted-format-string-literal` — the pipeline proof

**Measured over CPython `Lib/` (1,847 files): 4 raw candidates, 1 finding, 0 false positives.**
idlelib, `_pyrepl` and coverage.py each produce **0**, so it adds no FP pressure to the benchmarks.
The confirmed instance is `Lib/test/test_tarfile.py:3871` — `raise NotImplementedError("Need to guess
component length for {sys.platform}")` in the `else` branch of a platform check.

**Correction to the plan's §0.6 estimate.** It recorded "**2/2 recall** on the known bugs" and "18
raw candidates". The reproduction found **1** true positive in `Lib/`, not 2, and 4 raw candidates,
not 18 — because the candidate definition was never written down. My first attempt at it (any string
literal containing a brace field) produced **2,188 raw / 694 after the differential**, which is
useless. The shape only works when candidates are restricted to a **message sink**: an exception
constructor, a `warnings.warn`, a logging call, a `print`.

Two near-misses that look like true positives and are not — both are template CONSTANTS consumed by a
formatter elsewhere, and both are excluded by the extra-argument differential at their call site:

- `Lib/_py_warnings.py:814` `_DEPRECATED_MSG` → formatted by `warnings._deprecated(name, message, remove=)`
- `Lib/glob.py:153` `_deprecated_function_message` → same

**The differential that does the work is the identifier requirement.** `{}` and `{0}` are
indistinguishable from a regex quantifier (`\d{4}`) or a literal brace in a character class; those two
classes alone were ~90% of the raw candidates. Requiring the field name to be an identifier removes
them without losing the archetypal `{name}` slip.

### Phase 1 — the tier lists were measured once and lost

`run_lint_rules.py` had to re-derive the tiering because the previous session measured "59 tiered
codes" and never wrote the codes down. **They are now constants in the source.** The reconstruction
lands at tier-1+2 = **997** across the three corpora against the recorded 989, which is close enough
to treat the tiering as reproduced rather than reinvented.

Measured tier-1 totals, for regression comparison: **idlelib 67, `_pyrepl` 7, coverage.py 19.**

**`rule_validation` earned its keep on its first run.** It flagged two of my own tier-1 codes —
`PLW1514` and `RUF055` — as preview-gated, meaning they had been selected and silently did nothing.
ruff reports that on stderr and nowhere else. Three more (`PLC2701`, `PLR0202`, `PLR0203`) were
caught the same way in tier 2. Without this check the selection would have carried five dead rules
indefinitely and their absence from the findings would have read as absence in the code.

**The first novel-shape harvest immediately found a mapping gap:** `B019` was being reported as a
novel candidate while `lru-cache-on-method` had been catalogued since the first wave — a
double-report waiting to happen. Now mapped, along with `B017`.

**`has_suppression_comment` is as strong as the survey claimed.** 6 of 19 tier-1 findings on
coverage.py carry one and **every one is a deliberate idiom**, the clearest being
`open = open  # pylint: disable=redefined-builtin`, which captures the builtin at import time so
later mocking cannot break the module.

Strongest uncatalogued candidates from the harvest, for Phase 2.7: **`B905`** (`zip()` without
`strict=`, silently truncating to the shorter iterable — 16 instances across all three corpora, the
single best candidate), `DTZ005`/`DTZ006` (naive datetime), `PLE0704`, `S608`.

### 1.3 reproduced the typing survey exactly

coverage.py: plain mypy **0 errors**, `--disallow-any-unimported` **3 errors in 1 file**, all from
`from coverage.plugins import FileReporter`. `_pyrepl` correctly reports **FAILED** with the
stdlib-shadowing diagnosis rather than a false clean — `failure_reason` now names each known landmine
and its fix, so a FAILED status is actionable instead of just discouraging.

### Scanner runtime is now a real problem, with numbers

The plan's risk table records "5 min for a full `Lib/` sweep with 10 checks". With 38 checks a full
`Lib/` run **exceeded 20 minutes and was killed**. The new check alone over the same 1,847 files takes
**64 seconds**, and on a 40-file directory it is ~10% of total runtime — so no single check dominates
and the cost is broad. This makes Phase 4's profiling item load-bearing rather than housekeeping:
**a benchmark nobody can afford to run stops being run.**

---

## D-15 · 2026-07-27 · Phase 3 — verification infrastructure

### 3.3 measured its own ceiling on the first run

`check_known_findings.py` against the coverage.py catalog (60 entries):

```
present 2 | absent_in_qualname 1 | absent 2 | out_of_scope 2 | not_scannable 53
```

**53 of 60 catalogued findings name an `agent-only` shape.** A scanner cannot see them, so
`known-issues` can regression-check 7 of coverage.py's 60 findings and no more. That is not a defect
in the tool — it is the direct consequence of D-12's measurement that 32 of 90 shapes are agent-only,
and those shapes are exactly the ones the richest agents produce.

The design consequence: **`not_scannable` and `out_of_scope` are counted as `not_checked`, never as
`absent`.** A summary reading "2 still present, 58 clear" would have been a serious misrepresentation
of a run that examined 7 entries.

`out_of_scope` was added after the first run showed two `tests/` entries reported `absent` when the
scope was the package only. `absent` claims we looked; we had not.

### Keying on qualname removes a whole verdict class

Keyed on `(file, shape, qualname)`, so a finding whose line moved is `present`. The sibling C toolkit
needs a `line_drifted` verdict and a `nearest_line` heuristic to triage; Python's `ast` makes that
unnecessary. One less class of manual triage per run.

**Two catalog rows were being lost to a location-parsing bug**, both reported `file_missing`:
`patch.py:56-57, :74-75` (a continuation segment with no filename — `rpartition(":")` read
`patch.py:56-57, ` as the path) and `tests/a.py:256-259, tests/b.py:290` (two files in one location).
Real catalogs use four location shapes and the parser handled one. Each is now a test.

### 3.4 — `BLOCKED` is a state, not a severity

`AUDIT-RESULT: FIX=n CONSIDER=n POLICY=n SCANNERS=n/m -- <STATE>` on line 1, where the state is
`CLEAN` / `NEEDS-SIGN-OFF` / `BLOCKED`. **`BLOCKED` fires on any scanner that failed, timed out,
crashed, or analyzed zero files — even when every finding it did produce was clean.** An incomplete
audit reporting clean is the one failure mode that gets shipped; a dirty one gets fixed.

### 3.1 — the recipe is vendored, not summarised

`docs/searching-trackers.md` is copied verbatim from the family rather than paraphrased, because both
footguns produce a *silent empty result* that reads exactly like "not reported": `gh search issues
--state all` errors and pipes nothing to `jq`, and quoted multi-word queries mean exact-adjacent
phrases. The `prior-art` command adds the verdict vocabulary — `none` / `known` / `known-sharper` /
`partial` / `reverted` / `refuted` — where `reverted` exists because a merged-then-backed-out fix
reads as closed on the tracker and is live in the code.

---

## D-16 · 2026-07-27 · Phase 4 item 4.6 — complexity crossed with fix history

### The inversion reproduces, and the crossing corrects it

`measure_complexity.py` now runs a git-history pass and emits `fix_commits_2y`, `fix_density`,
`risk_rank` and `verdict` per hotspot. On coverage.py:

| rank | score | fixes/2y | verdict | function |
|---|---|---|---|---|
| 1 | 7.5 | 5 | `active-risk` | `sysmon.SysMonitor.sysmon_py_start` |
| 2 | 9.0 | 2 | `active-risk` | `pytracer.PyTracer._trace` |
| 3 | 5.0 | 2 | `active-risk` | `html.HtmlReporter.write_html_page` |
| 4 | 8.0 | 1 | `settled` | `data.combine_parallel_data` |

The most-repaired function in the codebase ranks **below three others on complexity alone**. That is
D-05's lesson, now enforced by the output rather than left to the reader.

### My first verdict rule reproduced the very bug it was written to fix

The first cut gated `active-risk` on `fix_commits >= busy AND score >= 8.0`. That labelled
`sysmon_py_start` — 5 fix commits, the most of any hotspot — **`quiet`**, because its score is 7.5.

**`active-risk` is gated on the fix history ALONE.** Complexity decides `settled` vs `quiet`;
history decides `active-risk`. Adding a complexity conjunct anywhere re-introduces the inversion.

### The threshold is a constant, not a median

The median-derived gate (`max(2, median + 1)`) was unstable: over a handful of hotspots the median
lands on whichever value sits in the middle and the gate moves with it. With two hotspots at 0 and 5
fixes, the median is 5 and the 5-fix hotspot fails its own threshold. Now `ACTIVE_RISK_FIXES = 2` —
two independent repairs to one function inside two years is a real signal at any codebase size.

**A missing history yields `unknown`, never zero.** Treating an absent or shallow history as zero fix
commits would mark every hotspot `settled` and reproduce the inverted ranking exactly.

### nesting_depth recalibrated

Two constructs the AST nests and a reader does not:

- **`elif` chains.** The AST models `elif` as an `If` inside each `orelse`, so `generic_visit`
  charged a level per arm and a flat if/elif/elif/else read as **depth 3**.
- **`if False:` / `if 0:` debug blocks**, common in older stdlib code, counted their whole contents.

`pytracer._trace` moved 10.0 → 9.0 as a direct result. Any comparison against a pre-1.9.0 complexity
number is invalid.

### 4.5b — `tools/`

Created, with the boundary stated: `plugins/.../scripts/` answers questions about a *reviewed
project*; `tools/` answers questions about *the toolkit*. Nothing in `plugins/` may import from it.
First inhabitant is `shape_coverage.py`, which measures Phase 0's metric on demand — it decays
silently otherwise, since every ad-hoc shape name that never reaches the catalog drops the ratio and
nothing else notices. It carries its own baseline history (36% → 100%).

---

## D-17 · 2026-07-27 · Phase 5 — the yield runs, and the two defects they exposed

Reports: `reports/tkinter_v1/README.md`, `reports/asyncio_v1/README.md`.

### `--isolated` was suppressing the entire ASYNC rule family

asyncio's first tier-1 run reported **zero** ASYNC findings — on the one corpus in the plan chosen
specifically to validate them. The rules were not broken: three of them fire on a synthetic blocking
-call fixture and all twelve report `Stable` in `rule_validation`.

The cause was mine. `--isolated` is on by default so a project's ruff config cannot silently change
the *rule selection* — but it also discards `requires-python`, and ruff falls back to its oldest
supported version. Passing `--target-version` (from `requires-python`, else the running interpreter):

- **`ASYNC109` fires 4 times** — `base_events.py:595`, `tasks.py:405/440/490`.
- **Four `F821` false positives vanish** — `ExceptionGroup` / `BaseExceptionGroup`, builtins since
  3.11 that ruff flagged as undefined under its assumed floor.

**Isolation should control the rule set, not the language level.** Had Phase 5.2 not been run, the
plan's conclusion would have been "asyncio does not exercise the ASYNC rules", which is false, and
the rules would have shipped permanently dead.

### `_returns` claimed things the code does not say

`_returns(name, body)` matched any occurrence of the name anywhere inside a returned expression, so
`return self._grid_configure('columnconfigure', index, cnf, kw)` read as returning `cnf`. Seven
tkinter methods were reported at **HIGH** confidence with "the shared object is returned to callers".

Now it asks whether the object actually escapes: the name itself, or inside a container literal, an
`or`-default, or a conditional. A call *may* return its argument, but that is a question about the
callee and guessing yes is what produced the false positives. tkinter high-confidence
mutable-default findings **7 → 3**; idlelib unchanged at 101 (no FP regression on the control).

### What the corpora actually measured

**tkinter is one finding, not 46.** 46 of 62 scanner findings and 46 of 52 tier-1 lint findings are
the same idiom — `def method(self, cnf={}, **kw)` across the widget API. Scanner and ruff `B006`
agree **exactly** on all 46, which is the strongest validation the merge design has had. Verdict
ACCEPTABLE: `_cnfmerge` returns a fresh dict, so the shared default is read-only on the ordinary path.
The scanner already rated 43 of 46 `medium` with "no mutation seen" — the differential was doing its
job before triage even started.

**asyncio validated the async shape family**: `asyncio-fire-and-forget-task` fires twice, and the
tier-1 lint pass reached the ASYNC rules once the version fix landed.

### An honest gap

The plan expected tkinter to stress reachability tiering and the dead-code FP classes hardest. **It
did not, because this run did not include `find_dead_symbols`** — that pairing needs Phase 4 item 4.3
(reachability tiering), which is not built. Recorded in the report rather than claimed.

---

## D-18 · 2026-07-27 · Phase 6 — the gates pass, and both caught a defect in the gate

### 6.1 idlelib v2 → v3: a clean FP-regression pass

```
scan_python_pitfalls  101 -> 101   added 0  gone 0  unchanged 101
measure_complexity     12 ->   9   (the documented nesting recalibration)
```

Zero false-positive regression across everything Phases 0-5 shipped: one new shape, three scanner bug
fixes, a retuned lint pass and a recalibrated complexity metric. First time the gate has been run for
its actual purpose rather than as a self-test.

### 6.2 coverage.py v1 → v2 at the same commit

`d37859cd` both times, so **every difference is the toolkit, none is the target**. `scan_python_pitfalls`
`26 -> 26` with zero movement. The large `gone` counts are the previously-recorded fixes finally
visible as a diff: `find_dead_symbols` `42/9/2 -> 0/0/0`, `analyze_imports.cycles` `20 -> 9`.

### Both gates found a defect in `diff_findings.py` itself

**`message` was part of the key.** Improving a check's wording re-split every finding it produces
into one `gone` plus one `added` — the identical spurious pair the line-number exclusion exists to
prevent, arriving through a different field. Caught on idlelib v2 → v3: the `duplicated-guard`
message dedup reported a regression *and* a fix at the same file, line and shape. `message` is
explanatory detail, not identity.

**Two runs over different trees were silently diffed.** coverage.py v1's `extract_test_invariants`
had been captured against `coveragepy/tests` and v2 against `coveragepy/coverage`. The diff reported
**30 findings "gone"** from a tree the second run never looked at — a completely fabricated
regression, reported with the same confidence as a real one. Mismatched `scan_root`s are now refused.

**Lesson, and it is the same one as D-13 and D-17:** every one of these was found by *using* the
artifact rather than reading it. A gate that has never been run is not a gate.

### Still open at the end of this pass

- **6.3** confidence-tier precision measurement, and **6.4** `_pyrepl` under `known-issues`.
- **Phase 2 items 2.2-2.8** — five shapes plus the ruff-derived harvest. The strongest candidate is
  **`B905`** (`zip()` without `strict=`), 16 instances across three corpora and no catalogued shape.
- **Phase 4 items 4.1-4.5, 4.7** — notably **4.3 reachability tiering**, without which the tkinter run
  could not stress the dead-code false-positive classes as the plan intended (D-17).
- **Scanner runtime** (plan §9). A full `Lib/` sweep with 38 checks exceeded 20 minutes and was
  killed; the plan's recorded baseline is 5 minutes with 10 checks. A benchmark nobody can afford to
  run stops being run.

---

## D-19 · 2026-07-27 · The idlelib informed-explore, and what it exposed in the toolkit

18 agents + 12 scanners over `Lib/idlelib` (125 files) @ CPython `6080c866096`. Full findings in
`reports/idlelib_v4/FINDINGS.md`. What matters for the toolkit:

### Four scanner defects, all of the same class: a failure reported as a result

- **`analyze_imports` reported a resolution failure as `cycles: []`.** idlelib IS the stdlib, so
  `_is_stdlib()` was consulted before `project_packages` and every internal import was dropped.
  **I repeated the false "0 cycles" to the user before an agent caught it.** Fixed three ways
  (scan-root self-detection, project-packages-beat-stdlib, and a `resolution` field). idlelib
  0 -> 113 edges; **asyncio 0 -> 19 cycles, so D-17's Phase 5 asyncio run had the same silent
  failure**; coverage.py unchanged.
- **Four lists are capped and presented as counts.** `count_types.unannotated_public_functions`
  reads 50; the true figure is **2079**. Same at `extract_test_invariants` (`[:15]`, `[:20]`) and
  `measure_complexity` (`[:30]`). I quoted the `[:20]` cap to an agent as a measurement. All now
  emit `*_total` / `*_capped`.
- **`correlate_tests` mis-measures three ways** — counts test-infrastructure files as source
  (84.8% vs a real 93.3%), silently subtracts skipped and unmapped tests from its own total
  (587 vs 613), and sees only `@skip` decorators, missing runtime `self.skipTest()`.

The pattern is one thing: **a scanner that cannot answer must say so, not return an empty answer.**
`check_typing`'s `status: FAILED` was the model; the others lacked it.

### D-07 was violated twice, despite `docs/reproduction-convention.md` existing

Two agents patch-tested in the live checkout. One restored; one left a `# MUTANT` marker in
`sidebar.py` that I found and restored. A third ran 13 mutation experiments, restoring each time —
every restore worked, but each left a file mutated for 60-90s.

**The convention doc was not enough because agent prompts do not read it.** The `git archive` recipe
is now **triage rule 7 in the informed briefing**, which every agent does read. That is the durable
fix; the doc alone demonstrably was not.

Verified final state: 0 modified files, no `MUTANT` markers, all SHAs match HEAD.

### The registry gap from item 0.6 recurred, live

`lint-rule-triager` and `typing-integrity-auditor` were not dispatchable — the installed plugin was
1.6.0, from before this session shipped 1.7.0-1.11.0. Routed through `general-purpose` with their
definition files. The tripwire fires in the repo; nothing can make a user re-run `/plugin`.

### What the informed run bought, measured

- **Five findings reached independently by two agents** from different evidence.
- **silent-failure-hunter dismissed 24 of 32** candidates against the FP taxonomy and spent the
  effort elsewhere; **dead-code-finder returned 1 of 164** with the denominator stated.
- **consistency-auditor measured a plausible hypothesis and killed it** — "after-callbacks leak onto
  destroyed widgets" fires zero callbacks, because `Misc.destroy` deletes the Tcl command.
- **git-history-analyzer declined a finding it wanted**: gh-102778 looked like a textbook
  `fix-reverted-and-never-relanded` and it verified the reland three months later.

### The sharpest methodological result: mutation as the arbiter

Against idlelib's full 623-test GUI suite (headless is only **296 run / 81 skipped**), mutations of
`searchengine.py:182`, `undo.py:218/279` and four `sidebar.py` lines all **survive**, while the
mirrored `search_forward` mutation dies with 5 failures. The cause is a test stub:
`test_searchengine.py:279` does `cls.text.index = lambda index: "4.0"`, freezing every index
expression to a constant.

**This reframes `test-cannot-fail`.** The high-value variant is not "no assertion" but **"assertion
against a stub that cannot express the failure"** — which is exactly how CRF-IDLELIB-0025 hid, and
what `mock_idle.get_selection_indices` does today. Worth a catalog entry of its own.

---

## D-20 · 2026-07-27 · Session boundary — state at handoff, and how to resume

Written before a context compaction. Between this and `docs/improvement-plan.md` the reasoning is
complete; nothing below needs re-deriving.

### State

| | |
|---|---|
| Toolkit | `main` @ `fb94994`, pushed, 0 unpushed. **v1.13.0** — 96 shapes, 47 FP classes, **671 tests passing**, ruff clean |
| Findings repo | `main` @ `8cb5319`, pushed. Private. 3 projects, 111 findings, coverage **111/111** |
| Improvement plan | Phases **0, 1, 3, 5, 6 complete**; **2 and 4 partial**. Status columns are current in the plan |
| Benchmarks | `reports/{idlelib_v1..v4, pyrepl_v1, coveragepy_v1, coveragepy_v2, tkinter_v1, asyncio_v1}` |
| Targets | CPython `~/projects/3.14` @ `6080c866096` — **clean, verified by SHA**. coveragepy @ `d37859cd` — clean (its 5 untracked files are ctracer artifacts from March, not this session) |
| Venvs | `~/venvs/cext-review-toolkit` (Python 3.14 debug; ruff 0.15.10 — the WRONG version for `run_lint_rules.py`). **Pinned ruff 0.16.0 at `~/venvs/code-review-lint/bin/ruff`, pass via `--ruff-bin`** |
| Background jobs | none |

### The user is on plugin 1.6.0; the repo is 1.13.0

`/plugin` was last run before 1.7.0. Consequence, observed live: `lint-rule-triager` and
`typing-integrity-auditor` were **not dispatchable** and had to be routed through `general-purpose`
with their definition files. Item 0.6's tripwire fires in the repo; nothing can make a user update.
**Ask them to re-run `/plugin` before the next agent run.**

### What remains, in priority order

1. **Phase 2 items 2.2-2.8** — five shapes plus the ruff-derived harvest. Also **23 `implementable`
   shapes** are now catalogued and un-coded; that queue grew from 19 with the idlelib write-back.
2. **Phase 4 items 4.1-4.5, 4.7** — notably **4.3 reachability tiering**, without which the tkinter
   run could not stress the dead-code FP classes as intended (D-17), and **4.1
   `discover_python_project.py`**, which would have prevented D-19's `analyze_imports` failure class.
3. **Phase 6 items 6.3/6.4** — confidence-tier precision, `_pyrepl` under `known-issues`.
4. **Scanner runtime** (plan §9) — a full `Lib/` sweep with 38 checks exceeded 20 minutes and was
   killed; the recorded baseline is 5 min for 10 checks. A benchmark nobody can afford to run stops
   being run.
5. **`analyze_imports` fan-in for a non-root package** — `internal_graph` keys sources on file paths
   and targets on dotted module names, which agree only when the package root IS the project root.
   idlelib resolves 113 edges and still reports 0 cycles; `resolution: PARTIAL` says so honestly, but
   the underlying mismatch is unfixed.

### The idlelib findings are NOT yet in the findings repo

`reports/idlelib_v4/FINDINGS.md` holds ~15 verified findings plus the agent-reported set. They have
**not** been migrated into `code-review-findings/cpython-idlelib/project-local/findings.json`, so the
111/111 coverage figure does not include them. Migrating them is the obvious next write-back, and
`gen_index.py` will regenerate the TSV and INDEX automatically.

### Traps that cost real time this session

- **`ruff format <dir>` reformats every file in the directory.** It rewrote 19 unrelated files; I had
  to `git checkout --` all of them. Format only the files you edited.
- **`git status` can report a file modified when only its mtime changed.** Check
  `git hash-object <f>` against `git rev-parse HEAD:<f>` before concluding an agent edited something,
  and `git update-index --refresh` to clear it.
- **Agents patch-test the live tree** unless told otherwise in the BRIEFING (rule 7 now). A doc they
  do not read does not count.
- `scan_common.load_data()` takes a filename **with** the `.json` extension; passing the stem
  silently returns `{}` and the caller degrades without saying so.
- The subagent concurrency cap is 20; a full 18-agent dispatch plus leftovers hits it.

### Deliberately not doing

`migrate` (dropped), `reproduce`/OOM sweep, `recursion-guard-auditor`, `parity-checker` as an agent,
`data/playbooks/`, campaign slice manifests. Upstream reporting of any finding — including the ten
verified idlelib bugs — is **out of scope by the user's decision**.

---

## D-21 · The idlelib write-back, and what re-verification changed (2026-07-27)

D-20 named this the obvious next step. It is done: `cpython-idlelib` goes **26 → 73 findings**,
the repo **111 → 158**, coverage **158/158 (100%)**, catalog **96 → 97 shapes**.
`code-review-findings@39bf9ea`, `code-review-toolkit@242c512`.

### Re-reading every site before writing it was not ceremony

Each of the 47 was re-read at its cited line in the `6080c866096` tree. That changed three:

1. **0059 upgraded from a reading to a reproduction.** The claim was "`_study1` has no f-string
   state, so a PEP 701 multi-line f-string is read as several statements". A three-way differential
   settles it: `x = (\n a+b\n)` → `goodlines [0,3,4]`, `x = """\n a+b\n"""` → `[0,3,4]`, and
   `x = f"{\n a+b\n}"` → **`[0,1,2,3,4]`**. The triple-quoted case IS the guarded twin, and the
   differential is stronger evidence than the agent's original argument.
2. **0073 corrects the report.** `FINDINGS.md` said "`exit=2` at 5 sites vs `exit=False` at 42 — the
   42 return 0 even when their tests fail." Measured: **51 plain, 5 `exit=2`, 4 `exit=False`.**
   `exit=2` is truthy and behaves as `exit=True`, so it is a harmless oddity; only four files are
   affected. The report inverted which number was the finding.
3. Line numbers for `autocomplete_w.py` (363-368, not 362-366) and `format.py` (59, not 57) were off.

**The rule this confirms:** an agent-reported count is the least reliable part of an agent report.
The *sites* held up under every check — 44 of 47 were exactly where they were said to be — but the
one figure nobody re-derived was wrong by an order of magnitude and inverted the finding.

### `verified_by`, and why `status` was not overloaded

The schema already distinguishes evidence class (`reproduced` / `confirmed` / `candidate`). It did
not distinguish evidence *author*, which matters because agent findings reach a briefing as
"confirm and move on" and an entrenched false finding is expensive. Added `verified_by`, backfilled
to `orchestrator` on the pass-1 set. Where a consequence rests on a measurement an agent ran and
this session did not re-run — 0056's 20k-stop memory figure, 0058's per-keystroke timing, 0072's
mutation survivals — the finding's `note` says so in that many words.

### Shape 97 was written rather than a wrong one reused

One finding (0057, `tree.py:234`, per-redraw `tag_bind` under an XXX correct since 1999) matched
none of the 96 shapes. The choice was: label it wrongly, or let `shape_coverage.py` fail. Neither —
`per-redraw-binding-never-released` now exists, with the discriminator that makes it usable:
**Tk deletes a widget's Tcl commands in `Misc.destroy`, so the common case is a non-issue.** The
real instance is a container that outlives its elements. The stale XXX is corroboration; the
measurement is the proof.

Writing the shape from the finding, rather than filing the finding under an approximate shape, is
the calibration loop working in the direction D-13 said it was broken in.

### A test that had been failing at HEAD on prose

`test_agent_filter_scopes_shapes` asserted `"other" not in briefing` while triage rule 7 says "every
**other** agent". It failed on wording, not on the filter it exists to check, and had been failing
since rule 7 landed — **D-20's "671 tests OK" was wrong at the moment it was written**, because the
suite was run before that wording. Fixture shape renamed to `unrelated-shape`; 671 pass now.

A bare-substring `assertNotIn` against generated text will eventually collide with the generator's
own boilerplate. Assert on a token that cannot appear by accident.

---

## D-22 · Review the branch you intend to report against (2026-07-27)

The idlelib review ran on **3.14**, and the umbrella issue was drafted citing 3.14 line numbers.
That is the wrong target for a CPython report, and the user caught it.

**3.14 is not an ancestor of main.** `git merge-base --is-ancestor 6080c866096 origin/main` → no.
They are separate lines, so a defect can be fixed on one and live on the other, and no line number
transfers. Re-verified against main `993a0c65a7b`: **72 of 73 survive, 1 is fixed there** —
CRF-IDLELIB-0066, fixed by gh-89520 on 2026-04-11, **which was in the report's "Start here" list**.
72/73 is a good survival rate; the point is that the one failure was the most prominent row.

### The method that made it cheap

Comparing the **enclosing function** rather than the cited line: a byte-identical function proves the
defect survives and needs no reading at all. 46 identical, 13 changed (read individually), 11
module-level (by hand). Roughly ten minutes of judgement instead of seventy re-reads.

### Two traps in the re-anchoring

- **Line remapping must be anchored on the enclosing function.** Keying on "nearest line with
  matching text" mapped `iomenu.py:333-348` to `360-347` — an end before its start — because `try:`
  and `except OSError:` repeat many times per file. Function-scoped matching fixed it.
- **A fingerprint built from one stripped line is too weak.** Six findings first read as GONE purely
  because `open(fname, 'w')` had gained `encoding='utf-8'`. All six were present.

### Use the build matrix

`~/projects/python_build_matrix` — `source/main` at the current commit, and
`builds/release-gil-nojit`, a **release** build of that same commit with working tkinter. The ad-hoc
checkouts under `~/projects/` are mostly ASAN/debug (a Tk reproduction under ASAN exceeded a
2-minute timeout) and one had a stale build failing on `SRE module mismatch`. Only the matrix records
which commit each build came from.

**Toolkit implication:** the review commands never ask which branch a finding will be *reported*
against, and `discover_python_project.py` (plan item 4.1) is the natural place to surface it. A
review of a maintenance branch is legitimate; silently drafting an upstream report from one is not.

---

## D-23 · The idlelib umbrella is filed — reporting conventions to reuse (2026-07-27)

**[python/cpython#154760](https://github.com/python/cpython/issues/154760)**, 69 findings, filed
2026-07-27. 73 found → 3 already reported → 1 fixed on main (D-22) → 69 reported.

Three conventions came from core-developer feedback and are **not** optional next time:

1. **Bare row numbers, never prefixed identifiers.** `IDLE-0035` was renamed to `35` because
   contributors were citing the prefixed form in issues and PRs. It does not autolink, so a reader
   who meets one has no route back to the umbrella. The issue now states that the number is a row
   and asks people to cite the issue plus the row — renaming alone would not have fixed the
   behaviour it was meant to fix.
2. **Every row ships as "Under analysis"** — explicitly *not cleared for work* — with the issue
   saying that a maintainer moving a row off that state is what opens it. A reviewer's findings are
   not triaged bugs: some are intentional, some not worth the churn, some wrong. `finding 34` is the
   concrete argument: four search/replace entry points work *only because* of the `TclError` swallow.
3. **Repeat both rules inside every gist.** People arrive at a gist from a search result, not from
   the issue, and would otherwise see neither.

**Structural choice that held up:** 8 cluster gists rather than 69 per-finding ones, because three
findings are systemic roots that explain their neighbours and only read as roots when the instances
sit next to them. Each finding still gets its own anchor, so the table is one row per finding.

**Mechanical trap, twice:** gist heading anchors must be **scraped from the rendered page**, never
computed. GitHub deletes apostrophes rather than replacing them and turns an em dash into a doubled
`-`; a locally-guessed slug silently lands the reader at the top of the gist. Both the renumbering
and the back-link edit were re-verified live (69/69).

Status is mirrored in `findings.json:upstream.row_status`, but the issue table is authoritative once
filed — maintainers edit it in place, so the generator no longer owns that column.
