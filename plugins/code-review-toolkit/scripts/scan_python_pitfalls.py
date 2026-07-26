#!/usr/bin/env python3
"""Detect the correctness pitfalls catalogued in data/python_bug_shapes.json.

Each check corresponds 1:1 to a shape `id` in that catalog, so a finding can be
traced straight back to its shape (with its guarded twin, sibling-hunt directive,
and differential). The differentials are applied here as confidence downgrades
rather than hard filters: the script's job is high recall with an honest
confidence signal, and the agent's job is the final call.

Confidence levels:
    high    -- the differential does not apply; this is very likely a real defect
    medium  -- matches the shape, but a legitimate reading exists; agent must check
    low     -- weak signal, reported only so a sibling hunt can start from it

Usage:
    python scan_python_pitfalls.py [path] [--max-files N] [--check ID[,ID...]] [--exclude PAT[,PAT...]]
"""

from __future__ import annotations

import ast
import builtins
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan_common import (  # noqa: E402
    build_envelope,
    collect_python_files,
    emit,
    parse_common_args,
    parse_source,
    relative_to_root,
)

# --------------------------------------------------------------------------
# Reference tables
# --------------------------------------------------------------------------

# Names that make a default value mutable. `datetime.now()`-style calls are
# evaluated once at def time, which is the same defect wearing different clothes.
_MUTABLE_CALLS = frozenset(
    {
        "list",
        "dict",
        "set",
        "bytearray",
        "collections",
        "Counter",
        "defaultdict",
        "OrderedDict",
        "deque",
    }
)
_EVALUATED_ONCE_CALLS = frozenset(
    {"now", "today", "utcnow", "time", "uuid4", "monotonic"}
)

# Calls that block the thread -- fatal inside `async def`.
_BLOCKING_CALLS = frozenset(
    {
        "time.sleep",
        "os.system",
        "subprocess.run",
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "urllib.request.urlopen",
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.delete",
        "requests.patch",
        "requests.head",
        "requests.request",
        "socket.create_connection",
    }
)

# Methods that mutate the receiver in place.
_MUTATING_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "remove",
        "pop",
        "clear",
        "update",
        "add",
        "discard",
        "sort",
        "setdefault",
        "popitem",
    }
)

# Calls that produce a safe snapshot of a container.
_SNAPSHOT_CALLS = frozenset(
    {
        "list",
        "tuple",
        "set",
        "dict",
        "sorted",
        "frozenset",
        "copy",
        "deepcopy",
        "reversed",
        "items",
        "keys",
        "values",
    }
)

# Decorators that make a class derive __eq__/__hash__ for you.
_DATACLASS_DECORATORS = frozenset(
    {"dataclass", "attrs", "define", "frozen", "total_ordering"}
)


def _exception_ancestors() -> dict[str, set[str]]:
    """Map each builtin exception name to the set of its ancestor names.

    Derived from the running interpreter, so it is always correct for the Python
    in use rather than a hand-maintained table that drifts.
    """
    table: dict[str, set[str]] = {}
    for name in dir(builtins):
        obj = getattr(builtins, name)
        if isinstance(obj, type) and issubclass(obj, BaseException):
            table[name] = {
                base.__name__
                for base in obj.__mro__[1:]
                if isinstance(base, type) and issubclass(base, BaseException)
            }
    return table


_EXC_ANCESTORS = _exception_ancestors()


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------


