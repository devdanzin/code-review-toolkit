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
