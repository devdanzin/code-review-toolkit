# code-review-toolkit — improvement plan

**Written** 2026-07-26, after the coverage.py benchmark (v1.5.0, 40 shapes, 570 tests).
**Revised** 2026-07-26 with the maintainer's answers to §10 — see `docs/decision-log.md` D-08.
**Scope** Toolkit improvement only. Upstream reporting of existing findings is deliberately out of scope.
**Pacing** Full build-out, phased across sessions. Every phase ends in a measurable checkpoint.

> **Persistence rule (D-09).** Every decision, correction, plan change and benchmark result is written
> to a file, not left in a conversation. Decisions and corrections go to `docs/decision-log.md` with a
> `D-nn` id; plan changes are edited here *and* logged there with the reason; runs go to
> `reports/<target>_v<n>/`; findings go to the findings repo. **Prefer committing a partial artifact
> over holding a perfect one in context** — context is compacted, files are not.

---

## 0. Evidence base

Three surveys were run before writing this plan. Everything below is grounded in what they measured,
not in what seemed plausible.

### 0.1 The calibration loop is broken in the write-back direction

```
catalog shapes                                     40
distinct shapes named in the findings repo         64
STRANDED (used in findings, absent from catalog)   43
findings mapping to a catalogued shape         40 / 111  (36%)
```

coverage.py contributed **60 findings and 7 catalogued shapes**. Shape names were invented ad-hoc
while writing `findings.json` — `one-concern-implemented-per-backend` (5 findings),
`fix-not-propagated-to-sibling-path` (4), `same-fact-derived-from-two-sources` (3) — and none was fed
back. Their `hunt` directives, differentials and guarded twins exist only as prose in three JSON files
where no scanner and no briefing can reach them.

The read direction is half-wired too: `informed-explore.md` documents a `--catalog` flag that
`build_informed_briefing.py` does not implement.

**This is the single highest-yield item in the plan and it blocks most of the rest.**

### 0.2 idlelib measures false-positive regression, not yield

Re-running the current toolkit against idlelib:

```
PITFALLS  v1: 100 findings (41 high)
PITFALLS  v2: 101 findings (42 high)
unchanged 100 | gone 0 | added 1
```

Fifteen shapes added since v1 produced **one** new idlelib finding. Partly because the shapes are
target-specific; mostly because 43 of the shapes those benchmarks produced were never implemented.

Either way the conclusion holds: **"new findings on idlelib" is the wrong success metric.** Every wave
would look like a failure. Two metrics are needed instead:

| Metric | Measured on | Success looks like |
|---|---|---|
| **FP regression** | idlelib (fixed control) | findings stay stable or shrink; no new FP class; no crash; runtime flat |
| **Yield** | tkinter, asyncio (never-seen targets) | new true positives in shape families the target exercises |

Keep all three idlelib checkpoints — they are cheap and the FP signal is worth having per wave — but
read them as a *regression gate*, not a scorecard.

### 0.3 The linter integration already exists and is mis-tuned

`run_external_tools.py` runs ruff with `--select F,B,SIM,S,RET,PIE,UP,PERF`. Measured over idlelib /
`_pyrepl` / coverage.py: **610 / 124 / 259 findings, of which 65% / 73% / 92% are style-grade**, while
*missing 16 of 65 tier-1-grade defects (25%)* because it excludes `PL`, `RUF`, `DTZ` and `ASYNC`
entirely.

`--select ALL` is 21,346 findings across the three corpora (Q000 alone is 41% of idlelib). A curated
tier-1 is **65** (0.30%); tier1+tier2 is 989.

Ruff overlaps 7 of 40 shapes. On 4 the agreement is exact. On `BLE001` ruff has ~30% better recall. On
`B023` **ruff finds 0 across all three corpora where the scanner finds a real one** — so the scanner
check must never be dropped. And ruff carries ~30 defect-class rules with **no shape at all**
(`PLW0127`, `PLE0704`, `PLW0602`, `DTZ005/6`, `B905`, `S608`, `RUF069`, `PLW1508`).

### 0.4 For typing: one checker, its own config, one extra flag

