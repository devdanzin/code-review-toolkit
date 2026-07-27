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

## Bug-shape templates for `silent-failure-hunter` (7)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

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

## Already recorded for THIS project in the findings catalog (26)

These are settled. Verify each still exists, then move on — do not re-derive them, and do not report them as new.

- **CRF-IDLELIB-0001** [FIX] A failed config save deletes the user's config file — `config.py:135-139` · shape `except-exception-too-broad`
- **CRF-IDLELIB-0002** [FIX] One subprocess-accept timeout wedges IDLE permanently — `pyshell.py:485-527` · shape `flag-not-reset-on-early-exit`
- **CRF-IDLELIB-0003** [FIX] Replace's NULL-guard tests the call receiver instead of the match — `replace.py:213-216` · shape `guard-rechecks-call-receiver`
- **CRF-IDLELIB-0004** [FIX] Autocomplete's mode filter never applies to ATTRS because ATTRS == 0 — `autocomplete.py:117,134` · shape `falsy-test-on-a-zero-valued-enum-member`
- **CRF-IDLELIB-0005** [FIX] Forward search abandons the rest of a line after a zero-width match — `searchengine.py:146-151` · shape `mirrored-direction-handles-fewer-cases`
- **CRF-IDLELIB-0006** [FIX] get_argspec guards two of its three touches of a user object — `calltip.py:189` · shape `except-exception-too-broad`
- **CRF-IDLELIB-0007** [FIX] Custom run arguments are corrupted by a Tcl list round-trip — `query.py:352,368-376` · shape `serialize-and-parse-use-different-grammars`
- **CRF-IDLELIB-0008** [FIX] Stack Viewer reads an attribute only runcode() ever creates — `run.py:575-579,635` · shape `attribute-created-outside-init`
- **CRF-IDLELIB-0009** [FIX] A failed window probe leaves the user's window stuck maximized — `zoomheight.py:66-105` · shape `cleanup-only-on-success-path`
- **CRF-IDLELIB-0010** [FIX] A failed is_active check permanently disables the completion window's Configure handler — `autocomplete_w.py:238` · shape `flag-not-reset-on-early-exit`
- **CRF-IDLELIB-0011** [CONSIDER] A bad print command orphans the user's unsaved source in /tmp — `iomenu.py:333-348` · shape `cleanup-only-on-success-path`
- **CRF-IDLELIB-0012** [CONSIDER] The subprocess's last-resort handler can itself raise NameError — `run.py:183-190` · shape `handler-reads-a-name-the-try-may-not-have-bound`
- **CRF-IDLELIB-0013** [CONSIDER] Every OSError on recv becomes 'the peer hung up' — `rpc.py:358-361` · shape `raise-without-from-in-except`
- **CRF-IDLELIB-0014** [CONSIDER] endexecuting() is skipped if showtraceback() fails — `pyshell.py:790-807` · shape `cleanup-only-on-success-path`
- **CRF-IDLELIB-0015** [CONSIDER] Remote internal errors are reported only at a permanently-disabled debug level — `rpc.py:258-260` · shape `error-reported-below-warning`
- **CRF-IDLELIB-0016** [CONSIDER] A failed getcwd() silently yields a relative path used as a window identity key — `filelist.py:105-108` · shape `identity-key-from-a-non-artifact-proxy`
- **CRF-IDLELIB-0017** [CONSIDER] A comment with no space after # is invisible to HyperParser — `pyparse.py:44-48` · shape `recognizer-rejects-a-legal-variant-spelling`
- **CRF-IDLELIB-0018** [CONSIDER] Reconnect resets some per-connection state but not the packet read buffer — `rpc.py:130-141` · shape `reinitializer-resets-a-subset-of-its-state`
- **CRF-IDLELIB-0019** [CONSIDER] Replace All's final selection uses the pre-replacement span — `replace.py:161-175` · shape `index-computed-before-a-mutation-used-after-it`
- **CRF-IDLELIB-0020** [CONSIDER] getprog catches only re.PatternError, so OverflowError escapes to every caller — `searchengine.py:85-89` · shape `except-exception-too-broad`
- **CRF-IDLELIB-0021** [CONSIDER] terminate_subprocess catches every OSError though its comment names one — `pyshell.py:551-561` · shape `except-exception-too-broad`
- **CRF-IDLELIB-0022** [CONSIDER] Debugger.close swallows every failure of quit() — `debugger.py:159-162` · shape `except-exception-too-broad`
- **CRF-IDLELIB-0023** [CONSIDER] A bare except guards a four-link attribute chain — `autocomplete.py:173-175` · shape `bare-except-swallows-control-flow`
- **CRF-IDLELIB-0024** [CONSIDER] Recent-files list is updated outside the success guard — `iomenu.py:229,237` · shape `commit-side-effect-outside-the-success-guard`
- **CRF-IDLELIB-0025** [CONSIDER] Idb.user_exception calls into the GUI unguarded where its twin is guarded — `debugger.py:55-56` · shape `fix-not-propagated-to-sibling-path`
- **CRF-IDLELIB-0026** [CONSIDER] Five tests in the suite cannot fail — `idle_test/test_autocomplete.py:241` · shape `test-cannot-fail`

## Confirmed in OTHER projects (8) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [coveragepy] **CRF-COVPY-0002** [FIX] patch = fork makes coverage worse than not patching at all — `control.py:1499-1503` · shape `unchecked-no-op-sentinel`
- [coveragepy] **CRF-COVPY-0005** [FIX] Nested Coverage permanently stops measurement on the default 3.14 core — `sysmon.py:335, 374-387` · shape `external-registration-not-reestablished`
- [coveragepy] **CRF-COVPY-0007** [FIX] --fail-under rounds toward 100 while the printed total rounds away from it — `results.py:502` · shape `asymmetric-rounding-between-display-and-gate`
- [coveragepy] **CRF-COVPY-0008** [FIX] XML line-rate publishes 99.997% as exactly 1 — `xmlreport.py:33-38` · shape `asymmetric-rounding-between-display-and-gate`
- [coveragepy] **CRF-COVPY-0016** [FIX] An unreadable config file reads as no config at all — `config.py:55-59, :319` · shape `empty-result-conflated-with-absent`
- [coveragepy] **CRF-COVPY-0023** [CONSIDER] A transient listdir failure is cached for the process lifetime — `files.py:133-139` · shape `failure-result-cached-as-if-successful`
- [coveragepy] **CRF-COVPY-0033** [FIX] A user-written __annotate__ has its whole body dropped from statements — `bytecode.py:41` · shape `name-based-filter-cannot-distinguish-generated-from-authored`
- [coveragepy] **CRF-COVPY-0060** [CONSIDER] find_spec failure is indistinguishable from module-not-found, and the caller's guard is dead code — `inorout.py:115-118` · shape `empty-result-conflated-with-absent`

Shapes represented above, in catalog terms: `asymmetric-rounding-between-display-and-gate`, `empty-result-conflated-with-absent`, `external-registration-not-reestablished`, `failure-result-cached-as-if-successful`, `name-based-filter-cannot-distinguish-generated-from-authored`, `unchecked-no-op-sentinel`

_77 further cross-project finding(s) were omitted here because they belong to shapes another agent owns._

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

