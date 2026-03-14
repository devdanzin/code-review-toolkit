---
description: "Find cleanup targets — complexity hotspots, dead code, and tech debt"
argument-hint: "[scope]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Cleanup Hotspots

Run the four agents most useful for planning cleanup work: git-history-context (churn data), complexity-simplifier, dead-code-finder, and tech-debt-inventory. Answers the question: "Where should I focus my cleanup efforts?"

**Scope:** "$ARGUMENTS" (default: entire project)

## Workflow

1. Identify project root and confirm scope
2. Run **architecture-mapper** and **git-history-context** first (provide structural and temporal context)
3. Run in parallel, feeding both context outputs to each:
   - **complexity-simplifier** — find the hardest-to-maintain code
   - **dead-code-finder** — find code to remove
   - **tech-debt-inventory** — find accumulated debt markers
4. Synthesize into a prioritized cleanup plan:

```markdown
# Cleanup Priorities

## Quick Wins (< 30 minutes each)
[Dead code removal, unused import cleanup, stale TODO resolution]

## Medium Effort (1-4 hours each)
[Complexity hotspot simplification, tech debt resolution]

## Larger Refactors (> 4 hours)
[Structural simplifications, major debt paydown]

## Churn Hotspots (high modification frequency)
[Files/functions that change frequently — these benefit most from simplification, better tests, and better documentation because every future modification is cheaper if the code is cleaner]
```

## Usage

```
/code-review-toolkit:hotspots              # Entire project
/code-review-toolkit:hotspots src/runner    # Specific module
```