| corpus | mypy | pyright | ty | pyrefly |
|---|---|---|---|---|
| coverage (own config) | **0** | 60 | 90 | 18 |
| `_pyrepl` (own config) | **0** | 50 | 51 | 25 |
| idlelib (no config) | 61 | 1,463 | 1,266 | 53 |

**Cross-referencing checkers is actively misleading.** Every consensus cluster was a shared blind
spot: all 10 in `_pyrepl` are `if False:` TYPE_CHECKING (only mypy special-cases it); 7 of 10 in
coverage are `hasattr()`-guarded assignment (only mypy narrows it). Consensus-among-the-others means
*mypy is right and they are misconfigured*.

The load-bearing addition is one flag. On coverage.py: `mypy` → 0 errors;
`mypy --disallow-any-unimported` → **exactly 3 errors in 1 file**, all from
`from coverage.plugins import FileReporter` — a module that does not exist. Same flag on `_pyrepl`
adds **0**, so it is a real finding, not a flag that fires everywhere.

Two landmines: **pyrefly silently reports 0 errors** when its config discovery excludes the tree
(idlelib: `0 errors` exit 0, or 53 errors from a staging root); and **mypy cannot analyze a
stdlib-shadowing tree** without symlink staging plus `--no-namespace-packages`.

### 0.5 Sibling capabilities worth porting — and not

Strongest signals (present in 4+ siblings, absent here): **project-discovery script**,
**triage-oriented preflight mapper**, **shallow-clone detection**, **version/deprecation
compatibility**.

