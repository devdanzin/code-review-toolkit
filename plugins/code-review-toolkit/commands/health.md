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
2. Run **architecture-mapper** and **git-history-context** (produce structural and temporal context for all other agents)
3. Run all remaining agents with both context outputs, requesting summary-tier output only
4. Deduplicate before scoring: when the same issue is flagged by multiple agents, count it once. Do not let duplicate findings inflate the problem count.
5. Synthesize into a health dashboard:

```markdown
# Codebase Health Dashboard

| Dimension        | Status | Score | FIX | Top Finding |
|-----------------|--------|-------|-----|-------------|
| Architecture     | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Consistency      | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Complexity       | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Test Coverage    | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Error Handling   | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Documentation    | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Project Docs     | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Type System      | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Dead Code        | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Tech Debt        | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Pattern Consistency | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| API Surface      | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Change Velocity  | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |
| Fix Quality      | 🟢/🟡/🔴 | X/10 | N  | [1-line summary] |

## Overall Health: X/10

## Top 3 Priorities
1. [Most impactful improvement]
2. [Next]
3. [Next]

For detailed analysis, run:
  /code-review-toolkit:explore . [aspect] deep
```

## Scoring Rubric

Each dimension is scored 1-10 with these anchor points:

- **10**: Exceptional — no findings above ACCEPTABLE.  Rare; represents best-in-class.
- **8-9**: Healthy — only CONSIDER-level findings, no FIX items.  Minor improvements possible but nothing urgent.
- **6-7**: Good with gaps — a few FIX items and several CONSIDER items.  Worth addressing proactively.
- **4-5**: Concerning — multiple FIX items or systemic CONSIDER patterns.  Should be prioritized.
- **2-3**: Problematic — many FIX items, systemic issues, or critical gaps (e.g., no tests for core modules, silent failures in critical paths).
- **1**: Severe — fundamental issues that affect reliability or correctness across the codebase.

**Score deductions (guidelines, not rigid rules):**
- Each FIX finding: -0.5 to -1.0 depending on severity
- Systemic CONSIDER pattern (same issue across many files): -0.5
- Individual CONSIDER finding: -0.1 to -0.2
- POLICY items: no deduction (decisions, not problems)
- ACCEPTABLE items: no deduction

**Overall score**: Weighted average across dimensions, where dimensions with FIX findings are weighted more heavily.

🟢 8-10 | 🟡 5-7 | 🔴 1-4

## Usage

```
/code-review-toolkit:health              # Full project health
/code-review-toolkit:health src/         # Package health
```
