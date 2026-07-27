# Informed-review briefing

Read this before your own analysis. It exists so you **confirm without re-litigating**, **suppress known false positives**, and spend the run hunting un-found siblings of established shapes rather than rediscovering the basics from scratch.

## Cross-cutting triage rules

1. **Guarded twin.** Most real defects have a sibling in the same codebase that
   already does it right. Find that twin — it is both proof the shape is a bug
   *in this project's own judgement* and the exact fix to propose. A shape with
   no twin anywhere may be a deliberate project-wide convention.
2. **Systemic root over instance count.** Ten instances of one shape is one
   finding with ten sites, not ten findings. Report the root and enumerate the
   sites; that is what a maintainer can act on in a single change.
3. **Silent beats loud.** A defect that raises is already visible to its
   authors; a defect that silently produces wrong results is not. When ranking,
   weight the silent shapes above the noisy ones even when severity ties.
4. **Behavioural divergence outranks stylistic.** Two modules formatting
   differently is noise. Two modules *handling the same error case differently*
   is a finding — one of them is wrong.
5. **Confirm, don't re-litigate.** Anything listed below as already-confirmed is
   settled. Verify it still exists and move on; spend the run on un-found
   siblings, not on re-deriving known results.
6. **Cite or drop.** Every finding needs `file:line` and a concrete failure
   scenario (inputs → wrong outcome). A finding you cannot make concrete is a
   hypothesis; label it as one or drop it.
7. **NEVER edit the reviewed tree.** Not to patch-test, not to mutation-test,
   not "just to check". Work on a copy:

       mkdir -p /tmp/repro && git -C <project> archive HEAD | tar -x -C /tmp/repro

   A review often runs many agents over one checkout at once. A file you
   modified is a file every other agent then reads wrongly, and one of them
   will report a confident, false finding about code that was never there.
   Restoring it afterwards does not undo that — the window is what does the
   damage. If you did edit the tree, say so plainly in your report; it will be
   verified independently either way.

## Bug-shape templates (97)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

### Owned by `api-surface-reviewer`

#### `unreachable-name-in-a-closed-vocabulary` — A producer emitting a name that the consumer's grammar cannot express

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** One component emits symbolic names into a closed vocabulary -- key names, event names, capability names -- and the consumer matches them against names written in a restricted grammar. A name the grammar cannot spell can never be matched, so the feature it belongs to is unreachable no matter how the user configures it.
- **Guarded twin (the fix):** Every other name in the same producer table, all of which the grammar accepts. The odd one out is the finding, and the majority is the specification.
- **Sibling hunt:** Extract the producer's full name table and the consumer's grammar, and test EVERY name for expressibility. Then check the reverse direction for names the grammar can express that nothing ever emits. This is a set-difference over two closed vocabularies and should be exhaustive rather than sampled.
- **Expected behaviour:** every name a producer can emit can be named by the consumer that binds behaviour to it.
- **Surfaces as:** As a feature that does nothing -- a key that beeps, an event nobody can subscribe to -- with no error anywhere.
- **Do NOT flag when:** A name deliberately reserved for internal dispatch and never intended to be bound is fine -- check whether the consumer is supposed to see it at all. Extending the grammar and renaming the emission are both valid fixes; say which the project's compatibility constraints allow.
- **Confirmed instances:** CRF-PYREPL-0018 -- the event queue emits a key name no keyspec can express, so keypad Enter can never be bound

### Owned by `complexity-simplifier`

#### `guarded-twin-with-false-reasoning` — A guard present on one sibling and absent on the others, where the stated reason is false

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** One of several structurally identical callbacks checks for a condition, behind a comment recording that the condition HAS been observed. Its siblings carry the same reasoning without the check. Each sibling would genuinely fail if reached -- but on current versions they are unreachable for an unrelated reason, so the code is safe by accident rather than by design.
- **Guarded twin (the fix):** The sibling that does check, and whose guard provably fires on an older runtime version. That version difference is the cleanest available evidence and turns an argument into a measurement.
- **Sibling hunt:** Where one member of a callback family checks something its siblings do not, take the guard's comment seriously and try to reach each unguarded sibling. Probe ACROSS RUNTIME VERSIONS -- a hole the runtime closed in a later release means the guards are load-bearing on the versions the project still supports. Then ask what would re-open it: a fourth registration path, or a revert upstream.
- **Expected behaviour:** safety comes from the code's own reasoning, and that reasoning is true.
- **Surfaces as:** Currently NOT AT ALL. It is a latent shape whose value is the argument it starts, and investigating it is how adjacent live bugs get found.
- **Do NOT flag when:** Downgrade to CONSIDER once unreachability is PROVEN rather than assumed -- and prove it by probing the runtime, not by reading. Report the false reasoning even so: the code's own stated justification being wrong is the durable part. Investigating this shape is high-yield even when the finding itself is downgraded.
- **Confirmed instances:** CRF-COVPY-0022 -- three callbacks index a map unguarded where their sibling checks; unreachable only because the runtime closed the hole, verified by a cross-version probe

### Owned by `documentation-auditor`

#### `doc-describes-a-superseded-model` — A docstring or rationale describes an architecture the code no longer has

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A class docstring or an inline justification states an invariant or a reason that was true when written and is false for the current default configuration -- 'installs a function to create a tracer for each new thread' after the default backend stopped doing that; 'the GIL is held for the duration of the copy' in a project shipping free-threaded wheels. The conclusion is often still correct; the stated REASON is not, which is worse than no comment because the next maintainer reasons from it.
- **Guarded twin (the fix):** A sibling declaration that WAS updated -- a Protocol, a constants module, a newer backend whose own comment states the opposite invariant in-tree. That asymmetry is what proves the drift rather than merely asserting it.
- **Sibling hunt:** For each architectural change the project has been through (a new default backend, a new concurrency model, a removed subsystem), grep for prose asserting the old model as universal fact, and check `git blame` -- fresh dates mean live debt rather than archaeology. Then verify the claim at runtime rather than by reading: construct the object under the current default and check the invariant.
- **Expected behaviour:** a stated invariant holds under the project's default configuration, and a stated rationale is still the reason the code is safe.
- **Surfaces as:** NEVER at runtime. It surfaces as a maintainer making a wrong change confidently, which is precisely when it is most expensive.
- **Do NOT flag when:** Distinct from `refactor-changed-behaviour-doc-did-not`, which is about a function's own observable contract and can be checked by calling it. This one is about a MODEL or a RATIONALE and can only be checked by understanding the system. A comment that is merely incomplete is not this shape; the claim must be false.
- **Confirmed instances:** CRF-COVPY-0051 -- Collector's docstring is false for the default core on 3.14+, contradicted by another module in-tree; CRF-COVPY-0052 -- two GIL-based justifications in a project shipping free-threaded wheels, blamed to a fresh date

#### `refactor-changed-behaviour-doc-did-not` — A docstring contradicts what the function does, provable by calling it

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A docstring states a return value, a parameter, or a guarantee that the body does not deliver -- 'if n is 1, return thing' from a function that returns '1 thing'; a documented parameter that has never existed; a `.. versionadded::` for a name that was never the name. The highest-severity instances are the ones rendered into published API documentation by Sphinx, and the ones a second module delegates to as its own documentation.
- **Guarded twin (the fix):** None in-tree -- but the function itself is the oracle. Call it with the documented input and compare.
- **Sibling hunt:** For every public docstring, extract each falsifiable claim (a return value, a parameter name, a count, a version) and CHECK IT by execution or by reading the signature. Prioritize docstrings that ship to users through Sphinx, and docstrings that another module reuses as its own help text -- an error there is load-bearing twice. A documented parameter name that does not appear in the signature is the cheapest and most reliable query.
- **Expected behaviour:** every falsifiable claim in a docstring holds when the function is called.
- **Surfaces as:** NEVER at runtime. It surfaces as a user or plugin author following the documentation and crashing.
- **Do NOT flag when:** Vagueness is not falsity. The claim must be checkable and wrong. Distinguish from `doc-describes-a-superseded-model` (a rationale, not a contract) and from `dead-cross-reference-in-a-docstring` (a pointer to a name that no longer exists).
- **Confirmed instances:** CRF-COVPY-0054 -- four docstrings contradicted by calling the function, including one describing machinery deleted months earlier; CRF-COVPY-0055 -- four public API docstrings rendered to Sphinx, one documenting a parameter that never existed

#### `dead-cross-reference-in-a-docstring` — A docstring points at a function, parameter, or module that no longer exists

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `See `foo()` for details`, `:func:`bar``, 'the `package` parameter' -- naming an entity that has been renamed or deleted. The dangerous variant is when an UNRELATED entity of the same name survives elsewhere in the project: the reference then resolves in the reader's head to the wrong thing, which is worse than a dangling pointer.
- **Guarded twin (the fix):** None -- but the check is mechanical: extract the referenced name, then test whether it exists in the module, the package, or the builtins.
- **Sibling hunt:** Grep every docstring for backticked identifiers, `:func:`/`:meth:`/`:class:` roles, and the phrases 'see', 'as in', 'like', 'the ... parameter'. Resolve each name against the current tree. Then check the survivors for the same-name-elsewhere trap. Cheap enough to run in CI, and in the confirmed corpus this was the single most productive query in an entire documentation audit.
- **Expected behaviour:** every name a docstring cites resolves to the thing it means.
- **Surfaces as:** NEVER at runtime. Surfaces as a reader chasing a name that is not there, or worse, finding a different one.
- **Do NOT flag when:** A reference to a genuinely external entity (a stdlib function, another project) is not dead -- resolve against the environment before reporting. Prose that happens to be backticked is not a reference. A documented parameter missing from the signature belongs to `refactor-changed-behaviour-doc-did-not`.
- **Confirmed instances:** CRF-COVPY-0053 -- eight docstrings citing renamed or deleted entities, one up to ten years stale and actively misleading because an unrelated closure of that name survives

#### `process-marker-invisible-to-its-own-checklist` — A maintenance marker spelled differently from what the process document searches for

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A project marks places needing attention at release or upgrade time with a grep-able token, and a checklist tells the maintainer to search for it -- but one or more live markers are spelled differently (singular vs plural, different case, a typo). Those markers carry real claims and are invisible to the only process that would revisit them.
- **Guarded twin (the fix):** The correctly-spelled markers elsewhere in the tree -- the majority spelling is the convention, and the count of it is the argument.
- **Sibling hunt:** Read the process documents (a release howto, a CONTRIBUTING file, a Makefile target) for every literal string they instruct someone to search for. Then grep case-insensitively for near-misses of each token and diff against what the documented search would find. Apply the same test to `# noqa`, `# pragma`, and `# type:` style markers whose spelling the tooling pins.
- **Expected behaviour:** every marker in the tree is found by the search the checklist prescribes.
- **Surfaces as:** NEVER. It surfaces as a stale version claim shipping in a release.
- **Do NOT flag when:** A marker in a vendored or generated file is not the project's to fix. A near-miss spelling that carries no live claim is cosmetic -- read what the marker says before rating it.
- **Confirmed instances:** CRF-COVPY-0058 -- two live markers spelled PYVERSION where the release checklist greps for PYVERSIONS, against 19 correctly-spelled siblings

### Owned by `git-history-analyzer`

#### `coverage-claiming-commit-that-reduced-coverage` — A commit claiming to add test coverage that removed it

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A commit whose message claims to increase coverage while its diff has a NEGATIVE net assertion count in the touched test files -- assertions replaced by a loop that runs zero times, a parametrize list emptied, a test renamed out of discovery.
- **Guarded twin (the fix):** The assertions the commit deleted; they are in the diff, ready to restore.
- **Sibling hunt:** Diff ASSERTION counts, not line counts, for every commit whose message contains coverage/test/regression. Line counts go up while coverage goes to zero, which is exactly how this passes review.
- **Expected behaviour:** a coverage commit increases the behaviour the suite can detect.
- **Surfaces as:** NEVER. The suite stays green, the diff looks like more test code, and the coverage report does not distinguish an executed assertion from an unexecuted one.
- **Do NOT flag when:** A commit that legitimately replaces many small assertions with one stronger one also shows a negative count. Read what the replacement asserts before concluding.
- **Confirmed instances:** CPython _pyrepl test_keymap.py:33-40 (6080c86) -- commit 73ab83b27f1, "Increase test coverage for keymap", replaced three passing assertions with `for key in []`. Coverage of the whole \C- path went to zero and stayed there roughly two years, hiding a live IndexError at keymap.py:124. Found by reports/pyrepl_v1.

#### `incomplete-fix-residue-at-an-answered-todo` — A TODO the fix already answered, left in place

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A TODO/FIXME/XXX whose question a later commit resolved, left behind in the code. The residue misleads the next reader into re-solving a solved problem, or into believing the surrounding code is provisional when it is not.
- **Guarded twin (the fix):** The commit that answered it -- `git log -S` on the marker's own text finds it.
- **Sibling hunt:** For every debt marker, `git log -S` its text and read the commits that touched the same function afterwards.
- **Expected behaviour:** a marker describes work that still needs doing.
- **Surfaces as:** Not a runtime defect -- it costs review attention and misdirects future changes.
- **Do NOT flag when:** A marker that names a REMAINING part of a partially-applied fix is still live. Only flag one whose question the fix fully answered.

#### `fix-not-propagated-to-sibling-path` — A guard or fix applied to one member of a family, with the siblings left as they were

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** One call site, method, or branch acquires a guard -- a lock, a `.copy()`, a `no_disk` test, a stderr redirect, a try/except -- and the structurally identical siblings in the same class, function, or module do not. Often traceable to a commit that fixed the reported instance and stopped there.
- **Guarded twin (the fix):** The sibling that received the fix. When the fix has a commit, that commit's diff IS the specification: everything it touched is the twin, and everything matching its pattern that it did not touch is the finding.
- **Sibling hunt:** Take the fix commit, abstract its diff to a pattern, and grep the whole tree for that pattern excluding what the commit changed. Then check the reverse: a guard present on four of five sibling methods marks the fifth. Read the fix's own test -- in the confirmed corpus the test added alongside a fix asserted something weaker than the fix, so it passed while the bug was live.
- **Expected behaviour:** every member of the family that can reach the same failure carries the same guard.
- **Surfaces as:** SILENT or as a rare exception under load. The fixed path is the one anyone reproduces, so the bug reads as fixed.
- **Do NOT flag when:** A sibling that cannot reach the failure does not need the guard -- prove reachability before reporting. If the guard was deliberately omitted, the omission usually carries a comment; its absence is part of the evidence. Distinguish from `fix-reverted-and-never-relanded`, where the fix landed everywhere and was then backed out.
- **Confirmed instances:** CRF-COVPY-0001 -- the reaper's close(force=True) defeats exactly the no_disk guard close() carries; CRF-COVPY-0012 -- three sibling dicts got .copy() in PR #2165, the fourth did not; CRF-COVPY-0041 -- 'write messages to stderr' established the channel and never touched cmdline.py; CRF-COVPY-0059 -- write() lacks the no_disk guard its four siblings have; CRF-IDLELIB-0025 -- Idb.user_exception calls the GUI bare where the twin user_line wraps it in try/except TclError

#### `guard-catches-wrong-exception-set` — An except clause narrower than what the call it wraps can raise

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A try block names a specific exception set, and a call inside it can raise something outside that set -- typically because a refactor swapped the callee. The classic instance is source-reading code that catches OSError and NoSource but not the SyntaxError a bad encoding cookie raises from `tokenize.detect_encoding`. A SECOND try block later in the same function often catches exactly the missing exception, which is the proof of intent.
- **Guarded twin (the fix):** The other try block in the same function whose except list is complete, or the exception list the REPLACED callee needed. When a commit swaps a callee, the old except list is the specification of what the author thought could go wrong.
- **Sibling hunt:** For every narrow except clause, enumerate what the wrapped calls can actually raise -- follow one level into the callee. Prioritize try blocks whose callee was changed by a recent commit: the except list is the part refactors forget. Check whether the class of bug was closed by an earlier issue; a regression re-opening a closed class is a stronger report than a fresh one.
- **Expected behaviour:** the except clause covers everything the wrapped calls can raise for the inputs the function is documented to accept.
- **Surfaces as:** As an UNCAUGHT exception escaping to a place with no handler -- often mid-measurement or mid-render, so it aborts the operation rather than degrading it.
- **Do NOT flag when:** A deliberately narrow clause that lets other exceptions propagate is correct design -- the test is whether the escaping exception reaches a handler that can do something sensible. The establishing commit's own message often names the trigger class, which settles intent quickly.
- **Confirmed instances:** CRF-COVPY-0004 -- SyntaxError from a bad coding cookie escapes a clause catching only OSError and NoSource, introduced when a refactor replaced the parser

#### `fix-reverted-and-never-relanded` — A merged fix backed out for a side effect, with no issue left open to finish it

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A pull request fixes a real bug, is merged, and is reverted days later because it broke something adjacent -- with a revert message promising a better fix. No follow-up issue is opened, the original issue stays closed, and the bug is live indefinitely while every tracker signal says it was fixed.
- **Guarded twin (the fix):** The reverted commit itself: it is a complete, reviewed specification of the fix, and the revert message names the one constraint it violated.
- **Sibling hunt:** Search the log for reverts of merges (`git log --grep=revert`, `--grep=reverting`), then for each one check whether ANY later commit touched the same function -- `git log -L` over the function from the revert to HEAD returning zero commits is the finding. Cross-check the tracker: a closed issue with a reverted fix and no successor is the highest-confidence instance of this shape and the most valuable single query in a history audit.
- **Expected behaviour:** a bug that was fixed and unfixed has an open, findable record that it is still live.
- **Surfaces as:** As the ORIGINAL bug, still reproducible, against a tracker that says it is closed.
- **Do NOT flag when:** A revert followed by a re-land under another name is not this shape -- search by function, not by PR number. A revert whose original bug turned out not to exist is fine. Report the tracker gap as part of the finding: re-opening the issue is usually the most useful first move.
- **Confirmed instances:** CRF-COVPY-0013 -- a thread-correctness fix merged then reverted two days later; zero commits to the function in the eleven months since, no follow-up issue

### Owned by `pattern-consistency-checker`

#### `one-concern-implemented-per-backend` — One concern implemented separately in each interchangeable backend, so some backends miss it

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A project offers N interchangeable implementations of one interface -- report formats, tracer cores, storage drivers, platform consoles -- and a cross-cutting concern (a config option, a skip flag, a warning, a self-check, a lifecycle call) is implemented inside each backend rather than hoisted into the shared driver. Some backends have it, some do not, and the user-visible behaviour of the SAME input then depends on which backend they chose.
- **Guarded twin (the fix):** The subset of backends that do implement it. The fix is almost never 'add it to the stragglers' -- it is to hoist the concern into the shared prepare/finalize lifecycle so a new backend cannot be written without it.
- **Sibling hunt:** Enumerate the interchangeable implementations, then build a FEATURE x BACKEND matrix and look at every cell that is not full. Do not stop at the first gap: in the confirmed corpus one such matrix yielded skip_covered honoured by 2 of 6 backends, skip_empty by 4 of 6, and four mutually incompatible notions of region reporting. Also check the INVERSE: a concern implemented as mutable state on a shared object leaks between backends invoked in one process.
- **Expected behaviour:** identical input produces the same answer to the same question regardless of which backend renders it, and a concern the project considers universal is enforced in one place.
- **Surfaces as:** SILENT. Each backend is internally consistent and its own tests pass; the divergence is only visible when two backends are run over the same input and compared, which no test suite does by default.
- **Do NOT flag when:** Backends that are NOT interchangeable do not carry this shape -- a debug renderer and a production renderer are allowed to differ. The test is whether a user selects between them for the same task via one config knob. A concern absent from EVERY backend is a missing feature, not this shape; the signal is the partial matrix. Deprecated backends weaken but do not void a finding -- say so rather than dropping them.
- **Confirmed instances:** CRF-COVPY-0010 -- [report] contexts honoured by 3 of 6 report backends, and leaks across reports in one process; CRF-COVPY-0028 -- dotted plugin names configurable from INI but not TOML; CRF-COVPY-0029 -- $VAR substitution applied to plugin options in INI but not TOML; CRF-COVPY-0032 -- zero-statement projects: two backends claim 100%, and --fail-under splits four ways; CRF-COVPY-0043 -- skip flags and region support differ across all six report backends; CRF-COVPY-0003 -- CTracer never calls its warn member, so a settrace hijack truncates data silently where PyTracer reports it; CRF-COVPY-0009 -- tracer backends disagree about which threads are measured

#### `same-fact-derived-from-two-sources` — One fact computed two different ways, so the two answers can disagree

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A predicate or quantity is derived from a stored declaration in one place and recomputed from the underlying data in another -- `has_arcs` read from a meta key here and inferred from whether the arc table is non-empty there; a branch total counted from exit_counts here and from a filtered arc list there. As long as the two agree the duplication is invisible; the bug is whichever operation can move one source without the other.
- **Guarded twin (the fix):** Whichever site the project treats as authoritative -- usually the declared/stored one. The fix is to route both readers through it, not to make the second derivation smarter.
- **Sibling hunt:** For each such fact, enumerate every site that answers the question and diff their inputs. Then look for the WRITE that can desynchronize them: in the confirmed corpus a branch-mode run that measured nothing wrote has_arcs=1 while leaving the arc table empty, which is the single reachable divergent state.
- **Expected behaviour:** every consumer of the fact gets the same answer, and no sequence of public operations can put the two sources out of step.
- **Surfaces as:** SILENT, and typically surfaces far downstream as two report formats disagreeing, or as an unexpected 'cannot combine' error -- or its absence.
- **Do NOT flag when:** Deliberate redundancy used as a cross-check (assert the two agree) is the guarded twin, not the bug. Two derivations that are provably equal by construction are fine -- the question is whether any public operation can move one and not the other.
- **Confirmed instances:** CRF-COVPY-0030 -- update() derives lines-vs-arcs from table contents while the compatibility guard uses the meta key; CRF-COVPY-0031 -- no_branch pragma filtered out of the arc lists but not the branch counters; CRF-COVPY-0047 -- env.py and igor.py read the same environment variable with different truthiness rules

#### `two-sides-of-a-comparison-normalized-differently` — A write path and a read path normalize the same key with different rules

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A value is used as a lookup key on both sides of a store -- a filename, a URL, a config name -- and the two sides apply different normalization. Typically the write path canonicalizes (realpath, casefold, strip) and the read path skips a step, often deliberately and under a config flag that was meant to change only what happens AFTER canonicalization.
- **Guarded twin (the fix):** The configuration where the two sides happen to agree -- that is why the bug survives the test suite. The fix is a single `normalize_for_key()` used by both, with the flag parameterizing what happens after it, never replacing it.
- **Sibling hunt:** For each key type, list every site that produces the key and every site that consumes it, then diff the transformation chains. Pay attention to conditionals INSIDE the chain: a flag that skips a canonicalization step is the shape. Test with the identity broken on purpose -- a symlink, a case-different path, a trailing slash.
- **Expected behaviour:** the same underlying artifact yields the same key from every path, under every configuration.
- **Surfaces as:** SILENT -- as an empty or 0% result, a missing entry, or a duplicated entry, with no error. Usually invisible under the default configuration, which is why it can live for years.
- **Do NOT flag when:** Two spellings that are genuinely different artifacts should produce different keys -- confirm the sides are meant to match. A normalization applied on only one side is fine if that side is the only producer. Adjacent findings can share a symptom and have distinct mechanisms; do not fold them together on symptom alone.
- **Confirmed instances:** CRF-COVPY-0014 -- relative_files=True skips canonicalization on the read path only; every symlinked file reports 0%; CRF-COVPY-0015 -- omit/include patterns are realpath-resolved only when they do not start with a wildcard

#### `off-by-one-against-a-correct-sibling` — An index or offset error in one branch of a family whose siblings get it right

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** One branch of a dispatch, or one member of a family of near-identical functions, indexes 1-based into a 0-based sequence, passes `end + 1` to a helper that treats the range as half-open, or omits a normalization step its siblings apply. The adjacent branches are correct, so the arithmetic looks reviewed.
- **Guarded twin (the fix):** The sibling branch -- frequently ten lines above in the same function. The diff between the two is the whole finding.
- **Sibling hunt:** Where a function dispatches on an opcode, a token, or a command name, put the branches side by side and diff their arithmetic literally. Then check the callee: an off-by-one that DEFEATS a guard (passing `eol + 1` to a helper that returns early on an empty range) is worse than one that merely shifts a result, because the guard's author believed it was covered.
- **Expected behaviour:** every branch of the family computes the same index convention, and a guard in a shared helper actually fires.
- **Surfaces as:** SILENT for the common inputs and wrong at the boundary -- an extra character killed, a cursor on the wrong line -- so it survives casual testing.
- **Do NOT flag when:** Branches that handle genuinely different conventions are allowed to differ -- read the specification the branch implements. The evidence is that a SIBLING implementing the same convention does it differently, not that the arithmetic looks unusual on its own.
- **Confirmed instances:** CRF-PYREPL-0004 -- one tparm branch indexes 1-based into a 0-based tuple and drops a normalization the sibling applies; CRF-PYREPL-0017 -- kill_line passes eol + 1, so the helper's empty-range guard never fires

#### `public-setter-skips-the-validation-the-loader-runs` — A programmatic setter that bypasses the post-processing the file loader performs

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** Configuration has two entry points: a file loader that parses and then runs a `post_process()` step, and a public `set_option()` that is a bare `setattr`. Everything post_process does -- merging additive options into their lists, implying one setting from another, validating regexes and enum values -- silently does not happen for the programmatic path, which is the one integration libraries use.
- **Guarded twin (the fix):** The loader, which does call post_process. Its call site is usually the ONLY one, which is itself the finding: semantics that belong to the object have been attached to one path into it.
- **Sibling hunt:** Find the post-load normalization step and count its callers. One caller means every other entry point is unnormalized. Then diff what the two paths accept: set an additive option, a derived option, and a malformed regex through each, and compare. Check the documentation -- if the setter is advertised as equivalent to the config file, this is a contract violation rather than misuse.
- **Expected behaviour:** setting an option programmatically has the same effect as setting it in the configuration file.
- **Surfaces as:** SILENT for the additive options (a pure no-op) and as a LATE, misplaced error for the validated ones -- a malformed regex surfaces from inside reporting instead of at load time.
- **Do NOT flag when:** Fine if the setter is documented as low-level and the project offers a normalizing alternative. The severity comes from the setter being public API with an advertised parity claim, and from it being the path integration libraries take.
- **Confirmed instances:** CRF-COVPY-0027 -- set_option is pure setattr; additive options never merge, implied settings never imply, and validation is deferred to a raw error deep in reporting

