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

## Bug-shape templates for `pattern-consistency-checker` (14)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

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

## Confirmed in OTHER projects (25) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [cpython-idlelib] **CRF-IDLELIB-0005** [FIX] Forward search abandons the rest of a line after a zero-width match — `searchengine.py:146-151` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0007** [FIX] Custom run arguments are corrupted by a Tcl list round-trip — `query.py:352,368-376` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0017** [CONSIDER] A comment with no space after # is invisible to HyperParser — `pyparse.py:44-48` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0018** [CONSIDER] Reconnect resets some per-connection state but not the packet read buffer — `rpc.py:130-141` · shape `reinitializer-resets-a-subset-of-its-state`
- [cpython-idlelib] **CRF-IDLELIB-0019** [CONSIDER] Replace All's final selection uses the pre-replacement span — `replace.py:172-188` · shape `index-computed-before-a-mutation-used-after-it`
- [cpython-idlelib] **CRF-IDLELIB-0030** [FIX] HyperParser's string-prefix scanner never learned `f` or `t` — `hyperparser.py:298` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0031** [CONSIDER] Five independent hand-written recognizers for Python syntax with no shared source of truth — `hyperparser.py:298` · shape `one-predicate-two-implementations`
- [cpython-idlelib] **CRF-IDLELIB-0032** [FIX] The `-n` execution backend is missing five cross-cutting protections the RPC backend has — `pyshell.py:792-803` · shape `one-concern-implemented-per-backend`
- [cpython-idlelib] **CRF-IDLELIB-0033** [FIX] Under `idle -n`, __file__ is silently IDLE's own path instead of the script's — `pyshell.py:680` · shape `one-concern-implemented-per-backend`
- [cpython-idlelib] **CRF-IDLELIB-0037** [FIX] The documented sys.argv[0] contract for `idle -r` is wrong, and `idle -h` contradicts it correctly — `Doc/library/idle.rst:731-732` · shape `same-fact-derived-from-two-sources`
- [cpython-idlelib] **CRF-IDLELIB-0047** [FIX] codecontext's BLOCKOPENERS lacks match/case, so those blocks never appear in Code Context — `codecontext.py:22` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0051** [FIX] restore_file_breaks appends without clearing, so Save As carries the old file's breakpoints over — `pyshell.py:268` · shape `reinitializer-resets-a-subset-of-its-state`
- [cpython-idlelib] **CRF-IDLELIB-0052** [FIX] Breakpoints are keyed by the raw filename while windows are keyed by the normalized one — `pyshell.py:244` · shape `two-sides-of-a-comparison-normalized-differently`
- [cpython-idlelib] **CRF-IDLELIB-0053** [FIX] breakpoints.lst uses `=` as its delimiter, which is legal in a path — `pyshell.py:259` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0058** [CONSIDER] _synchre matches `def` but cannot match `async def`, making indent analysis quadratic in async modules — `pyparse.py:21` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0059** [FIX] _study1 has no f-string state, so a PEP 701 multi-line f-string is read as three statements — `pyparse.py:245` · shape `recognizer-rejects-a-legal-variant-spelling`
- [cpython-idlelib] **CRF-IDLELIB-0061** [FIX] Help sources are numbered on write and sorted as strings on read, so entry 10 sorts before entry 2 — `config.py:756` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0062** [FIX] An advanced key binding stored as a Tk event sequence is read back as a whitespace-separated list — `config_key.py:227` · shape `serialize-and-parse-use-different-grammars`
- [cpython-idlelib] **CRF-IDLELIB-0063** [FIX] Bracket matching checks the bracket type on the backward scan only — `hyperparser.py:137-140` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0064** [CONSIDER] Untabify rewrites the whole line where its tabify mirror rewrites only the indent — `format.py:340` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0065** [CONSIDER] DeleteCommand.undo reinserts text without tags where the Insert mirror round-trips them — `undo.py:294` · shape `mirrored-direction-handles-fewer-cases`
- [cpython-idlelib] **CRF-IDLELIB-0069** [CONSIDER] Two extensions' in-code fallback defaults disagree with the values actually shipped — `parenmatch.py:53` · shape `same-fact-derived-from-two-sources`
- [cpython-pyrepl] **CRF-PYREPL-0003** [FIX] Terminfo lookup lowercases the first byte, degrading every uppercase-initial TERM — `terminfo.py:140` · shape `case-normalization-on-a-literal-key`
- [cpython-pyrepl] **CRF-PYREPL-0004** [FIX] tparm's %{n}%+ branch indexes 1-based into a 0-based tuple — `terminfo.py:479-481` · shape `off-by-one-against-a-correct-sibling`
- [cpython-pyrepl] **CRF-PYREPL-0017** [FIX] kill_line passes eol + 1, defeating its own empty-range guard — `commands.py:159` · shape `off-by-one-against-a-correct-sibling`

Shapes represented above, in catalog terms: `case-normalization-on-a-literal-key`, `index-computed-before-a-mutation-used-after-it`, `mirrored-direction-handles-fewer-cases`, `off-by-one-against-a-correct-sibling`, `one-concern-implemented-per-backend`, `one-predicate-two-implementations`, `recognizer-rejects-a-legal-variant-spelling`, `reinitializer-resets-a-subset-of-its-state`, `same-fact-derived-from-two-sources`, `serialize-and-parse-use-different-grammars`, `two-sides-of-a-comparison-normalized-differently`

_73 further cross-project finding(s) were omitted here because they belong to shapes another agent owns._

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

