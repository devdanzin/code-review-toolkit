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

## Bug-shape templates for `git-history-analyzer` (5)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

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

## Confirmed in OTHER projects (6) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [coveragepy] **CRF-COVPY-0001** [FIX] _reap_dead_thread_dbs destroys the in-memory database and mis-attributes coverage — `sqldata.py:390` · shape `fix-not-propagated-to-sibling-path`
- [coveragepy] **CRF-COVPY-0004** [FIX] SyntaxError from a bad coding cookie escapes compute_multiline_map — `sysmon.py:489-495` · shape `guard-catches-wrong-exception-set`
- [coveragepy] **CRF-COVPY-0012** [FIX] file_tracers is iterated unguarded in flush_data while the C writer holds the lock — `collector.py:495` · shape `fix-not-propagated-to-sibling-path`
- [coveragepy] **CRF-COVPY-0013** [FIX] Collector.resume() installs other threads' tracers onto the calling thread — `collector.py:369-370` · shape `fix-reverted-and-never-relanded`
- [coveragepy] **CRF-COVPY-0041** [CONSIDER] CLI error and status messages are split across stdout and stderr — `cmdline.py:953, :1188, :780` · shape `fix-not-propagated-to-sibling-path`
- [coveragepy] **CRF-COVPY-0059** [CONSIDER] write() lacks the no_disk guard its four siblings have — `sqldata.py:912-927` · shape `fix-not-propagated-to-sibling-path`

Shapes represented above, in catalog terms: `fix-not-propagated-to-sibling-path`, `fix-reverted-and-never-relanded`, `guard-catches-wrong-exception-set`

_79 further cross-project finding(s) were omitted here because they belong to shapes another agent owns._

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

