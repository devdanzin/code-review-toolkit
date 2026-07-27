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

## Bug-shape templates for `python-pitfall-scanner` (46)

Each shape is a reusable *pattern*, not a location. For each one, hunt this codebase for instances, then follow the sibling-hunt directive to find the ones a cold pass would miss.

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

## Confirmed in OTHER projects (30) — hunt them here

These are **not** claims about this codebase. Each is a shape that was confirmed somewhere else, which makes it worth a targeted look here. A hit is a new finding for this project; a miss is not a finding at all, so do not report absence.

- [coveragepy] **CRF-COVPY-0006** [FIX] CoverageData.update() never DETACHes, so a second in-memory combine destroys the first data file — `sqldata.py:744-884` · shape `cleanup-only-on-success-path`
- [coveragepy] **CRF-COVPY-0021** [FIX] An unparseable non-.py file leaves both numerator and denominator, inflating TOTAL — `report_core.py:105-115` · shape `cleanup-only-on-success-path`
- [coveragepy] **CRF-COVPY-0024** [FIX] patch = _exit / execv discard the whole process's data with zero trace — `patch.py:56-57, :74-75` · shape `cleanup-only-on-success-path`
- [coveragepy] **CRF-COVPY-0025** [FIX] SqliteDb.__exit__ skips close() on a commit failure and then reuses the stale connection — `sqlitedb.py:102-112` · shape `cleanup-only-on-success-path`
- [coveragepy] **CRF-COVPY-0026** [FIX] The .pth bare except hides a broken install, so every subprocess contributes nothing — `pth_file.py:11-16` · shape `bare-except-swallows-control-flow`
- [coveragepy] **CRF-COVPY-0034** [FIX] Region analysis never walks orelse, handlers or finalbody — `regions.py:53-55` · shape `partial-traversal-of-a-node-family`
- [coveragepy] **CRF-COVPY-0035** [FIX] PathAliases rewrites a path prefix with str.replace and a greedy regex — `files.py:508-509, :352, :354, :539` · shape `prefix-rewrite-done-as-a-content-search`
- [coveragepy] **CRF-COVPY-0038** [FIX] PyTracer reads an emptied set as an untraced file and disables line events for the frame — `pytracer.py:241-242` · shape `empty-container-read-as-absent`
- [coveragepy] **CRF-COVPY-0045** [FIX] test_thread_safe_save_data has zero assertions and passes with its fix reverted — `tests/test_concurrency.py:635` · shape `test-cannot-fail`
- [coveragepy] **CRF-COVPY-0048** [CONSIDER] Two regression tests are switched off for every configuration — `tests/test_oddball.py:256-259, tests/test_concurrency.py:290` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0001** [FIX] Unix and Windows event queues disagree on the empty-data sentinel — `unix_console.py:335,780` · shape `divergent-sentinel-across-parallel-modules`
- [cpython-pyrepl] **CRF-PYREPL-0002** [FIX] Control-character guard compares against a category the API never returns — `input.py:94` · shape `api-value-domain-mismatch`
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
- [cpython-pyrepl] **CRF-PYREPL-0019** [CONSIDER] GetConsoleMode/SetConsoleMode return values ignored where every other Win32 call is checked — `windows_console.py:152,156` · shape `return-ignored-against-checked-family`
- [cpython-pyrepl] **CRF-PYREPL-0020** [CONSIDER] Threading handler restores, prints, then re-prepares, swallowing failure in a 10 Hz loop — `_threading_handler.py:38-51` · shape `except-exception-too-broad`
- [cpython-pyrepl] **CRF-PYREPL-0021** [FIX] The regression test for gh-139391 cannot fail — `test_unix_console.py:336` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0022** [FIX] MagicMock(lambda ...) sets spec, not side_effect -- inert at seven sites — `test_unix_console.py (7 sites)` · shape `mock-callable-as-spec`
- [cpython-pyrepl] **CRF-PYREPL-0023** [FIX] getpending is mocked out entirely, so the function containing CRF-PYREPL-0001 is never executed — `test_unix_console.py:33,216,236` · shape `test-cannot-fail`
- [cpython-pyrepl] **CRF-PYREPL-0024** [CONSIDER] RefreshCache.valid checks only dimensions, though its own comment names paste mode — `reader.py:241-246` · shape `flag-not-reset-on-early-exit`

Shapes represented above, in catalog terms: `api-value-domain-mismatch`, `asymmetric-encode-decode-pair`, `bare-except-swallows-control-flow`, `cleanup-only-on-success-path`, `decode-error-treated-as-incomplete`, `divergent-sentinel-across-parallel-modules`, `duplicated-guard-wrong-operand`, `empty-container-read-as-absent`, `except-exception-too-broad`, `except-in-loop-without-exit`, `flag-not-reset-on-early-exit`, `isinstance-on-container-not-element`, `isinstance-second-arg-not-a-type`, `mock-callable-as-spec`, `one-lifecycle-hook-two-meanings`, `partial-traversal-of-a-node-family`, `prefix-rewrite-done-as-a-content-search`, `return-ignored-against-checked-family`, `save-state-clobbered-by-reentry`, `signed-length-from-untrusted-header`, `test-cannot-fail`, `unguarded-inverse-of-guarded-operation`, `unvalidated-numeric-from-environment`

_55 further cross-project finding(s) were omitted here because they belong to shapes another agent owns._

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

