# tools/

Harnesses that calibrate and validate the toolkit. **Not part of the plugin** — nothing here ships
to a user, and nothing in `plugins/` may import from here.

The distinction that matters: `plugins/code-review-toolkit/scripts/` answers questions about a
*reviewed project*. `tools/` answers questions about *the toolkit itself* — is a shape well
calibrated, is a confidence tier predictive, did a rule selection drift.

## Contents

| Tool | Answers |
|---|---|
| `shape_coverage.py` | What fraction of recorded findings map to a catalogued shape? (Phase 0's metric) |

## Conventions

- Take paths as arguments; never assume a checkout location.
- Print a human-readable summary to stdout. These are read by people, not piped into agents.
- A tool that measures something must print the **denominator** alongside every number.
