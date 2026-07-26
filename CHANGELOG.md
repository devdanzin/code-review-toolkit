# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- New shape `test-cannot-fail` — tests that pass regardless of what the code under test does: empty
  bodies, constant-only assertions, `assertTrue(all(filter(...)))` (where `filter` already dropped
  everything the predicate rejects), asserting methods that lost their `test` prefix, and classes with
  fixtures but no tests. Calibrated on idlelib, where the raw pass was 133 findings and ~85% were two
  false-positive classes: assertions aliased to locals (`Equal = self.assertEqual`, ubiquitous in
  CPython's tests) and DRY assertion helpers called from real tests. After encoding both, 21 findings
  with all five high-confidence hits matching an agent's independent findings.
- **Three more shapes from the idlelib agent benchmark**: `flag-not-reset-on-early-exit` (a guard
  flag set at entry but reset only on the success path, so every later call silently no-ops),
  `guard-rechecks-call-receiver` (`m = prog.match(...)` followed by `if not prog:` — the guard names
  the receiver, not the result), and `falsy-check-for-none-default`. Catalog is now 22 shapes, 4 of
  them `confirmed` against real findings.
- **Five new bug shapes derived from a 40-bug audit of CPython's pure-Python stdlib** — the catalog
  previously covered *none* of that audit's pattern families. Added `except-exception-too-broad`
  (~50% of the audit's confirmed findings: `except Exception:` around a narrow operation with a
  swallowing handler), `cleanup-only-on-success-path` (~20%: `close()`/`quit()` at the end of a `try`
  instead of in `finally`), `error-reported-below-warning` (~17%: failures logged only at
  debug/info, invisible under default configuration), `except-in-loop-without-exit` (a persistent
  failure inside `while True:` becomes a silent hang), and `raise-without-from-in-except`. Catalog is
  now 19 shapes.
- **New agent + script: `python-pitfall-scanner` / `scan_python_pitfalls.py`** — the toolkit's first
  dedicated bug-finding capability. Fourteen AST checks mapping 1:1 to the shapes in
  `python_bug_shapes.json`, each emitting a confidence level (`high`/`medium`/`low`) derived from that
  shape's differential. The builtin exception hierarchy is read from the running interpreter rather
  than a hardcoded table, so `except`-ordering analysis is always correct for the Python in use.
  Options: `--check ID[,ID...]` to select shapes and `--exclude PAT[,PAT...]` to drop generated trees.
  Output includes a `by_directory` breakdown, because real-world runs showed generated content
  (report artifacts, golden fixtures) is the dominant false-positive source and is best triaged a
  directory at a time.
- Registered the `pitfalls` aspect in `explore`, and put `python-pitfall-scanner` first in Group B —
  behavioural bugs rank above code smells.
- New shared module: `scan_common.py` — the utilities every analysis script needs (project-root
  detection, file discovery, AST parsing, CLI parsing, the JSON envelope, finding deduplication).
  Every script now imports from it. Previously `find_project_root` was byte-identical in all nine
  scripts and `discover_python_files` had drifted into three divergent variants.
- New data catalog: `data/python_bug_shapes.json` — 14 reusable Python bug *shapes* (not file:line),
  each with its guarded twin (the fix pattern), a sibling-hunt directive, expected behavior, how the
  defect surfaces, and a differential for when *not* to flag it. Covers mutable default arguments,
  late-binding closures, unreachable `except` ordering, `return`-in-`finally`, `__eq__` without
  `__hash__`, mutation during iteration, the asyncio family (fire-and-forget tasks, blocking calls in
  `async def`, un-awaited coroutines), `lru_cache` on methods, shared class-level mutable attributes,
  bare `except`, exceptions in `__del__`, and `is`-with-a-literal.
- New data catalog: `data/python_non_bugs.md` — false-positive taxonomy in 15 classes, each stating
  the symptom, why it is a non-bug, and what the real bug looks like so genuine instances are never
  suppressed.
- New script: `build_informed_briefing.py` — assembles the informed-review briefing (bug shapes
  scoped per agent + false-positive taxonomy + cross-cutting triage rules) as Markdown. Folds in a
  target project's accumulated findings memory from `.code-review/findings.json` when present, using
  a schema wire-compatible with the `*-review-findings` companion repositories.
- New command: `informed-explore` — same coverage as `explore`, but every agent reads the briefing
  first, so a run hunts un-found siblings of established shapes instead of re-deriving basics.
  Records confirmed findings to `.code-review/findings.json` for the next run.
- New agent: `test-investigation-agent` — finds bugs by treating tests as invariant specifications. Reads existing tests to extract what developers believe should be true, maps those beliefs to structurally similar code, and checks whether the invariants hold everywhere they should.
- New script: `extract_test_invariants.py` — supporting script that extracts assertions from test files, classifies invariant types, maps tests to source functions, and finds structurally similar functions using name-pattern and signature matching. Three-tier test selection (bug-fix tests, error/boundary tests, churn-guided) with 30-test budget cap.
- Added `test-invariants` aspect to the explore command (Group D).
- `explore` now supports `--runs N` (independent naive passes, deduplicated across runs) and
  `--informed-reruns` (with `--runs 3`, the third pass targets adjacent code and structural siblings
  of what the earlier passes confirmed). Documents the 2-naive-plus-1-informed review shape.
- `CLAUDE.md` — development guide covering architecture, conventions, the data catalogs and their
  `validation` grades, gotchas, and an explicit list of known gaps.

### Fixed

- `analyze_imports.py`: `from .X import Y` resolved to the *parent* package instead of the containing
  one (`Lib.terminfo` rather than `Lib._pyrepl.terminfo`), so resolved targets matched no file and
  **`fan_in` was zero for every file** in any project using relative imports. On `_pyrepl`, 0 of 25
  files had a nonzero fan-in; after the fix, 22 do. The four existing tests asserted the wrong values —
  rewritten against ground truth obtained by building the package layout on disk and importing it.
- `analyze_imports.py`: `detect_cycles` fabricated edges. `module_to_file` covers only files that have
  imports, so a target naming an import-free module fell through to a prefix match that resolved it to
  the enclosing package's `__init__`. A three-file DAG reported a phantom cycle. On `_pyrepl`, reported
  cycles went from 15 phantom to 1 real.
- `scan_python_pitfalls.py`: `except-in-loop-without-exit` no longer fires when the handler reports
  loudly (the shape's complaint is "no diagnostic"), and reserves `high` for a `while True:` whose
  entire body is the guarded operation. A REPL or accept loop that does other work each iteration makes
  progress even when one operation keeps failing.

- `--max-files` with a non-integer argument now exits with a JSON error instead of an unhandled
  `ValueError` traceback.
- Documentation drift: both READMEs claimed 14 agents / 4 commands / 7 helper scripts; the actual
  counts are 16 / 5 / 12 as of this release.
- `correlate_tests.py` omitted `scan_root` from its JSON envelope, unlike every other script.
- `scan_python_pitfalls.py` scopes a single-file target to that file. Several sibling scripts instead
  fall back to the project root, silently turning "scan this file" into "scan everything".
- `extract_test_invariants.py` emitted `invariant_types` in set-iteration order, so output varied
  between runs with `PYTHONHASHSEED`. Output is now sorted and reproducible — non-reproducible output
  would otherwise defeat cross-run deduplication under `explore --runs N`.

## [1.3.0] - 2026-03-16

### Enhanced

- Memory reduction: all 7 file-processing scripts now accept `--max-files N` to cap file processing (default: unlimited).
- Memory reduction: `discover_python_files` converted to generators across 6 scripts.
- Memory reduction: `analyze_history.py` streams git log output instead of buffering.
- Memory reduction: `analyze_history.py` uses `-U0` diffs for function churn (zero context lines).
- Memory reduction: `analyze_imports.py` prunes intermediate fields after graph building.
- Memory reduction: `find_dead_symbols.py` drops per-file referenced_names after global accumulation.
- Memory reduction: `run_external_tools.py` early-stops parsing at max_findings limit.
- Memory reduction: explore/health/hotspots commands default to max 2 concurrent agents.
- Memory reduction: git-history-analyzer reuses git-history-context output instead of re-running script.

## [1.2.0] - 2026-03-16

### Enhanced

- External tool integration: 6 agents now incorporate findings from ruff, mypy, vulture, and coverage.py artifacts when available. Tools are optional — all agents work fully without them.
- explore command: Phase 0.5 runs external tools when available, with --skip-tools and --tools flags for control.
- dead-code-finder: merges ruff F401/F811/F841 and vulture findings with script output, deduplicating overlaps.
- silent-failure-hunter: incorporates ruff B (bugbear) and S (security) findings as additional bug-risk signals.
- complexity-simplifier: uses ruff SIM/RET/PERF findings as concrete simplification targets, with readability override.
- tech-debt-inventory: adds ruff UP (pyupgrade) deprecated-syntax findings to debt inventory.
- type-design-analyzer: incorporates mypy type errors to validate annotation accuracy and type design ratings.
- test-coverage-analyzer: uses coverage.py artifacts (XML/JSON) for precise line-level coverage when available, with freshness assessment.

## [1.1.0] - 2026-03-16

### Added

- `run_external_tools.py` script: detects, runs, and normalizes output from ruff, mypy, vulture, and reads coverage artifacts. Works when no tools are installed.
- Test suite for `run_external_tools.py` with coverage XML/JSON parsing, freshness assessment, tool detection, and CLI tests.
- Marketplace file (`.claude-plugin/marketplace.json`) for plugin discovery and installation.
- Installation instructions in both top-level README and plugin README (marketplace, direct, local, and manual methods).
- Prerequisites section documenting Python 3.10+ and Git requirements.
- Task-workflow skill for standardized development workflow (issue, branch, code, test, commit, PR, merge).
- CHANGELOG.md to track all notable changes.
- README.md with overview, quick start, and links to detailed plugin docs.
- MIT LICENSE crediting original and adapted authors.
- .gitignore (Python template).
- Test suite for all 6 plugin scripts (116 tests).
- project-docs-auditor agent for auditing out-of-code documentation (README, CLAUDE.md, config files) accuracy against the codebase.
- git-history-context agent: runs first in explore pipeline, provides churn metrics, change velocity, co-change clusters, and per-module stability as temporal context for all subsequent agents.
- git-history-analyzer agent: runs last in explore pipeline, performs fix completeness review, similar bug detection (fix propagation), feature review, churn×quality risk matrix, historical context annotation, and co-change coupling analysis.
- analyze_history.py script: queries git history for file/function churn, commit classification, recent fixes/features/refactors, and co-change clusters.
- Test suite for analyze_history.py (45 tests) including GitTempProject helper for git-based tests.

### Enhanced

- 6 agent prompts now invoke their corresponding analysis scripts for precise, machine-verified data before qualitative analysis: architecture-mapper, complexity-simplifier, test-coverage-analyzer, tech-debt-inventory, type-design-analyzer, dead-code-finder.
- All 11 agents now include a Classification Guide (FIX/CONSIDER/POLICY/ACCEPTABLE) for consistent finding categorization.
- consistency-auditor: split severity into correctness vs. readability dimensions with examples.
- complexity-simplifier: added "When NOT to Simplify" section (heterogeneous cases, intentional duplication, readable complexity) and abstraction cost validation.
- test-coverage-analyzer: risk-weighted ratings based on failure impact, code complexity, and change frequency.
- pattern-consistency-checker: behavioral similarity verification before flagging divergence, abstraction qualification for missing abstraction suggestions.
- api-surface-reviewer: breaking change classification ([breaking]/[additive]/[deprecation]) with migration path guidance.
- explore command: deduplication and conflict resolution in synthesis phase, classification-based summary template with "Tensions" section.
- health command: calibrated scoring rubric with anchor points, FIX count column, deduplication before scoring.
- architecture-mapper: classification tags on circular dependency findings.

### Fixed

- `typing_extensions` removed from `_STDLIB_TOP_LEVEL` in `analyze_imports.py` — it is a third-party package, not stdlib.
- Dead `elif` branch in `correlate_tests.py` `_match_test_to_source` — duplicate condition made subpackage matching unreachable.
- Missing trailing newline after `json.dump` in `analyze_history.py` output (6/7 scripts had it).
- Missing `.egg-info` directory exclusion in `analyze_history.py` `compute_function_churn_level2`.
- Unused variable `scores` removed from `measure_complexity.py`.
- 10 unused imports removed across `correlate_tests.py`, `helpers.py`, and 6 test files.
- Dead `"*.egg-info"` entry removed from `analyze_imports.py` exclude set (glob pattern in set intersection never matches).
- Unprotected `int()` calls in `analyze_history.py` `parse_args` now catch `ValueError` with clear error messages.
- Unknown CLI flags in `analyze_history.py` now produce a warning instead of being silently ignored.
- Broken `../pr-review-toolkit/` links removed from plugin README.
- Test helper `_SCRIPTS_DIR` path to point to `plugins/code-review-toolkit/scripts/`.