#### `one-predicate-two-implementations` — A decision procedure implemented richly in one place and thinly in another

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Two code paths answer the same question -- should this file be included, is this user allowed, does this record belong -- and one implements N rules while the other implements a subset. Every rule present only in the richer implementation becomes a phantom entry in whatever the thinner one produces. The project frequently STATES the shared invariant, having threaded exactly one of the rules through both.
- **Guarded twin (the fix):** The single rule that WAS threaded through both, usually with a comment explaining why -- 'this was omitted, so do not pull it back in'. That comment is the specification the other rules were never held to.
- **Sibling hunt:** Find the two implementations, enumerate the rules in each, and diff. The thin one is typically an enumerator of things that were NOT processed, which is exactly where a missing rule is invisible. Reproduce by arranging for one of the missing rules to fire and watching the item appear in the output it should have been excluded from. Also check that the thin path can even handle what it emits -- in the confirmed corpus one missing rule existed because such items cannot be stored at all.
- **Expected behaviour:** both paths answer the question identically, because they share the predicate.
- **Surfaces as:** SILENT and DRAMATIC in aggregate -- in the confirmed instance a total dropped from 100% to 11% because vendored files reappeared as never-executed.
- **Do NOT flag when:** Two predicates that are deliberately different (a cheap pre-filter and an exact test) are fine as long as the cheap one is a strict superset. This shape is the case where neither contains the other, or where the thin one is used to produce user-visible output.
- **Confirmed instances:** CRF-COVPY-0037 -- the should-trace gate knows eight rules; the unexecuted-file enumerator knows one

#### `suppression-keyed-on-an-optional-identifier` — A suppression mechanism keyed on an identifier that the emitting call sites may omit

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** Warnings can be disabled by naming a slug, and the check is `if slug in disabled`. The slug parameter is optional, so every call site that omits it emits a warning nobody can turn off -- and, being unnamed, one that never appears in the documented list either. Undocumented and unsuppressible are the same bug seen from two sides.
- **Guarded twin (the fix):** The slugged warnings, which are both documented and suppressible. The count of them is the argument: eleven documented against six anonymous is a convention with holes, not an absent convention.
- **Sibling hunt:** Find the suppression predicate, then enumerate every emitting call site and check which supply the key. Cross-reference against the documented list -- the two sets should be identical. Look for aggravators: a warning emitted while reading the very file that would contain the suppression list, and lazy initialization that lets an early warning permanently prevent the list from being read. Check that the suppression list is VALIDATED, since a typo in it is otherwise silent.
- **Expected behaviour:** every warning has a key, every key is documented, and the documented list is generated from the same source the code checks.
- **Surfaces as:** As NOISE the user cannot silence, which trains people to ignore the channel entirely.
- **Do NOT flag when:** An optional key is fine if the mechanism also supports suppressing by category or by message. Making the key required is the fix; generating the documentation from the registry is what stops it recurring.
- **Confirmed instances:** CRF-COVPY-0040 -- six warnings carry no slug, so they are unsuppressible and undocumented; one of them fires while reading the config that would suppress it

#### `error-escapes-the-project-exception-hierarchy` — A builtin exception raised where the project's own hierarchy is what callers catch

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A project defines its own exception base and its command-line or API boundary catches exactly that, turning it into a clean message. One code path raises a bare `RuntimeError`/`ValueError` instead, so it sails past the boundary handler and the user gets a raw traceback. Frequently paired with a second defect: every OTHER instance of the same condition degrades gracefully, and this one has no fallback because it happens too late in the lifecycle for the fallback to exist.
- **Guarded twin (the fix):** A sibling in the same module raising the project's own exception type for a comparable condition, and the graceful-degradation path taken by every other instance of the same class of unavailability.
- **Sibling hunt:** Find the boundary handler and the exception types it catches, then grep for `raise` of anything outside that set in library code. For each, ask two questions: does it reach a handler, and does a fallback exist at the point it fires? A condition that is handled gracefully when detected early and fatally when detected late is the richer half of the finding.
- **Expected behaviour:** every error a user can trigger arrives as the project's own exception type and is rendered by the boundary handler.
- **Surfaces as:** As a RAW TRACEBACK where every comparable failure produces a one-line message.
- **Do NOT flag when:** A builtin exception is correct for programming errors that should never be caught. The shape requires the condition to be reachable by ordinary use -- here, another process holding a shared runtime resource.
- **Confirmed instances:** CRF-COVPY-0042 -- a bare RuntimeError on resource exhaustion escapes the CLI handler, and unlike every sibling condition has no fallback because it fires after backend selection

#### `case-normalization-on-a-literal-key` — A lookup key case-folded where the store indexes on the literal bytes

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** `name[0].lower()` or `name.lower()` applied before a filesystem or database lookup whose entries are stored under the literal spelling. Every key whose real spelling differs in case silently misses, and a fallback path then supplies a degraded default with no diagnostic.
- **Guarded twin (the fix):** The reference implementation of the same lookup -- for a terminfo-style database, the C library that uses the byte as stored. Where none exists, the store's own listing is the oracle: enumerate it and count how many entries the normalization makes unreachable.
- **Sibling hunt:** For every `.lower()`/`.upper()`/`.casefold()` on a lookup key, check whether the STORE is case-insensitive. Then measure: enumerate the store and count entries the normalization cannot reach -- a concrete number is far more persuasive than the argument. Check whether a fallback masks the miss, which is what makes it silent rather than an error.
- **Expected behaviour:** a key that exists in the store is found, whatever its case.
- **Surfaces as:** SILENT DEGRADATION -- a fallback default is used, so the program works badly rather than failing.
- **Do NOT flag when:** Normalization is correct when the store is genuinely case-insensitive, and a case-insensitive FILESYSTEM can hide the bug on one platform while it bites on another. The fix is usually to try the literal form first and fall back to the normalized one, not to remove the normalization.
- **Confirmed instances:** CRF-PYREPL-0003 -- the first byte of a terminal name is lowercased before lookup, degrading 36 of 2,903 system entries to a three-capability stub with no diagnostic

#### `mirrored-direction-handles-fewer-cases` — One direction of a forward/backward pair handles fewer cases than its mirror

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A pair of functions implements the same operation in opposite directions -- forward/backward search, next/previous, up/down, encode/decode -- and one delegates to a complete helper while the other open-codes a partial version. The classic instance is a scan loop whose failure branch advances to the next unit instead of continuing within the current one, so everything after the first unsuccessful match in that unit is never examined.
- **Guarded twin (the fix):** The mirror function. It usually delegates to a shared helper, and the diff between 'delegates' and 'open-codes' is the whole finding.
- **Sibling hunt:** Enumerate every forward/backward, next/prev, first/last, push/pop pair in the module and diff their control flow rather than their arithmetic. Look specifically at the FAILURE branch of each scan loop: advancing past the remainder of the current unit is the shape. The project's own test suite is worth reading here -- in the confirmed instance the assertion for this exact case was commented out with a note that it 'seems buggy', while the mirror's equivalent case was asserted and passing.
- **Expected behaviour:** both directions find the same set of results on the same input, modulo order.
- **Surfaces as:** SILENT WRONG OUTPUT -- a replace-all that skips matches, a search that reports fewer hits going one way than the other. No error.
- **Do NOT flag when:** Genuine asymmetry is common and legitimate -- a forward iterator may be streaming where the backward one is not. The evidence is a case the mirror handles and this one drops, demonstrated on a concrete input, not a structural difference on its own. A commented-out or xfailed assertion in the test suite is the strongest corroboration available.
- **Confirmed instances:** CRF-IDLELIB-0005 -- forward search abandons the rest of a line after a zero-width match; the backward twin delegates to a helper that scans the whole prefix

#### `serialize-and-parse-use-different-grammars` — A value serialized by one grammar and parsed back by another

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A structured value is stringified by one mechanism and read back by an incompatible one -- a list handed to a Tcl variable and parsed back with `shlex.split`, `repr()` written and `json.loads` read, `shlex.quote` on write and `str.split` on read. Round-tripping a value containing any character the two grammars quote differently corrupts it, and the corruption is PERSISTED, so it compounds on every subsequent round trip.
- **Guarded twin (the fix):** Storing the structure itself rather than a string, or using the matching quote/unquote pair from one grammar. Where the string form is required by an external API, the twin is the quoting function that API ships.
- **Sibling hunt:** Find every place a container is assigned to something that stringifies it implicitly -- a GUI variable, an environment variable, a database text column -- and locate the corresponding parse. Test the round trip with a value containing a space, an empty string, a backslash, a newline, and each grammar's metacharacters. Check the test suite for a round-trip test that uses only trivial values, which is what lets this survive.
- **Expected behaviour:** parse(serialize(x)) == x for every value the feature accepts.
- **Surfaces as:** SILENT CORRUPTION that is STICKY -- the mangled value is written back, so it stays wrong forever after one round trip, and the user cannot repair it through the interface.
- **Do NOT flag when:** Two different grammars are fine if the values are constrained to their common subset AND that constraint is enforced -- an unenforced convention is not a constraint. A test asserting the feature supports spaces, alongside a round-trip test that only uses space-free values, is the classic evidence pair.
- **Confirmed instances:** CRF-IDLELIB-0007 -- run arguments stringified by Tcl with brace quoting and parsed back with shlex.split, corrupting quoted arguments permanently

#### `recognizer-rejects-a-legal-variant-spelling` — A lexical recognizer written for the common spelling, excluding a legal variant

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A regex or string test recognizes a construct by its usual formatting rather than its syntax -- requiring a space after a comment marker, a specific case, a particular quote style. Text written the other legal way is not recognized, so a downstream classifier reports the exact opposite of the truth for it: 'inside a comment' becomes 'inside code'.
- **Guarded twin (the fix):** The language's own tokenizer, or a sibling recognizer in the same module that handles the general form. Where the project ships tests, the tests for the common spelling pass and prove nothing about the variant.
- **Sibling hunt:** For every hand-written recognizer of a language construct, enumerate the LEGAL spellings from the language reference and test each. Optional whitespace after a marker is the single most common omission. Check the test suite for a case that records the divergence as expected behaviour -- a test asserting the wrong answer with a comment calling it 'a special case' is the shape confessing.
- **Expected behaviour:** the recognizer accepts every spelling the language accepts.
- **Surfaces as:** SILENT and INVERTED -- a completion popup inside a comment, a bell on a matching bracket that is commented out. It looks like a UI glitch, not a parser bug.
- **Do NOT flag when:** A recognizer deliberately restricted to a project's own style is fine for a linter and wrong for a parser -- ask which role it plays. Where the standard library ships a tokenizer for the language in question, not using it is the deeper finding.
- **Confirmed instances:** CRF-IDLELIB-0017 -- a comment with no space after the marker is invisible to the parser, so code completion fires inside comments and bracket matching rings on commented text

#### `reinitializer-resets-a-subset-of-its-state` — A re-runnable initializer that resets some per-instance state and not the rest

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** `__init__` (or a `reset`/`reconnect` method) is deliberately re-run on a live object, and resets several attributes -- establishing that per-instance state belongs there -- but omits others. The omitted ones are typically declared at CLASS level and rebound on `self` only from working methods, so they never look like instance state in `__init__` and are reset by neither it nor `close()`.
- **Guarded twin (the fix):** The attributes the same initializer DOES reset. Their presence is the author's statement of intent, which is what makes the omission a defect rather than a design choice.
- **Sibling hunt:** Find initializers that are re-invoked on an existing object (a reconnect path calling `Class.__init__(self, ...)` is the tell) and diff the attributes they reset against every `self.X = ` in the class. Class-level declarations that are rebound per-instance are the usual gap. Then trace the consequence: leftover parsing or buffering state usually surfaces as a decode error on the FIRST message after reconnect, and if the error escapes a polling loop's try block the loop may stop rescheduling entirely.
- **Expected behaviour:** after re-initialization the object behaves as a fresh one for every piece of state it owns.
- **Surfaces as:** As a rare, timing-dependent parse or protocol error after a reconnect, often ending in a permanently wedged event loop rather than a crash.
- **Do NOT flag when:** State deliberately preserved across re-initialization (statistics, a sequence counter) is not a defect -- but it should be evident from a comment or a name. Distinct from `class-level-mutable-attribute`: the class-level value here is immutable and rebound per instance, so it is not shared; the bug is that it is never reset.
- **Confirmed instances:** CRF-IDLELIB-0018 -- reconnect re-runs __init__, which resets the response and condition-variable maps but not the packet read buffer; a reconnect mid-packet concatenates the stale tail onto the next message

#### `index-computed-before-a-mutation-used-after-it` — A position captured before a length-changing edit, applied after it

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Start and end offsets are taken from a match or a selection, the buffer is then edited in a way that changes its length, and the ORIGINAL end offset is used afterwards -- to set a selection, to seek, to slice. The result is correct only when the replacement is exactly as long as what it replaced.
- **Guarded twin (the fix):** A sibling operation doing the same job that asks the buffer where the edit ended -- `text.index('insert')`, the return value of the edit, `match.start() + len(replacement)`. In the confirmed instance the single-step sibling is correct and only the batch version is wrong.
- **Sibling hunt:** For every mutate-then-report sequence, check whether the reported position was computed before or after the mutation. The batch variant of an operation is the likely offender, because the single-step one is exercised interactively and gets fixed. Test with a replacement LONGER and SHORTER than the original -- equal-length replacements hide it completely. Read the tests: the sibling's test often asserts the selection and the batch version's does not.
- **Expected behaviour:** the reported position corresponds to the buffer as it is after the edit.
- **Surfaces as:** SILENT and cosmetic-looking -- a selection one character long, or spilling into the following text -- which is why it survives as a known oddity rather than a bug report.
- **Do NOT flag when:** Fine when the mutation is length-preserving by construction, or when the index is recomputed. Distinct from `mutation-during-iteration`: nothing is being iterated here, and the stale value is a position rather than a cursor.
- **Confirmed instances:** CRF-IDLELIB-0019 -- Replace All computes the final selection from the pre-replacement span, so the selection is wrong whenever the replacement differs in length

### Owned by `project-docs-auditor`

#### `generated-doc-propagates-a-source-error` — An error in a generated-documentation source is baked into every generated copy

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Help text, a usage string, or an option list lives in code and is inlined into documentation by a generator (cog, sphinx-argparse, a Makefile). When the source string drifts from the code around it, the error is checked in to every generated file -- and re-running the generator cannot fix it, because the generator faithfully reproduces the wrong source.
- **Guarded twin (the fix):** A hand-written document covering the same ground that is CORRECT -- its existence is what proves the generated one wrong rather than merely different.
- **Sibling hunt:** Find the generator's markers, identify the source of each generated block, and verify the SOURCE against the code by executing it rather than reading it. Then count the copies: the blast radius is the number of generated files, and the fix must be applied upstream then regenerated. Also check for the same list repeated in a hand-maintained file (a man page, a README) that the generator does not touch.
- **Expected behaviour:** the generated text matches what the code actually does, and the generator is the only writer of those blocks.
- **Surfaces as:** SILENT. Every generated file is byte-consistent with its source, so a generator-drift check passes.
- **Do NOT flag when:** If the generated copies disagree with their source, that is ordinary generator drift and the generator fixes it. This shape is specifically the case where regeneration does NOT help. Verify the source claim by executing the code path, not by reading a sibling document.
- **Confirmed instances:** CRF-COVPY-0056 -- the --rcfile help string omits one candidate file, and cog baked the wrong list into ten doc files plus a man page

#### `implemented-but-undocumented-option` — A configuration option is parsed, defaulted, consumed and tested, but documented nowhere

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** An option exists in the parser's table, has a default, is read at the point of use, and has tests -- but does not appear in the reference documentation. Because it IS recognized, it produces no 'unrecognized option' warning, so it is fully supported and completely invisible. Often the documentation narrates the behaviour the option controls without ever naming the option.
- **Guarded twin (the fix):** Every other option in the same table, which is documented. The inverse shape -- documented but not implemented (a phantom option) -- is worth checking in the same pass and is usually rarer.
- **Sibling hunt:** Extract the option names the parser accepts and the option names the reference documentation defines, and diff both directions. Then check the CLI surface separately: an option may be documented as a flag and undocumented as a config-file setting. Also confirm the parser does not warn -- an option that warns is discoverable and much less serious.
- **Expected behaviour:** the set of options the code accepts equals the set the documentation defines.
- **Surfaces as:** NEVER. Users cannot discover the option, and maintainers cannot deprecate what is not written down.
- **Do NOT flag when:** Deliberately private or experimental options are a POLICY call, not a defect -- but they should still be marked as such somewhere. An option documented only in a changelog entry is undocumented for this purpose.
- **Confirmed instances:** CRF-COVPY-0057 -- two options parsed, defaulted, consumed and tested but absent from 50 documented option headings

#### `documented-recipe-not-wired-up` — A documented recipe depends on a hook the default code path never installs

