# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- New agent: `test-investigation-agent` — finds bugs by treating tests as invariant specifications. Reads existing tests to extract what developers believe should be true, maps those beliefs to structurally similar code, and checks whether the invariants hold everywhere they should.
- New script: `extract_test_invariants.py` — supporting script that extracts assertions from test files, classifies invariant types, maps tests to source functions, and finds structurally similar functions using name-pattern and signature matching. Three-tier test selection (bug-fix tests, error/boundary tests, churn-guided) with 30-test budget cap.
- Added `test-invariants` aspect to the explore command (Group D).

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
