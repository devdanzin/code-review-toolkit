# Reproduction convention

How a finding earns the word **reproduced**, and what the `status` field means.

This formalises what already worked: 47 of 60 coverage.py findings reached `status: reproduced` and
six harnesses were preserved. It also formalises what went wrong — see *Never patch-test in a live
checkout*, which cost a session and produced one confident, wrong finding.

---

## The status ladder

| `status` | What it claims | What is required |
|---|---|---|
| `candidate` | A scanner or an agent flagged it | Nothing beyond the flag. **Not** a finding yet |
| `confirmed` | A human read the code and the mechanism holds | A cited `file:line` and a concrete failure scenario: inputs → wrong outcome |
| `reproduced` | The failure was **observed** | A command and its output. Someone else can run it |
| `reported` | Filed or commented upstream | An issue or PR link |
| `fixed` | The fix landed | The commit |

**`confirmed` → `reproduced` is the expensive step and the one that matters.** A confirmed finding is
an argument; a reproduced finding is a fact. When a report mixes them, label every row — a reader
cannot tell them apart from the prose.

A finding that **fails** to reproduce does not disappear. It becomes `refuted`, and it stays in the
report with the evidence. **A negative result is a real result**: it is worth as much as a positive
one and it prevents the same hypothesis being re-derived next session.

---

## Never patch-test in a live checkout

**This is the rule that exists because it was broken.**

To prove a bug is load-bearing, the natural move is to re-introduce it (or apply the fix and watch
the symptom vanish). Doing that in the checkout under review corrupts the review itself:

- Another reviewer — or you, twenty minutes later — reads the modified file and produces a
  **confident, wrong finding** about code that was never in the tree.
- An agent that claims to have restored the file may not have. One did exactly that.

**Always work on a copy:**

```bash
# from the project root, at the commit under review
mkdir -p /tmp/repro && git archive HEAD | tar -x -C /tmp/repro
# or, if you need git history in the copy:
git worktree add /tmp/repro HEAD
```

Then patch, run, and observe in `/tmp/repro`.

**Verify the target tree yourself afterwards.** `git -C <project> status --short` must be clean, or
show only what was there before you started. Do not accept an agent's claim of restoration; check.

---

## Prove the repro exercised the tree it thinks it did

A reproduction that ran against different code than you believe is worse than no reproduction,
because it carries the authority of an observation. Three ways this happens, all seen:

- **Editable installs.** `pip install -e` means `import coverage` resolves to the working tree, not
  the copy you patched. Print `module.__file__` inside the harness and check it.
- **Stale `__pycache__`.** A `.pyc` from before your edit will be used if the mtime granularity
  works against you. Run with `-B`, or delete `__pycache__` in the copy.
- **`sys.path` order.** A test run from the project root puts the project first regardless of what
  you installed. Print `sys.path[:3]`.

Every preserved harness should begin by printing the resolved module path. It costs one line and it
converts "I think this ran the patched code" into evidence.

---

## What a preserved harness looks like

Store it under `repros/<FINDING-ID>/` in the findings repo, with:

- `repro.py` (or `repro.sh`) — self-contained, no arguments, exits non-zero on the bug
- `README.md` — the command, the expected output on a buggy tree, the expected output on a fixed
  tree, and the exact commit it was run against
- **no machine-specific paths.** One captured artifact embedded a local venv path and a CPython
  build path and had to be removed before the first push. Check before committing.

The two-tree contrast is what makes a harness durable: "prints 75% here, 100% there" survives a
refactor that moves every line number.

---

## Windowed fault injection

For a finding that depends on an allocation or syscall failing, injecting failure **everywhere** is
the wrong experiment: it masks the specific failure under a flood of unrelated ones, and the crash
you observe is usually not the one you are testing.

Use a **windowed, single-shot** injection — fail the Nth call and only the Nth — and sweep N. Then
patch-test to attribute: apply the candidate fix, re-run the same N, and confirm the crash moves or
vanishes. Attribution is what turns "it crashed under fault injection" into "this line is the cause".

---

## The `status` gate in synthesis

When a report is assembled, every finding must carry a `status`, and the summary must state the
mix — "38 FIX, of which 31 reproduced" rather than "38 FIX". A report that does not distinguish
argued findings from observed ones invites the reader to trust both equally, and the argued ones are
where the errors are.

**A finding with `status: candidate` does not belong in a report at all.** It belongs in the working
notes until someone reads the code.
