# Code Review Toolkit

A comprehensive collection of specialized agents for exploring and analyzing existing codebases. While [pr-review-toolkit](../pr-review-toolkit/) reviews changes in a PR, this toolkit answers a different question: **where are the problems in this codebase, and what should I fix first?**

## Overview

This plugin bundles 14 expert analysis agents and 4 commands. Each agent focuses on a specific aspect of code quality and is designed for codebase-scale analysis — scanning entire modules or projects rather than reviewing diffs.

### Key Design Principles

- **Discovery-first**: Agents do a broad sweep, then offer ranked findings for drill-down
- **Context-aware**: Two foundational agents — architecture-mapper (structural) and git-history-context (temporal) — run first and feed their output to all other agents, so findings are contextualized by module importance and change patterns
- **Prioritized output**: Each agent caps its output to avoid overwhelming reports, ranking by severity and offering deeper analysis on request
- **Python-calibrated**: All agents are tuned for Python idioms (gradual typing, unittest, dynamic dispatch, `__init__.py` conventions, etc.)

## Commands

### `/code-review-toolkit:explore [scope] [aspects] [options]`

The primary command. Runs the foundational context providers (architecture-mapper + git-history-context) first, then dispatches selected agents with both structural and temporal context.

```bash
# Full exploration (all 14 agents)
/code-review-toolkit:explore

# Specific directory
/code-review-toolkit:explore src/benchmarks

# Specific aspects only
/code-review-toolkit:explore . complexity errors tests

# Quick summary mode
/code-review-toolkit:explore . all summary
```

**Aspects**: `architecture`, `history-context`, `history`, `history-full`, `consistency`, `complexity`, `tests`, `errors`, `docs`, `project-docs`, `types`, `dead-code`, `tech-debt`, `patterns`, `api`, `all`

**Options**: `deep` (full detail), `summary` (top-level only), `parallel` (concurrent agents)

### `/code-review-toolkit:map [scope]`

Quick architecture mapping only. The fastest way to get oriented.

```bash
/code-review-toolkit:map
/code-review-toolkit:map src/runner
```

### `/code-review-toolkit:hotspots [scope]`

Find cleanup targets: churn hotspots, complexity hotspots, dead code, and tech debt. Answers "where should I focus my cleanup efforts?"

```bash
/code-review-toolkit:hotspots
/code-review-toolkit:hotspots src/
```

### `/code-review-toolkit:health [scope]`

Quick health dashboard — all agents in summary mode, producing a scored table across every dimension.

```bash
/code-review-toolkit:health
```

## Agents

### Tier 1: Foundational

| Agent | Focus | Adapted From |
|-------|-------|-------------|
| **architecture-mapper** | Module structure, dependency graph, layering, circular deps | New |
| **git-history-context** | Churn metrics, change velocity, co-change clusters, module stability | New |
| **consistency-auditor** | Pattern divergence across codebase, convention discovery | code-reviewer |
| **complexity-simplifier** | Complexity hotspots ranked by severity, with simplification strategies | code-simplifier |

### Tier 2: Targeted Analysis

| Agent | Focus | Adapted From |
|-------|-------|-------------|
| **test-coverage-analyzer** | Source↔test correlation, undertested modules, coverage gaps | pr-test-analyzer |
| **pattern-consistency-checker** | Same concern solved different ways across modules | New |
| **silent-failure-hunter** | Swallowed exceptions, bare except, silent error patterns | silent-failure-hunter |
| **git-history-analyzer** | Fix completeness, similar bug detection, churn×quality risk matrix, historical context | New |

### Tier 3: Specific Concerns

| Agent | Focus | Adapted From |
|-------|-------|-------------|
| **documentation-auditor** | Docstring coverage, comment accuracy, stale docs | comment-analyzer |
| **type-design-analyzer** | Type hint coverage, dataclass design, Any overuse | type-design-analyzer |
| **dead-code-finder** | Unused imports, unreferenced functions, orphan files | New |
| **tech-debt-inventory** | TODOs/FIXMEs, deprecated usage, debt age analysis | New |
| **api-surface-reviewer** | Public API naming consistency, parameter conventions, learnability | New |
| **project-docs-auditor** | README/docs accuracy, cross-file consistency, reference validation | New |

