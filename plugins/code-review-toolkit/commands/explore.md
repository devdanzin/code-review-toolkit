---
description: "Comprehensive codebase exploration and analysis using specialized agents"
argument-hint: "[scope] [aspects] [options]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Comprehensive Codebase Exploration

Run a comprehensive analysis of an existing codebase using multiple specialized agents, each focusing on a different aspect of code quality. The architecture-mapper always runs first, and its output is fed to subsequent agents as context.

**Arguments:** "$ARGUMENTS"

## Argument Parsing

Parse arguments into three categories:

**Scope** (path or glob):
- `.` or omitted → entire project (default)
- `src/module` → specific directory tree
- `src/file.py` → specific file
- `**/*.py` → glob pattern

**Aspects** (which agents to run):
- `architecture` → architecture-mapper only
- `consistency` → consistency-auditor
- `complexity` → complexity-simplifier
- `tests` → test-coverage-analyzer
- `errors` → silent-failure-hunter
- `docs` → documentation-auditor
- `types` → type-design-analyzer
- `dead-code` → dead-code-finder
- `tech-debt` → tech-debt-inventory
- `patterns` → pattern-consistency-checker
- `api` → api-surface-reviewer
- `all` → all agents (default)

**Options**:
- `deep` → full detail, no output truncation
- `summary` → summary tier only (faster)
- `parallel` → run agents concurrently where possible

## Execution Workflow

### Phase 0: Project Discovery

Before launching any agents:
1. Identify the project root (look for pyproject.toml, setup.cfg, setup.py, .git)
2. Count source files and test files in scope
3. Check for CLAUDE.md or equivalent project documentation
4. Determine project language(s) and framework(s)
5. Print a brief project summary to confirm scope

### Phase 1: Architecture Mapping (always runs first)

Launch the **architecture-mapper** agent with the specified scope.

This is the foundation — its output provides module boundaries, dependency relationships, and structural context that enriches every subsequent agent.

Store the architecture-mapper output for injection into Phase 2 agents.

### Phase 2: Targeted Analysis

Based on the requested aspects (default: all), launch the appropriate agents. Each agent receives:
- The specified scope
- The architecture-mapper output as additional context
- Any relevant CLAUDE.md content

**Agent dispatch order** (sequential by default):

**Group A — Structural analysis** (benefits most from architecture context):
1. consistency-auditor
2. pattern-consistency-checker

**Group B — Code quality analysis**:
3. complexity-simplifier
4. silent-failure-hunter
5. dead-code-finder

**Group C — Interface and documentation**:
6. test-coverage-analyzer
7. documentation-auditor
8. type-design-analyzer
9. api-surface-reviewer

**Group D — Inventory**:
10. tech-debt-inventory

If `parallel` is specified, run agents within each group concurrently. Groups still execute sequentially because later groups may benefit from earlier findings.

### Phase 3: Synthesis

After all agents complete, produce a unified summary:

```markdown
# Codebase Exploration Report

## Project: [name]
## Scope: [what was analyzed]
## Agents Run: [list]

## Executive Summary

[3-5 sentence overview of codebase health across all dimensions analyzed]

## Key Metrics
- Architecture: [healthy/concerning/problematic] — [1-line summary]
- Consistency: [healthy/concerning/problematic] — [1-line summary]
- Complexity: [N hotspots found, N critical]
- Test Coverage: [N modules untested, N critical gaps]
- Error Handling: [N silent failures, N critical]
- Documentation: [X% coverage, N accuracy issues]
- Type System: [X% annotated, N design issues]
- Dead Code: [N items identified]
- Tech Debt: [N markers, age distribution summary]
- API Surface: [learnability score X/10]

## Critical Issues (must address)

[Aggregated from all agents — issues rated critical/high by any agent]
- [agent-name]: Issue description [file:line]

## Important Issues (should address)

[Aggregated medium-priority issues]
- [agent-name]: Issue description [file:line]

## Strengths

[What the codebase does well — aggregated positive findings]

## Recommended Action Plan

### Immediate (this week)
1. [Critical issue fix]
2. [Critical issue fix]

### Short-term (this month)
1. [Important improvement]
2. [Important improvement]

### Ongoing
1. [Convention to establish]
2. [Practice to adopt]
```

## Usage Examples

**Full exploration (default):**
```
/code-review-toolkit:explore
```

**Specific scope:**
```
/code-review-toolkit:explore src/benchmarks
```

**Specific aspects:**
```
/code-review-toolkit:explore . complexity errors
# Only complexity and error handling analysis

/code-review-toolkit:explore . tests docs
# Only test coverage and documentation
```

**Quick summary:**
```
/code-review-toolkit:explore . all summary
# All agents, summary output only
```

**Deep dive on a module:**
```
/code-review-toolkit:explore src/runner.py all deep
# All agents, full detail, single file
```

## How Architecture Context Flows

When the explore command passes architecture-mapper output to other agents, frame it as:

```
[Include architecture-mapper output]

The above is the architecture analysis of this project. Use it to:
- Understand module boundaries and responsibilities
- Prioritize findings in high-traffic/high-fan-in modules
- Identify when an issue is localized vs. cross-cutting
- Calibrate severity based on where code sits in the dependency graph
```

## Tips

- **Start broad, then narrow**: Run with `summary` first, then drill into specific aspects
- **Architecture first**: Even if you only want one aspect, the architecture context significantly improves the analysis
- **Prioritize by criticality**: Focus on critical issues from the synthesis before medium/low
- **Re-run after fixes**: Use specific aspects to verify that addressed issues are resolved
- **Scope to what changed**: After fixing issues, run specific agents on the modified scope
