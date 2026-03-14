# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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

- Test helper `_SCRIPTS_DIR` path to point to `plugins/code-review-toolkit/scripts/`.