Deliberately **not** porting, with reasons: `reproduce`/OOM sweep (no `set_nomemory` analogue and no
finding class — pure Python does not crash on allocation failure); `recursion-guard-auditor` (Python
raises `RecursionError`, not SIGSEGV — the whole severity argument evaporates); `parity-checker` *as an
agent* (needs the safe/unsafe asymmetry; the static half is already three catalogued shapes);
`data/playbooks/` (cext has produced 1 of 5 advertised; Python's framework matrix would rot faster);
campaign slice manifests (built for 358k lines; our benchmarks fit in one run).

### 0.6 Nine tracker-derived shapes, three empirically validated

Top of the list is essentially free: **`unformatted-format-string-literal`** — a `{...}` literal
nothing formats, so the braces reach the user verbatim. **2/2 recall on the known bugs, 0 false
positives across all of `Lib/`**, completely silent at runtime. Its three-part differential
(docstring / `.format` receiver / any extra argument) takes raw candidates from 18 to 0 while keeping
both true positives, and every near-miss is a real guarded twin (`runpy.py:125`, `_pyrepl/trace.py:28`).

---

## 1. Phase 0 — Repair the loop *(blocking; nothing else should ship first)*

| # | Item | Size |
|---|---|---|
| 0.1 | **Reconcile the 43 stranded shapes** into `python_bug_shapes.json` | L |
| 0.2 | Implement `--catalog-dir` in `build_informed_briefing.py` | S |
| 0.3 | `gen_known_findings.py` — reports → TSV, marked GENERATED | S |
| 0.4 | Fix the 11 malformed rows in one findings-repo TSV (column mismatch) | XS |
| 0.5 | `diff_findings.py` — compare two report dirs, emit added/gone/unchanged | S |
| 0.6 | Release discipline: bump the plugin version whenever an agent is added | XS |

**0.1 is the bulk.** Each stranded shape already has a title, location, consequence, guarded twin and
fix in `findings.json`; what it needs is the catalog's `pattern` / `hunt` / `expected` / `caught_as` /
`differential` / `detectability` fields, and a decision: **implement as a check, or mark
`agent-only`**. Expect roughly a third to be AST-decidable. Candidates that look immediately
implementable, from the coverage.py set:

- `type-checking-import-of-a-nonexistent-module` — trivially decidable, and §0.4 shows the payoff
- `hand-mirrored-wrapper-drifts-from-its-interface` — compare a wrapper class's methods to what it wraps
- `subclass-only-method-called-through-the-base`
- `partial-traversal-of-a-node-family` — an AST visitor that only reads `.body`
- `dead-cross-reference-in-a-docstring` — the documentation agent's single most productive query
- `empty-container-read-as-absent`, `prefix-rewrite-done-as-a-content-search`,
  `one-predicate-two-implementations`, `identity-key-from-a-non-artifact-proxy` *(the four banked
  novel shapes from coverage.py, still unimplemented)*

**0.6 is a process fix for a real incident:** `python-pitfall-scanner` and `test-investigation-agent`
were both invisible to the agent registry this session because they were added after 1.3.0 was cut.
The user's installed plugin genuinely did not contain them.

**Checkpoint:** re-run `diff_findings.py` on idlelib v2 → v3. Expect **zero** FP regression and a
measurable rise in shape coverage (`findings mapping to a catalogued shape`, currently 36%).

---

## 2. Phase 1 — External tools

| # | Item | Size |
|---|---|---|
| 1.1 | `run_lint_rules.py` + `lint-rule-triager` agent | S |
| 1.2 | Retune or retire `run_external_tools.py`'s ruff selection | XS |
| 1.4 | **Pin `ruff==0.16.0` + `rule_validation` in the envelope** (decided, D-10) | S |
| 1.3 | `check_typing.py` + `typing-integrity-auditor` agent | M |

**1.1** ships the measured tier-1/tier-2/tier-3 selection, `--isolated` by default so results are
comparable across projects, and two fields that carry the design: `shape_id` (non-null ⇒ merge with the
scanner's finding at raised confidence, don't double-report) and `has_suppression_comment` (measured to
be the strongest dismissal signal — tier-1 precision is **50-70%, not 100%**, and an existing
`# pylint: disable=` naming the rule class is usually why).

Its highest-value output is not the findings — it is the **novel-shape harvest**: any tier-1 rule with
`shape_id: null` that yields a confirmed true positive becomes a new catalog entry. ~30 ruff rules
currently have no shape.

**1.2 is mandatory, not optional.** Leaving both selections in place ships two contradictory ruff
configurations in one toolkit.

**1.4 — the ruff default set moved 59 → 413 in 0.16.0, released three days before this plan** (D-10).
Verified: `B006` fires with no `--select` on 0.16.0 and not on 0.15.10. It is **not a superset** — 18
rules were dropped — and **27 of our 59 tiered codes are outside the new default**, including every
security and complexity rule. Nothing we use was renamed or removed, and one earlier claim is
corrected: `PLW1641` is Stable, not preview-gated.

Consequences for the design, all measured:

- **Pin the version and the rule list.** Always explicit `--select`, never `--extend-select` (it
  composes with a default that just changed 7×). A ruff bump is a calibration event.
- **JSON only.** Concise output changed shape between versions *and* modes; 0.16.0 preview drops the
  rule code entirely.
- **Capture stderr** — remapped codes and preview-gated codes warn there and nowhere else.
- **No `--preview` by default.** It mutates already-stable rules and carries no deprecation policy.
  Run a separate, labelled preview pass if `RUF069`/`B909` are wanted.
- **`rule_validation` must inspect `status`, not membership.** Verified trap: removed rules
  (`RUF076`, `UP038`, `ANN101`) are still present in `ruff rule --all`, so a membership test passes
  for a deleted rule.

**1.3** defaults to mypy with the project's own config (`--config-file`, never overridden), runs
`--disallow-any-unimported` as a labelled second pass so the baseline count stays honest, and emits
`summary.phantom_imports` as a pre-correlated deliverable. Hard rules from the measurements:
ignore-staleness comes **only** from mypy's own `unused-ignore` code (never from grep — that is exactly
the "36 stale ignores" false alarm); `files_checked == 0` is reported as **FAILED, not clean**; `ty` is
opt-in and labelled experimental; `pyrefly` is not integrated until its silent-zero mode is addressed.

**Checkpoint:** idlelib run #2 → `diff_findings.py` vs #1. FP regression gate.

---

## 3. Phase 2 — Shape expansion

