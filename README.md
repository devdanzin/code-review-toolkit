# Code Review Toolkit

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that bundles 12 specialized agents and 4 commands for exploring and analyzing existing codebases. It answers the question: **where are the problems in this codebase, and what should I fix first?**

## Quick Start

Install the plugin, then run:

```bash
/code-review-toolkit:map        # Understand structure
/code-review-toolkit:health     # Quick health assessment
/code-review-toolkit:hotspots   # Find cleanup targets
/code-review-toolkit:explore    # Full exploration (all 12 agents)
```

## What's Included

- **12 analysis agents** covering architecture, consistency, complexity, test coverage, error handling, documentation, project documentation accuracy, type design, dead code, tech debt, pattern consistency, and API surface review.
- **4 commands** (`explore`, `map`, `hotspots`, `health`) for different analysis workflows.
- **Helper scripts** for complexity measurement, import analysis, dead symbol detection, test correlation, type counting, and debt collection.

For detailed usage, agent descriptions, and recommended workflows, see the [plugin README](plugins/code-review-toolkit/README.md).

## License

MIT — see [LICENSE](LICENSE) for details.

## Credits

Originally created by Daisy (Anthropic). Adapted by Daniel Diniz.