## Recommended Workflows

### First Time Exploring a Codebase

```
1. /code-review-toolkit:map            → Understand structure
2. /code-review-toolkit:health         → Quick health assessment
3. /code-review-toolkit:explore . [weakest area] deep  → Deep dive
```

### Planning a Cleanup Sprint

```
1. /code-review-toolkit:hotspots       → Find cleanup targets
2. Address quick wins (dead code, unused imports)
3. Tackle complexity hotspots
4. /code-review-toolkit:health         → Verify improvement
```

### Before a Release

```
1. /code-review-toolkit:explore . api docs project-docs types  → Public surface quality
2. Fix API inconsistencies and documentation gaps
3. /code-review-toolkit:explore . errors tests history  → Reliability + fix completeness
```

### Ongoing Maintenance

```
# Monthly health check
/code-review-toolkit:health

# After major feature work
/code-review-toolkit:explore src/new_feature all

# Quarterly debt review
/code-review-toolkit:explore . tech-debt dead-code
```

## How Foundational Context Works

Two agents provide foundational context for all other agents:

**architecture-mapper** produces a structural model: module boundaries, dependency graph, fan-in/fan-out metrics, and layering. Other agents use it to:
- **Prioritize**: Findings in high fan-in modules (used by many others) are more critical
- **Contextualize**: A broad except in a CLI entry point is different from one in a core library module
- **Detect cross-cutting issues**: Patterns that span module boundaries vs. localized concerns

**git-history-context** produces a temporal model: churn metrics, change velocity, co-change clusters, and module stability. Other agents use it to:
- **Prioritize by volatility**: Findings in high-churn code are more urgent (and more likely to regress)
- **Detect recent changes**: Code flagged by another agent may have been recently changed intentionally
- **Focus testing effort**: High-churn + low-coverage areas are the highest-risk testing gaps

## Agent Configuration

All agents use `model: opus` for highest analysis quality. Each agent:

- Accepts a scope parameter (directory, file, glob, or whole project)
- Produces a summary tier (always shown, capped output) and a detail tier (available on request)
- Provides confidence ratings and severity levels for findings
- Includes specific file:line references and concrete fix suggestions

## Comparison with pr-review-toolkit

| Dimension | pr-review-toolkit | code-review-toolkit |
|-----------|------------------|-------------------|
| **Scope** | Git diff (recent changes) | Entire codebase or targeted scope |
| **Question** | "Are these changes good?" | "Where are the problems?" |
| **Discovery** | Knows what changed | Must discover structure first |
| **Output** | All findings shown | Ranked, capped, drill-down available |
| **Architecture** | Not needed (small diff) | Foundation for all analysis |
| **Agents** | 6 | 14 |
| **Use when** | Before creating a PR | Exploring, planning cleanup, health checks |

## Tips

- **Start with map or health** before deep exploration — orientation saves time
- **Use scope narrowing** after initial exploration to focus on problem areas
- **Run specific agents** for targeted questions rather than always running all
- **Address critical issues first** — the synthesis prioritizes findings
- **Re-run after fixes** to verify improvements, scoped to what you changed
- **Architecture context matters** — even if you only want one agent, the architecture context (via explore) significantly improves analysis quality

## Plugin Structure

```
code-review-toolkit/
├── .claude-plugin/
│   └── plugin.json
├── README.md
├── agents/
│   ├── architecture-mapper.md
│   ├── consistency-auditor.md
│   ├── complexity-simplifier.md
│   ├── test-coverage-analyzer.md
│   ├── pattern-consistency-checker.md
│   ├── silent-failure-hunter.md
│   ├── documentation-auditor.md
│   ├── type-design-analyzer.md
│   ├── dead-code-finder.md
│   ├── tech-debt-inventory.md
│   ├── api-surface-reviewer.md
│   ├── project-docs-auditor.md
│   ├── git-history-context.md
│   └── git-history-analyzer.md
└── commands/
    ├── explore.md
    ├── map.md
    ├── hotspots.md
    └── health.md
```

## Author

Danzin — adapted from Daisy's [pr-review-toolkit](../pr-review-toolkit/)