| # | Item | Size |
|---|---|---|
| 2.1 | `unformatted-format-string-literal` | S |
| 2.2 | `quadratic-string-consume-or-accumulate` | M |
| 2.3 | `lazy-shared-cache-published-before-complete` | M |
| 2.4 | `assert-guards-caller-supplied-input` | M |
| 2.5 | `unbounded-chain-walk-without-cycle-guard` | S |
| 2.6 | The four banked coverage.py shapes (folded into 0.1) | M |
| 2.7 | Ruff-derived shapes with no catalog twin | M |
| 2.8 | `fallback-path-validates-less-than-fast-path` — **agent-only**, do not force into a scanner | S |

Ship **2.1 first and alone** — it is the cleanest validation the plan has (0 FP measured across all of
`Lib/`), so it proves the calibration pipeline end-to-end at minimal risk.

Note the differentials that carry each: 2.2 must **not** flag a plain local `s += t` (CPython's
`BINARY_OP_INPLACE_ADD_UNICODE` specialisation makes local accumulation amortised-linear; only
attribute/subscript targets are quadratic). 2.4 needs the sibling-`raise` narrowing or it produces 76
raw candidates on `Lib/`. 2.6's `empty-container-read-as-absent` must be distinguished from the
existing `falsy-check-for-none-default` — different shapes, adjacent forms.

Shapes 6-8 from the tracker survey (`redos-*`, `loop-bound-local-escapes-*`,
`truthiness-test-on-caller-supplied-object`) are **needs-dataflow** and deferred to Phase 4.

**Checkpoint:** idlelib run #3 → diff vs #2.

---

## 4. Phase 3 — Verification infrastructure *(you chose: standard, not opt-in)*

| # | Item | Size |
|---|---|---|
| 3.1 | `prior-art` command — tracker search before any novelty claim | S |
| 3.2 | Repro convention doc + `status` gate in synthesis | S |
| 3.3 | `known-issues` command + `check_known_findings.py` | M |
| 3.4 | `audit` command with a machine-readable sign-off line | S |

**3.1 is the cheapest high-value item in the entire plan.** It caught a false finding this session (a
"released changelog contradicts the code" claim that 7.11.3 explicitly refutes) and correctly
redirected three findings from "file a new issue" to "comment on the existing one" — including #1689,
open since 2023, where our diagnosis is sharper than the reporter's. Vendor the `gh api search/issues`
recipe; `gh search issues` has two footguns that silently return empty.

**3.2 formalises what already worked.** 47 of 60 coverage.py findings are `status: reproduced` and six
harnesses are preserved. The convention to encode: patch-test on a **`git archive` copy, never the live
checkout** (two patch-tests were left in the user's tree this session, and reading `collector.py` cold
during that window yields a *confident, wrong* finding); prove the repro exercised the tree it thinks
it did (editable installs, stale `__pycache__`, `sys.path` order); **a negative result is a real
result**.

**3.3 is now unblocked** — `code-review-findings/*/catalog/known_findings.tsv` holds 111 rows across 3
projects. Key on **`(file, qualname, shape)`**, not `(file, line)`: Python's `ast` gives stable
qualified names, so cpython's whole `line_drifted` verdict class collapses into `present`. Keep its
caveat — **`absent` is not proof of a fix**, since project-level shapes carry no local token.

**3.4** converts the toolkit from exploratory to release-gating for ~200 lines. Line 1 of `AUDIT.md`
is `AUDIT-RESULT: FIX=n CONSIDER=n ... -- NEEDS-SIGN-OFF`, and a crashed scanner is `BLOCKED` — an
*incomplete* audit is worse than a dirty one.

---

## 5. Phase 4 — Precision infrastructure

| # | Item | Size |
|---|---|---|
| 4.1 | `discover_python_project.py` + preflight mapper upgrade | M |
| 4.2 | `python_idioms.json` — machine-readable half of the FP taxonomy | S |
| 4.3 | Reachability tiering (`public` / `protocol` / `internal`) | M |
| 4.4 | `python_version_matrix.json` + version-compat agent | M |
| 4.5 | Denominator honesty in the scan envelope | S |
| 4.5b | **Create `tools/`** (decided, D-08) — home for the calibration and validation harnesses | XS |
| 4.6 | **`measure_complexity` ingests git history directly** (decided, D-08) | M |
| 4.7 | Dataflow-dependent shapes (tracker survey 6-8) | L |

