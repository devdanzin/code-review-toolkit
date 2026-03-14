# Code Review Toolkit

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugin that bundles 14 specialized agents and 4 commands for exploring and analyzing existing codebases. It answers the question: **where are the problems in this codebase, and what should I fix first?**

## Installation

### From the marketplace (recommended)

Add this repository as a Claude Code marketplace, then install the plugin:

```bash
# Add the marketplace (one-time setup)
claude plugin marketplace add devdanzin/code-review-toolkit

# Install the plugin
claude plugin install code-review-toolkit@code-review-toolkit
```

Or use the interactive plugin manager:

```bash
# Open the plugin manager
/plugin

# Go to the Discover tab, find code-review-toolkit, and install
```

### Direct install from GitHub

Install the plugin directly without adding the marketplace:

```bash
claude plugin install code-review-toolkit --source github:devdanzin/code-review-toolkit --path plugins/code-review-toolkit
```

### Without installing (try it first)

Clone the repo and launch Claude Code with `--plugin-dir` — the plugin is loaded for that session only, nothing is installed:

```bash
# Clone the repository
git clone https://github.com/devdanzin/code-review-toolkit.git

# Run Claude Code with the plugin loaded for this session
claude --plugin-dir code-review-toolkit/plugins/code-review-toolkit
```

## Quick Start

After installation, these commands are immediately available in Claude Code:

```bash
/code-review-toolkit:map        # Understand project structure
/code-review-toolkit:health     # Quick health assessment
/code-review-toolkit:hotspots   # Find cleanup targets
/code-review-toolkit:explore    # Full exploration (all agents)
```

For your first time, start with `map` to understand the architecture, then `health` for a quick overview, then drill into specific areas with `explore`.

## What's Included

- **14 analysis agents** covering architecture, git history context, consistency, complexity, test coverage, error handling, documentation, project documentation accuracy, type design, dead code, tech debt, pattern consistency, API surface review, and git history analysis (fix propagation, churn×quality risk).
- **4 commands** (`explore`, `map`, `hotspots`, `health`) for different analysis workflows.
- **7 helper scripts** for complexity measurement, import analysis, dead symbol detection, test correlation, type counting, debt collection, and git history analysis.

For detailed usage, agent descriptions, and recommended workflows, see the [plugin README](plugins/code-review-toolkit/README.md).

## License

MIT — see [LICENSE](LICENSE) for details.

## Credits

Originally created by Daisy (Anthropic). Adapted by Daniel Diniz.
