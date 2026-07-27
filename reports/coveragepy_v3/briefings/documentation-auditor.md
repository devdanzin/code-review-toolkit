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

## Bug-shape templates for `documentation-auditor` (4)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

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

## Confirmed in OTHER projects (1) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [cpython-idlelib] **CRF-IDLELIB-0040** [CONSIDER] Documentation still names UI that was renamed or split two releases ago — `Doc/library/idle.rst` · shape `refactor-changed-behaviour-doc-did-not`

Shapes represented above, in catalog terms: `refactor-changed-behaviour-doc-did-not`

_97 further cross-project finding(s) were omitted here because they belong to shapes another agent owns._

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