**4.1** fixes a whole *class* of bug rather than an instance. `find_dead_symbols` and `correlate_tests`
both assumed the reviewed package was the whole project — the same defect, found twice, fixed twice.
`scan_common.EXCLUDE_DIRS` still has **no generated-file exclusion at all**. One resolver answering
"where are the tests, docs, packaging metadata; what is generated; what is vendored; is this a shallow
clone" removes the class.

**4.2** converts 35 already-written prose FP classes into scanner-readable suppression at near-zero
marginal cost, with an `fp_class` back-reference so the prose stays the source of truth.

**4.3** turns FP classes 1-4 (dynamic dispatch, public API surface, protocol conformance, test-only
helper) from per-finding prose into a lookup. The **`protocol` tier is the payoff** — dunders, ABC
registrations, `singledispatch`, descriptors are reachable without any export, and an `__all__`-based
scanner silences them. `analyze_imports.py` already extracts `__all__`/`re_exports`.

**4.4** is the largest genuinely-new finding class and the strongest 4-sibling signal. Steal the
`detect` field that makes the table executable, plus cext's `version_added` /
`code_removal_opportunities` sections — dead compatibility shims are *removable code*, which pays into
`dead-code-finder` and `tech-debt-inventory` as well.

**4.6** encodes this session's sharpest calibration lesson, and is now a **build item rather than an
agent's responsibility** (D-08). On coverage.py churn and complexity were **inverted**:
`pytracer._trace` scores 10.0 with 2 fix-commits in two years; `sysmon.py` scores 7.5 with 11. High
complexity marked *settled* code, and complexity-driven triage would have pointed at exactly the wrong
files.