- **Default severity:** POLICY (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Official documentation gives users a recipe -- import this module, set this attribute, register this callback -- that works only under a legacy or opt-in code path. The default path replaces one half of the integration and never installs the other, so the recipe silently does nothing. No error, because the recipe's own imports still succeed.
- **Guarded twin (the fix):** The legacy path where the recipe genuinely works, usually still reachable behind an environment variable. Its existence is what makes the omission a bug rather than a documentation error -- and it is also what makes the fix a POLICY call between installing the hook and rewriting the docs.
- **Sibling hunt:** Take each documented integration recipe and execute it under the DEFAULT configuration, not the one the docs were written against. Check specifically for module aliases and registry entries the recipe depends on being present. Any recipe predating a rewrite of the subsystem it touches is a candidate.
- **Expected behaviour:** a recipe printed in the documentation has the documented effect under the default configuration.
- **Surfaces as:** SILENT -- the user sees no error and no effect, and has no way to tell which.
- **Do NOT flag when:** A recipe that raises is a bug report waiting to happen and is far less serious than one that silently succeeds. If the default path was always intended to supersede the recipe, this is a documentation fix; if the recipe is still advertised as current, it is a wiring fix. Say which.
- **Confirmed instances:** CRF-PYREPL-0025 -- the documented rlcompleter recipe is a no-op under the default REPL because the module alias is never installed

### Owned by `python-pitfall-scanner`

#### `mutable-default-argument` — Mutable object as a default parameter value -- shared across every call

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `def`/`async def` whose default is a mutable literal or call: `def f(items=[])`, `def f(opts={})`, `def f(s=set())`, `def f(now=datetime.now())`. The default is evaluated ONCE at function-definition time, so every call that mutates it sees the accumulated state of all prior calls.
- **Guarded twin (the fix):** The `None` sentinel: `def f(items=None): items = [] if items is None else items`. In most codebases the correct twin already exists on a sibling function -- find it and match it.
- **Sibling hunt:** For each confirmed instance, check every other function in the same module and every override/implementation of the same interface; this shape is copy-pasted along a family of similar signatures.
- **Expected behaviour:** each call with the argument omitted starts from a fresh empty container (or a freshly-evaluated timestamp).
- **Surfaces as:** SILENT -- results that grow across calls, stale timestamps, or test pollution that only appears when tests run in a particular order. Never raises.
- **Do NOT flag when:** A mutable default that is only ever READ (never mutated, never returned) is a style issue, not a bug -- do not report it as FIX. Read the body before classifying.

#### `late-binding-closure-in-loop` — Closure captures the loop variable by reference, not by value

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `lambda` or nested `def` created inside a loop that references the loop variable: `handlers = [lambda: process(i) for i in items]`, or `for name in names: register(lambda: use(name))`. Every closure shares one cell and sees the FINAL value after the loop ends.
- **Guarded twin (the fix):** Bind at creation time via a default argument (`lambda i=i: process(i)`) or `functools.partial(process, i)`. A sibling loop in the same file that already does this is the fix pattern.
- **Sibling hunt:** Grep every loop body that constructs a callable -- callbacks, event handlers, retry wrappers, click/argparse command registration, and thread/task targets are the recurring hosts.
- **Expected behaviour:** each closure operates on the loop value that was current when it was created.
- **Surfaces as:** SILENT -- every callback behaves as if it were the last iteration. Often mistaken for a race or a caching bug.
- **Do NOT flag when:** Safe when the closure is CALLED inside the same iteration (immediately consumed), or when the loop variable is not referenced in the closure body. Trace whether the callable escapes the iteration.

#### `except-clause-ordering-unreachable` — A broad `except` precedes a narrower one, making the specific handler dead

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** In one `try` statement, an `except` naming a base class appears BEFORE an `except` naming its subclass -- `except Exception:` then `except ValueError:`, or `except OSError:` then `except FileNotFoundError:`. Python matches clauses top-to-bottom, so the specific branch can never run.
- **Guarded twin (the fix):** Most-specific-first ordering. The correct order usually already exists in a neighbouring try/except in the same module.
- **Sibling hunt:** For each hit, audit every try/except in the same error-handling layer -- ordering mistakes cluster where handlers were appended over time rather than inserted.
- **Expected behaviour:** the specific handler runs for its exception type; the broad handler only catches what the specific ones did not.
- **Surfaces as:** SILENT -- the specialized recovery path (retry, fallback, targeted cleanup) is quietly replaced by the generic one.
- **Do NOT flag when:** Not a bug if the earlier clause re-raises unconditionally, or if the two types are unrelated (no subclass relationship) -- verify the MRO, do not assume from the names.

#### `return-or-break-in-finally` — `return`/`break`/`continue` inside `finally` discards the in-flight exception

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `finally:` block containing `return`, `break`, or `continue`. Any exception propagating through the `try` is silently dropped when the `finally` transfers control, so the caller sees a normal return instead of the error.
- **Guarded twin (the fix):** Do the cleanup in `finally` but let control flow continue; put the `return` after the try/finally, or use a context manager.
- **Sibling hunt:** Audit every `finally` in the module; also check `__exit__` methods that `return True` unconditionally -- that is the same defect expressed through the context-manager protocol.
- **Expected behaviour:** the original exception propagates to the caller; cleanup still runs.
- **Surfaces as:** SILENT -- errors vanish. A function that should have raised returns a normal (often `None`) value; failures surface far downstream as an unexpected `None`.
- **Do NOT flag when:** `__exit__` returning a computed truthy value for a SPECIFIC exception type is a legitimate suppression idiom; an unconditional `return True` is the bug.

#### `eq-without-hash` — `__eq__` defined without `__hash__` -- instances become unhashable or hash inconsistently

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A class defining `__eq__` but not `__hash__`. Python 3 sets `__hash__ = None`, so instances can no longer go in a `set` or be used as `dict` keys. The mirror defect: a class defining BOTH where `__hash__` does not agree with `__eq__` (equal objects hashing differently), which corrupts set/dict membership.
- **Guarded twin (the fix):** Define `__hash__` over the same fields `__eq__` compares, or use `@dataclass(frozen=True)`/`eq=True, frozen=True` which derives both consistently.
- **Sibling hunt:** Check every class in the module hierarchy that defines `__eq__`; also check whether instances are ever placed in a set, used as dict keys, or deduplicated -- that is where the breakage surfaces.
- **Expected behaviour:** equal objects hash equally and can be used in hash-based containers.
- **Surfaces as:** `TypeError: unhashable type` at the first set/dict use (loud), OR -- when both are defined inconsistently -- SILENT duplicate entries and failed lookups.
- **Do NOT flag when:** Intentional for deliberately-unhashable mutable value objects. Only report when the type is actually used (or plausibly used) in a hash-based container.

#### `mutation-during-iteration` — A container is mutated while being iterated

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `for k in d:` with `del d[k]` / `d[new] = v` in the body; `for x in lst:` with `lst.remove(x)` / `lst.append(...)`; iterating a set while adding to it. Dict/set raise `RuntimeError: dictionary changed size during iteration`; LISTS DO NOT -- they silently skip elements as indices shift.
- **Guarded twin (the fix):** Iterate over a snapshot (`for k in list(d)`) or build a new container via comprehension and rebind.
- **Sibling hunt:** For each hit, check every loop in the same module that mutates its own iteration target; the list variant is the dangerous one because it never raises.
- **Expected behaviour:** every element is visited exactly once, and the intended removals all happen.
- **Surfaces as:** `RuntimeError` for dict/set (loud); SILENT element-skipping for lists -- roughly every other element is missed.
- **Do NOT flag when:** Safe when the mutation happens after a `break`, or when the loop iterates an explicit copy (`list(...)`, `.copy()`, a slice). Confirm the iterated expression is the SAME object being mutated.

#### `asyncio-fire-and-forget-task` — `asyncio.create_task()` result is discarded -- the task can be garbage-collected mid-flight

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `asyncio.create_task(coro())` / `loop.create_task(...)` / `ensure_future(...)` whose return value is not stored, awaited, or added to a set. The event loop keeps only a WEAK reference, so the task may be collected before it completes -- and any exception it raised is swallowed.
- **Guarded twin (the fix):** Retain a strong reference: keep a module/instance-level `set`, `add()` the task, and `task.add_done_callback(tasks.discard)`; or `await` it; or gather it.
- **Sibling hunt:** Grep every `create_task`/`ensure_future` call site; also check whether a task-exception handler exists at all -- a project with one retained-task set usually has other sites that forgot it.
- **Expected behaviour:** the task runs to completion and its exception surfaces (logged or re-raised), not silently dropped.
- **Surfaces as:** SILENT and NONDETERMINISTIC -- work intermittently does not happen under load; exceptions never appear. Sometimes an 'Task was destroyed but it is pending!' warning.
- **Do NOT flag when:** Fine when the call is immediately awaited, gathered, or the returned task is assigned. A task stored ONLY in a local that goes out of scope is still the bug.

#### `blocking-call-in-async-function` — A synchronous blocking call inside `async def` stalls the whole event loop

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** Inside an `async def`: `time.sleep(...)`, `requests.get(...)`, `open(...).read()` on a large file, `subprocess.run(...)`, a blocking DB driver call, or `socket` I/O. The coroutine holds the single event-loop thread, so every other task stops.
- **Guarded twin (the fix):** `await asyncio.sleep(...)`, an async client (`aiohttp`/`httpx.AsyncClient`), or `await asyncio.to_thread(fn, ...)` / `run_in_executor` for unavoidable blocking work. A sibling coroutine already doing this is the fix.
- **Sibling hunt:** Audit every `async def` in the module for imports of known-blocking libraries; a project mixing sync and async clients usually has several.
- **Expected behaviour:** the coroutine yields to the loop while waiting; concurrent tasks continue.
- **Surfaces as:** SILENT -- manifests as latency, timeouts, and apparent deadlock under concurrency, never as an exception. Easily misread as a performance problem rather than a defect.
- **Do NOT flag when:** Acceptable at startup/shutdown before the loop is serving, or in a coroutine documented as running in an executor. Check whether the call is on the hot path.

#### `unawaited-coroutine` — A coroutine function is called without `await` -- the body never runs

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** Calling an `async def` and discarding the result, or using it in a boolean/truthiness context: `self.flush()` where `flush` is async; `if self.check():`. A coroutine object is truthy, so guards silently take the wrong branch and the work never executes.
- **Guarded twin (the fix):** `await self.flush()`, or `asyncio.create_task(...)` WITH a retained reference (see asyncio-fire-and-forget-task).
- **Sibling hunt:** For each async method, grep every call site; the shape appears when a previously-sync method is converted to async and one caller is missed. Check git history for the sync->async commit and audit all callers touched (or not touched) by it.
- **Expected behaviour:** the coroutine body executes and its result/exception is observed.
- **Surfaces as:** A `RuntimeWarning: coroutine '...' was never awaited` (easily lost in log noise, and only if the object is collected); otherwise SILENT no-op.
- **Do NOT flag when:** Deliberate when the coroutine object is passed to `gather`/`wait`/`create_task` or returned to a caller that awaits it. Follow the value.

#### `lru-cache-on-method` — `@lru_cache` on an instance method keeps every `self` alive forever

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `@functools.lru_cache` / `@cache` applied to a method taking `self`. The cache is stored on the CLASS and keys include `self`, so every instance ever passed is strongly referenced for the process lifetime -- an unbounded leak -- and cache entries are shared across instances.
- **Guarded twin (the fix):** `functools.cached_property` for per-instance memoization, a per-instance cache dict built in `__init__`, or making the function a `@staticmethod`/module-level function keyed only on the real inputs.
- **Sibling hunt:** Grep every `lru_cache`/`cache` decorator and check whether the first parameter is `self`/`cls`; long-lived services accumulate these.
- **Expected behaviour:** cached values are released when the instance is; memory is stable across instance churn.
- **Surfaces as:** SILENT -- steadily growing RSS in a long-running process; instances that should be collected never are.
- **Do NOT flag when:** Harmless for singletons or classes with a small fixed instance count. Judge by instance lifecycle, not by the decorator alone.

#### `class-level-mutable-attribute` — A mutable class attribute is shared by every instance

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `class C: items = []` (or `{}`/`set()`) where instances mutate `self.items.append(...)`. Because the attribute lives on the class, all instances share one object; only REBINDING (`self.items = [...]`) creates a per-instance copy.
- **Guarded twin (the fix):** Initialize in `__init__` (`self.items = []`), or use `dataclasses.field(default_factory=list)`.
- **Sibling hunt:** Audit every class-body assignment to a mutable literal in the module; also check dataclasses for a bare mutable default (which raises at class-creation time and so is self-correcting -- the plain-class form is the silent one).
- **Expected behaviour:** each instance owns its own container.
- **Surfaces as:** SILENT -- state bleeds between instances; frequently first noticed as cross-test contamination.
- **Do NOT flag when:** Correct and idiomatic for CONSTANTS that are never mutated (and better expressed as a tuple/frozenset). Confirm a mutation exists before reporting.

#### `bare-except-swallows-control-flow` — `except:` / `except BaseException:` swallows KeyboardInterrupt and SystemExit

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A bare `except:` or `except BaseException:` whose handler does not re-raise. These catch `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit` -- so Ctrl-C is ignored, `sys.exit()` is neutralized, and shutdown hangs. Worse inside a retry loop, which will spin forever against Ctrl-C.
- **Guarded twin (the fix):** `except Exception:` (which excludes the control-flow exceptions), or a bare except that re-raises after cleanup.
- **Sibling hunt:** Every bare except in the codebase; prioritize those inside loops, signal handlers, and long-running worker/daemon bodies.
- **Expected behaviour:** Ctrl-C interrupts promptly; `sys.exit()` terminates the process.
- **Surfaces as:** SILENT until an operator tries to stop the process and cannot -- then it looks like a hang, not an exception-handling bug.
- **Do NOT flag when:** Legitimate in a top-level crash-reporting boundary that logs and RE-RAISES, and in `__del__`/atexit cleanup. The discriminator is whether control flow continues as if nothing happened.
- **Confirmed instances:** CPython idlelib autocomplete.py:175 (6080c86, 3.14) -- `try: rpcclt = self.editwin.flist.pyshell.interp.rpcclt / except: rpcclt = None` catches everything to guard an attribute chain; `except AttributeError:` is the intended narrow form. Found by reports/idlelib_v1.

#### `exception-in-del-or-finalizer` — `__del__` raises or resurrects -- the exception is discarded and cleanup is skipped

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `__del__` that performs failure-prone work (I/O, network close, dict lookups on possibly-torn-down module globals) with no guard. Exceptions in `__del__` are printed and ignored -- never propagated -- so the remainder of the finalizer silently does not run. At interpreter shutdown module globals may already be `None`.
- **Guarded twin (the fix):** `weakref.finalize` or an explicit `close()`/context manager; if `__del__` is unavoidable, wrap the whole body in try/except and hold direct references to anything it needs.
- **Sibling hunt:** Every `__del__` in the codebase, plus classes owning an OS resource (file, socket, subprocess, lock) that rely on `__del__` for release.
- **Expected behaviour:** resources are released deterministically; failures are visible.
- **Surfaces as:** SILENT -- 'Exception ignored in: <function C.__del__>' on stderr at best; leaked file descriptors/sockets at worst.
- **Do NOT flag when:** A trivially-safe `__del__` (pure attribute assignment) is fine. Rank by what the body can actually raise.

#### `is-comparison-with-literal` — Identity comparison against a literal -- works only by interning accident

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `x is 0`, `x is 'name'`, `x is 256`, `status is ''`. `is` compares identity; small-int caching and string interning make this appear to work in testing and then fail for computed or large values.
- **Guarded twin (the fix):** `==` for value comparison; keep `is` for `None`, `True`, `False`, and genuine sentinels.
- **Sibling hunt:** Grep `is` / `is not` followed by a numeric or string literal across the codebase.
- **Expected behaviour:** comparison is by value and holds for every equal value, not just interned ones.
- **Surfaces as:** `SyntaxWarning: "is" with a literal` at compile time on modern CPython; otherwise SILENT and input-dependent -- passes for small values, fails for large ones.
- **Do NOT flag when:** `is None` / `is True` / `is False` and sentinel-object comparisons are correct and must not be flagged.

#### `except-exception-too-broad` — `except Exception:` around a narrow operation swallows unrelated failures

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `try` whose body is one or two narrow operations -- a single attribute access, one call, one parse -- wrapped in `except Exception:` (or `except BaseException:`) whose handler swallows: `pass`, or assigning a default/`None`, or `return`ing a fallback. The author meant one specific failure (`AttributeError`, `TypeError`, `ValueError`); everything else -- `RuntimeError`, `MemoryError`, a genuine bug in the callee -- is silently absorbed and reported as the expected condition.
- **Guarded twin (the fix):** The same operation elsewhere guarded by the SPECIFIC exception it can raise: `except AttributeError:` for an attribute chain, `except (TypeError, ValueError):` for a parse. Most codebases already contain the narrow form somewhere -- find it and match it.
- **Sibling hunt:** For each instance, grep every other site performing the same operation (same method, same parse, same attribute chain). Broad catches propagate by copy-paste, and the narrow twin is usually adjacent.
- **Expected behaviour:** the anticipated failure is handled; anything else propagates so it can be seen and fixed.
- **Surfaces as:** SILENT -- a genuine bug in the guarded call is indistinguishable from the expected condition. Frequently surfaces much later as an empty result, a `None`, or a missing side effect.
- **Do NOT flag when:** A broad catch at a genuine trust boundary is legitimate: a plugin/entry-point loader, a top-level CLI handler, or a call into user-supplied code -- ESPECIALLY when it logs at warning+ or re-raises, or carries a comment explaining the containment. The discriminator is the size and nature of the try body: one narrow operation = too broad; a whole subsystem call at a boundary = fine.

#### `cleanup-only-on-success-path` — Resource released at the end of `try` instead of in `finally` -- leaked on the error path

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A resource is acquired, used, and released (`close()`, `quit()`, `shutdown()`, `release()`, `disconnect()`) as the LAST statement of a `try` body, with `except` clauses but no `finally`. Any exception raised mid-body skips the release, leaking a file descriptor, socket, or connection.
- **Guarded twin (the fix):** `finally: resource.close()`, or a `with` block. A sibling function in the same module usually already does it correctly.
- **Sibling hunt:** Audit every acquire/release pair in the module. Also check `__exit__`/`close()` methods that release several resources in sequence -- an exception on the first leaks the rest.
- **Expected behaviour:** the resource is released on every path, success or failure.
- **Surfaces as:** SILENT under normal operation; surfaces only under load or after repeated failures as fd exhaustion, connection-pool starvation, or `ResourceWarning: unclosed ...` at GC time.
- **Do NOT flag when:** Fine if the resource is returned to the caller (ownership transfers), if a `with` block already governs it, or if the except clause itself performs the release. Confirm no path skips it.

#### `error-reported-below-warning` — Failure reported only at debug/info level -- invisible under default logging

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** An `except` handler whose ONLY reporting is `logger.debug(...)` / `logger.info(...)` / `util.debug(...)` / `print` to a non-default stream, with no re-raise and no state change signalling failure. Default logging configuration discards DEBUG and INFO, so the failure produces literally no output in production.
- **Guarded twin (the fix):** `logger.warning(...)`/`logger.exception(...)` for a genuine failure; debug level is for tracing, not for errors. The same module usually logs comparable failures at warning or above.
- **Sibling hunt:** Grep every `debug(`/`info(` call inside an except handler across the project; also check whether the module's logger is even configured by default.
- **Expected behaviour:** an operator running with default configuration can tell the operation failed.
- **Surfaces as:** SILENT in production by construction -- the report exists in source, so a reader believes it is handled, but nothing reaches the logs.
- **Do NOT flag when:** Debug level is correct for genuinely-expected, high-frequency, non-actionable conditions (a cache miss, an optional import). The discriminator: would an operator want to know? If the handler is recovering from something that should not normally happen, it belongs at warning+.

#### `except-in-loop-without-exit` — Swallowed exception inside an unbounded loop -- a persistent failure becomes a hang

- **Default severity:** FIX (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `while True:` (or a retry loop) containing a `try`/`except` whose handler neither breaks, returns, raises, nor increments a bounded attempt counter -- typically `except OSError: pass` or `except Exception: continue`. If the failure is transient the loop recovers; if it is persistent the process spins forever with no diagnostic.
- **Guarded twin (the fix):** A bounded retry: `for attempt in range(N)` with a final re-raise, or a `break`/`raise` after a threshold. Backoff loops elsewhere in the same module usually show the correct shape.
- **Sibling hunt:** Every unbounded loop containing a try/except. Also check loops that poll a resource which can be permanently unavailable (a deleted directory, a closed socket, a dead peer).
- **Expected behaviour:** a persistent failure terminates the loop with a diagnostic instead of spinning.
- **Surfaces as:** A HANG with no output -- the worst diagnostic profile of any shape here, because there is no exception, no log line, and no exit.
- **Do NOT flag when:** Correct for an event loop or server accept-loop that MUST survive individual failures -- but even those should log. The discriminator: can the guarded operation fail permanently? If yes, the loop needs an exit.

#### `raise-without-from-in-except` — Re-raising a new exception inside `except` without `from` loses the cause

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `raise NewError(...)` inside an `except` handler with no `from err` and no `from None`. Python still records the original as implicit context, but the explicit cause is lost and tooling/readers cannot distinguish 'this replaced that deliberately' from 'the author forgot'. The severe variant passes the wrong object entirely -- e.g. `raise TypeError(msg, err.__traceback__)`, which stuffs a traceback object into `args` instead of chaining.
- **Guarded twin (the fix):** `raise NewError(...) from err` to chain, or `from None` to deliberately suppress. Both are explicit and both read correctly.
- **Sibling hunt:** Every `raise` inside an `except` in the module; the convention is applied per-codebase, so a module that chains in one place and not another has a real inconsistency.
- **Expected behaviour:** the traceback shows the original cause, explicitly marked as cause or deliberately suppressed.
- **Surfaces as:** Visible in the traceback as 'During handling of the above exception, another exception occurred' rather than 'The above exception was the direct cause' -- confusing rather than silent, but it degrades every downstream diagnosis.
- **Do NOT flag when:** Not a defect when the new exception is genuinely unrelated to the caught one and `from None` would be noise, or in code targeting Python 2 compatibility. Judge by whether the original would help someone debugging.
- **Confirmed instances:** CPython idlelib (6080c86): ALL SIX raise-inside-except sites lack `from` -- config.py:211, pyshell.py:12, rpc.py:345, rpc.py:361, run.py:360, zoomheight.py:74. rpc.py:361 (`except OSError: raise EOFError`) is the costly one: it discards the errno, so there is no record of whether IDLE restarted because the peer exited or because the kernel ran out of buffers. Found by reports/idlelib_v1.

#### `flag-not-reset-on-early-exit` — Guard flag set at entry but reset only on the success path

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A method sets a persistent guard flag (`self.busy = True`, `self.restarting = True`) to mark work in progress, then resets it (`= False`) as the last statement -- with one or more `return`/`raise` between them that skip the reset. The flag stays set for the object's lifetime.
- **Guarded twin (the fix):** `try: self.busy = True; ...work... finally: self.busy = False`. This twin is almost always already present on a sibling method, because the author got it right somewhere else.
- **Sibling hunt:** Grep every `self.<name> = True`/`= False` pair in the class, then every early `return` between them. Also check the guard's READERS: the damage is proportional to how many entry points consult the flag.
- **Expected behaviour:** the flag reflects reality on every path, so a later call proceeds normally.
- **Surfaces as:** SILENT and PERMANENT -- every subsequent call takes the 'already in progress' branch and returns immediately, doing nothing and reporting nothing. Looks like a frozen or unresponsive component, not an error.
- **Do NOT flag when:** Only state that OUTLIVES the call matters -- an attribute or a qualified global. Re-binding a bare LOCAL is ordinary computation, not a missed reset. Also fine if a `finally` elsewhere in the function restores it, or if the early exit happens BEFORE the flag is set.
- **Confirmed instances:** CPython idlelib pyshell.py:488 (6080c86) -- `self.restarting` set at 488, reset only at 526; a TimeoutError from `rpcclt.accept()` returns at 508, so IDLE can never restart its subprocess again: Run Module, Restart Shell and the auto-restart all hit the guard and silently do nothing. Found by reports/idlelib_v1.; CPython idlelib autocomplete_w.py:238 -- `self.is_configuring` set at 238, reset only at 284; `if not self.is_active(): return` at 240 skips it, permanently disabling the <Configure> handler for that completion window.

#### `guard-rechecks-call-receiver` — A NULL-guard tests the call receiver instead of the result

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `m = prog.match(...)` immediately followed by `if not prog:` (or `if prog is None:`). The guard names the RECEIVER of the call rather than the freshly-bound result. The receiver was just used successfully as a call target, so the branch is dead; the result is never checked and flows on possibly-None.
- **Guarded twin (the fix):** The same guard spelled with the result name -- `if not m:`. Sibling methods performing the same match/lookup almost always have it right; this is a one-character class of typo that survives review because it LOOKS like a guard.
- **Sibling hunt:** For each instance, check every sibling that performs the same call. In idlelib, `replace_all` and `do_find` both guard their match correctly and only `do_replace` misspells it -- three near-identical guards, one wrong.
- **Expected behaviour:** a failed match returns early instead of reaching code that dereferences the result.
- **Surfaces as:** AttributeError on the None result, raised somewhere DOWNSTREAM of the guard that was supposed to prevent it -- so the traceback points away from the actual defect.
- **Do NOT flag when:** Not a defect if the receiver is genuinely re-tested for a different reason (e.g. it is reassigned between the call and the check). Confirm the receiver is unchanged and was already known non-None.
- **Confirmed instances:** CPython idlelib replace.py:213-214 (6080c86) -- `m = prog.match(chars, col)` then `if not prog:` (already proven non-None at :201). With Regular-expression on, Find `\Z`, Replace: search_forward matches the line without its newline, do_replace re-matches WITH the newline, `m` is None, and `m.expand()` raises AttributeError. Found by reports/idlelib_v1.

#### `falsy-check-for-none-default` — `if not param:` where the parameter defaults to None conflates None with 0/''/[]

- **Default severity:** CONSIDER (before triage) · **grounding:** documented
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A parameter declared `def f(x=None)` and then tested with `if not x:`. The author means 'argument omitted', but the test also fires for every legitimate falsy value a caller may pass -- `0`, `''`, `[]`, `{}`, `False`.
- **Guarded twin (the fix):** `if x is None:` -- explicit, and the standard idiom paired with a None sentinel default.
- **Sibling hunt:** Every parameter with a None default in the module, then every truthiness test of it. Also check int-valued flags drawn from a constant set that includes 0: `ATTRS, FILES = 0, 1` makes `not mode` true for ATTRS, silently disabling a mode filter.
- **Expected behaviour:** the branch runs only when the argument was actually omitted.
- **Surfaces as:** SILENT and input-dependent -- correct for every caller until one passes a falsy value, then the function behaves as if the argument were missing.
- **Do NOT flag when:** Fine when the parameter is reassigned from its default before the test (no longer a sentinel test), or when every falsy value should genuinely take the same branch as None. This check already skips reassigned parameters.

#### `test-cannot-fail` — A test that passes regardless of what the code under test does

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `unittest.TestCase` method that cannot fail: an empty body (`pass`/`...`/docstring only); an assertion over constants (`assertTrue(True)`, `assertEqual(1, 1)`); `assertTrue(all(filter(pred, xs)))`, where `filter` has already dropped everything the predicate rejects so the predicate is never tested; a method that asserts but lost its `test` prefix, so unittest never runs it; a class with fixtures but no tests; or a test with no assertion at all.
- **Guarded twin (the fix):** The sibling test that does the same setup and then asserts on a value the code under test produced. For the `all(filter(...))` form the twin is `all(pred(x) for x in xs)`.
- **Sibling hunt:** Scan the whole test module: these cluster, because they come from the same habits (a placeholder left behind, an extraction that dropped a prefix, a copy-paste of an assertion idiom that was already wrong).
- **Expected behaviour:** the test fails when the behaviour it names regresses.
- **Surfaces as:** NEVER -- by construction. Worse than no test: it reports as coverage, consumes review attention, and makes every other invariant the suite claims less trustworthy.
- **Do NOT flag when:** An asserting method that is CALLED from a test is correct DRY design, not an orphan -- only flag one nothing calls. A test with no assertion may be a deliberate does-not-raise smoke test (`test_init` constructing an object) -- that is why it is medium, not high. Assertions aliased to locals and tests delegating to an in-class asserting helper both count as assertions.
- **Confirmed instances:** CPython idlelib (6080c86): test_autocomplete.py:241-242 `assertTrue(all(filter(lambda x: x.startswith('_'), s)))` -- true whether s has none or all such names; the intent (per line 242's twin) was assertFalse(any(...)). test_editor.py:236 RMenuTest.test_rclick and test_configdialog.py:55 test_deactivate_current_config are `pass`. Independently found by both an agent and this check in reports/idlelib_v1.

#### `self-referential-accumulate` — A value accumulated into itself -- the source was never updated

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `x += x`, or `obj.field += obj.field`, where an ADJACENT statement accumulates into the same object from a different source (`obj.other += src.other`). The line was copied and its source not changed.
- **Guarded twin (the fix):** The sibling accumulate one line away, which names the correct source. It is literally adjacent -- that is what makes this shape so cheap to confirm.
- **Sibling hunt:** Grep every `+=` whose two sides are the same name. Then check whether a neighbouring statement accumulates into the same object from a different source; if so it is near-certain.
- **Expected behaviour:** the accumulator collects the values it is meant to collect.
- **Surfaces as:** NOTHING -- for an accumulator starting empty (`b""`, `""`, `0`, `[]`) the statement is a permanent no-op, so the data it should have gathered is silently discarded. It surfaces only when someone finally reads the field, which may be years later.
- **Do NOT flag when:** `x += x` is legitimate for deliberate doubling (`s += s` to repeat a string, `n += n`). The discriminator is the adjacent sibling using a different source, which is why that raises confidence to high.
- **Confirmed instances:** CPython _pyrepl unix_console.py:545 and :569 (6080c86) -- `e.raw += e.raw` in both `getpending()` variants, directly below the correct `e.data += e2.data`. `e.raw` starts `b""`, so the raw bytes of every already-queued event are dropped. Latent because all three callers read only `.data`. Found by reports/pyrepl_v1.

#### `duplicated-guard-wrong-operand` — A bounds check copied without updating its operand

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** Two structurally identical guards in one block (`if offset > len(data): raise ...`), with a new value computed between them (`end_offset = offset + 2 * n`). The second guard should test the NEW value but repeats the first verbatim, so the computed value is never validated.
- **Guarded twin (the fix):** A nearby guard that does check its computed end -- in the confirmed instance, nine lines below: `if offset + str_size > len(data): raise ValueError(...)`.
- **Sibling hunt:** Any `end = start + n` followed by a check that does not mention `end`; or two textually identical guard tests within a few statements of each other.
- **Expected behaviour:** malformed input is rejected at the guard.
- **Surfaces as:** QUIETLY WRONG rather than an exception -- the code proceeds with the value the guard should have rejected (a short slice, an unclamped index), so the failure re-emerges downstream as a DIFFERENT exception type than the caller's `except` clause was written for.
- **Do NOT flag when:** A repeated guard is CORRECT when its own operand was rebound in between -- the `path = ...; if path.is_file(): return ...` loop idiom, or `token, value = get_fws(value)` before re-checking `value`. The check must consider bindings at any nesting depth and via tuple targets; missing either produces false positives on very common code.
- **Confirmed instances:** CPython _pyrepl terminfo.py:401 (6080c86) -- `end_offset = offset + 2 * str_count` then `if offset > len(data)`, repeating line 396. A truncated terminfo file yields a short slice; if its length is odd `struct.iter_unpack` raises `struct.error`, which is not a `ValueError` and so escapes `__post_init__`'s `except (OSError, ValueError)`, defeating `fallback=True` and disabling PyREPL for the session. Found by reports/pyrepl_v1.

#### `signed-length-from-untrusted-header` — A length or offset unpacked SIGNED from an untrusted binary header

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `struct.unpack` with a signed integer code (`b`/`h`/`i`/`l`/`q`/`n`, as opposed to their uppercase unsigned twins) binding a name that is then used as a length, offset, count, or index -- with only upper-bound validation (`if offset > len(data)`) and no check that the value is non-negative.
- **Guarded twin (the fix):** The uppercase format code (`<HHHHHH` instead of `<hhhhhh`), or an explicit `if size < 0: raise`, or a clamp (`max(0, size)`). For terminfo specifically the twin is ncurses itself, which range-checks all six header fields.
- **Sibling hunt:** Every other field unpacked from the same header, then every other header parser in the module: the signed format code is chosen once for a whole struct and copied to the next one. Also check whether the format was transcribed from a C header, where the fields were `short` and the C reader did its own range check.
- **Expected behaviour:** a malformed or hostile file is rejected at the header check.
- **Surfaces as:** SILENT, and this is the whole point -- in C a negative length is an out-of-bounds read that usually crashes, but Python's negative slicing RE-ANCHORS from the end of the buffer. `data[-5:10]` is a legal, non-empty slice. So a crafted file parses with no error at all and yields attacker-chosen bytes, which the caller then trusts.
- **Do NOT flag when:** A header the program itself just WROTE is not untrusted -- test fixtures that round-trip their own structs are the main medium-confidence noise. A sentinel comparison (`if size == -1`) is not a bounds check: it excludes exactly one negative value. Conversely `if not size` is not one either, since it only tests zero. Only a comparison that actually excludes the negative range, or a clamp, discharges the obligation.
- **Confirmed instances:** CPython _pyrepl terminfo.py:373 (6080c86) -- five header counts unpacked `<hhhhhh` with only upper-bound checks. A negative `name_size` drives `offset` negative; a 100-byte crafted file parses without error and yields attacker-chosen `bel`/`clear` byte strings that `UnixConsole` writes straight to the terminal. ncurses range-checks all six fields and refuses `$TERMINFO` under setuid; this reimplementation does neither. Found by reports/pyrepl_v1.; CPython multiprocessing/connection.py:449 -- `size, = struct.unpack('!i', ...)` guarded only by `if size == -1` (a SENTINEL test, which does not exclude other negatives) before reaching `self._recv(size)`.

#### `asymmetric-encode-decode-pair` — The same file read and written with different text codecs, so a round-trip is lossy

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** One path opened for reading and for writing with different `encoding=`/`errors=`. The destructive form is a LENIENT read (`errors='replace'`/`'ignore'`) paired with a strict write: the read substitutes replacement characters for bytes it cannot decode, and the write persists those substitutions, so the original bytes are gone. The binary variant hides the codec in a hand-written `.decode(enc, errors='replace')` next to an `open(p, 'rb')`.
- **Guarded twin (the fix):** The same `errors=` on both sides -- `surrogateescape` is the round-trip-safe choice and is what `Modules/readline.c` uses for exactly this file. Any codec is acceptable as long as decode and encode agree.
- **Sibling hunt:** For every path the module opens for writing, find every read of the same path and diff `encoding=`/`errors=`. Then widen past `open`: the same asymmetry appears as escape-at-one-granularity/unescape-globally, and as a format marker the reader understands but the writer never emits. Property-test `unescape(escape(x)) == x` over a corpus containing the escape characters themselves.
- **Expected behaviour:** reading a file and writing it back leaves it byte-identical.
- **Surfaces as:** SILENT and IRREVERSIBLE. Nothing raises -- that is what `errors='replace'` bought. The data is destroyed on the first write-back, so by the time anyone notices, the original is gone.
- **Do NOT flag when:** A deliberate TRANSCODER reads in one codec and writes another BY DESIGN -- read the write to see whether it is a write-back of what was read or a conversion. A path opened under three or more distinct codecs is a module varying the codec on purpose (codec test suites do this, and they dominated the raw output by two orders of magnitude), so it is not evidence of asymmetry. Two different variable names are not evidence either -- they may hold the same value.
- **Confirmed instances:** CPython _pyrepl readline.py:443 vs :460 (6080c86) -- history read decodes with `errors='replace'`, write is strict UTF-8. A latin-1 `~/.python_history` is destroyed unrecoverably on first exit: `b'caf\xe9'` becomes `b'caf\xef\xbf\xbd'`. `Modules/readline.c` uses `surrogateescape` on BOTH sides and round-trips correctly. `site.register_readline` writes at exit, so one launch suffices. Found by reports/pyrepl_v1.

#### `one-lifecycle-hook-two-meanings` — A commit-semantic lifecycle hook invoked on the abort path

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A hook whose NAME means 'the operation completed' (`finish`, `commit`, `save`, `accept`, `submit`, `done`, `complete`, `finalize`) called from a scope whose name means the operation was ABANDONED (`cancel`, `abort`, `interrupt`, `ctrl_c`, `rollback`, `discard`, `reject`, `escape`). The override implements only the success meaning -- it persists something -- so tearing down through it records work the user cancelled.
- **Guarded twin (the fix):** Parameterize the hook by outcome so it implements both meanings. `tkinter/dnd.py` is the stdlib's model: `finish(self, event, commit=0)`, where `on_release` calls `self.finish(event, 1)` and `cancel` calls `self.finish(event, 0)`. The alternative twin is a separate `abort()`/`discard()` entry point.
- **Sibling hunt:** Enumerate every call site of each overridden `finish`/`close`/`commit`/`cleanup` and flag any on an error or cancel path. Then read the OVERRIDE, not the base: the base class hook is usually a harmless no-op and the subclass is where the success semantics were added, which is why this survives review.
- **Expected behaviour:** abandoning an operation leaves no trace of it.
- **Surfaces as:** SILENT, and privacy-relevant when the persisted thing is user input. Nothing raises; the abandoned work simply shows up later as though it had completed.
- **Do NOT flag when:** RELEASE-semantic hooks (`close`, `cleanup`, `flush`) mean 'let go of the resource', which is correct on both paths -- checking them buries the signal, so they are excluded by construction. A call in EXPRESSION position is a predicate being read, not a hook being invoked: `if self.done():` is asyncio's `Future.done()` query and was the largest false-positive class in the raw pass. If the abort path passes different arguments than the success path, the hook is being TOLD which outcome it is handling -- that is the guarded twin, not the bug. On a resource-like receiver (`console`, `socket`, `stream`) a commit-named hook may still just mean tear-down; report it lower rather than suppressing it.
- **Confirmed instances:** CPython _pyrepl commands.py:225-229 (6080c86) -- `ctrl_c`/`interrupt` call `reader.finish()` on the ABORT path, but `HistoricalReader.finish()` implements 'line accepted' and appends to history. So Ctrl-C persists the abandoned line to `~/.python_history`; verified that an abandoned `print(SECRET_TOKEN)` reaches disk. GNU readline discards on SIGINT. Found by reports/pyrepl_v1.

#### `api-value-domain-mismatch` — A guard compares against a value the API can never return

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** An `==`/`!=` between a call to an API with a KNOWN return domain and a constant outside it. `unicodedata.category(k) == "C"` is the archetype: the API returns two-letter subclasses (`Cc`, `Cf`, ...), so the comparison is false for every input.
- **Guarded twin (the fix):** `.startswith("C")`, or membership in the set of two-letter codes -- the idiom used at the stdlib's own call sites.
- **Sibling hunt:** Every other comparison against the same API in the module, then every guard written from the same mental model (an author who thinks `category` returns one letter usually wrote more than one).
- **Expected behaviour:** the branch fires for the inputs it names.
- **Surfaces as:** SILENT and INVERTED -- the guard looks like validation, reviews like validation, and never fires, so the rejected inputs fall through into the accepting branch. Worse than no guard, because the reader stops looking.
- **Do NOT flag when:** Only APIs with a genuinely closed domain give high confidence. `sys.platform` is open-ended -- new platforms appear -- so an unrecognized value there is medium, not a certainty. A `.startswith()` or an `in` against a prefix is the CORRECT idiom and must never be flagged.
- **Confirmed instances:** CPython _pyrepl input.py:94 (6080c86) -- `unicodedata.category(key) == "C"` can never be true, so unbound control characters self-insert into the buffer (a\x00b, a\x1cb) and the misclassification is then cached permanently into the root keymap. Found by reports/pyrepl_v1.

#### `isinstance-on-container-not-element` — isinstance tests the container where the element was meant

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `isinstance(x, T)` where the same scope already subscripted `x` (`x[0]`) BEFORE the test, proving `x` holds a sequence, and `T` is not a sequence type. The object built from the sequence is usually sitting in a neighbouring variable with a similar name.
- **Guarded twin (the fix):** The neighbouring variable holding the constructed object -- in the confirmed instance `command` beside `cmd`, with the correct idiom at completing_reader.py:257.
- **Sibling hunt:** Every other use of the shorter name in the same function; the collision that produced it (`cmd` vs `command`) tends to recur wherever the pair is in scope together.
- **Expected behaviour:** the branch fires when the object is of that type.
- **Surfaces as:** SILENT -- always False, so the guarded branch is dead and its inverse always runs.
- **Do NOT flag when:** ORDER is everything. `if not isinstance(other, Counter): return NotImplemented` followed by `other[elem]` is the CORRECT idiom -- the guard comes first and the subscript is safe because of it. Only a subscript that PRECEDES the test is evidence, and a subscript inside a conditional body proves nothing because it usually sits under a type guard of its own. Testing a sequence against a sequence type is also normal.
- **Confirmed instances:** CPython _pyrepl reader.py:675 (6080c86) -- `isinstance(cmd, commands.digit_arg)` tests the spec TUPLE, not the command object, so kill-ring and yank-pop semantics break across a numeric argument. Found by reports/pyrepl_v1.; CRF-PYREPL-0005 -- isinstance tests the command spec tuple, not the command object

#### `mock-callable-as-spec` — A callable passed to Mock() where side_effect was meant

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `MagicMock(lambda ...)` / `Mock(some_function)`. The first positional parameter of the Mock constructors is `spec`, which is used only to derive the mock's attribute set. The callable is never called.
- **Guarded twin (the fix):** `side_effect=` or `return_value=` -- in the confirmed instance the correct form appears two lines away in the same file.
- **Sibling hunt:** Every Mock construction in the module: this is a copy-paste shape, and the confirmed instance had seven sites.
- **Expected behaviour:** the stub supplies the value the callable computes.
- **Surfaces as:** NEVER, by construction. The mock returns a fresh Mock, which is truthy and has every attribute, so every assertion downstream passes vacuously and the test reports coverage it does not have.
- **Do NOT flag when:** `Mock(SomeClass)` is the DOCUMENTED use of spec and must not be flagged; only a lambda or a locally-bound function is evidence of the confusion.
- **Confirmed instances:** CPython _pyrepl test_unix_console.py (6080c86) -- `MagicMock(lambda _: (h, w))` at 7 sites, with the correct `side_effect=` form two lines away. Found by reports/pyrepl_v1.

#### `decode-error-treated-as-incomplete` — A decode failure handled as "need more bytes", with no invalid case

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A `try` containing a `.decode()` whose handler for `UnicodeError`/`UnicodeDecodeError` simply gives up (`return`/`pass`/`break`), inside a function that accumulates into a buffer. The code cannot tell an INCOMPLETE multi-byte sequence from an INVALID one, and treats both as incomplete.
- **Guarded twin (the fix):** `codecs.getincrementaldecoder`, which distinguishes the two cases by construction; or an explicit buffer bound that drops the offending byte with a diagnostic.
- **Sibling hunt:** Every accumulate-and-retry loop in the module -- byte queues, framing readers, line splitters all share this structure.
- **Expected behaviour:** invalid input is rejected; incomplete input waits for more.
- **Surfaces as:** A SILENT HANG, which is the worst variant. On invalid input the buffer is never drained, so it grows without bound and the stream goes permanently deaf. Nothing raises, nothing logs, and the process looks alive.
- **Do NOT flag when:** A handler that DRAINS or bounds the buffer before giving up has discharged the obligation. Note that `_dotted_name`-style resolution misses `bytes(buf).decode(...)` because a call sits in the receiver chain -- read the method name off the attribute, or the archetypal instance is invisible.
- **Confirmed instances:** CPython _pyrepl base_eventqueue.py:104 (6080c86) -- one undecodable byte wedges the event queue permanently and the REPL goes deaf to all further input; the next Backspace trips `assert len(self.buf) == 1`. ENCODING is sys.getdefaultencoding() regardless of locale, so a latin-1 paste suffices. Found by reports/pyrepl_v1.

#### `unvalidated-numeric-from-environment` — A dimension read from the environment with no range check

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `int(os.environ[...])` / `int(os.getenv(...))` used as a size, count, or dimension with no comparison or clamp. Typically one branch of a multi-source value, where the OTHER branch -- the syscall -- is validated.
- **Guarded twin (the fix):** The sibling branch in the same function that does check (`if not height: return 25, 80`). The twin is usually a few lines away, which is what makes the omission visible once you look.
- **Sibling hunt:** Every environment read in the module, then every other multi-source value: the unvalidated branch is systematically the untrusted one.
- **Expected behaviour:** a hostile or nonsensical environment value is rejected or clamped.
- **Surfaces as:** An UNRECOVERABLE LOOP in the confirmed instance rather than a clean error -- COLUMNS=0 raises ZeroDivisionError inside readline(), which the REPL loop retries forever, spewing tracebacks and never exiting.
- **Do NOT flag when:** The validation may be applied to the NAME the value was bound to rather than to the call expression -- resolve the binding or every guarded instance is reported. `if not x` counts as awareness even though it only excludes zero. Confidence is high only when the same scope validates a value from a different source, because that proves the author knew the check was needed.
- **Confirmed instances:** CPython _pyrepl unix_console.py:471 (6080c86) -- COLUMNS=0 gives ZeroDivisionError at reader.py:347 and LINES=0 gives IndexError, both inside readline(), so the REPL retries forever. The ioctl branch guards `if not height`; the env branch, which takes precedence and is user-controlled, validates nothing. Found by reports/pyrepl_v1.

#### `wrapper-mutates-foreign-collection` — A wrapper mutates a collection it reached through another object

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A resizing mutation (`append`/`insert`/`pop`/`clear`, or `del x[:]`) on an attribute of a call result -- `self.get_reader().history.append(...)`. The wrapper reaches past the owner's API into its data.
- **Guarded twin (the fix):** A method on the owner that mutates the collection AND updates its bookkeeping in the same step.
- **Sibling hunt:** Every attribute the owner maintains alongside the collection -- a cursor, a parallel list, a dirty flag -- and every other site that reaches through to the same data.
- **Expected behaviour:** the owner's invariants hold after the mutation.
- **Surfaces as:** SILENT and DELAYED. The data is correct; the bookkeeping is stale, so the failure surfaces later in the owner's own code and looks like the owner's bug.
- **Do NOT flag when:** Mutating one's OWN attribute is not this shape. Neither is using an object a call returned (`self.get_list().append(x)`) -- the receiver must be an ATTRIBUTE OF a call result, which is what 'reaching past the API into its data' means structurally.
- **Confirmed instances:** CPython _pyrepl readline.py (6080c86) -- `del history[:]` and `history.append(...)` go straight at the list while historical_reader maintains `historyi` and `transient_history` alongside it. Found by reports/pyrepl_v1.

#### `save-state-clobbered-by-reentry` — A snapshot-then-modify method with no guard against running twice

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A method that stores state into `self.<attr>` via a `get`-style call and then modifies that same state via the matching `set`-style call, where `<attr>` is read by a `restore`/`__exit__`/`close` sibling and nothing guards a second entry.
- **Guarded twin (the fix):** An idempotence guard (`if self._saved is None:`), or splitting save from apply so the snapshot happens once.
- **Sibling hunt:** Every path that can re-enter the method -- signal handlers, suspend/resume, nested context managers, retry loops.
- **Expected behaviour:** restore() returns the system to the state before the FIRST call.
- **Surfaces as:** Damage OUTSIDE the process, which no test sees. In the confirmed instance the terminal is left in raw mode after the interpreter exits, and the user must type `reset` blind.
- **Do NOT flag when:** `__init__` and `__enter__` are SUPPOSED to snapshot and cannot be re-entered on the same object -- flagging them produced 60 findings dominated by ordinary initialization. The modify must be the same API as the snapshot (tcgetattr/tcsetattr), not merely any `set`-prefixed call.
- **Confirmed instances:** CPython _pyrepl unix_console.py (6080c86) -- prepare() snapshots termios AND modifies it, and is called twice across the SIGCONT boundary, so the saved 'original' is the raw state. Ctrl-Z, fg, exit leaves the terminal wedged. Found by reports/pyrepl_v1.

#### `return-ignored-against-checked-family` — A status-returning binding discarded where its siblings are all checked

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** In a module that binds foreign functions (ctypes/_winapi/msvcrt), a CamelCase call used as a bare statement while three or more sibling calls in the same file have their result tested.
- **Guarded twin (the fix):** Every other foreign call in the same file -- the argument is the file's OWN convention, not an external rule.
- **Sibling hunt:** Every foreign call in the module, and then the paired twin of each flagged one (a Get whose Set is checked, or vice versa).
- **Expected behaviour:** a failed call raises rather than being ignored.
- **Surfaces as:** SILENT -- the following code operates on state it never established, so the symptom appears far from the cause and looks like a logic bug.
- **Do NOT flag when:** The FFI gate is load-bearing. Without it the check fires on every test module that constructs CamelCase objects as bare statements: 720 of 787 raw findings were tests. 'Checked' must also mean actually TESTED -- an if/while/assert test or a comparison. Counting every non-statement position also counted `f(Foo())` and inflated the sibling count until the convention argument became meaningless.
- **Confirmed instances:** CPython _pyrepl windows_console.py:152,156 (6080c86) -- GetConsoleMode/SetConsoleMode discard their return values while every other Win32 call in the file is checked. Found by reports/pyrepl_v1.

#### `divergent-sentinel-across-parallel-modules` — Parallel implementations construct one type with different empty-value sentinels

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** Two modules that are per-platform implementations of one interface (`unix_console.py` / `windows_console.py`) construct the same type with different empty-ish literals at the same argument position -- `None` on one side, `""` on the other.
- **Guarded twin (the fix):** The side that emits the safe value. Note the twin relation is INVERTED here, which is why it survives review: that same side often ALSO carries a defensive guard it never needs, while the side that needs one has none.
- **Sibling hunt:** Every constructor shared by the parallel pair, and every consumer of the type -- the consumer is written against whichever side its author ran.
- **Expected behaviour:** both implementations of an interface produce interchangeable values.
- **Surfaces as:** A TypeError on the platform the author does not develop on, under a condition their CI does not reach. In the confirmed instance: resize the terminal during a bracketed paste.
- **Do NOT flag when:** Requires a genuine parallel pair, detected by a platform filename prefix. Two unrelated modules using different sentinels for different types is not this shape. Because it compares files, it is a PROJECT-level check and cannot run per-file.
- **Confirmed instances:** CPython _pyrepl unix_console.py:335,780 (6080c86) -- Unix emits Event(evt, None) where the Windows twin emits Event(evt, ""); getpending() then does `e.data += e2.data` and raises TypeError. Windows carries a defensive `if e2:` it does not need; Unix, which needs one, has none. Found by reports/pyrepl_v1.

#### `unguarded-inverse-of-guarded-operation` — An operation guarded by a policy flag, with its inverse unguarded

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** `obj.collection.append(x)` under an `if <policy flag>`, and `obj.collection.pop()` elsewhere in the same package with no guard at all. Turn the policy off and the inverse still runs.
- **Guarded twin (the fix):** The guarded add itself -- the condition it carries is exactly the one the inverse is missing.
- **Sibling hunt:** Every inverse pair on the same owned collection (append/pop, add/discard, acquire/release), and every consumer of the policy flag.
- **Expected behaviour:** when the policy says no, neither half runs.
- **Surfaces as:** DESTRUCTIVE and silent -- the inverse consumes something it never added, so it removes a NEIGHBOURING entry (the user's data) or raises IndexError on empty.
- **Do NOT flag when:** Three filters carry this shape, and dropping any one buries it. The guard must read as a POLICY switch (a bare name or attribute, possibly ANDed with a data condition) -- an `if` on the data itself is algorithmic and an unguarded inverse beside it is normal. The collection must be OWNED by an object (`reader.history`), not a bare local: generic locals like `parts`/`lines` otherwise match across unrelated files. And add and remove must be in different functions, or it is one algorithm managing its own stack.
- **Confirmed instances:** CPython _pyrepl simple_interact.py:124 (6080c86) -- `reader.history.pop()` is unconditional while the append it inverts (historical_reader.py:415) is guarded by should_auto_add_history. With readline.set_auto_history(False), which is public API, typing `clear` destroys the user's manually-managed history entry. Found by reports/pyrepl_v1.

#### `empty-container-read-as-absent` — A truthiness test standing in for `is None`, where the container is legitimately emptied in place

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `if not self.cache:` used to mean `if self.cache is None:` -- an absent-vs-present test written as a truthiness test -- in a codebase where the container is deliberately emptied IN PLACE rather than replaced. After the first flush the container is falsy but present, and the branch meant for 'we have never seen this' runs against fully-initialized state.
- **Guarded twin (the fix):** `is None` on the same attribute -- often already spelled correctly on a sibling path or in a parallel implementation, which is what makes the two backends diverge. The in-place emptying is usually deliberate and carries a comment explaining why it cannot be `.clear()` on the outer dict.
- **Sibling hunt:** Find every place the project empties a container IN PLACE (a comment usually says the values are still in use higher up the stack), then find every truthiness test on those containers. Compare against a parallel implementation if one exists -- the divergence after a flush is the reproduction.
- **Expected behaviour:** an emptied-but-present container takes the same branch as a full one; only a genuinely absent one takes the absent branch.
- **Surfaces as:** SILENT and ORDER-DEPENDENT -- correct until the first flush, then wrong, and in the confirmed instance permanently wrong for the remaining lifetime of the affected frame.
- **Do NOT flag when:** Distinct from `falsy-check-for-none-default`, which is about a PARAMETER with a None default and a caller passing a falsy value. Here the value is an attribute the program empties itself. A truthiness test is correct when empty and absent genuinely deserve the same branch -- the tell is that they do not, because absent triggers initialization.
- **Confirmed instances:** CRF-COVPY-0038 -- PyTracer reads an emptied set as an untraced file and turns line events off for the callee's whole frame

#### `partial-traversal-of-a-node-family` — A tree walk that visits only `.body`, missing orelse, handlers and finalbody

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `for child in getattr(node, "body", ())` or `node.body` as the sole descent in a walker over an AST or any other multi-block tree. Python statement nodes carry FOUR block lists -- `body`, `orelse`, `handlers`, `finalbody` -- so anything defined in an `else`, an `except`, a `finally`, or a loop-else is invisible. The `getattr(..., ())` is what makes it silent: a node with no body and a node whose other blocks were never consulted are treated identically.
- **Guarded twin (the fix):** `ast.iter_child_nodes()` or `ast.NodeVisitor`, which the standard library provides precisely so this cannot happen. Any other walker in the same project that uses them is the twin.
- **Sibling hunt:** Grep for `.body` in an iteration or descent position and check whether the same walker also reads `orelse`, `handlers`, `finalbody`. Construct a fixture defining the target construct in all six positions -- if-body, else, try, except, finally, for-else -- and count what comes back; the confirmed instance returned two of six. Apply the same test to walkers over JSON schemas, config trees, and IR.
- **Expected behaviour:** the walk reaches every node of the family regardless of which block it is written in.
- **Surfaces as:** SILENT -- as absent entries in an index, wrong function counts, and lines falling into an 'unattributed' bucket.
- **Do NOT flag when:** A walker that deliberately handles only one block is fine if it is documented and its callers know -- but check the callers, because they usually do not. `getattr(node, 'body', ())` is the strongest single tell and worth grepping for on its own.
- **Confirmed instances:** CRF-COVPY-0034 -- region analysis walks only .body; four of six functions are invisible, corrupting LCOV function counts and the HTML/JSON function index

#### `prefix-rewrite-done-as-a-content-search` — A path prefix replaced with str.replace or a greedy regex instead of a positional splice

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A path or namespace prefix is rewritten with `path.replace(matched, new)` -- unbounded, so it hits every later occurrence too -- or with a regex whose leading `(.*[\\/])?` is greedy, so the reported match runs to the LAST occurrence and swallows intermediate components. One regex is doing two jobs, 'does it match' and 'how long is the prefix', and greedy matching is only correct for the first.
- **Guarded twin (the fix):** A sibling in the same module that strips the same class of prefix correctly -- a `startswith` test followed by `s[len(prefix):]`, or a matcher that checks an explicit separator boundary. The same tokens are frequently reused SAFELY elsewhere in the project for a boolean-only match, which is why the bug is invisible in review.
- **Sibling hunt:** Grep for `.replace(` where the receiver is a path and the search term came from a match, and for regexes combining a greedy leading wildcard with a captured prefix. Reproduce with a path that repeats a component (`proj/sub/proj/mod.py`) -- the shape is invisible when the prefix occurs once. Check whether a plausibility guard downstream (an `exists()` test) is silently discarding mangled results, which is what turns a loud failure into a quiet one.
- **Expected behaviour:** only the leading prefix is rewritten, and the rest of the path is preserved byte for byte.
- **Surfaces as:** SILENT -- a file vanishes from the output and its data is attributed to a different, unrelated file that shares a component name.
- **Do NOT flag when:** `str.replace` is fine when the match is anchored at position 0 and known unique. The fix is always positional -- `new + path[match.end():]`. Note which documented pattern idioms are safe: a wildcard that cannot cross a separator is fine, one that can is not.
- **Confirmed instances:** CRF-COVPY-0035 -- str.replace plus a greedy regex; a file disappears and its coverage lands on an unrelated never-executed file

#### `isinstance-second-arg-not-a-type` — isinstance/issubclass arguments transposed, so the predicate answers a different question

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `issubclass(cls, self.last_command)` where the second argument holds a runtime VALUE rather than the type being tested against. It does not raise, because the value happens to be a class, so the predicate simply returns the wrong answer and every branch it guards is effectively dead.
- **Guarded twin (the fix):** The same idiom written the right way round elsewhere in the project -- `issubclass(command, KillCommand)`, with the fixed type second.
- **Sibling hunt:** Check the SECOND argument of every isinstance/issubclass call. A literal class name or a tuple of them is fine; an instance attribute, a subscript, or a call result is a candidate, because the type being tested against is normally a constant of the module. Confirm by asking which of the two is the varying value.
- **Expected behaviour:** the predicate answers 'is this value one of these types', and the branches it guards are reachable.
- **Surfaces as:** SILENT. No TypeError is raised when the second argument happens to be a class, so the only symptom is a feature that never triggers.
- **Do NOT flag when:** Passing a dynamically-computed type as the second argument is legitimate -- a registry lookup, a generic. The evidence is that the FIRST argument is the constant and the second is the varying value, which is backwards. Distinct from `isinstance-on-container-not-element`, where the second argument is right and the first names the wrong object.
- **Confirmed instances:** CRF-PYREPL-0016 -- issubclass arguments transposed; every branch guarded by the predicate is dead

#### `falsy-test-on-a-zero-valued-enum-member` — `if not x:` where x is an int constant whose first member is 0

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A module defines mode constants as plain ints -- `ATTRS, FILES = 0, 1` -- and a filter is written `if (not mode or mode == FILES)`. `not 0` is True, so the zero-valued member always takes the 'unspecified' branch and is never actually filtered, while every other member is. Half the dispatch is protected and half is a no-op, which is why it reads correctly.
- **Guarded twin (the fix):** The non-zero leg of the same expression, which does compare explicitly; and the mirrored code path elsewhere that returns early instead of falling through. The docstring frequently promises the behaviour the zero member does not get.
- **Sibling hunt:** Find every int-constant group whose members start at 0 (`A, B = 0, 1`, an IntEnum with a zero member, a module-level `X = 0`), then find every truthiness test on a variable that carries one. Check the docstring for the intended semantics -- in the confirmed instance it promised the opposite of what the code did. Prefer `is None`, an explicit `== CONST`, or starting the enumeration at 1.
- **Expected behaviour:** the zero-valued member is treated as a value like any other, and only a genuinely absent argument takes the absent branch.
- **Surfaces as:** SILENT and asymmetric -- the feature works for every member except the first, which is also usually the default.
- **Do NOT flag when:** Distinct from `falsy-check-for-none-default`, which is about a parameter with a None default and applies even when the parameter is never reassigned -- this shape needs constant tracking to see that a falsy non-None value is reachable, and it fires even where the parameter IS reassigned. Not a defect if zero and absent genuinely deserve the same branch.
- **Confirmed instances:** CRF-IDLELIB-0004 -- a mode filter never applies to the zero-valued member, so a directory listing pops up inside a string literal

#### `attribute-created-outside-init` — An attribute created only by one method and read unconditionally by another

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `self.state` is assigned nowhere in `__init__` -- only inside another method, sometimes as the first line of a `try` -- and a third method reads it with no `hasattr` guard and no class-level default. Any entry point that reaches the reader before the writer has run raises AttributeError, and it is usually a user-facing command that is enabled unconditionally in the interface.
- **Guarded twin (the fix):** A parallel implementation of the same feature that DOES handle the not-yet state -- in the confirmed instance a sibling code path that shows a 'there is no stack trace yet' dialog. A class-level default, or initialization in `__init__`, is the fix.
- **Sibling hunt:** Collect every `self.X` assigned in the class and every `self.X` read; the reads whose name is never assigned in `__init__` or at class level are the candidates. Then check reachability: an interface entry point that is always enabled, or an error path that runs before the normal one. Reading the attribute inside an exception handler is a strong signal, because the handler runs precisely when the normal flow did not.
- **Expected behaviour:** every attribute a method reads exists from the moment the object does.
- **Surfaces as:** As an AttributeError from a user action taken in an unexpected order -- reported as 'internal error' rather than as the missing feature it is.
- **Do NOT flag when:** Deliberate lazy attributes guarded by `hasattr`, `getattr(self, x, default)`, or `try/except AttributeError` are fine, as are attributes documented as only valid within a lifecycle phase. `__slots__` classes and dataclasses need their own handling. The finding requires an UNGUARDED read plus a reachable path that skips the writer.
- **Confirmed instances:** CRF-IDLELIB-0008 -- an attribute assigned only inside one method's try block, read by an always-enabled menu command; using it before running anything prints an internal exception

#### `handler-reads-a-name-the-try-may-not-have-bound` — An except handler reading a name bound only partway into the try body

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A name is assigned inside a `try` -- or inside a conditional within it -- and read by the `except` handler. If the exception fires before the assignment, the handler raises `NameError` (or `UnboundLocalError`) while handling the original error, replacing the real diagnostic with a confusing one. Inside a LOOP it is worse: the name retains its value from a previous iteration, so the handler acts on stale data and, in the confirmed instance, sends a reply under a completed request's sequence number.
- **Guarded twin (the fix):** Initializing the name to a sentinel before the `try` and testing it in the handler. A sibling handler in the same module that does exactly this is the usual twin.
- **Sibling hunt:** For each `except` block, take the names it reads and check whether each is bound before the `try` begins or on every path through the body up to the earliest raising statement. Conditional binding inside the try (`if request: seq = ...`) is the most common form. Loops raise severity: report the stale-value consequence, not just the NameError, since it is silent where the NameError is loud.
- **Expected behaviour:** the handler can run after a failure at any point in the try body.
- **Surfaces as:** As the WRONG EXCEPTION -- a NameError from the handler, masking the original error. In a loop it is fully SILENT: a response emitted under a stale identifier and delivered to the wrong waiter.
- **Do NOT flag when:** Fine when the name is bound before the try, is a parameter, is global, or when nothing in the try before the assignment can raise -- but note that almost anything can raise KeyboardInterrupt or MemoryError, so a bare `except:` weakens that defence considerably. A handler that only re-raises does not read the name and is not this shape.
- **Confirmed instances:** CRF-IDLELIB-0012 -- a bare except reads a name bound only inside a conditional in the try; on the first iteration it raises NameError and exits the subprocess, and on later iterations it replies under a stale sequence number

#### `unformatted-format-string-literal` — A `{name}` literal in a message nothing formats, so the braces reach the reader verbatim

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implemented — a scanner check emits candidates for this — triage them, don't re-derive
- **Pattern:** A plain string literal carrying a `str.format` replacement field -- `raise NotImplementedError('cannot guess for {sys.platform}')` -- passed as the sole argument to something that renders a message: an exception constructor, a `warnings.warn`, a logging call, a `print`. Nothing ever calls `.format` on it and it has no `f` prefix, so the field name is shown to the reader exactly as typed. Almost always a dropped `f`.
- **Guarded twin (the fix):** The same literal with an `f` prefix, or an explicit `.format(...)` on it. Both twins are usually present elsewhere in the same file, because the author writes far more of them correctly than not.
- **Sibling hunt:** For each instance, check every other message in the same module for the same slip -- a codebase that drops one `f` drops several, and they cluster in rarely-executed branches (a platform fallback, an unreachable `else`, an error path) because a formatted message would have been noticed the first time anyone saw it. Grep the whole tree for a brace field in a message argument, then apply the differential below.
- **Expected behaviour:** the reader sees the value the field names, not the field.
- **Surfaces as:** COMPLETELY SILENT. It is not an error to have braces in a string; the message simply renders wrong. It surfaces only when a human reads the output, which for an error path may be never.
- **Do NOT flag when:** Three filters carry this shape, and each corresponds to a real guarded twin. (1) ANY other argument on the call means something may still format the string -- `_pyrepl/trace.py` formats `line.format(*k, **kw)` only `if k or kw`, so `trace('{x}', v)` is correct. (2) A literal that is the RECEIVER of `.format`/`.format_map` is formatted in place -- `runpy.py:125` builds a multi-line braced message and formats it on the spot. (3) Only fields whose name is an IDENTIFIER count: `{}` and `{0}` are indistinguishable from a regex quantifier (`\d{4}`) or a literal brace in a character class, and those two classes alone were 90% of the raw candidates over CPython's `Lib/`. Also skip `${name}`, which is `string.Template` or shell syntax. A template CONSTANT consumed by a formatter elsewhere (`_DEPRECATED_MSG` in `warnings`, `glob._deprecated_function_message`) is the commonest near-miss and is excluded by filter 1 at its call site.
- **Confirmed instances:** CPython Lib/test/test_tarfile.py:3871 -- `raise NotImplementedError("Need to guess component length for {sys.platform}")`, in the `else` branch of a platform check. The ONLY finding across 1,847 files of CPython's Lib/, with zero false positives.

#### `zip-truncates-on-length-mismatch` — `zip()` without `strict=` silently truncates when the two sides disagree in length

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `zip(a, b)` where the two operands come from DIFFERENT computations over the same underlying data -- one from arithmetic over an index (`range(...)`, a parsed line number, a slice bound), the other from the data itself (`.splitlines()`, `.readlines()`, a widget query, a directory listing). When they disagree, `zip` stops at the shorter one and the surplus is dropped with no error and no log line.
- **Guarded twin (the fix):** `zip(a, b, strict=True)`, which raises `ValueError` on the first mismatch. The twin is frequently in the project's OWN TESTS for the very function that lacks it -- idlelib's `idle_test/test_sidebar.py:764` passes `strict=True` while `pyshell.py:1002`, the production code it tests, does not.
- **Sibling hunt:** Rank every un-stricted `zip` by whether the operands share a derivation. Same expression on both sides, or two calls with an identical count argument, are structurally equal -- skip them. Escalate when one side comes from `range()`/`int()`/a slice bound and the other from a split, a read, or a query. Then grep the tests for the same pairing done with `strict=True`.
- **Expected behaviour:** every element of both sequences is consumed; disagreeing lengths are a bug the program surfaces.
- **Surfaces as:** SILENT -- a short file, a missing last row, a clipboard one line short. In test code it is worse than silent: the test still passes, having asserted less than it claims.
- **Do NOT flag when:** Do NOT report when both operands are provably equal-length: a list zipped against a comprehension over it, `zip(x[::2], x[1::2])` over a contract-even sequence, or two generators sharing a count argument. Ragged truncation must be REACHABLE, not merely unproven. Conversely a `zip` in a test pairing EXPECTED against ACTUAL is worth flagging even when currently balanced -- there truncation silently weakens the assertion, which is `test-cannot-fail` arriving by another route.
- **Confirmed instances:** CPython Lib/idlelib/pyshell.py:1002 -- copy-with-prompts drops the last selected line whenever the selection ends at a column that is a multiple of 10; verified against a live tkinter.Text; CPython Lib/idlelib/idle_test/test_searchbase.py:122,134 -- zip(declared_options, actually_packed_widgets); a dialog packing too few buttons would pass vacuously

#### `guard-conjoined-with-a-preference-flag` — A validity guard ANDed with a preference flag, so turning the preference off removes the guard

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** An early return that combines a validity test with a configuration flag governing only a side effect: `if value is None and self.NOTIFY: notify(); return`. Turn the preference off and the guard disappears entirely, letting the invalid value reach code that dereferences it. It reads correctly because the null test IS present and the preference defaults to on -- so the bug is unreachable in every default configuration and in every test.
- **Guarded twin (the fix):** Split the conjunction: the guard unconditional, only the side effect optional. Sibling callers in the same module almost always already return unconditionally on their own None conditions.
- **Sibling hunt:** Grep `if <null/validity test> and <FLAG>:` and its mirror, where FLAG is a module/class constant, a settings lookup, or a name matching BELL/VERBOSE/WARN/NOTIFY/DEBUG/QUIET/STRICT. Ask what the flag controls: a NOTIFICATION conjoined with a VALIDITY condition is the shape. Then flip the flag off and re-trace every consumer past the guard for a subscript or attribute access.
- **Expected behaviour:** the invalid value is rejected on every path; the preference only decides whether the user is told.
- **Surfaces as:** SILENT under every default configuration, then a hard TypeError/AttributeError once the preference is changed -- reported as 'turning off the bell broke bracket matching', which points at the notification rather than the guard.
- **Do NOT flag when:** Not this shape when both conjuncts are data conditions, nor when the flag selects a different valid behaviour rather than a notification. Discriminator: does the code after the guard tolerate the value the guard was testing for? If it dereferences it, the conjunction is the bug.
- **Confirmed instances:** CPython Lib/idlelib/parenmatch.py:97 -- `if indices is None and self.BELL:`; unchecking 'Bell on Mismatch' makes an unmatched bracket raise TypeError out of a Tk callback and leaves the restore bindings registered

#### `per-line-property-derived-from-the-aggregate` — A per-element property computed once from the concatenated whole, then applied to every element

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A property that belongs to each ELEMENT -- a comment prefix, an indent width, a field separator, a record header -- is derived once from the joined value (`header = get_header('\n'.join(lines))`) and applied to all of them. An anchored regex or a `split()[0]` answers for element one only; the consumer then does `line[len(header):]` on every element, so each one that lacked the property loses that many leading characters.
- **Guarded twin (the fix):** The sibling path that ESTABLISHES the invariant before relying on it -- typically a loop extending the region only while `get_header(line) == header`. That twin usually exists in the same module for the auto-detect case, with the bug living in the explicit/user-supplied-range case.
- **Sibling hunt:** Find every helper named or documented for a single line/record and grep its call sites for one passing a joined or multi-line value. Then check whether the consumer applies the result per-element. Reproduce with a two-element input whose first element has the property and the second does not -- the shape is invisible on homogeneous input, which is why every test passes.
- **Expected behaviour:** each element is transformed according to its own properties, or the operation refuses a heterogeneous region.
- **Surfaces as:** SILENT DATA LOSS. Nothing raises; a fixed number of leading characters simply disappears from every non-conforming element, proportional to the first element's prefix length.
- **Do NOT flag when:** Fine when the aggregate genuinely has one answer (a file-level encoding, a uniform delimiter). The evidence is an ANCHORED match (`^`) or a first-element pick applied across a multi-element value, plus a consumer that slices by the derived length.
- **Confirmed instances:** CPython Lib/idlelib/format.py:57-59 -- Format Paragraph over a selection whose first line is a comment: verified by execution, `result = compute(a, b)` becomes `esult = compute(a, b)` and the result is written back to the buffer

#### `viewport-scoped-index-consumed-globally` — A render-scoped cache read by a consumer that iterates the whole model

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A dict or list built for RENDERING -- populated only while walking the currently-visible rows, reset on every redraw -- is later read by a consumer that iterates the FULL range and treats a missing key as a legitimate 'no value' (`.get(k)` -> None) rather than as 'not indexed'. The display cache silently doubles as a data model.
- **Guarded twin (the fix):** A consumer that recomputes the property from the underlying model rather than the render cache, or a producer that indexes the whole model and only DRAWS the visible slice.
- **Sibling hunt:** For every attribute assigned inside a paint/redraw/update method, find every reader outside that method. Flag any reader whose key range comes from the full model rather than the same visible window. `.get(k)` with an implicit None default is the strongest tell, because it converts 'absent' into a valid value. Reproduce by making the model taller than the viewport and scrolling before invoking the consumer.
- **Expected behaviour:** the consumer sees a value for every element of the model, not only those currently on screen.
- **Surfaces as:** SILENT and SCROLL-DEPENDENT. The output is well-formed and merely incomplete, and it is correct whenever the model fits on one screen -- so it survives every small-input test and every interactive check.
- **Do NOT flag when:** Not this shape when the consumer's range is itself bounded by the same viewport, nor when a missing key is explicitly distinguished from a null value. The bug requires BOTH the render-scoped producer AND a full-range consumer that cannot tell absent from empty.
- **Confirmed instances:** CPython Lib/idlelib/sidebar.py:466-486 -> pyshell.py:997 -- shell prompts are indexed with `@0,0` + `dlineinfo` (viewport-only) and consumed across the whole buffer on save, so every prompt scrolled off-screen is missing from the saved file

#### `structured-index-tested-by-string-suffix` — A structured index interrogated with a string operation instead of being parsed

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A value with internal structure -- a Tk text index `line.col`, a dotted version, an `ip:port`, a `path:lineno` -- is tested with `[-1]`, `endswith`, `startswith` or a slice in place of splitting it and comparing the field numerically. The test then agrees with the intended predicate only for a subset of values: `sellast[-1] != '0'` means `column != 0` for single-digit columns and silently means the wrong thing for 10, 20, 100.
- **Guarded twin (the fix):** Parse then compare -- `int(index.split('.')[1]) != 0` -- or use the API's own arithmetic. A correct sibling is usually adjacent: idlelib's own `text.index('sel.first linestart')` on the line above does exactly this for the start index while the end index is tested by suffix.
- **Sibling hunt:** Grep for `[-1] ==`, `[-1] !=`, `.endswith(` and `.startswith(` applied to a variable produced by an index-, version-, address- or location-returning API. For each, ask which values of the underlying FIELD the character test misclassifies; a non-empty reachable set is a defect.
- **Expected behaviour:** the predicate holds for every value of the structured field, not only its single-character encodings.
- **Surfaces as:** SILENT and PERIODIC -- fails for one value in ten (or one in twenty-six), which reads as an intermittent glitch and is very hard to attribute from a bug report.
- **Do NOT flag when:** A string test on a genuinely flat string (a file extension, a scheme prefix) is correct and not this shape. The shape requires the value to have a PARSED field the test stands in for. Exclude cases where the field is provably single-character by construction.
- **Confirmed instances:** CPython Lib/idlelib/pyshell.py:1020 -- `if sellast[-1] != '0'` intends `column != 0`; verified against live Tk, selecting to column 10 or 20 drops the last line from the clipboard

### Owned by `silent-failure-hunter`

#### `asymmetric-rounding-between-display-and-gate` — The number shown to a human and the number a gate compares are rounded in opposite directions

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A project deliberately clamps a displayed percentage away from its endpoints -- so 100 is printed only when the value is truly 100 -- and then implements the threshold comparison, or a second output format, with a plain `round()` or a bare format spec. The gate passes on a value the report prints as failing, or a machine-readable format publishes an endpoint the human-readable one refuses to.
- **Guarded twin (the fix):** The display function that gets the direction right, and whose docstring usually states the intent explicitly. Every other consumer should be routed through it rather than reimplementing the arithmetic.
- **Sibling hunt:** Find the display/format helper and its stated rounding intent, then find every OTHER site that turns the same quantity into a number a consumer sees or compares -- gates, alternate report formats, exit-code decisions, API return values. Check each against the stated intent, and check whether it honours the project's precision setting.
- **Expected behaviour:** the number a gate compares is the same number the report prints, at the project's configured precision.
- **Surfaces as:** SILENT. A CI gate passes while the report a human reads says otherwise -- and each side is individually defensible, so neither looks wrong alone.
- **Do NOT flag when:** Different precision for different audiences is legitimate; different DIRECTION at an endpoint is not. The defect is specifically that one path can reach an endpoint value the other path is written to avoid. A partial fix that special-cases only the 100.0 threshold leaves every other threshold broken -- check the general case before assuming a closed issue covers it.
- **Confirmed instances:** CRF-COVPY-0007 -- --fail-under rounds toward 100 while the printed total clamps away from it; CRF-COVPY-0008 -- XML line-rate publishes 99.997% as exactly 1, bypassing the display helper entirely

#### `empty-result-conflated-with-absent` — A failure is collapsed into the same value a legitimate negative produces

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A helper answers a question -- does this config exist, where does this module live -- and swallows an error into the SAME value it returns for a legitimate 'no'. `except OSError: pass` leaving an empty parse result, or `except Exception: return None, []`. The caller cannot distinguish 'nothing to find' from 'we failed to look', so a permission error, an NFS glitch, or an import-time exception silently reconfigures the program.
- **Guarded twin (the fix):** The sibling path that does raise -- the explicitly-named config file, the caller's own `except` clause written to report exactly this. When that guard is unreachable because the callee already swallowed everything, the dead guard is itself the proof of intent.
- **Sibling hunt:** For every 'lookup that may legitimately find nothing', separate the not-found case from the failed-to-look case. Then check the CALLER for a handler that can never fire -- an unreachable `except` is the strongest available evidence that the swallowing was not intended. Reproduce by making the resource unreadable rather than absent.
- **Expected behaviour:** a not-found answer means the thing is not there; an error means an error, and reaches someone.
- **Surfaces as:** SILENT, exit 0, nothing on stderr. The program runs with a completely different configuration than the user believes.
- **Do NOT flag when:** Distinguish FileNotFoundError (a legitimate negative -- skip it) from every other OSError (a failure to look). A warning that fires but names the wrong cause is still this shape, at reduced severity. Not the same as `empty-container-read-as-absent`, which is a truthiness test on a value that was correctly produced.
- **Confirmed instances:** CRF-COVPY-0016 -- chmod 000 .coveragerc takes a report from 2 files/75% to 7 files/9%, exit 0; CRF-COVPY-0060 -- find_spec failure is indistinguishable from module-not-found, and the caller's except is dead code

#### `unchecked-no-op-sentinel` — A function whose 'I did nothing' answer is a return value nobody reads

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A setup or restart routine signals 'preconditions absent, I did nothing' by returning None or False, and a caller invokes it for effect and discards the result. The caller has already torn down the previous state, so the no-op leaves the system in a WORSE condition than not calling at all.
- **Guarded twin (the fix):** A sibling entry point that solves the same problem without the sentinel -- constructing the object directly from the live configuration rather than re-deriving it from environment variables, and raising or printing when that fails.
- **Sibling hunt:** For every function that can legitimately do nothing, find its callers and check whether any of them has already destroyed state that the call was supposed to replace. That teardown-then-optional-rebuild sequence is the shape. Compare against the project's own documentation of the feature: this shape usually contradicts a written contract, which raises it from misuse to defect.
- **Expected behaviour:** either the operation happens, or the caller learns that it did not in time to do something about it.
- **Surfaces as:** SILENT, exit 0. The measured or managed thing is simply less than it was, which reads as a smaller workload rather than a failure.
- **Do NOT flag when:** A no-op return is fine when the caller has not yet destroyed anything, or when the caller checks it. The severity comes from the teardown, not from the ignored return on its own. Distinguish from `return-ignored-against-checked-family`, which argues from a file's own convention rather than from a destroyed precondition.
- **Confirmed instances:** CRF-COVPY-0002 -- patch=fork stops the inherited collector and never restarts it, producing worse results than not patching at all

#### `external-registration-not-reestablished` — A registration the runtime can revoke is installed only on the first-sight path

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Code registers something with an external authority -- an interpreter-level event system, a signal handler, an atexit hook, a foreign library callback -- inside a branch guarded by 'have I seen this before'. The authority can revoke the registration independently (another consumer takes and releases the resource, a fork clears handlers), but the local bookkeeping still says 'seen', so the install block is skipped and the registration is never restored.
- **Guarded twin (the fix):** Sibling backends that re-check on every call rather than caching a first-sight decision, and produce the correct result on the same input. Their agreement with each other and disagreement with this one is the reproduction.
- **Sibling hunt:** For every registration with an external authority, ask what can revoke it without going through this code, and check whether the local cache would notice. Nested or concurrent use of the same library is the usual trigger. Reproduce by running the same program under two backends and diffing the results -- do not try to observe the revocation directly.
- **Expected behaviour:** the registration is live whenever the local bookkeeping says it is, or the bookkeeping is invalidated when the registration is lost.
- **Surfaces as:** SILENT and PERMANENT -- everything already seen stops working for the rest of the process, while newly-seen items keep working, so the failure looks partial and random.
- **Do NOT flag when:** Fine when the registration is process-global and cannot be revoked, or when the code owns the authority exclusively. The question is always whether a SECOND consumer of the same runtime facility exists.
- **Confirmed instances:** CRF-COVPY-0005 -- a nested consumer frees and re-takes the tool id, the runtime wipes the outer local events, and the first-sight guard prevents reinstalling them

#### `failure-result-cached-as-if-successful` — An error handler's fallback value written into a cache that outlives the error

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `try: value = compute() except Exception: value = <empty>` followed by an UNCONDITIONAL `cache[key] = value`. One transient failure -- a lock, a network hiccup, a concurrent rename -- is memoized for the lifetime of the process, so the system does not recover when the underlying condition does.
- **Guarded twin (the fix):** The success path of the same function, which caches a correct result. Moving the cache write inside the `try` is usually a one-line fix.
- **Sibling hunt:** For every `except`-with-fallback, check whether the fallback reaches a cache, a memo, a module-level dict, or an lru_cache-decorated return. Then check the except is narrow enough -- a bare `except Exception` here also catches the programming errors that should surface. Reproduce by failing once and then healing, and confirming the stale value persists.
- **Expected behaviour:** a transient failure degrades one call, not every subsequent call.
- **Surfaces as:** SILENT and STICKY -- correct before the glitch, wrong forever after, which makes it nearly impossible to reproduce from a bug report.
- **Do NOT flag when:** Caching a negative result is correct when the answer is genuinely stable (a capability probe). It is wrong when the failure is transient. Check the platform gate before rating severity -- in the confirmed instance the whole function is Windows-only, which lowers it substantially.
- **Confirmed instances:** CRF-COVPY-0023 -- a transient listdir failure is cached for the process lifetime, splitting one file's data across two spellings

#### `name-based-filter-cannot-distinguish-generated-from-authored` — A filter keyed on a name that both compiler-generated and user-written code can have

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Code skips compiler-generated constructs by matching a reserved-looking name -- a dunder the language emits for annotations, comprehensions, or lambdas -- when the language ALSO permits a user to define something with that name. User-written code silently inherits the skip, and its statements disappear from whatever the filter feeds.
- **Guarded twin (the fix):** None in-tree -- the AST is the available oracle. A generated construct has no corresponding definition node in the parsed source, and a user-written one does.
- **Sibling hunt:** For every skip keyed on a name, check the language reference for whether a user can produce that name. Newly-added dunders from recent PEPs are the richest source, because the filter is usually written the week the PEP lands. Then check which direction the error runs: statements dropped from a denominator INFLATE a percentage, which is the failure mode nobody reports.
- **Expected behaviour:** the filter skips exactly the constructs the compiler generated.
- **Surfaces as:** SILENT, and in the FAVOURABLE direction -- a metric improves, so nobody investigates.
- **Do NOT flag when:** Fine when the language forbids the user from producing the name. Check the PEP rather than assuming a dunder is reserved. Cross-checking against the AST is the general fix and applies to every instance of this shape.
- **Confirmed instances:** CRF-COVPY-0033 -- a user-written __annotate__ has its whole body dropped from the statement count, inflating the file's percentage

#### `commit-side-effect-outside-the-success-guard` — A commit-semantic side effect performed regardless of whether the operation succeeded

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A method performs an operation that can fail or be cancelled and then unconditionally records that it happened -- appending to a recent-items list, bumping a counter, firing a 'saved' event. The sibling method for the inverse operation reaches its equivalent call only after returning early on every failure path, which establishes the project's own standard.
- **Guarded twin (the fix):** The sibling that gets it right -- typically the load half of a save/load pair, which returns False on every error path before recording anything.
- **Sibling hunt:** For every persistent record of 'this succeeded', walk backwards to the operation and check whether every failure and cancellation path returns before reaching it. Cancellation matters as much as failure and is easier to trigger. Check whether any downstream pruning would repair a bad entry -- if the pruning is an existence test and the failed operation created a truncated file, it will not.
- **Expected behaviour:** the record of an operation is written only when the operation actually completed.
- **Surfaces as:** SILENT -- a cancelled save appears in the recent-files list, a zero-byte truncated file becomes the most recent entry, and no pruning removes it.
- **Do NOT flag when:** Recording an ATTEMPT is a legitimate design -- read what the record is used for. If it drives a 'reopen this' menu, it must mean success. Distinct from `flag-not-reset-on-early-exit`: there the early exit skips a reset, here it fails to skip a write.
- **Confirmed instances:** CRF-IDLELIB-0024 -- the recent-files list is updated outside the success guard in two save methods, while the load twin records only after success

#### `per-redraw-binding-never-released` — A binding, callback, or handle created inside a redraw is never released

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A render/redraw/refresh routine creates a per-element registration -- a widget event binding, a signal connection, an observer, a scheduled callback, a native handle -- once per element per pass, and there is no matching release. The routine is called again on every expand, scroll, resize or refresh, so registrations accumulate linearly with redraws rather than with elements. Each one usually captures the element, so the retained set pins application objects too.
- **Guarded twin (the fix):** A sibling view in the same package that binds ONCE at construction, or that explicitly unbinds before rebinding. Frameworks that auto-release on widget destruction (Tk deletes a widget's Tcl commands in `Misc.destroy`) make some instances harmless -- the twin worth citing is one that survives destruction of the individual element but not of the container.
- **Sibling hunt:** Find the redraw entry point and every registration call inside it (`tag_bind`, `bind`, `connect`, `addObserver`, `after`, `register`), then grep the whole class for the matching release (`tag_unbind`, `unbind`, `disconnect`, `after_cancel`). Absence of the release verb anywhere in the file is the signal. MEASURE it: drive N redraws and count registrations (in Tk, `len(widget.tk.call('info','commands'))`), and confirm growth is linear in redraws, not in elements.
- **Expected behaviour:** registrations track live elements, not cumulative redraws.
- **Surfaces as:** SILENT. Nothing raises; the window is simply slower and larger the longer it is open, and the objects it displayed are not collected. Frequently already documented by a stale in-code TODO/XXX that has outlived several maintainers.
- **Do NOT flag when:** Not this shape if the framework releases on element destruction AND elements are destroyed per redraw -- measure before reporting, because that is the common case and it is a non-issue. The real instance is a container that outlives its elements: the container is destroyed rarely (a browser window open for a session) while elements are re-rendered constantly. A long-lived XXX naming the leak is corroboration, not proof; the measurement is the proof.
- **Confirmed instances:** CRF-IDLELIB-0057 -- idlelib tree.py:234 calls canvas.tag_bind twice per node on every redraw, under a comment reading 'XXX This leaks bindings until canvas is deleted' that has been correct since 1999

### Owned by `tech-debt-inventory`

#### `identity-by-id-requires-retention` — `id()` used as an identity key, forcing the object to be retained forever

- **Default severity:** POLICY (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** An `id()` value is used as a dictionary key or set member to identify an object. Because CPython reuses addresses, the object must be kept alive for the key to stay meaningful -- so the code appends every object it sees to a list that is never trimmed. Memory then grows linearly with how many objects the process has ever created, not with how many are live.
- **Guarded twin (the fix):** A sibling implementation of the same job that keys off the object itself, a weak reference, or a per-object attribute, and retains nothing. If two backends do the same work and one retains nothing, that is the argument.
- **Sibling hunt:** Grep for `id(` in a key or membership position, then find the companion retention list -- there is always one, and the tell is that it is appended to unconditionally and cleared by nothing, not even the object's own reset method. MEASURE it: create N objects, record RSS and the retained count, and confirm linearity rather than asserting it. Check whether an existing regression test for a leak in a sibling backend is switched off for this one -- that skip decorator's comment is usually a confession.
- **Expected behaviour:** memory tracks live objects, not cumulative objects; or the retention is documented as a limitation of that backend.
- **Surfaces as:** SILENT until a long-lived process that exec/eval/compiles -- a templating engine, a notebook kernel, an ORM, a plugin loader -- is killed by the OOM killer.
- **Do NOT flag when:** Deliberate and documented retention is POLICY, not a leak -- but 'documented' must mean the user-facing documentation, not a comment inside a skip decorator. A bounded cache is fine. A `WeakValueDictionary` or an attribute on the object itself avoids the shape entirely and is the fix to argue for.
- **Confirmed instances:** CRF-COVPY-0044 -- one backend retains every code object it ever sees, measured dead-linear at ~0.97 KB each; the sibling backends retain zero

#### `measurement-depends-on-mutable-external-state` — An observation re-derived from a mutable external source at the moment it is used

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Code that observes a running program re-reads the artifact from disk (or re-queries an external service) at measurement time rather than capturing it when the program was loaded. Anything that edits the artifact between load and measurement silently invalidates the results, and errors from the re-read are swallowed into an empty result -- often with an in-source admission that this 'might be slightly wrong'.
- **Guarded twin (the fix):** Sibling implementations that take the same information straight from the runtime structures and never touch the external source -- their byte-identical results across the same perturbations are the proof.
- **Sibling hunt:** Find every read of an external artifact that happens during measurement rather than during setup, and check what invalidates it. PERTURB the artifact between load and measurement and diff the output across backends. Treat any in-source admission of imprecision as a pointer, and check whether the real effect is imprecision or total absence -- in the confirmed corpus 'slightly wrong branch coverage' meant the arcs were missing entirely.
- **Expected behaviour:** the observation reflects the artifact as it was when the program was loaded, or the code detects that it has changed.
- **Surfaces as:** SILENT and only on one backend -- a report that is simply wrong, with plausible-looking numbers and no error, for anyone who edits a file while a long-lived process is running.
- **Do NOT flag when:** Re-reading is fine when the artifact is immutable for the process lifetime, or when the code keys the cache on a content hash. The swallowed error is a separate aggravator: even a correct re-read strategy must not turn a tokenize failure into an empty map.
- **Confirmed instances:** CRF-COVPY-0017 -- source re-read and re-tokenized at measurement time; a valid two-line edit after import takes a report from 83% to 50% on one backend only

#### `conflict-resolved-silently-where-siblings-warn` — One configuration conflict resolved without a warning where every sibling conflict warns

- **Default severity:** CONSIDER (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A settings resolver detects incompatible options and picks one. Most conflicts emit a user-visible warning; one branch assigns the winner early -- often before the losing option is even read, making a later `elif` dead -- and logs only at debug level. The user's explicit setting is discarded with no indication.
- **Guarded twin (the fix):** The sibling conflict branches in the same function, which all warn. Their existence establishes the project's own standard, so the argument is about consistency rather than taste.
- **Sibling hunt:** In every settings resolver, list the branches that can override an explicit user choice and check each for a user-visible warning. Ordering matters: a branch that assigns before reading the option it overrides leaves a dead `elif`, which is the mechanical tell. Reproduce each conflict and capture the warning list -- an empty list beside a populated one for the sibling is the finding.
- **Expected behaviour:** any time an explicit setting is overridden, the user is told.
- **Surfaces as:** SILENT -- the program works, using a different backend or mode than the user asked for.
- **Do NOT flag when:** A documented precedence rule reduces this to CONSIDER, not to nothing -- documented precedence still deserves a warning when it discards an explicit choice. A debug-level log does not count as telling the user.
- **Confirmed instances:** CRF-COVPY-0039 -- timid=True silently discards an explicit core setting while every other conflict on the same option warns

### Owned by `test-investigation-agent`

#### `over-broad-test-flag-mutes-instead-of-narrowing` — A test-suite capability flag is broader than the fact it names, so tests silently skip

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A test-suite constant conflates two independent facts -- a language-version fact and a backend fact, or a feature fact and a configuration fact -- and is then used as a skip predicate under a reason naming only one of them. Whole test classes stop running on configurations where the feature works fine, or where it is broken and nothing notices.
- **Guarded twin (the fix):** The legs of the matrix where the flag is True: run the mutation there and it dies, which is what proves the muted leg is untested rather than merely redundant.
- **Sibling hunt:** MUTATION-TEST the flag. Break the feature the flag claims to gate and re-run each configuration: any configuration whose failure count does not move is not testing it. Then check the skip is visible at all -- an addopts without `-rs` hides every skip, so a developer running the suite bare sees green over a totally broken feature. Also check class-level skips: if only one test in the class needs the capability, the other tests are collateral.
- **Expected behaviour:** a skip predicate names exactly the fact that makes the test impossible, the skip is visible in the default test output, and the mutation dies somewhere.
- **Surfaces as:** SILENT -- as a passing suite. This shape hides other bugs rather than causing them, which is why it is worth FIX severity despite living in tests.
- **Do NOT flag when:** A flag that is over-broad but whose extra breadth is never False in practice costs nothing -- check the actual matrix before reporting. CI sweeping every configuration mitigates but does not fix it: the local developer experience is still a silent green.
- **Confirmed instances:** CRF-COVPY-0046 -- dynamic-context detection unguarded on the default 3.14 core; the mutant survives on sysmon; CRF-COVPY-0049 -- CAN_MEASURE_BRANCHES is a pure version predicate used under a 'this core cannot' reason; CRF-COVPY-0050 -- a class-level skip covers three tests where only one needs the capability

#### `assertion-against-a-stub-that-cannot-fail` — A test whose assertion is made against a stub incapable of expressing the failure

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A test achieves full line coverage of a guarded path while asserting against a mock or stub that can never produce the condition the guard exists for. `self.gui = Mock()` then asserting `interaction` was called proves nothing about a `try/except TclError` around it, because a Mock never raises TclError. Likewise a fake widget whose `index()` is frozen to a constant, or a stub returning a value unconditionally where the real object returns a sentinel.
- **Guarded twin (the fix):** The same test with `side_effect` set to the exception, or a real object in place of the stub. A sibling test in the same file usually already does one or the other.
- **Sibling hunt:** MUTATION-TEST the guarded line: break it and run the suite. A surviving mutant is proof, not a guess. Then look for the stub in the fixture -- `Mock()` with no `side_effect`, a lambda assigned over a method (`cls.text.index = lambda i: '4.0'`), or a fake returning a value unconditionally where the real API can fail. Compare against the real object's contract: which states can it reach that the stub cannot?
- **Expected behaviour:** a test covering a guard can distinguish the guarded code from the unguarded code.
- **Surfaces as:** NEVER. The test passes, the line is covered, and no coverage tool reports anything. The defect it was meant to catch ships.
- **Do NOT flag when:** A stub is correct when the test's subject is the CALL, not the guard -- verifying an argument was forwarded needs no ability to raise. The shape requires a guard, branch or sentinel handler whose condition the stub cannot produce. Distinct from `test-cannot-fail`, where the assertion is tautological or absent; here the assertion is real and the FIXTURE is what cannot fail.
- **Confirmed instances:** CPython Lib/idlelib/idle_test/test_debugger.py:53,59 -- both user_line (guarded) and user_exception (unguarded) tested with `self.gui = Mock()`; a Mock never raises TclError, so both pass identically. This is what hid CRF-IDLELIB-0025; CPython Lib/idlelib/idle_test/test_searchengine.py:279 -- `cls.text.index = lambda index: '4.0'` freezes every index expression; two mutations of search_backward's wrap survive the full 623-test suite while the mirrored search_forward mutation kills five tests

### Owned by `type-design-analyzer`

#### `identity-key-from-a-non-artifact-proxy` — An identity key derived from a proxy that is not a function of the artifact it identifies

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** Something is identified by a value that correlates with it but is not determined by it -- a content hash accumulated from the subset of writes that happened to go through one accumulator, a path canonicalized against the current working directory, a name computed before the last mutation. Two distinct artifacts collide, or one artifact yields two keys, depending on timing or environment.
- **Guarded twin (the fix):** The implementation that hashed or resolved the real thing -- often the code that was replaced by the proxy for performance, still visible in the `else` branch or in git history. Where the key is a path, a sibling that resolves against a stable base rather than the ambient cwd.
- **Sibling hunt:** For every identity key, ask what inputs determine it and enumerate what can change WITHOUT changing them. Then look for the deduplication or collision handling that consumes the key -- if collisions cause a silent discard, the severity is data loss rather than confusion. Check post-write mutations specifically: a hash written once at first save misses everything after it.
- **Expected behaviour:** the key is a pure function of the artifact, so equal keys mean equal artifacts and vice versa.
- **Surfaces as:** SILENT, and often NON-DETERMINISTIC -- in the confirmed corpus which of two colliding files survived was decided by sorting over names containing a random token, so the same suite reported different totals run to run.
- **Do NOT flag when:** A cheap proxy is fine when a collision is merely a cache miss. It is a bug when the consumer treats equal keys as proof of equal content -- especially when it then DISCARDS one side. Distinguish from `identity-key-reallocated-under-a-cached-index`, where the key is correct but the mapping to it goes stale.
- **Confirmed instances:** CRF-COVPY-0036 -- the data-file hash short-circuits to a filename suffix written once, missing later writes and touched files entirely; colliding files are deleted; CRF-IDLELIB-0016 -- a swallowed getcwd() failure leaves a relative path as the identity key for an open editor window, so one file gets two windows that overwrite each other

#### `identity-key-reallocated-under-a-cached-index` — A cached name-to-id map outlives a write path that mints new ids

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** agent-only — no scanner will ever hand you this — the sibling hunt below IS the method
- **Pattern:** A mapping from a natural key to a surrogate id is populated once and only ever appended to, while some write path can DELETE and re-create the row -- `INSERT OR REPLACE`, a delete-then-insert, a reconnect that re-runs schema creation. The cache then hands out an id that no longer refers to the same row, orphaning every child record that pointed at it.
- **Guarded twin (the fix):** A sibling write path in the same class that does it correctly -- `INSERT OR IGNORE` followed by a re-read of the id, rather than trusting `lastrowid`. Where a reconnect can re-create the schema, the twin is whatever else the reconnect path resets.
- **Sibling hunt:** For every cached surrogate-id map, enumerate every statement that can remove or replace the underlying row, including reconnect and schema-init paths. Check whether declared foreign keys are actually ENFORCED -- if the pragma is never issued they are inert documentation and will not catch the orphaning. Reproduce with two writers appending to one store, which is the ordinary 'forgot parallel mode' shape.
- **Expected behaviour:** a cached id refers to the same row for as long as the cache lives, or the cache is invalidated when it cannot.
- **Surfaces as:** SILENT -- as coverage, records, or rows attributed to the wrong parent, or vanishing. No error, and the totals still look plausible.
- **Do NOT flag when:** Not a defect if the id is never cached across the operation that can replace it, or if the store enforces the foreign keys and fails loudly. Confirm the pragma or constraint is actually active rather than merely declared.
- **Confirmed instances:** CRF-COVPY-0011 -- a stale file map plus INSERT OR REPLACE orphans every child row; declared foreign keys are inert because the pragma is never issued

#### `type-checking-import-of-a-nonexistent-module` — A TYPE_CHECKING import of a module that does not exist, silently degrading annotations to Any

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** `from package.modul import Thing` under `if TYPE_CHECKING:` where the module name is misspelled -- `plugins` for `plugin`, `util` for `utils`. There is no runtime error because the import never executes, and if the project sets `ignore_missing_imports = true` the type checker reports nothing either. Every annotation using the name silently becomes `Any`, so those signatures stop checking anything.
- **Guarded twin (the fix):** Every other module in the same package, which spells the import correctly. The correct spelling being one character away in the same tree is what makes this both easy to introduce and easy to confirm.
- **Sibling hunt:** Resolve every TYPE_CHECKING import against the actual package tree. Then run the type checker with unfollowed-import reporting enabled (`mypy --disallow-any-unimported`): each 'becomes Any due to an unfollowed import' names an annotation that has stopped working. Do the same for `if False:` and string-annotation-only imports.
- **Expected behaviour:** every name imported for typing resolves, and no annotation silently degrades to Any.
- **Surfaces as:** NEVER. Both the runtime and the type checker are quiet; the only symptom is that type errors in those signatures are never reported.
- **Do NOT flag when:** An import of a genuinely optional third-party module under TYPE_CHECKING is legitimate and is exactly what `ignore_missing_imports` is for -- resolve against the project's OWN package first and report only those. This is the cheapest true positive in the typing family and worth running on every project.
- **Confirmed instances:** CRF-COVPY-0018 -- a one-character module name error disabled three annotations, proven with --disallow-any-unimported

#### `hand-mirrored-wrapper-drifts-from-its-interface` — A wrapper that subclasses its interface and hand-mirrors a subset of it

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** A debugging, logging, or instrumentation wrapper INHERITS from the interface it wraps and explicitly delegates only some methods. The unmirrored methods do not fall through to the wrapped object -- they hit the base-class defaults, which return empty lists and generic text. Turning the wrapper on therefore changes program OUTPUT, not just its logging.
- **Guarded twin (the fix):** Sibling wrapper classes in the same module that mirror their interfaces completely -- a count like 6/6 and 4/4 beside this one's 10/14 is the argument, and it also shows the project knows the correct standard.
- **Sibling hunt:** For every wrapper that subclasses what it wraps, diff its method set against the base's public method set. Then check what the missing ones return by default: inheriting a benign default is what makes this silent rather than an AttributeError. Prefer `__getattr__` passthrough or composition in the fix, because a mirrored list rots again the moment the interface grows.
- **Expected behaviour:** enabling a debug wrapper changes what is logged and nothing else.
- **Surfaces as:** SILENT, and only when a plugin or subclass implements the methods the wrapper forgot -- so the project's own tests, which use minimal implementations, cannot see it.
- **Do NOT flag when:** A wrapper that does NOT inherit gets an AttributeError instead, which is loud and much less serious. A deliberately partial wrapper is fine if the base raises NotImplementedError for the rest. The severity comes from benign inherited defaults.
- **Confirmed instances:** CRF-COVPY-0019 -- a debug wrapper mirrors 10 of 14 methods; enabling it deletes an entire key from the JSON report

#### `subclass-only-method-called-through-the-base` — A method defined only on one subclass, called on a base-typed value

- **Default severity:** FIX (before triage) · **grounding:** confirmed
- **How you find it:** implementable — AST-decidable but NOT yet implemented — hunt it by hand this run
- **Pattern:** Code calls a method that exists on the project's own implementation of an interface but not on the base class that third-party implementations subclass. It is usually reached only on an error path, and it usually carries a `# type: ignore[attr-defined]` and an adjacent comment asserting the premise that makes it safe -- a premise that is false because the triggering exception is part of the public API.
- **Guarded twin (the fix):** The comment itself. It states the assumption ('only ever raised by our own reporter'), which makes the finding a matter of checking that claim rather than arguing about design.
- **Sibling hunt:** Grep for `type: ignore[attr-defined]` and treat each one as a candidate -- it is a machine-checkable marker that the author knew the call was not type-safe. For each, ask whether a third-party implementation can reach the call site. Check the ORDER of the failing call against nearby error handling: if the AttributeError precedes the `ignore_errors` test, both intended branches become unreachable and a documented warning can never fire.
- **Expected behaviour:** any implementation of the published interface can flow through the code path without an AttributeError.
- **Surfaces as:** As an AttributeError on an error path, which replaces a designed diagnostic with an internal crash -- so users see the wrong problem.
- **Do NOT flag when:** Fine if the value is provably always the concrete subclass -- an isinstance check makes it provable and is the fix. A `type: ignore` on a call that only the project's own code can reach is acceptable; the shape requires an externally-implementable interface.
- **Confirmed instances:** CRF-COVPY-0020 -- should_be_python() called on plugin file reporters that do not have it, making both branches of the intended error handling unreachable

## Already recorded for THIS project in the findings catalog (60)

These are settled. Verify each still exists, then move on — do not re-derive them, and do not report them as new.

- **CRF-COVPY-0001** [FIX] _reap_dead_thread_dbs destroys the in-memory database and mis-attributes coverage — `sqldata.py:390` · shape `fix-not-propagated-to-sibling-path`
- **CRF-COVPY-0002** [FIX] patch = fork makes coverage worse than not patching at all — `control.py:1499-1503` · shape `unchecked-no-op-sentinel`
- **CRF-COVPY-0003** [FIX] CTracer never calls its warn member, so a settrace hijack silently truncates data — `ctracer/tracer.c:1055` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0004** [FIX] SyntaxError from a bad coding cookie escapes compute_multiline_map — `sysmon.py:489-495` · shape `guard-catches-wrong-exception-set`
- **CRF-COVPY-0005** [FIX] Nested Coverage permanently stops measurement on the default 3.14 core — `sysmon.py:335, 374-387` · shape `external-registration-not-reestablished`
- **CRF-COVPY-0006** [FIX] CoverageData.update() never DETACHes, so a second in-memory combine destroys the first data file — `sqldata.py:744-884` · shape `cleanup-only-on-success-path`
- **CRF-COVPY-0007** [FIX] --fail-under rounds toward 100 while the printed total rounds away from it — `results.py:502` · shape `asymmetric-rounding-between-display-and-gate`
- **CRF-COVPY-0008** [FIX] XML line-rate publishes 99.997% as exactly 1 — `xmlreport.py:33-38` · shape `asymmetric-rounding-between-display-and-gate`
- **CRF-COVPY-0009** [FIX] Tracer backends disagree about which threads are measured — `collector.py:334, core.py:120` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0010** [FIX] [report] contexts is silently ignored by xml, lcov and annotate, and leaks across reports — `xmlreport.py, lcovreport.py, annotate.py` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0011** [FIX] Stale _file_map plus INSERT OR REPLACE orphans every child row — `sqldata.py:468-475` · shape `identity-key-reallocated-under-a-cached-index`
- **CRF-COVPY-0012** [FIX] file_tracers is iterated unguarded in flush_data while the C writer holds the lock — `collector.py:495` · shape `fix-not-propagated-to-sibling-path`
- **CRF-COVPY-0013** [FIX] Collector.resume() installs other threads' tracers onto the calling thread — `collector.py:369-370` · shape `fix-reverted-and-never-relanded`
- **CRF-COVPY-0014** [FIX] relative_files = True reports 0% for any file reached through a symlink — `python.py:155-161 vs inorout.py:401` · shape `two-sides-of-a-comparison-normalized-differently`
- **CRF-COVPY-0015** [FIX] omit/include patterns starting with * are not symlink-resolved — `files.py:211-215` · shape `two-sides-of-a-comparison-normalized-differently`
- **CRF-COVPY-0016** [FIX] An unreadable config file reads as no config at all — `config.py:55-59, :319` · shape `empty-result-conflated-with-absent`
- **CRF-COVPY-0017** [FIX] sysmon re-reads source from disk at measurement time and swallows tokenize errors — `sysmon.py:489-503` · shape `measurement-depends-on-mutable-external-state`
- **CRF-COVPY-0018** [FIX] html.py imports coverage.plugins, a module that does not exist — `html.py:42` · shape `type-checking-import-of-a-nonexistent-module`
- **CRF-COVPY-0019** [FIX] DebugFileReporterWrapper mirrors 10 of 14 methods, so debug=plugin changes report content — `plugin_support.py:243-290` · shape `hand-mirrored-wrapper-drifts-from-its-interface`
- **CRF-COVPY-0020** [FIX] should_be_python() is called on plugin FileReporters that do not have it — `report_core.py:110` · shape `subclass-only-method-called-through-the-base`
- **CRF-COVPY-0021** [FIX] An unparseable non-.py file leaves both numerator and denominator, inflating TOTAL — `report_core.py:105-115` · shape `cleanup-only-on-success-path`
- **CRF-COVPY-0022** [CONSIDER] Three sysmon callbacks index code_infos unguarded where their sibling checks — `sysmon.py:410, :436, :451` · shape `guarded-twin-with-false-reasoning`
- **CRF-COVPY-0023** [CONSIDER] A transient listdir failure is cached for the process lifetime — `files.py:133-139` · shape `failure-result-cached-as-if-successful`
- **CRF-COVPY-0024** [FIX] patch = _exit / execv discard the whole process's data with zero trace — `patch.py:56-57, :74-75` · shape `cleanup-only-on-success-path`
- **CRF-COVPY-0025** [FIX] SqliteDb.__exit__ skips close() on a commit failure and then reuses the stale connection — `sqlitedb.py:102-112` · shape `cleanup-only-on-success-path`
- **CRF-COVPY-0026** [FIX] The .pth bare except hides a broken install, so every subprocess contributes nothing — `pth_file.py:11-16` · shape `bare-except-swallows-control-flow`
- **CRF-COVPY-0027** [FIX] set_option() bypasses post_process(), silently no-opping several settings — `config.py:494-529` · shape `public-setter-skips-the-validation-the-loader-runs`
- **CRF-COVPY-0028** [FIX] A plugin whose name contains a dot cannot be configured from TOML — `tomlconfig.py:91` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0029** [FIX] $VAR substitution applies to plugin options in INI but not TOML — `tomlconfig.py:146-148` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0030** [FIX] update() derives lines-vs-arcs from table contents while the guard uses the meta key — `sqldata.py:804-809 vs :725-732` · shape `same-fact-derived-from-two-sources`
- **CRF-COVPY-0031** [FIX] no_branch pragma desynchronizes the branch counters from the arc lists — `results.py:131-140 vs :146-148, :183-197` · shape `same-fact-derived-from-two-sources`
- **CRF-COVPY-0032** [FIX] Zero statements: two backends claim 100% and --fail-under splits — `results.py:336-340` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0033** [FIX] A user-written __annotate__ has its whole body dropped from statements — `bytecode.py:41` · shape `name-based-filter-cannot-distinguish-generated-from-authored`
- **CRF-COVPY-0034** [FIX] Region analysis never walks orelse, handlers or finalbody — `regions.py:53-55` · shape `partial-traversal-of-a-node-family`
- **CRF-COVPY-0035** [FIX] PathAliases rewrites a path prefix with str.replace and a greedy regex — `files.py:508-509, :352, :354, :539` · shape `prefix-rewrite-done-as-a-content-search`
- **CRF-COVPY-0036** [FIX] The data-file hash is derived from a proxy that is not a function of the artifact — `data.py:99-129, sqldata.py:912-929` · shape `identity-key-from-a-non-artifact-proxy`
- **CRF-COVPY-0037** [FIX] The should-trace gate knows eight rules; the unexecuted-file enumerator knows one — `inorout.py:445-507 vs :599-621` · shape `one-predicate-two-implementations`
- **CRF-COVPY-0038** [FIX] PyTracer reads an emptied set as an untraced file and disables line events for the frame — `pytracer.py:241-242` · shape `empty-container-read-as-absent`
- **CRF-COVPY-0039** [CONSIDER] timid = True silently discards an explicit core = setting — `core.py:83-89` · shape `conflict-resolved-silently-where-siblings-warn`
- **CRF-COVPY-0040** [CONSIDER] Six warnings carry no slug, so disable_warnings cannot reach them — `control.py:474-499` · shape `suppression-keyed-on-an-optional-identifier`
- **CRF-COVPY-0041** [CONSIDER] CLI error and status messages are split across stdout and stderr — `cmdline.py:953, :1188, :780` · shape `fix-not-propagated-to-sibling-path`
- **CRF-COVPY-0042** [CONSIDER] sysmon raises a bare RuntimeError on tool-id exhaustion with no fallback — `sysmon.py:253` · shape `error-escapes-the-project-exception-hierarchy`
- **CRF-COVPY-0043** [CONSIDER] GetConsoleMode-style: skip-flag and region support differ across the six report backends — `report.py, html.py, xmlreport.py, lcovreport.py, jsonreport.py, annotate.py` · shape `one-concern-implemented-per-backend`
- **CRF-COVPY-0044** [POLICY] sysmon retains every code object for the process lifetime — `sysmon.py:213-215, :372` · shape `identity-by-id-requires-retention`
- **CRF-COVPY-0045** [FIX] test_thread_safe_save_data has zero assertions and passes with its fix reverted — `tests/test_concurrency.py:635` · shape `test-cannot-fail`
- **CRF-COVPY-0046** [FIX] Dynamic-context detection is unguarded on the default 3.14 core — `context.py:49, tests/testenv.py, pyproject.toml:121` · shape `over-broad-test-flag-mutes-instead-of-narrowing`
- **CRF-COVPY-0047** [CONSIDER] env.py and igor.py disagree on what METACOV means — `env.py:124 vs igor.py:247` · shape `same-fact-derived-from-two-sources`
- **CRF-COVPY-0048** [CONSIDER] Two regression tests are switched off for every configuration — `tests/test_oddball.py:256-259, tests/test_concurrency.py:290` · shape `test-cannot-fail`
- **CRF-COVPY-0049** [CONSIDER] CAN_MEASURE_BRANCHES is a version fact applied as a core fact — `tests/testenv.py:43` · shape `over-broad-test-flag-mutes-instead-of-narrowing`
- **CRF-COVPY-0050** [CONSIDER] SwitchContextTest is skipped wholesale on sysmon though two thirds of it is core-independent — `tests/test_api.py:739` · shape `over-broad-test-flag-mutes-instead-of-narrowing`
- **CRF-COVPY-0051** [CONSIDER] Collector's class docstring is false for the default core on Python 3.14+ — `collector.py:44-53` · shape `doc-describes-a-superseded-model`
- **CRF-COVPY-0052** [CONSIDER] Two GIL justifications in a project shipping free-threaded wheels — `collector.py:453-459, :420-423` · shape `doc-describes-a-superseded-model`
- **CRF-COVPY-0053** [CONSIDER] Eight docstrings cross-reference functions that were renamed or deleted — `control.py:448, parser.py:1039, regions.py:84, data.py:144/152/155, types.py:41, execfile.py:289, annotate.py:57, sqldata.py:39` · shape `dead-cross-reference-in-a-docstring`
- **CRF-COVPY-0054** [CONSIDER] Four docstrings contradict what the function does, provable by calling it — `misc.py:364, files.py:204-205, files.py:498-500, patch.py:115` · shape `refactor-changed-behaviour-doc-did-not`
- **CRF-COVPY-0055** [CONSIDER] Public API docstrings that ship to users via Sphinx are wrong — `control.py:197-199, control.py:1149-1150, plugin.py:537-539, lcovreport.py:202-203` · shape `refactor-changed-behaviour-doc-did-not`
- **CRF-COVPY-0056** [CONSIDER] The --rcfile help text omits .coveragerc.toml, and cog has baked it into ten doc files — `cmdline.py:299-303` · shape `generated-doc-propagates-a-source-error`
- **CRF-COVPY-0057** [CONSIDER] Two config options are implemented and tested but documented nowhere — `config.py:437, :441` · shape `implemented-but-undocumented-option`
- **CRF-COVPY-0058** [CONSIDER] The release checklist greps for PYVERSIONS but two live markers are spelled PYVERSION — `execfile.py:95, phystokens.py:98` · shape `process-marker-invisible-to-its-own-checklist`
- **CRF-COVPY-0059** [CONSIDER] write() lacks the no_disk guard its four siblings have — `sqldata.py:912-927` · shape `fix-not-propagated-to-sibling-path`
- **CRF-COVPY-0060** [CONSIDER] find_spec failure is indistinguishable from module-not-found, and the caller's guard is dead code — `inorout.py:115-118` · shape `empty-result-conflated-with-absent`

## Confirmed in OTHER projects (98) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [cpython-idlelib] **CRF-IDLELIB-0001** [FIX] A failed config save deletes the user's config file — `config.py:136-140` · shape `except-exception-too-broad`
- [cpython-idlelib] **CRF-IDLELIB-0002** [FIX] One subprocess-accept timeout wedges IDLE permanently — `pyshell.py:499-540` · shape `flag-not-reset-on-early-exit`
- [cpython-idlelib] **CRF-IDLELIB-0003** [FIX] Replace's NULL-guard tests the call receiver instead of the match — `replace.py:226-229` · shape `guard-rechecks-call-receiver`
- [cpython-idlelib] **CRF-IDLELIB-0004** [FIX] Autocomplete's mode filter never applies to ATTRS because ATTRS == 0 — `autocomplete.py:117,134` · shape `falsy-test-on-a-zero-valued-enum-member`
- [cpython-idlelib] **CRF-IDLELIB-0005** [FIX] Forward search abandons the rest of a line after a zero-width match — `searchengine.py:146-151` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0006** [FIX] get_argspec guards two of its three touches of a user object — `calltip.py:189` · shape `except-exception-too-broad`
- [cpython-idlelib] **CRF-IDLELIB-0007** [FIX] Custom run arguments are corrupted by a Tcl list round-trip — `query.py:352,368-376` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0008** [FIX] Stack Viewer reads an attribute only runcode() ever creates — `run.py:635-639,695` · shape `attribute-created-outside-init`
- [cpython-idlelib] **CRF-IDLELIB-0009** [FIX] A failed window probe leaves the user's window stuck maximized — `zoomheight.py:66-105` · shape `cleanup-only-on-success-path`
- [cpython-idlelib] **CRF-IDLELIB-0010** [FIX] A failed is_active check permanently disables the completion window's Configure handler — `autocomplete_w.py:238` · shape `flag-not-reset-on-early-exit`
- [cpython-idlelib] **CRF-IDLELIB-0011** [CONSIDER] A bad print command orphans the user's unsaved source in /tmp — `iomenu.py:360-375` · shape `cleanup-only-on-success-path`
- [cpython-idlelib] **CRF-IDLELIB-0012** [CONSIDER] The subprocess's last-resort handler can itself raise NameError — `run.py:190-197` · shape `handler-reads-a-name-the-try-may-not-have-bound`
- [cpython-idlelib] **CRF-IDLELIB-0013** [CONSIDER] Every OSError on recv becomes 'the peer hung up' — `rpc.py:358-361` · shape `raise-without-from-in-except`
- [cpython-idlelib] **CRF-IDLELIB-0014** [CONSIDER] endexecuting() is skipped if showtraceback() fails — `pyshell.py:804-821` · shape `cleanup-only-on-success-path`
- [cpython-idlelib] **CRF-IDLELIB-0015** [CONSIDER] Remote internal errors are reported only at a permanently-disabled debug level — `rpc.py:258-260` · shape `error-reported-below-warning`
- [cpython-idlelib] **CRF-IDLELIB-0016** [CONSIDER] A failed getcwd() silently yields a relative path used as a window identity key — `filelist.py:105-108` · shape `identity-key-from-a-non-artifact-proxy`
- [cpython-idlelib] **CRF-IDLELIB-0017** [CONSIDER] A comment with no space after # is invisible to HyperParser — `pyparse.py:44-48` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0018** [CONSIDER] Reconnect resets some per-connection state but not the packet read buffer — `rpc.py:130-141` · shape `reinitializer-resets-a-subset-of-its-state`
- [cpython-idlelib] **CRF-IDLELIB-0019** [CONSIDER] Replace All's final selection uses the pre-replacement span — `replace.py:172-188` · shape `index-computed-before-a-mutation-used-after-it`
- [cpython-idlelib] **CRF-IDLELIB-0020** [CONSIDER] getprog catches only re.PatternError, so OverflowError escapes to every caller — `searchengine.py:85-89` · shape `except-exception-too-broad`
- [cpython-idlelib] **CRF-IDLELIB-0021** [CONSIDER] terminate_subprocess catches every OSError though its comment names one — `pyshell.py:564-574` · shape `except-exception-too-broad`
- [cpython-idlelib] **CRF-IDLELIB-0022** [CONSIDER] Debugger.close swallows every failure of quit() — `debugger.py:159-162` · shape `except-exception-too-broad`
- [cpython-idlelib] **CRF-IDLELIB-0023** [CONSIDER] A bare except guards a four-link attribute chain — `autocomplete.py:173-175` · shape `bare-except-swallows-control-flow`
- [cpython-idlelib] **CRF-IDLELIB-0024** [CONSIDER] Recent-files list is updated outside the success guard — `iomenu.py:253,261` · shape `commit-side-effect-outside-the-success-guard`
- [cpython-idlelib] **CRF-IDLELIB-0025** [CONSIDER] Idb.user_exception calls into the GUI unguarded where its twin is guarded — `debugger.py:55-56` · shape `fix-not-propagated-to-sibling-path`
- [cpython-idlelib] **CRF-IDLELIB-0026** [CONSIDER] Five tests in the suite cannot fail — `idle_test/test_autocomplete.py:241` · shape `test-cannot-fail`
- [cpython-idlelib] **CRF-IDLELIB-0027** [FIX] Copy-with-prompts drops the last line whenever the selection ends at column 10, 20, 100... — `pyshell.py:1034` · shape `structured-index-tested-by-string-suffix`
- [cpython-idlelib] **CRF-IDLELIB-0028** [FIX] get_prompt_text zips a computed line range against actual lines — `pyshell.py:1016` · shape `zip-truncates-on-length-mismatch`
- [cpython-idlelib] **CRF-IDLELIB-0029** [FIX] `and` binds tighter than `or`, so the modifier guard covers one completion mode of two — `autocomplete_w.py:363-368` · shape `guard-conjoined-with-a-preference-flag`
- [cpython-idlelib] **CRF-IDLELIB-0030** [FIX] HyperParser's string-prefix scanner never learned `f` or `t` — `hyperparser.py:298` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0031** [CONSIDER] Five independent hand-written recognizers for Python syntax with no shared source of truth — `hyperparser.py:298` · shape `one-predicate-two-implementations`
- [cpython-idlelib] **CRF-IDLELIB-0032** [FIX] The `-n` execution backend is missing five cross-cutting protections the RPC backend has — `pyshell.py:792-803` · shape `one-concern-implemented-per-backend`
- [cpython-idlelib] **CRF-IDLELIB-0033** [FIX] Under `idle -n`, __file__ is silently IDLE's own path instead of the script's — `pyshell.py:680` · shape `one-concern-implemented-per-backend`
- [cpython-idlelib] **CRF-IDLELIB-0034** [FIX] WidgetRedirector swallows every TclError, so text.index() can never raise on any IDLE widget — `redirector.py:116` · shape `empty-result-conflated-with-absent`
- [cpython-idlelib] **CRF-IDLELIB-0035** [FIX] Format Paragraph silently deletes characters from every non-comment line of a selection — `format.py:59` · shape `per-line-property-derived-from-the-aggregate`
- [cpython-idlelib] **CRF-IDLELIB-0036** [FIX] A literal % in any setting strips every open window's keybindings and leaves them off — `config.py:48` · shape `cleanup-only-on-success-path`
- [cpython-idlelib] **CRF-IDLELIB-0037** [FIX] The documented sys.argv[0] contract for `idle -r` is wrong, and `idle -h` contradicts it correctly — `Doc/library/idle.rst:731-732` · shape `same-fact-derived-from-two-sources`
- [cpython-idlelib] **CRF-IDLELIB-0038** [FIX] The network diagnostic in the docs names a port IDLE has never listened on — `Doc/library/idle.rst:752` · shape `documented-recipe-not-wired-up`
- [cpython-idlelib] **CRF-IDLELIB-0039** [CONSIDER] The in-app help is generated correctly, so every documentation error is faithfully shipped — `help.py:251` · shape `generated-doc-propagates-a-source-error`
- [cpython-idlelib] **CRF-IDLELIB-0040** [CONSIDER] Documentation still names UI that was renamed or split two releases ago — `Doc/library/idle.rst` · shape `refactor-changed-behaviour-doc-did-not`
- [cpython-idlelib] **CRF-IDLELIB-0041** [CONSIDER] Four config options are fully supported and completely invisible, and one has no consumer — `config-main.def:48` · shape `implemented-but-undocumented-option`
- [cpython-idlelib] **CRF-IDLELIB-0042** [FIX] <<python-context-help>> is offered in Settings, bound by nothing, and has never had a handler — `config.py:651` · shape `unreachable-name-in-a-closed-vocabulary`
- [cpython-idlelib] **CRF-IDLELIB-0043** [FIX] Three keysyms shipped in every keyset cannot be spelled by the key-configuration dialog — `config_key.py:15` · shape `unreachable-name-in-a-closed-vocabulary`
- [cpython-idlelib] **CRF-IDLELIB-0044** [CONSIDER] Three virtual events are declared but unreachable, one of them from a live menu — `mainmenu.py:80` · shape `unreachable-name-in-a-closed-vocabulary`
- [cpython-idlelib] **CRF-IDLELIB-0045** [FIX] undo_block_start/stop is unpaired on the exception path in four places — `replace.py:161` · shape `cleanup-only-on-success-path`
- [cpython-idlelib] **CRF-IDLELIB-0046** [CONSIDER] undo_block_stop does not guard the sentinel its own twin guards — `undo.py:104` · shape `unguarded-inverse-of-guarded-operation`
- [cpython-idlelib] **CRF-IDLELIB-0047** [FIX] codecontext's BLOCKOPENERS lacks match/case, so those blocks never appear in Code Context — `codecontext.py:22` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0048** [FIX] An invalid value in the DEFAULT config is swallowed where the user-config clause warns — `config.py:244` · shape `conflict-resolved-silently-where-siblings-warn`
- [cpython-idlelib] **CRF-IDLELIB-0049** [FIX] The keybinding collision test compares whole lists, so a partial overlap is undetected and silent — `config.py:605` · shape `conflict-resolved-silently-where-siblings-warn`
- [cpython-idlelib] **CRF-IDLELIB-0050** [CONSIDER] The whole IDLE profile location is a function of the launch directory when HOME is unusable — `config.py:199` · shape `identity-key-from-a-non-artifact-proxy`
- [cpython-idlelib] **CRF-IDLELIB-0051** [FIX] restore_file_breaks appends without clearing, so Save As carries the old file's breakpoints over — `pyshell.py:268` · shape `reinitializer-resets-a-subset-of-its-state`
- [cpython-idlelib] **CRF-IDLELIB-0052** [FIX] Breakpoints are keyed by the raw filename while windows are keyed by the normalized one — `pyshell.py:244` · shape `two-sides-of-a-comparison-normalized-differently`
- [cpython-idlelib] **CRF-IDLELIB-0053** [FIX] breakpoints.lst uses `=` as its delimiter, which is legal in a path — `pyshell.py:259` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0054** [FIX] After a Name Conflict the displaced window is marked None instead of re-pointed, so the NEXT collision is silent — `filelist.py:90` · shape `unchecked-no-op-sentinel`
- [cpython-idlelib] **CRF-IDLELIB-0055** [FIX] DictProxy.__getitem__ returns a repr, and only one of its two consumers strips the extra quotes — `debugger_r.py:271` · shape `fix-not-propagated-to-sibling-path`
- [cpython-idlelib] **CRF-IDLELIB-0056** [CONSIDER] Four id()-keyed debugger tables are never cleared, so memory grows with every debugger stop — `debugger_r.py:35` · shape `identity-by-id-requires-retention`
- [cpython-idlelib] **CRF-IDLELIB-0057** [CONSIDER] Tree redraw re-binds every node's canvas item and never deletes the bindings — `tree.py:234` · shape `per-redraw-binding-never-released`
- [cpython-idlelib] **CRF-IDLELIB-0058** [CONSIDER] _synchre matches `def` but cannot match `async def`, making indent analysis quadratic in async modules — `pyparse.py:21` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0059** [FIX] _study1 has no f-string state, so a PEP 701 multi-line f-string is read as three statements — `pyparse.py:245` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0060** [FIX] Saving a file whose coding cookie cannot encode its text writes a BOM and keeps the cookie — `iomenu.py:324-326` · shape `asymmetric-encode-decode-pair`
- [cpython-idlelib] **CRF-IDLELIB-0061** [FIX] Help sources are numbered on write and sorted as strings on read, so entry 10 sorts before entry 2 — `config.py:756` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0062** [FIX] An advanced key binding stored as a Tk event sequence is read back as a whitespace-separated list — `config_key.py:227` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0063** [FIX] Bracket matching checks the bracket type on the backward scan only — `hyperparser.py:137-140` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0064** [CONSIDER] Untabify rewrites the whole line where its tabify mirror rewrites only the indent — `format.py:340` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0065** [CONSIDER] DeleteCommand.undo reinserts text without tags where the Insert mirror round-trips them — `undo.py:294` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0066** [FIX] Configure IDLE -> Keys raises KeyError for any third-party extension that ships disabled — `config.py (GetExtensionKeys — rewritten)` · shape `fix-not-propagated-to-sibling-path`
- [cpython-idlelib] **CRF-IDLELIB-0067** [FIX] Run Module ignores the return of io.save(), so a failed save runs the old code from disk — `runscript.py:189` · shape `unchecked-no-op-sentinel`
- [cpython-idlelib] **CRF-IDLELIB-0068** [FIX] The completion popup teardown is unguarded where the calltip's identical teardown guards every step — `autocomplete_w.py:454-491` · shape `fix-not-propagated-to-sibling-path`
- [cpython-idlelib] **CRF-IDLELIB-0069** [CONSIDER] Two extensions' in-code fallback defaults disagree with the values actually shipped — `parenmatch.py:53` · shape `same-fact-derived-from-two-sources`
- [cpython-idlelib] **CRF-IDLELIB-0070** [CONSIDER] Stack Viewer module globals pin every frame of the last exception for the process lifetime — `stackviewer.py:12` · shape `fix-not-propagated-to-sibling-path`
- [cpython-idlelib] **CRF-IDLELIB-0071** [CONSIDER] The shared test stubs cannot express the conditions the guards under test exist for — `idle_test/mock_idle.py:48` · shape `assertion-against-a-stub-that-cannot-fail`
- [cpython-idlelib] **CRF-IDLELIB-0072** [CONSIDER] A test class freezes text.index to a constant, leaving seven mutations of live code undetected — `idle_test/test_searchengine.py:279` · shape `assertion-against-a-stub-that-cannot-fail`
- [cpython-idlelib] **CRF-IDLELIB-0073** [CONSIDER] Four test files exit 0 even when their tests fail — `idle_test/test_undo.py` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0001** [FIX] Unix and Windows event queues disagree on the empty-data sentinel — `unix_console.py:335,780` · shape `divergent-sentinel-across-parallel-modules`
- [cpython-pyrepl] **CRF-PYREPL-0002** [FIX] Control-character guard compares against a category the API never returns — `input.py:94` · shape `api-value-domain-mismatch`
- [cpython-pyrepl] **CRF-PYREPL-0003** [FIX] Terminfo lookup lowercases the first byte, degrading every uppercase-initial TERM — `terminfo.py:140` · shape `case-normalization-on-a-literal-key`
- [cpython-pyrepl] **CRF-PYREPL-0004** [FIX] tparm's %{n}%+ branch indexes 1-based into a 0-based tuple — `terminfo.py:479-481` · shape `off-by-one-against-a-correct-sibling`
- [cpython-pyrepl] **CRF-PYREPL-0005** [FIX] isinstance tests the command spec tuple instead of the command object — `reader.py:675` · shape `isinstance-on-container-not-element`
- [cpython-pyrepl] **CRF-PYREPL-0006** [FIX] History pop is unconditional where the append it undoes is guarded — `simple_interact.py:124` · shape `unguarded-inverse-of-guarded-operation`
- [cpython-pyrepl] **CRF-PYREPL-0007** [FIX] One undecodable byte wedges the event queue permanently — `base_eventqueue.py:104` · shape `decode-error-treated-as-incomplete`
- [cpython-pyrepl] **CRF-PYREPL-0008** [FIX] A terminfo bounds check copied without updating its operand — `terminfo.py:401` · shape `duplicated-guard-wrong-operand`
- [cpython-pyrepl] **CRF-PYREPL-0009** [FIX] Terminfo header counts unpacked signed with only upper-bound checks — `terminfo.py:373` · shape `signed-length-from-untrusted-header`
- [cpython-pyrepl] **CRF-PYREPL-0010** [FIX] A coverage-increasing commit replaced three assertions with a loop over an empty list — `test_keymap.py:33-40` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0011** [FIX] Unterminated bracketed paste busy-spins at 100% CPU — `commands.py:496` · shape `except-in-loop-without-exit`
- [cpython-pyrepl] **CRF-PYREPL-0012** [FIX] Ctrl-Z then fg then exit leaves the terminal wedged — `unix_console.py (prepare/restore)` · shape `save-state-clobbered-by-reentry`
- [cpython-pyrepl] **CRF-PYREPL-0013** [FIX] History file read leniently and written back strictly, destroying non-UTF-8 history — `readline.py:443,460` · shape `asymmetric-encode-decode-pair`
- [cpython-pyrepl] **CRF-PYREPL-0014** [FIX] Ctrl-C persists the abandoned line to the history file — `commands.py:225-229` · shape `one-lifecycle-hook-two-meanings`
- [cpython-pyrepl] **CRF-PYREPL-0015** [FIX] COLUMNS=0 makes the REPL loop spew tracebacks forever — `unix_console.py:471` · shape `unvalidated-numeric-from-environment`
- [cpython-pyrepl] **CRF-PYREPL-0016** [FIX] issubclass arguments transposed, so last_command_is is always wrong — `reader.py:604` · shape `isinstance-second-arg-not-a-type`
- [cpython-pyrepl] **CRF-PYREPL-0017** [FIX] kill_line passes eol + 1, defeating its own empty-range guard — `commands.py:159` · shape `off-by-one-against-a-correct-sibling`
- [cpython-pyrepl] **CRF-PYREPL-0018** [FIX] Event queue emits a key name no keyspec can express — `unix_eventqueue.py:33` · shape `unreachable-name-in-a-closed-vocabulary`
- [cpython-pyrepl] **CRF-PYREPL-0019** [CONSIDER] GetConsoleMode/SetConsoleMode return values ignored where every other Win32 call is checked — `windows_console.py:152,156` · shape `return-ignored-against-checked-family`
- [cpython-pyrepl] **CRF-PYREPL-0020** [CONSIDER] Threading handler restores, prints, then re-prepares, swallowing failure in a 10 Hz loop — `_threading_handler.py:38-51` · shape `except-exception-too-broad`
- [cpython-pyrepl] **CRF-PYREPL-0021** [FIX] The regression test for gh-139391 cannot fail — `test_unix_console.py:336` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0022** [FIX] MagicMock(lambda ...) sets spec, not side_effect -- inert at seven sites — `test_unix_console.py (7 sites)` · shape `mock-callable-as-spec`
- [cpython-pyrepl] **CRF-PYREPL-0023** [FIX] getpending is mocked out entirely, so the function containing CRF-PYREPL-0001 is never executed — `test_unix_console.py:33,216,236` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0024** [CONSIDER] RefreshCache.valid checks only dimensions, though its own comment names paste mode — `reader.py:241-246` · shape `flag-not-reset-on-early-exit`
- [cpython-pyrepl] **CRF-PYREPL-0025** [POLICY] sys.modules['readline'] is never installed, so the documented rlcompleter recipe is a no-op — `readline.py:592-617` · shape `documented-recipe-not-wired-up`

Shapes represented above, in catalog terms: `api-value-domain-mismatch`, `assertion-against-a-stub-that-cannot-fail`, `asymmetric-encode-decode-pair`, `attribute-created-outside-init`, `bare-except-swallows-control-flow`, `case-normalization-on-a-literal-key`, `cleanup-only-on-success-path`, `commit-side-effect-outside-the-success-guard`, `conflict-resolved-silently-where-siblings-warn`, `decode-error-treated-as-incomplete`, `divergent-sentinel-across-parallel-modules`, `documented-recipe-not-wired-up`, `duplicated-guard-wrong-operand`, `empty-result-conflated-with-absent`, `error-reported-below-warning`, `except-exception-too-broad`, `except-in-loop-without-exit`, `falsy-test-on-a-zero-valued-enum-member`, `fix-not-propagated-to-sibling-path`, `flag-not-reset-on-early-exit`, `generated-doc-propagates-a-source-error`, `guard-conjoined-with-a-preference-flag`, `guard-rechecks-call-receiver`, `handler-reads-a-name-the-try-may-not-have-bound`, `identity-by-id-requires-retention`, `identity-key-from-a-non-artifact-proxy`, `implemented-but-undocumented-option`, `index-computed-before-a-mutation-used-after-it`, `isinstance-on-container-not-element`, `isinstance-second-arg-not-a-type`, `mirrored-direction-handles-fewer-cases`, `mock-callable-as-spec`, `off-by-one-against-a-correct-sibling`, `one-concern-implemented-per-backend`, `one-lifecycle-hook-two-meanings`, `one-predicate-two-implementations`, `per-line-property-derived-from-the-aggregate`, `per-redraw-binding-never-released`, `raise-without-from-in-except`, `recognizer-rejects-a-legal-variant-spelling`, `refactor-changed-behaviour-doc-did-not`, `reinitializer-resets-a-subset-of-its-state`, `return-ignored-against-checked-family`, `same-fact-derived-from-two-sources`, `save-state-clobbered-by-reentry`, `serialize-and-parse-use-different-grammars`, `signed-length-from-untrusted-header`, `structured-index-tested-by-string-suffix`, `test-cannot-fail`, `two-sides-of-a-comparison-normalized-differently`, `unchecked-no-op-sentinel`, `unguarded-inverse-of-guarded-operation`, `unreachable-name-in-a-closed-vocabulary`, `unvalidated-numeric-from-environment`, `zip-truncates-on-length-mismatch`

## Known false positives — suppress these

If a candidate matches one of these classes, dismiss it *with the stated reason* rather than reporting it. Each entry also states what the REAL bug looks like, so a genuine instance is never suppressed.

## Dead code / unused symbols

### 1. Dynamically-dispatched name
- **Symptom:** a function/method/class reported as unreferenced.
- **Why non-bug:** Python reaches it without a literal reference — `getattr(obj, name)`, a registry
  populated by decorator, `__init_subclass__`, entry points in `pyproject.toml`, a plugin loader,
  `globals()[name]`, Django/SQLAlchemy/pydantic model hooks, or a name only used in a template or
  config string.
- **Real bug:** genuinely nothing constructs the name — no decorator registry, no entry point, no
  string occurrence anywhere including non-Python files. **Grep the whole repo for the bare name
  (including `.toml`, `.cfg`, `.ini`, `.yaml`, `.html`) before reporting.**

### 2. Public API surface of a library
- **Symptom:** exported functions unreferenced *within* the package.
- **Why non-bug:** the consumers are downstream users, not this repo. Anything in `__all__`, or
  re-exported from `__init__.py`, is API by definition.
- **Real bug:** an internal helper (leading underscore, not in `__all__`, not re-exported) with no
  in-repo callers.

### 3. Protocol / ABC / override conformance
- **Symptom:** a method that "no one calls" — `__enter__`, `visit_*`, `do_GET`, `setUp`, an
  overridden base method.
- **Why non-bug:** the caller is the language, the framework, or a base class. Visitor methods
  (`ast.NodeVisitor.visit_*`), unittest fixtures, and dunder protocol methods are dispatched by name.
- **Real bug:** a `visit_X`/`do_X` whose suffix matches no real node type or verb — a typo'd hook
  that will never fire. That one IS worth reporting.

### 4. Test-only helper
- **Symptom:** a symbol used exclusively from `tests/`.
- **Why non-bug:** that is its purpose.
- **Real bug:** a symbol used by *nothing*, including tests.

---

## Error handling

### 5. Intentional narrow suppression
- **Symptom:** an `except ...: pass`.
- **Why non-bug:** it catches a *specific* exception it can legitimately ignore, and the intent is
  documented — `except FileNotFoundError: pass` around a best-effort cleanup, `contextlib.suppress`.
- **Real bug:** the suppressed type is broad (`Exception`/bare), or the body swallows an error the
  caller needed in order to be correct. See `bare-except-swallows-control-flow` for the
  `BaseException` variant, which is a real bug regardless of intent.

### 6. Re-raising boundary handler
- **Symptom:** a broad `except Exception:` at a top-level entry point.
- **Why non-bug:** it logs, adds context, and **re-raises** (or deliberately converts to an exit
  code at the true process boundary — a CLI `main()`, a request handler, a worker loop that must not
  die on one bad item).
- **Real bug:** the same shape with no re-raise and no logging, in the middle of a call stack, where
  the caller cannot tell the operation failed.

### 7. `logging.exception` inside the handler
- **Symptom:** an exception "swallowed" but logged.
- **Why non-bug:** at a genuine boundary, logging with traceback and continuing is the designed
  behavior.
- **Real bug:** logged at `debug`/`info` level, or logged without the traceback (`logger.error(str(e))`),
  so the failure is invisible in production — and control continues as if it succeeded.

---

## Complexity / structure

### 8. Inherently-complex dispatch
- **Symptom:** a function scoring high on branch count / cognitive complexity.
- **Why non-bug:** it is a flat dispatch table — a long `match`/`if-elif` over opcodes, token types,
  or message kinds, or generated/vendored code. Splitting it would *reduce* readability.
- **Real bug:** deep NESTING (4+ levels) mixing distinct concerns, or a long function where extract-
  method would produce independently-nameable units. Judge nesting depth over raw length.

### 9. Parser / state machine
- **Symptom:** high complexity in a tokenizer, parser, or protocol decoder.
- **Why non-bug:** state machines are irreducibly branchy; the complexity is essential, not accidental.
- **Real bug:** a state machine whose states are implicit in ad-hoc booleans rather than an enum —
  that is a real refactor target.

---

## Types

### 10. Deliberate `Any` at a boundary
- **Symptom:** `Any` flagged as weak typing.
- **Why non-bug:** it sits at a genuinely dynamic edge — deserialized JSON, `**kwargs` passthrough,
  a decorator wrapping arbitrary callables, or a C-extension boundary.
- **Real bug:** `Any` on an internal function whose actual type is known and stable, especially when
  a `TypedDict`/dataclass for that shape already exists in the codebase.

### 11. Missing annotations in a deliberately-untyped area
- **Symptom:** low annotation coverage.
- **Why non-bug:** the project is gradually typed and this module is explicitly excluded in
  `pyproject.toml`/`mypy.ini`, or it is test code where annotations add little.
- **Real bug:** an unannotated *public* API in a package that otherwise ships `py.typed`.

---

## Consistency / patterns

### 12. Justified local divergence
- **Symptom:** one module handles a concern differently from the majority.
- **Why non-bug:** the divergence has a reason — a performance-critical path, a compatibility shim
  for an older Python, or a deliberate migration in progress (new pattern being rolled out).
- **Real bug:** divergence with no rationale, where the two variants have *different behavior* on
  edge cases (error handling, encoding, path separators) — behavioral divergence outranks stylistic.

### 13. Vendored / generated code
- **Symptom:** any finding inside `_vendor/`, `third_party/`, `*_pb2.py`, `*.generated.py`, migrations.
- **Why non-bug:** not this project's code to change; regenerating overwrites edits.
- **Real bug:** none here — but a *stale vendored copy with a known CVE* is worth raising separately
  as a dependency finding, not a code finding.

---

## Documentation

### 14. Intentionally-terse docstring
- **Symptom:** a one-line or missing docstring flagged.
- **Why non-bug:** the function is a trivial, self-describing accessor, a private helper, or an
  override whose contract is documented on the base class.
- **Real bug:** a docstring that is **wrong** — documents parameters that no longer exist, states a
  return type that changed, or describes behavior the body contradicts. Stale beats absent as a
  finding: absent docs mislead nobody.

---

## Git history

### 15. Churn from mechanical change
- **Symptom:** a file topping the churn/risk ranking.
- **Why non-bug:** the churn is formatting, a lint sweep, a mass rename, dependency bumps, or a
  license-header change — high line counts, zero semantic risk.
- **Real bug:** churn concentrated in *bug-fix* commits touching the same function repeatedly. Read
  the commit subjects before ranking; `fix:`/`hotfix` density is the signal, not raw line count.

---

## Learned from validation runs

Classes below were confirmed by triaging real findings, not anticipated in advance. Each names the
run that produced it, so the evidence is traceable.

### 16. Value rewrite during iteration *(idlelib, 4 instances)*
- **Symptom:** `for k in d: d[k] = transform(d[k])` flagged as mutation-during-iteration.
- **Why non-bug:** assigning to a key **already present** does not change the container's size, and
  CPython raises only on a size change. Rewriting values in place while iterating is correct and
  idiomatic.
- **Real bug:** anything that changes size — `del d[k]`, `d[new_key] = v`, `lst.append/remove/pop`.
  *(The scanner now encodes this discriminator; it is documented here because a reviewer reading
  the raw pattern will otherwise re-flag it.)*

### 17. Mutable default as a deliberate counter cell *(idlelib `multicall.py:426`)*
- **Symptom:** `def bindseq(seq, n=[0]): ... n[0] += 1` flagged as a mutable default argument.
- **Why non-bug:** the shared-across-calls behaviour is exactly what the author wants — a
  pre-`nonlocal` mutable cell used as a persistent counter. The function is *correct only because*
  the default persists.
- **Real bug:** the caller expects a fresh container per call. The tell: a single-element
  list/dict mutated by index (`n[0] += 1`) is a cell; `items.append(x)` on a list that grows
  unboundedly across calls is the defect.

### 18. Declarative class configuration *(idlelib, 14 instances)*
- **Symptom:** `class EditorWindow: menu_specs = [...]` flagged as a shared mutable class attribute.
- **Why non-bug:** it is declarative configuration read by the framework and **overridden in
  subclasses** (`PyShell.menu_specs = [...]`), never mutated. The same shape as Django's `Meta`,
  DRF's `fields`, or Tk widget specs.
- **Real bug:** the attribute is actually mutated somewhere (`self.items.append(...)`), so state
  bleeds between instances. Search the whole project for a mutation before reporting — absence of
  mutation in one module is not proof, but presence is proof of the defect.

### 19. Documented boundary around user-supplied code *(idlelib `calltip.py:141`)*
- **Symptom:** `except BaseException:` around `eval(expression, namespace)` flagged.
- **Why non-bug (arguably):** the handler carries a comment explaining that an uncaught exception
  would close the IDE and that user code can raise anything. It is a deliberate, documented
  containment boundary at a genuine trust edge.
- **Real bug:** the same shape with no rationale, or one that also swallows the interrupt a user
  needs in order to *stop* long-running user code. Treat a documented boundary as **POLICY** for the
  maintainer, not as a defect to fix — but do say that Ctrl-C is caught too.

### 20. Control-flow exception re-raised by an earlier clause *(idlelib `rpc.py:109`)*
- **Symptom:** a bare `except:` flagged for swallowing `SystemExit`/`KeyboardInterrupt`.
- **Why non-bug (partly):** an earlier clause in the same `try` already handles and re-raises it —
  `except SystemExit: raise` then `except:`. The obligation is discharged for whatever the earlier
  clause covers.
- **Real bug:** the *remaining* control-flow exceptions. In the `rpc.py` shape `SystemExit` is
  re-raised but `KeyboardInterrupt` is still swallowed, so the finding is real but narrower than it
  first appears. Name precisely which exceptions remain swallowed.

### 21. Poll loop draining a queue or socket *(idlelib `rpc.py:424`, `run.py:166`)*
- **Symptom:** `while True: ... except queue.Empty: pass` flagged as a swallowed exception in an
  unbounded loop (the "persistent failure hangs the process" shape).
- **Why non-bug:** `queue.Empty`, `TimeoutError`, `socket.timeout`, `BlockingIOError` and
  `InterruptedError` mean *"nothing ready right now"*, not *"this failed"*. Catching one and
  continuing **is** the design of an event loop; the body goes on to do other work before retrying.
- **Real bug:** the caught exception denotes an actual failure that can be permanent — the gist's
  genuine instance was `except OSError: pass` around a directory scan in
  `importlib._bootstrap_external`, which spins forever if the directory is gone. The discriminator is
  the exception's *meaning*, not the loop shape.

### 22. Codec-varying test suite *(CPython `test_io.py`, `test_tarfile.py`)*
- **Symptom:** the same path opened for reading and for writing with different `encoding=`/`errors=`,
  flagged as an asymmetric round-trip.
- **Why non-bug:** the module is *varying the codec on purpose* — that is the thing under test. The
  raw stdlib pass produced **876 findings of which 543 came from one file**, purely from pairing
  every reader against every writer of `TESTFN`.
- **Real bug:** "the two sides disagree" presupposes each side has *one* answer. Require exactly one
  distinct codec per side; a path opened under three or more is deliberate variation, not asymmetry.
  Two different *variable* names are not evidence either — they may hold the same value.

### 23. Predicate read as a lifecycle hook *(asyncio `tasks.py`, `taskgroups.py`)*
- **Symptom:** `self.done()` inside `Task.cancel` flagged as a commit-semantic hook on an abort path.
- **Why non-bug:** `Future.done()` is a **query returning a bool**, not a hook. It appears in
  expression position — `if self.done(): return False`.
- **Real bug:** a hook *invoked as a statement*. Statement-vs-expression position separates the two
  cleanly, and without it asyncio alone supplied the largest false-positive class in the raw pass.

### 24. Lifecycle hook parameterized by outcome *(`tkinter/dnd.py:183`)*
- **Symptom:** `cancel()` calling `self.finish(...)` flagged as the abort path invoking the
  success hook.
- **Why non-bug:** the hook takes an explicit outcome flag and implements **both** meanings —
  `finish(self, event, commit=0)`, where `on_release` passes `1` and `cancel` passes `0`. This is
  the *guarded twin* of the shape, sitting in the stdlib.
- **Real bug:** the abort path and the success path calling the hook with **identical** arguments, so
  nothing tells it which meaning to use (`_pyrepl/commands.py`: both call a bare `reader.finish()`).

### 25. Self-written header round-tripped by a test *(CPython `test_zipfile`, `xpickle_worker.py`)*
- **Symptom:** a signed `struct.unpack` field used as a length, with no negative check.
- **Why non-bug:** the header was constructed by the same test moments earlier. The shape is about
  *untrusted* input; a value the program itself just wrote cannot be hostile.
- **Real bug:** the bytes come from a file, a socket, or an environment the caller does not control.
  Also beware two near-misses that look like validation and are not: `if size == -1` is a **sentinel**
  test that excludes exactly one negative value, and `if not size` only tests zero.

### 26. Setter that correctly returns None *(CPython `_pydatetime.py`, `_pydecimal.py`)*
- **Symptom:** a call whose result is discarded, flagged against "sibling calls that check theirs".
- **Why non-bug:** a *setter* returning `None` is the convention, not an oversight. Keying the family
  on get/set stems collapsed `self.__setstate` and `self.state` into one bucket and produced **1414
  findings across the stdlib**, almost all of them setters.
- **Real bug:** a **foreign-function binding** whose status return is dropped where its siblings' are
  checked. The convention argument only holds inside a module that imports `ctypes`/`_winapi` — without
  that gate, 720 of 787 findings were test modules constructing CamelCase objects.

### 27. Type guard followed by a subscript *(CPython `collections/__init__.py` Counter)*
- **Symptom:** `isinstance(other, Counter)` flagged because `other[elem]` appears in the same scope.
- **Why non-bug:** the guard comes **first** — `if not isinstance(other, Counter): return NotImplemented`
  — and the subscript is safe *because of it*. Counter alone supplied eight findings.
- **Real bug:** a subscript that **precedes** the test, proving the name already held a sequence
  (`cmd[0]` at line 658, `isinstance(cmd, digit_arg)` at 675). Order is the whole discriminator; a
  subscript inside a conditional body proves nothing either, since it usually sits under its own guard.

### 28. Local list managed by one algorithm *(CPython `glob.py`, `inspect.py`, `_pylong.py`)*
- **Symptom:** `parts.pop()` unguarded while some `parts.append()` elsewhere is inside an `if`.
- **Why non-bug:** generic local names (`parts`, `lines`, `stack`, `cands`) recur everywhere, so
  matching on the name paired `glob.py` against `argparse.py`. A local list is managed by a single
  algorithm, and its `if` is a data condition, not a policy.
- **Real bug:** a collection **owned by an object** (`reader.history`), whose add is guarded by a
  **policy flag** (`should_auto_add_history`), with the inverse in a *different function*. All three
  filters are load-bearing — dropping any one takes the count from 7 to 164.

### 29. Initialization and context entry snapshotting state *(CPython `_pyio.py`, `asyncio/base_events.py`)*
- **Symptom:** `__init__` storing `self._saved = get_something()` flagged as a clobberable snapshot.
- **Why non-bug:** `__init__` and `__enter__` are *supposed* to snapshot, and cannot be re-entered on
  the same object. Including them gave 60 findings dominated by ordinary attribute assignment.
- **Real bug:** an ordinary method that snapshots via `Xget…` and modifies via the matching `Xset…`,
  reachable twice — across a signal, a suspend/resume, or a retry.

### 30. Constructing an object as a bare statement *(CPython `test_zstd.py`, `test_winreg.py`)*
- **Symptom:** `_ProactorSocketTransport(...)` as an expression statement, flagged for discarding a result.
- **Why non-bug:** constructing for side effects is normal, and a constructor has no status to return.
- **Real bug:** see class 26 — restrict to FFI modules, and count a sibling as "checked" only when its
  result is genuinely *tested* (an `if`/`while`/`assert` test or a comparison). Counting every
  non-statement position also counted `f(Foo())` and inflated the sibling count until the argument
  meant nothing.

### 31. Import cycle through a package facade via a submodule import *(coverage.py)*
- **Symptom:** a reported import cycle whose closing edge is `from pkg import submodule`
  (`from coverage import env`, at 12+ sites).
- **Why non-bug:** that statement binds the **submodule**, not a name in `__init__.py` — Python's
  `_handle_fromlist` falls back to importing `pkg.submodule` when the attribute is missing on the
  partially-initialised package. The dependency is on `pkg/submodule.py`. Attributing it to the
  package manufactures a cycle through the facade: **16 of the 20 cycles first reported for
  coverage.py were this one idiom**, and none was real.
- **Real bug:** `from pkg import SomeName` where `SomeName` is genuinely *bound* in `__init__.py`.
  That one is order-sensitive — coverage.py's `jsonreport.py:14` / `xmlreport.py:16` do
  `from coverage import __version__`, which works only because `__init__.py` binds `__version__`
  before importing `control`. Reordering those two blocks — a change no reviewer would flag —
  raises `ImportError` at import time.
- **Second-order lesson:** the phantom edges came from an **incomplete index**, not a bad matching
  rule. A leaf module with no imports of its own is absent from the graph's keys, so indexing from
  those alone leaves it unresolvable and the bare-package fallback blames the facade. Index every
  file. This is the same root cause as the prefix fallback removed after the `_pyrepl` run.

### 32. `from __future__ import annotations` reported as an unused import *(coverage.py)*
- **Symptom:** every module in the project reported with one unused import.
- **Why non-bug:** it is a **compiler directive** (PEP 563), not an import — it binds no name, so a
  name-reference scanner will *always* call it unused. Removing it flips annotation evaluation from
  lazy to eager and breaks every unquoted forward reference. It was **42 of the 42** unused imports
  reported for coverage.py: the entire category.
- **Real bug:** an ordinary import whose bound name is never referenced. Exclude `__future__` outright.

### 33. Symbol referenced only outside the reviewed package *(coverage.py)*
- **Symptom:** a public helper reported as unreferenced.
- **Why non-bug:** the reference lives outside the scanned tree — a `console_scripts` entry point in
  `setup.py`, a helper used only by `tests/`, an API shown in `doc/`. All **9** unreferenced symbols
  reported for coverage.py were referenced elsewhere in the same repository.
- **Real bug:** a symbol nothing anywhere references. Collect references from the wider project
  (`setup.py`, `tests/`, `doc/`) without analysing those files as subjects; and treat
  `# pragma: debugging` as an exclusion marker, since a maintainer's hand-invoked debug tool is
  unreferenced by design.

### 34. `__main__.py` reported as an orphan *(coverage.py)*
- **Symptom:** `pkg/__main__.py` never imported by any module.
- **Why non-bug:** `python -m pkg` has the interpreter execute it; being unimported is what it is
  *for*. Likewise a file read as **text** rather than imported — coverage.py's `pth_file.py` is
  embedded into the installed `.pth` by `setup.py`, making it a source template, not a module.
- **Real bug:** a module that is genuinely reachable from nothing. Exclude `__main__.py`, and treat a
  filename appearing anywhere in project text as a reference.

### 35. `type: ignore` age read as staleness *(coverage.py)*
- **Symptom:** a debt inventory reporting "36 stale, 12 ancient" suppressions.
- **Why non-bug:** age measures **commit date**, not whether the suppression still suppresses
  anything. coverage.py sets `warn_unused_ignores = true`, and `mypy` is clean — so **zero** of its 47
  ignores are stale, whatever their age.
- **Real bug:** a suppression mypy would now report as unused. For a mypy-gated repository,
  `warn_unused_ignores` is the oracle and marker age carries no signal at all. Check for that setting
  before reporting ignore-debt as actionable.

### 36. The option-dict convention (`cnf={}`) in a Tk-style API

**Looks like:** `mutable-default-argument` / ruff `B006`, at scale — 46 instances across tkinter's
widget API, every one `def method(self, cnf={}, **kw)`.

**Why it is not a bug:** the dict is read-only on the ordinary path. `_cnfmerge` builds a *fresh*
dict rather than mutating its argument, and every method routes through it. A convention repeated
across an entire API surface, where the shared object is never written, is one design decision — not
46 defects.

**Dismiss with:** "read-only option-dict convention; `_cnfmerge` returns a new dict".

**What the REAL bug looks like:** the same signature where the body *writes* to the parameter —
`cnf[k] = v`, `del cnf[k]`, `cnf.update(...)` — on a path reachable with the argument omitted. Three
tkinter `__init__` methods do reach `del cnf[k]`, and are correctly reported at high confidence; they
are harmless only because the deletion is driven by a comprehension that is empty for an empty dict.
Note that mutating a dict the *caller* supplied is a different catalogued shape,
`wrapper-mutates-foreign-collection`.

### 37. `F821` on a name bound in an enclosing function and read in a nested closure

**Looks like:** ruff `F821` "Undefined name `x`" where `x` is plainly assigned a few lines above.

**Why it is not a bug:** a ruff scope-resolution limitation. `asyncio/staggered.py` binds
`parent_task`, `unhandled_exceptions` and `exceptions` at lines 67-72 and reads all three inside the
nested `task_done`; ruff reports six `F821` for them.

**Dismiss with:** "bound in the enclosing function scope at line N; closure read".

**What the REAL bug looks like:** a name with no binding on any path into the read — typically a typo,
or a name bound only inside a conditional branch. Check for an assignment in *any* enclosing scope
before dismissing, and note that `F821` on a version-gated builtin (`ExceptionGroup`,
`BaseExceptionGroup`) is a third thing again: it means `--target-version` was not passed, and the fix
is to pass it rather than to dismiss the finding.

### 38. A `unittest.TestCase` subclass reported as an unreferenced symbol

**Looks like:** `dead-code-finder` unreferenced symbols, at scale — **163 of idlelib's 164** were this
one class.

**Why it is not a bug:** `unittest.TestLoader` selects by `issubclass(obj, TestCase)`, never by name.
Zero literal references is the correct and expected state.

**Discriminator:** `unittest.TestCase` in the MRO **and** the filename matches the `pattern=` of a
reachable `loader.discover(...)`. Both must hold — a `TestCase` in a file the discovery pattern
excludes really is unreachable, and that is a finding.

### 39. A commented-out block that is prose, not code

**Looks like:** `commented_code_blocks`, because the regex matches `# for `, `# if `, `# from `,
`# return `, `# while `, `# raise `, `# with `, `# print `.

**Why it is not a bug:** English sentences that happen to start with a Python keyword —
`# for the handler to run after it finishes...`.

**Discriminator, and it kills the whole class mechanically:** strip the `#` and `ast.parse()` the
block. **Prose raises `SyntaxError`.** Same test disposes of pseudocode algorithm sketches, whose
bodies are English (`delete it`, `do indent-region`).

**What the REAL bug looks like:** a block that parses cleanly *and* does not self-describe as a
template or example.

### 40. A class-body import creating a class attribute

**Looks like:** an unused import, at high confidence.

**Why it is not a bug:** names imported inside a `class` statement become class attributes read as
`self.X` — text sharing nothing with the import. idlelib's `editor.py:39-52` places 14 imports in the
`EditorWindow` class body as a deliberate dependency-injection idiom, with subclasses substituting
implementations by overriding the attribute.

**Discriminator:** if the `ImportFrom` node's parent is a `ClassDef`, search for `self.<name>` and
`<ClassName>.<name>` across the whole subclass tree before reporting; downgrade to medium regardless.

### 41. An import that IS the assertion

**Looks like:** an unused import in a test module.

**Why it is not a bug:** `from tokenize import open, detect_encoding` under a comment reading *"Fail
if either tokenize.open and t.detect_encoding does not exist."* Removing the import removes coverage.

**Discriminator:** an unused import in a `test_*.py` whose line or preceding comment contains
"fail" / "exist" / "available". **Real bug:** the same shape with no such comment.

### 42. An import for its side effect

**Looks like:** an unused import.

**Why it is not a bug:** `import idlelib.pyshell  # Set Windows DPI awareness before Tk().`

**Discriminator:** a trailing comment describing an *effect* rather than a use, or a module known for
import-time registration. **Real bug:** the same shape with no comment and no registration.

### 43. A placeholder identifier in a scaffold file

**Discriminator:** filename is `template.py` / `*_template.py`, or the file contains other unfilled
blanks (idlelib's has the docstring `"Test , coverage %."`). Exclude the whole file.

### 44. A changelog entry read as a reference

**Looks like:** a symbol that appears "referenced" in project text, suppressing a real dead-code
finding — the inverse of the usual false positive.

**Why it is wrong:** idlelib ships `ChangeLog` (1591 lines) and `HISTORY.txt` (296). A symbol's only
non-definition occurrences there are **records of a 1990s change, not references**.

**Discriminator:** exclude `ChangeLog`, `HISTORY*`, `NEWS*` from the reference corpus. The rule
remains correct for `README`, `Doc/` and `*.def`.

### 45. `PLE0704` inside a documented from-handler callback

**Looks like:** a bare `raise` outside an exception handler.

**Why it is not a bug:** `socketserver.BaseServer.handle_error` is invoked by the stdlib only from
inside `except Exception:`, so the bare `raise` has a live exception. ruff cannot see dynamic context.

**Discriminator:** the enclosing function overrides a documented callback whose contract is "invoked
from within a handler". **Real bug:** a bare `raise` with no such contract — `RuntimeError: No active
exception to reraise`.

### 46. `S608` on English prose

**Why it is not a bug:** ruff's `select … from` heuristic fires on natural language. idlelib's hit is
GUI help text: *"Select the desired modifier keys above, and the final key from the list on the right."*

**Discriminator:** dismiss immediately when the module imports no DB-API driver. **Real bug:** an
f-string or `%`/`+` interpolation feeding `cursor.execute`.

### 47. `B018` as a deliberate probe

**Why it is not a bug:** `obj.attr` bare inside `try: … except AttributeError:` is a hasattr-probe; a
bare undefined name inside `try: … except NameError:` exists to manufacture a traceback; a bare
attribute read followed by an assertion about a cache exercises `__getattr__` for its side effect.
B018 scored **0 of 5** on idlelib.

**Discriminator:** an expression statement with no side effect **and** no surrounding handler —
typically a dropped `assert` or a `==` that should have been `=`.

