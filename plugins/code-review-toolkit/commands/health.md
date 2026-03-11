---
description: "Quick health dashboard — all agents in summary mode"
argument-hint: "[scope]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Codebase Health Dashboard

Run all agents in summary mode to produce a quick health dashboard. Each agent reports only its top-level findings — no deep analysis.

**Scope:** "$ARGUMENTS" (default: entire project)

## Workflow

1. Identify project root and confirm scope
2. Run **architecture-mapper** (produces context for all other agents)
3. Run all remaining agents with architecture context, requesting summary-tier output only
4. Synthesize into a health dashboard:

```markdown
# Codebase Health Dashboard

| Dimension        | Status | Score | Top Finding |
|-----------------|--------|-------|-------------|
| Architecture     | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Consistency      | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Complexity       | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Test Coverage    | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Error Handling   | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Documentation    | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Type System      | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Dead Code        | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Tech Debt        | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| Pattern Consistency | 🟢/🟡/🔴 | X/10 | [1-line summary] |
| API Surface      | 🟢/🟡/🔴 | X/10 | [1-line summary] |

## Overall Health: X/10

## Top 3 Priorities
1. [Most impactful improvement]
2. [Next]
3. [Next]

For detailed analysis, run:
  /code-review-toolkit:explore . [aspect] deep
```

## Scoring Guide

- 🟢 **8-10**: Healthy — minor improvements possible
- 🟡 **5-7**: Concerning — should address proactively
- 🔴 **1-4**: Problematic — needs immediate attention

## Usage

```
/code-review-toolkit:health              # Full project health
/code-review-toolkit:health src/         # Package health
```