def _dotted_name(node: ast.AST) -> str:
    """Render an attribute/name chain as a dotted string ('a.b.c'), else ''."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _call_name(node: ast.Call) -> str:
    """Best-effort dotted name of what a Call invokes."""
    return _dotted_name(node.func)


def _names_used(node: ast.AST) -> set[str]:
    """All bare Name identifiers loaded anywhere under *node*."""
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _is_snapshot(node: ast.AST) -> bool:
    """True if *node* evaluates to a copy rather than the live container."""
    if isinstance(node, ast.Call):
        name = _call_name(node)
        return bool(name) and name.split(".")[-1] in _SNAPSHOT_CALLS
    # d[:] / lst[:] produce a copy.
    return isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)


def _decorator_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> set[str]:
    """Flattened decorator names, including the attribute tail."""
    found: set[str] = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        name = _dotted_name(target)
        if name:
            found.add(name)
            found.add(name.split(".")[-1])
    return found


def _mutates(name: str, body: list[ast.stmt]) -> bool:
    """True if *name* is mutated (method call, item/attr assignment, del) in *body*."""
    for stmt in body:
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _MUTATING_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == name
            ):
                return True
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for tgt in targets:
                    if isinstance(tgt, ast.Subscript) and isinstance(
                        tgt.value, ast.Name
                    ):
                        if tgt.value.id == name:
                            return True
            if isinstance(node, ast.Delete):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Subscript) and isinstance(
                        tgt.value, ast.Name
                    ):
                        if tgt.value.id == name:
                            return True
    return False


def _walk_same_scope(node: ast.AST):
    """Yield descendants of *node* without entering a nested function scope.

    ``ast.walk`` descends unconditionally, so a `return` inside a nested `def`
    would otherwise be attributed to the enclosing construct.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        yield child
        yield from _walk_same_scope(child)


def _returns(name: str, body: list[ast.stmt]) -> bool:
    """True if *name* is returned or yielded from *body*."""
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.Return, ast.Yield)) and node.value is not None:
                if name in _names_used(node.value):
                    return True
    return False


def _finding(
    shape: str,
    severity: str,
    confidence: str,
    node: ast.AST,
    message: str,
    detail: str = "",
) -> dict:
    """Build one finding keyed to a bug-shape id."""
    return {
        "shape": shape,
        "type": shape,
        "severity": severity,
        "confidence": confidence,
        "line": getattr(node, "lineno", 0),
        "column": getattr(node, "col_offset", 0),
        "message": message,
        "detail": detail,
    }


# --------------------------------------------------------------------------
# Checks -- one per bug shape
# --------------------------------------------------------------------------


def _check_mutable_default(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        args = fn.args
        pairs = list(
            zip(
                args.args[-len(args.defaults) :] if args.defaults else [], args.defaults
            )
        )
        pairs += [
            (a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None
        ]
        for arg, default in pairs:
            kind = ""
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                kind = type(default).__name__.lower()
            elif isinstance(default, ast.Call):
                name = _call_name(default)
                tail = name.split(".")[-1] if name else ""
                if tail in _MUTABLE_CALLS:
                    kind = f"{tail}()"
                elif tail in _EVALUATED_ONCE_CALLS:
                    kind = f"{name}()"
            if not kind:
                continue
            mutated = _mutates(arg.arg, fn.body)
            returned = _returns(arg.arg, fn.body)
            if mutated:
                conf, why = "high", "the parameter is mutated in the body"
            elif returned:
                conf, why = "high", "the shared object is returned to callers"
            else:
                conf, why = (
                    "medium",
                    "no mutation seen; may be read-only (see differential)",
                )
            out.append(
                _finding(
                    "mutable-default-argument",
                    "FIX",
                    conf,
                    default,
                    f"{fn.name}(): default for '{arg.arg}' is {kind}, evaluated once at "
                    f"def time and shared by every call",
                    why,
                )
            )
    return out


def _check_late_binding_closure(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.AsyncFor, ast.While)):
            continue
        if isinstance(loop, ast.While):
            loop_vars: set[str] = set()
        else:
            loop_vars = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
        if not loop_vars:
            continue
        for node in ast.walk(loop):
            if not isinstance(
                node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            body = node.body if isinstance(node, ast.Lambda) else node
            captured = (
                _names_used(body if isinstance(body, ast.AST) else node) & loop_vars
            )
            if not captured:
                continue
            # Default-argument binding (lambda i=i: ...) is the documented fix.
            bound = (
                {a.arg for a in (node.args.args if hasattr(node, "args") else [])}
                if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef))
                else set()
            )
            if captured <= bound:
                continue
            out.append(
                _finding(
                    "late-binding-closure-in-loop",
                    "FIX",
                    "medium",
                    node,
                    f"closure created in a loop captures {sorted(captured)} by reference; "
                    f"every instance will see the final value",
                    "safe if the callable is consumed within the same iteration -- "
                    "check whether it escapes the loop",
                )
            )
    return out


