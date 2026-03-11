---
description: "Quick architecture mapping — understand project structure and dependencies"
argument-hint: "[scope]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Task"]
---

# Architecture Map

Run only the architecture-mapper agent to quickly understand project structure, module boundaries, and dependency relationships.

**Scope:** "$ARGUMENTS" (default: entire project)

## Workflow

1. Identify project root and confirm scope
2. Launch **architecture-mapper** agent with specified scope
3. Present the architecture map directly — no synthesis needed

This is the fastest way to get oriented in a codebase. Use this before diving into specific analysis with other commands.

## Usage

```
/code-review-toolkit:map                  # Map entire project
/code-review-toolkit:map src/benchmarks   # Map specific package
/code-review-toolkit:map src/runner.py    # Map single file's dependencies
```
