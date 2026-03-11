---
description: "Find cleanup targets — complexity hotspots, dead code, and tech debt"
argument-hint: "[scope]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Cleanup Hotspots

Run the three agents most useful for planning cleanup work: complexity-simplifier, dead-code-finder, and tech-debt-inventory. Answers the question: "Where should I focus my cleanup efforts?"

**Scope:** "$ARGUMENTS" (default: entire project)

## Workflow

1. Identify project root and confirm scope
2. Run **architecture-mapper** first (provides context for complexity scoring)
3. Run in parallel, feeding architecture output to each:
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
```

## Usage

```
/code-review-toolkit:hotspots              # Entire project
/code-review-toolkit:hotspots src/runner    # Specific module
```