def _check_except_ordering(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        seen: list[tuple[str, ast.ExceptHandler]] = []
        for handler in node.handlers:
            names: list[str] = []
            if isinstance(handler.type, ast.Name):
                names = [handler.type.id]
            elif isinstance(handler.type, ast.Tuple):
                names = [e.id for e in handler.type.elts if isinstance(e, ast.Name)]
            for name in names:
                ancestors = _EXC_ANCESTORS.get(name)
                if ancestors is None:
                    continue  # user-defined; hierarchy unknown statically
                for earlier, _ in seen:
                    if earlier in ancestors:
                        out.append(
                            _finding(
                                "except-clause-ordering-unreachable",
                                "FIX",
                                "high",
                                handler,
                                f"`except {name}` is unreachable: `except {earlier}` above "
                                f"already catches it ({name} subclasses {earlier})",
                                "clauses are tested top-to-bottom; order most-specific first",
                            )
                        )
                        break
            for name in names:
                seen.append((name, handler))
    return out


def _check_return_in_finally(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try) or not node.finalbody:
            continue
        for stmt in node.finalbody:
            # Control flow belonging to THIS finally only -- a return inside a
            # nested def belongs to that function, not to the finally.
            candidates = [stmt, *_walk_same_scope(stmt)]
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                candidates = []
            for inner in candidates:
                kw = None
                if isinstance(inner, ast.Return):
                    kw = "return"
                elif isinstance(inner, ast.Break):
                    kw = "break"
                elif isinstance(inner, ast.Continue):
                    kw = "continue"
                if kw:
                    out.append(
                        _finding(
                            "return-or-break-in-finally",
                            "FIX",
                            "high",
                            inner,
                            f"`{kw}` inside `finally` discards any exception propagating "
                            f"through the try block",
                            "the caller sees a normal return instead of the error",
                        )
                    )
    return out


def _check_eq_without_hash(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        decorators = _decorator_names(cls)
        if decorators & _DATACLASS_DECORATORS:
            continue  # eq/hash are derived
        methods = {
            m.name
            for m in cls.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # An explicit `__hash__ = None` is a deliberate opt-out.
        explicit = {
            t.id
            for stmt in cls.body
            if isinstance(stmt, ast.Assign)
            for t in stmt.targets
            if isinstance(t, ast.Name)
        }
        if (
            "__eq__" in methods
            and "__hash__" not in methods
            and "__hash__" not in explicit
        ):
            out.append(
                _finding(
                    "eq-without-hash",
                    "CONSIDER",
                    "medium",
                    cls,
                    f"class {cls.name} defines __eq__ but not __hash__; instances become "
                    f"unhashable (Python sets __hash__ = None)",
                    "only a problem if instances are used in a set or as dict keys -- check",
                )
            )
    return out


def _check_mutation_during_iteration(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.AsyncFor)):
            continue
        iterated = loop.iter
        # `for k in d.items()` etc. still iterates d -- unwrap one attribute call.
        if isinstance(iterated, ast.Call) and isinstance(iterated.func, ast.Attribute):
            if iterated.func.attr in {"items", "keys", "values"}:
                iterated = iterated.func.value
            elif _is_snapshot(iterated):
                continue
        elif _is_snapshot(iterated):
            continue
        if not isinstance(iterated, ast.Name):
            continue
        name = iterated.id
        if _mutates(name, loop.body):
            out.append(
                _finding(
                    "mutation-during-iteration",
                    "FIX",
                    "high",
                    loop,
                    f"'{name}' is mutated while being iterated",
                    "dict/set raise RuntimeError; LISTS SILENTLY SKIP elements as indices "
                    "shift -- iterate over a snapshot such as list(...)",
                )
            )
    return out


def _check_fire_and_forget_task(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        # A bare expression statement -- the return value goes nowhere.
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        name = _call_name(node.value)
        tail = name.split(".")[-1] if name else ""
        if tail in {"create_task", "ensure_future"} and (
            "asyncio" in name or "loop" in name or tail == "create_task"
        ):
            out.append(
                _finding(
                    "asyncio-fire-and-forget-task",
                    "FIX",
                    "high",
                    node,
                    f"{name}(...) result is discarded; the event loop keeps only a weak "
                    f"reference, so the task may be garbage-collected before it finishes",
                    "retain it in a set with add_done_callback(discard), or await it",
                )
            )
    return out


def _check_blocking_in_async(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        for node in ast.walk(fn):
            # Do not descend into nested synchronous defs.
            if isinstance(node, ast.FunctionDef) and node is not fn:
                continue
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in _BLOCKING_CALLS:
                out.append(
                    _finding(
                        "blocking-call-in-async-function",
                        "FIX",
                        "high",
                        node,
                        f"blocking call {name}(...) inside async def {fn.name}() stalls the "
                        f"entire event loop",
                        "use the async equivalent, or await asyncio.to_thread(...)",
                    )
                )
    return out


def _check_unawaited_coroutine(tree: ast.AST) -> list[dict]:
    """Intra-file only: a coroutine defined here, called here, never awaited."""
    out: list[dict] = []
    async_names = {
        n.name for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)
    }
    if not async_names:
        return out
    awaited: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            awaited.add(id(node.value))
        # gather/wait/create_task consume the coroutine object legitimately.
        if isinstance(node, ast.Call):
            name = _call_name(node)
            tail = name.split(".")[-1] if name else ""
            if tail in {
                "gather",
                "wait",
                "create_task",
                "ensure_future",
                "run",
                "wait_for",
            }:
                for arg in node.args:
                    if isinstance(arg, ast.Call):
                        awaited.add(id(arg))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if id(call) in awaited:
            continue
        name = _call_name(call)
        tail = name.split(".")[-1] if name else ""
        if tail in async_names:
            out.append(
                _finding(
                    "unawaited-coroutine",
                    "FIX",
                    "high",
                    call,
                    f"coroutine {tail}() is called without await; the body never runs",
                    "an un-awaited coroutine object is truthy, so guards silently take the "
                    "wrong branch",
                )
            )
    return out


def _check_lru_cache_on_method(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = _decorator_names(fn)
            if not (decorators & {"lru_cache", "cache"}):
                continue
            first = fn.args.args[0].arg if fn.args.args else ""
            if first not in {"self", "cls"}:
                continue
            out.append(
                _finding(
                    "lru-cache-on-method",
                    "CONSIDER",
                    "high",
                    fn,
                    f"{cls.name}.{fn.name}() is cached on the CLASS with '{first}' in the key, "
                    f"so every instance ever passed is retained for the process lifetime",
                    "use cached_property or a per-instance cache; harmless for singletons",
                )
            )
    return out


def _check_class_level_mutable(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        if _decorator_names(cls) & _DATACLASS_DECORATORS:
            continue
        for stmt in cls.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(stmt, ast.Assign):
                targets, value = stmt.targets, stmt.value
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                targets, value = [stmt.target], stmt.value
            if value is None or not isinstance(value, (ast.List, ast.Dict, ast.Set)):
                continue
            for tgt in targets:
                if not isinstance(tgt, ast.Name):
                    continue
                # ALL_CAPS reads as a constant; downgrade rather than drop.
                conf = "medium" if tgt.id.isupper() else "high"
                out.append(
                    _finding(
                        "class-level-mutable-attribute",
                        "FIX",
                        conf,
                        stmt,
                        f"{cls.name}.{tgt.id} is a mutable class attribute shared by every "
                        f"instance",
                        "initialize in __init__ (or use field(default_factory=...)); "
                        "acceptable only if never mutated",
                    )
                )
    return out


def _check_bare_except(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_bare = node.type is None
        is_base = isinstance(node.type, ast.Name) and node.type.id == "BaseException"
        if not (is_bare or is_base):
            continue
        # A handler that re-raises is a legitimate boundary.
        if any(isinstance(n, ast.Raise) for n in ast.walk(node)):
            continue
        # Capturing the exception for the caller to re-raise (the standard
        # thread/worker-body pattern) preserves control flow -- observed in real
        # code, so downgrade rather than drop.
        captured = bool(node.name) and any(
            isinstance(n, ast.Name) and n.id == node.name
            for stmt in node.body
            for n in ast.walk(stmt)
        )
        label = "except:" if is_bare else "except BaseException:"
        if captured:
            conf = "medium"
            detail = (
                f"the exception is captured as '{node.name}' -- legitimate if the caller "
                f"re-raises it (thread/worker boundary); a real bug if it is only logged"
            )
        else:
            conf = "high"
            detail = "use `except Exception:` so Ctrl-C and sys.exit() still work"
        out.append(
            _finding(
                "bare-except-swallows-control-flow",
                "FIX",
                conf,
                node,
                f"`{label}` without re-raise also swallows KeyboardInterrupt and SystemExit",
                detail,
            )
        )
    return out


def _check_exception_in_del(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.name != "__del__":
            continue
        guarded = any(isinstance(n, ast.Try) for n in fn.body)
        if guarded:
            continue
        risky = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and _call_name(n)]
        if not risky:
            continue
        out.append(
            _finding(
                "exception-in-del-or-finalizer",
                "CONSIDER",
                "medium",
                fn,
                "__del__ performs calls without a try/except; an exception here is "
                "printed and ignored, silently skipping the rest of the finalizer",
                "prefer weakref.finalize or an explicit close(); module globals may "
                "already be None at interpreter shutdown",
            )
        )
    return out


def _check_is_literal(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, (ast.Is, ast.IsNot)):
                continue
            for side in (node.left, comparator):
                if not isinstance(side, ast.Constant):
                    continue
                if side.value is None or side.value is True or side.value is False:
                    continue
                if side.value is Ellipsis:
                    continue
                out.append(
                    _finding(
                        "is-comparison-with-literal",
                        "CONSIDER",
                        "high",
                        node,
                        f"`is` compared against the literal {side.value!r}; identity holds "
                        f"only by interning accident",
                        "use == for value comparison; keep `is` for None/True/False/sentinels",
                    )
                )
    return out


_CHECKS = {
    "mutable-default-argument": _check_mutable_default,
    "late-binding-closure-in-loop": _check_late_binding_closure,
    "except-clause-ordering-unreachable": _check_except_ordering,
    "return-or-break-in-finally": _check_return_in_finally,
    "eq-without-hash": _check_eq_without_hash,
    "mutation-during-iteration": _check_mutation_during_iteration,
    "asyncio-fire-and-forget-task": _check_fire_and_forget_task,
    "blocking-call-in-async-function": _check_blocking_in_async,
    "unawaited-coroutine": _check_unawaited_coroutine,
    "lru-cache-on-method": _check_lru_cache_on_method,
    "class-level-mutable-attribute": _check_class_level_mutable,
    "bare-except-swallows-control-flow": _check_bare_except,
    "exception-in-del-or-finalizer": _check_exception_in_del,
    "is-comparison-with-literal": _check_is_literal,
}


def analyze_file(
    path: Path, project_root: Path, checks: list[str] | None = None
) -> list[dict]:
    """Run the selected checks over one file. Unparseable files yield nothing."""
    tree = parse_source(path)
    if tree is None:
        return []
    selected = checks or list(_CHECKS)
    findings: list[dict] = []
    rel = relative_to_root(path, project_root)
    for name in selected:
        check = _CHECKS.get(name)
        if check is None:
            continue
        for finding in check(tree):
            finding["file"] = rel
            findings.append(finding)
    return findings


def analyze(
    target: str,
    *,
    max_files: int = 0,
    checks: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict:
    """Scan *target* for catalogued Python pitfalls.

    ``exclude`` drops files whose project-relative path contains any of the given
    substrings. Real-world runs show generated content (report artifacts, golden
    fixtures, vendored trees) is the dominant false-positive source, and it is
    project-specific enough that it cannot be hardcoded -- hence the option, plus
    the ``by_directory`` breakdown below so such clustering is visible at a glance.
    """
    resolved = Path(target).resolve()
    from scan_common import find_project_root

    project_root = find_project_root(resolved)
    # A file target scans exactly that file. (Several sibling scripts instead
    # fall back to the project root here, which silently turns "scan this file"
    # into "scan everything" -- a trap worth not reproducing. discover_python_files
    # handles a file path directly, so no special-casing is needed.)
    scan_root = resolved
    files, files_total = collect_python_files(scan_root, max_files)

    findings: list[dict] = []
    for path in files:
        rel = relative_to_root(path, project_root)
        if exclude and any(pattern in rel for pattern in exclude):
            continue
        findings.extend(analyze_file(path, project_root, checks))

    # Deterministic ordering -- see explore's --runs cross-run deduplication.
    findings.sort(key=lambda f: (f["file"], f["line"], f["shape"]))

    by_shape: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    by_directory: dict[str, int] = {}
    for finding in findings:
        by_shape[finding["shape"]] = by_shape.get(finding["shape"], 0) + 1
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_confidence[finding["confidence"]] = (
            by_confidence.get(finding["confidence"], 0) + 1
        )
        top = finding["file"].split("/")[0] if "/" in finding["file"] else "."
        by_directory[top] = by_directory.get(top, 0) + 1

    result = build_envelope(project_root, scan_root, files_total, len(files))
    result["summary"] = {
        "total_findings": len(findings),
        "by_shape": dict(sorted(by_shape.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "by_confidence": dict(sorted(by_confidence.items())),
        # Sorted by count: a single directory dominating usually means generated
        # content, not a real defect cluster. Triage the directory, not each hit.
        "by_directory": dict(
            sorted(by_directory.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "checks_run": sorted(checks or _CHECKS),
        "excluded_patterns": sorted(exclude or []),
    }
    result["findings"] = findings
    return result


def _extract_options(
    argv: list[str],
) -> tuple[list[str], list[str] | None, list[str] | None]:
    """Pull ``--check`` and ``--exclude`` out of argv, returning the remainder."""
    rest: list[str] = []
    checks: list[str] | None = None
    exclude: list[str] | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--check" and i + 1 < len(argv):
            checks = [c.strip() for c in argv[i + 1].split(",") if c.strip()]
            i += 2
        elif argv[i] == "--exclude" and i + 1 < len(argv):
            exclude = [p.strip() for p in argv[i + 1].split(",") if p.strip()]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return rest, checks, exclude


def main() -> None:
    argv, checks, exclude = _extract_options(sys.argv[1:])
    target, max_files = parse_common_args(argv)
    if checks:
        unknown = [c for c in checks if c not in _CHECKS]
        if unknown:
            emit(
                {
                    "error": f"unknown check(s): {', '.join(unknown)}",
                    "available": sorted(_CHECKS),
                }
            )
            sys.exit(2)
    emit(analyze(target, max_files=max_files, checks=checks, exclude=exclude))


if __name__ == "__main__":
    main()