`measure_complexity.py` gains an optional history pass (reusing `analyze_history.py`'s collection) and
emits a **fix-density-crossed ranking** as a first-class output, so the crossing cannot be forgotten:

```json
"hotspots": [{"qualified_name": "...", "score": 10.0,
              "fix_commits_2y": 2, "fix_density": 0.08,
              "risk_rank": 14, "verdict": "settled"}]
```

`verdict ∈ {settled, active-risk, quiet}` — `settled` is high complexity + low fix density
(deprioritize, and say so), `active-risk` is high on both. Also calibrate `nesting_depth`, which
currently counts `try`/`else`/`finally` arms and `if 0:` debug blocks as levels and so overstates
reader-facing depth.

---

## 6. Phase 5 — New targets *(yield measurement)*

| # | Target | Why |
|---|---|---|
| 5.1 | **tkinter** | Old stdlib. Heavy dynamic dispatch, `**kw` passthrough, C-extension boundary. Stresses reachability tiering and the dead-code FP classes hardest. |
| 5.2 | **asyncio** | Newer stdlib. The only corpus that will exercise the async shapes and the `ASYNC`/`RUF006` ruff rules — all currently **unvalidated**, because the three benchmark corpora are nearly async-free. |

Run the full suite on each, fix whatever toolkit problems they expose, and harvest new shapes. These
are where **yield** is measured; idlelib cannot serve that role.

Expect tkinter to be the harder test. idlelib at **0% annotation coverage** and coverage.py at 99.3%
are near-opposite poles for the typing agent, and tkinter sits at the idlelib end — the agent must
produce something useful there, not just on annotated code.

---

## 7. Phase 6 — Re-runs and calibration

| # | Item |
|---|---|
| 6.1 | idlelib run #4 → diff vs #3 (final FP-regression gate) |
| 6.2 | coverage.py re-run → diff vs v1; **`known-issues` regression check** against its 60 catalogued findings |
| 6.3 | Confidence-tier precision measurement |
| 6.4 | Re-run `_pyrepl` under `known-issues` |

**6.2 is the first real test of `known-issues`** — 60 findings with locations and shapes, against a
repo that will have moved on. Expect some `absent` verdicts that are drift, not fixes.

**6.3 is overdue and now possible.** Confidence tiers (`high`/`medium`/`low`) have never been measured
against outcomes. With 111 findings carrying `status` and `severity`, we can finally compute
per-tier precision and recalibrate — or discover the tiers are not predictive, which would itself be
worth knowing.

---

## 8. Sequencing

```
Phase 0  Repair the loop            ── BLOCKING ──┐
                                                  │
Phase 1  External tools ────────────┐             │
Phase 2  Shape expansion ───────────┤ ← depends on 0.1 (catalog is the target)
Phase 3  Verification ──────────────┘             │
                          ↓                       │
         idlelib #2, #3 (FP gates) ───────────────┘
                          ↓
Phase 4  Precision infrastructure
                          ↓
Phase 5  tkinter, asyncio (YIELD measurement)
                          ↓
Phase 6  idlelib #4, coverage.py re-run, tier calibration
```

Phases 1-3 are independent of each other and can be reordered or parallelised. **Phase 0 gates all of
them** — shipping new shapes into a catalog that is 36% connected to the findings repo compounds the
drift rather than fixing it.

Suggested minimum viable slice, if the full build-out stalls: **0.1 + 0.2 + 2.1 + 3.1**. That repairs
the loop, proves it end-to-end with the zero-FP shape, and adds the prior-art step that already caught
one false finding.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| **Phase 0 is large and unglamorous** — 43 shapes is a lot of writing with no new findings at the end | Its checkpoint is *shape coverage*, not new findings. Measure 36% → target. |
| Tier-1 lint precision is 50-70%, not 100% | Ship it as agent-triaged, never as a gate. `has_suppression_comment` is the measured dismissal signal. |
| Async shapes and ASYNC ruff rules are **entirely unvalidated** | That is precisely what Phase 5.2 (asyncio) is for. Do not claim yield for them before then. |
| `known-issues` `absent` verdicts read as fixes | Encode cpython's caveat in the command's own output, not just its docs. |
| Scanner runtime — 5 min for a full `Lib/` sweep with 10 checks | Profile in Phase 4; two quadratic walks were already found and fixed this session. |
| Agents invisible until a release is cut | Item 0.6. |

---

## 10. Decisions taken, and what remains open

### Answered (D-08) — folded into the phases above

| Question | Answer | Where it landed |
|---|---|---|
| Push `code-review-findings`? | **Yes, private.** Now at `github.com/devdanzin/code-review-findings`, default branch `main` to match the family. | Done. One artifact removed pre-push for embedding local paths; `.gitignore` added. |
| Should `measure_complexity` ingest history? | **Yes, directly.** | Item 4.6, promoted from question to build item, with a `verdict` field. |
| `migrate` command? | **No.** Out of scope entirely, not deferred. | Removed. |
| A `tools/` directory? | **Yes.** | Item 4.5b; home for 6.3's calibration harness. |

### Still open

1. **How far to take `tools/`.** 6.3 (confidence-tier calibration) is the clear first inhabitant.
   Whether a `sample_scan.py`-style sampling harness or a precision-regression baseline is worth
   building depends on whether corpora grow past what one run handles.
3. **Whether the FP taxonomy should become the source of truth for suppression.** Item 4.2 adds a JSON
   companion with an `fp_class` back-reference so the prose stays authoritative. If scanners start
   consuming it heavily, that relationship may need inverting — worth revisiting after Phase 4.

---

## 11. Working conventions

Beyond the persistence rule at the top:

- **Never patch-test in a live checkout** (D-07). `git archive HEAD | tar -x -C <scratch>`, or a
  worktree. Verify the target tree yourself before reporting; do not accept an agent's claim of
  restoration — one was made falsely this session.
- **A negative result is a real result.** A plausible finding that dies under a patch-test is worth as
  much as one that survives, and belongs in the report so it is not re-derived.
- **Prior-art before novelty** (D-06). `gh api search/issues`, never `gh search issues`.
- **Bump the plugin version whenever an agent is added** (item 0.6). Two agents were invisible to the
  registry this session because they were added after the last release was cut.
- **Report the denominator with every zero** (item 4.5). A check that silently stops firing is
  currently invisible.
