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


# Methods that change a container's SIZE. Only these are unsafe during
# iteration -- reassigning an existing key/index leaves the size untouched and
# is explicitly safe (CPython raises only on a size change).
_RESIZING_METHODS = frozenset(
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
        "setdefault",
        "popitem",
    }
)


def _resizes_during_iteration(
    name: str, loop_vars: set[str], body: list[ast.stmt]
) -> bool:
    """True if *name* may change SIZE inside a loop iterating over it.

    The discriminator that matters: ``d[k] = v`` where ``k`` is the loop
    variable rewrites an existing entry and is safe; ``del d[k]``, a resizing
    method call, or ``d[something_else] = v`` (which can insert a new key) is
    not. Getting this wrong flags idiomatic in-place value updates -- observed
    on CPython's own idlelib, where all four raw hits were safe rewrites.
    """
    for stmt in body:
        for node in ast.walk(stmt):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _RESIZING_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == name
            ):
                return True
            if isinstance(node, ast.Delete):
                for tgt in node.targets:
                    if (
                        isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == name
                    ):
                        return True
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for tgt in targets:
                    if not (
                        isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == name
                    ):
                        continue
                    # Subscript by the loop variable -> existing entry -> safe.
                    key = tgt.slice
                    if isinstance(key, ast.Name) and key.id in loop_vars:
                        continue
                    return True
    return False


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
        loop_vars = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
        if _resizes_during_iteration(name, loop_vars, loop.body):
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


def _attribute_mutated_anywhere(tree: ast.AST, attr: str) -> bool:
    """True if ``<anything>.attr`` is mutated anywhere in this module.

    A class-level mutable that is never mutated is declarative configuration
    (the `menu_specs`/`Meta`-style pattern), not shared-state corruption. This
    is a whole-module check because the mutation, if any, lives in a method far
    from the class-body assignment.
    """
    for node in ast.walk(tree):
        # obj.attr.append(...) / obj.attr.update(...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _MUTATING_METHODS
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == attr
        ):
            return True
        # obj.attr[k] = v  /  del obj.attr[k]
        targets: list[ast.expr] = []
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        elif isinstance(node, ast.Delete):
            targets = node.targets
        for tgt in targets:
            if (
                isinstance(tgt, ast.Subscript)
                and isinstance(tgt.value, ast.Attribute)
                and tgt.value.attr == attr
            ):
                return True
    return False


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
                # The defect requires an actual mutation. ALL_CAPS reads as a
                # constant, and an attribute never mutated in this module is
                # declarative class config (the menu_specs/Meta pattern seen
                # throughout idlelib) -- downgrade rather than drop, since the
                # mutation could live in another module.
                mutated = _attribute_mutated_anywhere(tree, tgt.id)
                if mutated:
                    conf, why = (
                        "high",
                        "the shared object is mutated in this module -- state bleeds "
                        "between instances",
                    )
                elif tgt.id.isupper():
                    conf, why = (
                        "low",
                        "ALL_CAPS and no mutation seen: reads as a constant (prefer a "
                        "tuple/frozenset to make that explicit)",
                    )
                else:
                    conf, why = (
                        "medium",
                        "no mutation seen in this module: likely declarative class "
                        "config, possibly overridden by subclasses -- confirm nothing "
                        "elsewhere mutates it",
                    )
                out.append(
                    _finding(
                        "class-level-mutable-attribute",
                        "FIX",
                        conf,
                        stmt,
                        f"{cls.name}.{tgt.id} is a mutable class attribute shared by every "
                        f"instance",
                        why,
                    )
                )
    return out


_CONTROL_FLOW_EXCEPTIONS = frozenset(
    {"SystemExit", "KeyboardInterrupt", "GeneratorExit"}
)


def _guarded_by_earlier_reraise(
    try_node: ast.Try, handler: ast.ExceptHandler
) -> set[str]:
    """Control-flow exceptions already re-raised by an earlier clause of *try_node*.

    ``except SystemExit: raise`` followed by a bare ``except:`` discharges the
    obligation for SystemExit -- the bare clause can no longer swallow it. The
    idiom appears in CPython's own idlelib (`rpc.py`).
    """
    covered: set[str] = set()
    for clause in try_node.handlers:
        if clause is handler:
            break
        if not any(isinstance(n, ast.Raise) for n in ast.walk(clause)):
            continue
        names: list[str] = []
        if isinstance(clause.type, ast.Name):
            names = [clause.type.id]
        elif isinstance(clause.type, ast.Tuple):
            names = [e.id for e in clause.type.elts if isinstance(e, ast.Name)]
        covered |= {n for n in names if n in _CONTROL_FLOW_EXCEPTIONS}
    return covered


def _check_bare_except(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    # Map each handler to its owning Try so sibling clauses can be inspected.
    owner: dict[int, ast.Try] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for clause in node.handlers:
                owner[id(clause)] = node
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
        try_node = owner.get(id(node))
        covered = _guarded_by_earlier_reraise(try_node, node) if try_node else set()
        remaining = sorted(_CONTROL_FLOW_EXCEPTIONS - covered)
        if not remaining:
            continue  # every control-flow exception re-raised by an earlier clause
        if covered:
            conf = "medium"
            detail = (
                f"an earlier clause re-raises {sorted(covered)}, but this one still "
                f"swallows {remaining}"
            )
        elif captured:
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


# --------------------------------------------------------------------------
# Shapes derived from a 40-bug audit of CPython's pure-Python stdlib.
# Overly-broad `except Exception:` alone accounted for ~50% of those findings.
# --------------------------------------------------------------------------

# Releasing a resource. Not exhaustive by design -- these are the verbs whose
# omission on an error path actually leaks something.
_RELEASE_METHODS = frozenset(
    {"close", "quit", "shutdown", "release", "disconnect", "terminate", "unlink"}
)

# Logging calls too quiet to surface a failure under default configuration.
_QUIET_LOG_METHODS = frozenset({"debug", "info"})
_LOUD_LOG_METHODS = frozenset(
    {"warning", "warn", "error", "exception", "critical", "fatal"}
)


def _handler_swallows(handler: ast.ExceptHandler) -> bool:
    """True if the handler neither re-raises nor propagates a failure signal.

    `pass`, a bare default assignment, or returning a fallback all mean the
    caller cannot tell the operation failed.
    """
    if any(isinstance(n, ast.Raise) for n in ast.walk(handler)):
        return False
    for stmt in handler.body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        if isinstance(stmt, ast.Return):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            # A logging/reporting call is still swallowing unless it is loud.
            name = _call_name(stmt.value)
            tail = name.split(".")[-1] if name else ""
            if tail in _QUIET_LOG_METHODS or tail in _LOUD_LOG_METHODS:
                continue
            return False
        return False
    return True


def _check_except_exception_too_broad(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        # A narrow try body is the signal: the author guarded one operation.
        narrow = len(node.body) <= 2
        for handler in node.handlers:
            if not isinstance(handler.type, ast.Name):
                continue
            if handler.type.id not in {"Exception", "BaseException"}:
                continue
            if not _handler_swallows(handler):
                continue
            # A loud log makes the failure visible -- not silent, so not FIX.
            loud = any(
                isinstance(n, ast.Call)
                and (_call_name(n).split(".")[-1] if _call_name(n) else "")
                in _LOUD_LOG_METHODS
                for n in ast.walk(handler)
            )
            if narrow and not loud:
                conf = "high"
                why = (
                    f"the try body is {len(node.body)} statement(s) -- one narrow "
                    f"operation guarded by a catch-all"
                )
            elif narrow:
                conf, why = (
                    "medium",
                    "narrow try body, but the handler logs loudly -- confirm the "
                    "broad catch is deliberate containment",
                )
            else:
                conf, why = (
                    "low",
                    "large try body: may be a genuine boundary (plugin loader, CLI "
                    "top level, call into user code) -- check for a rationale",
                )
            out.append(
                _finding(
                    "except-exception-too-broad",
                    "FIX",
                    conf,
                    handler,
                    f"`except {handler.type.id}:` swallows every failure of the "
                    f"guarded operation, not just the expected one",
                    why,
                )
            )
    return out


def _check_cleanup_only_on_success(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try) or not node.handlers or node.finalbody:
            continue
        if not node.body:
            continue
        last = node.body[-1]
        if not (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call)):
            continue
        call = last.value
        if not isinstance(call.func, ast.Attribute):
            continue
        verb = call.func.attr
        if verb not in _RELEASE_METHODS:
            continue
        target = _dotted_name(call.func.value) or "<resource>"
        # If a handler also releases it, the error path is covered.
        released_in_handler = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == verb
            for h in node.handlers
            for n in ast.walk(h)
        )
        if released_in_handler:
            continue
        out.append(
            _finding(
                "cleanup-only-on-success-path",
                "FIX",
                "high" if len(node.body) > 1 else "medium",
                last,
                f"`{target}.{verb}()` runs only when the try body succeeds; an "
                f"exception above it leaks the resource",
                "move it to a `finally:` block, or use a `with` statement",
            )
        )
    return out


def _check_error_reported_below_warning(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if any(isinstance(n, ast.Raise) for n in ast.walk(node)):
            continue
        quiet: list[str] = []
        loud = False
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            name = _call_name(inner)
            tail = name.split(".")[-1] if name else ""
            if tail in _LOUD_LOG_METHODS:
                loud = True
            elif tail in _QUIET_LOG_METHODS and name:
                quiet.append(name)
        if loud or not quiet:
            continue
        out.append(
            _finding(
                "error-reported-below-warning",
                "CONSIDER",
                "medium",
                node,
                f"the only report of this failure is {quiet[0]}(...), which default "
                f"logging configuration discards",
                "an operator running with defaults sees nothing; use warning/exception "
                "if the condition is actionable",
            )
        )
    return out


# "Nothing to do right now" signals. Catching one of these in a poll loop and
# continuing IS the design -- an event loop that drains a queue with a timeout
# is not a hang. Observed on idlelib's rpc.py/run.py event loops, where every
# raw hit was this pattern; the gist's genuine instance was `except OSError:`
# on a directory scan, where the error means real failure.
_POLL_SIGNAL_EXCEPTIONS = frozenset(
    {
        "Empty",
        "Full",
        "queue.Empty",
        "queue.Full",
        "timeout",
        "socket.timeout",
        "TimeoutError",
        "BlockingIOError",
        "InterruptedError",
        "asyncio.TimeoutError",
        "KeyboardInterrupt",
    }
)


def _is_poll_signal(handler: ast.ExceptHandler) -> bool:
    """True if the handler catches only 'nothing ready yet' conditions."""
    if handler.type is None:
        return False
    parts = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    names = {_dotted_name(p) for p in parts}
    names |= {n.split(".")[-1] for n in names if n}
    caught = {n for n in names if n}
    # An unresolvable name (not a plain Name/Attribute) means we cannot tell.
    if len(caught) < len(parts):
        return False
    return bool(caught) and caught <= _POLL_SIGNAL_EXCEPTIONS


def _check_except_in_loop_without_exit(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for loop in ast.walk(tree):
        # Unbounded loop only: `while True:` / `while 1:`.
        if not isinstance(loop, ast.While):
            continue
        test = loop.test
        unbounded = (isinstance(test, ast.Constant) and bool(test.value)) or (
            isinstance(test, ast.Name) and test.id == "True"
        )
        if not unbounded:
            continue
        for node in ast.walk(loop):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                # Any exit from the loop discharges the obligation.
                exits = any(
                    isinstance(n, (ast.Break, ast.Return, ast.Raise))
                    for n in ast.walk(handler)
                )
                if exits:
                    continue
                if _is_poll_signal(handler):
                    continue  # poll loop draining a queue/socket, not a hang
                if not _handler_swallows(handler):
                    continue
                label = (
                    ast.unparse(handler.type) if handler.type is not None else "bare"
                )
                out.append(
                    _finding(
                        "except-in-loop-without-exit",
                        "FIX",
                        "high",
                        handler,
                        f"`except {label}` inside `while True:` neither breaks, returns "
                        f"nor raises; a persistent failure spins forever",
                        "a transient failure recovers, but a permanent one hangs the "
                        "process with no diagnostic -- bound the retries",
                    )
                )
    return out


def _check_raise_without_from(tree: ast.AST) -> list[dict]:
    out: list[dict] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        for node in ast.walk(handler):
            if not isinstance(node, ast.Raise):
                continue
            if node.exc is None:  # bare `raise` re-raises; correct
                continue
            if node.cause is not None:  # explicit `from err` / `from None`
                continue
            # Re-raising the caught name itself needs no cause.
            if isinstance(node.exc, ast.Name) and node.exc.id == handler.name:
                continue
            out.append(
                _finding(
                    "raise-without-from-in-except",
                    "CONSIDER",
                    "medium",
                    node,
                    "raising a new exception inside `except` without `from` loses the "
                    "explicit cause",
                    "use `from err` to chain or `from None` to suppress deliberately",
                )
            )
    return out


def _flag_assignments(fn: ast.AST) -> dict[str, list[tuple[int, ast.AST]]]:
    """Map `self.attr` / bare-name targets to their constant assignments."""
    found: dict[str, list[tuple[int, ast.AST]]] = {}
    for node in _walk_same_scope(fn):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        target = node.targets[0]
        name = _dotted_name(target)
        # Only state that OUTLIVES the call can wedge anything -- an attribute
        # (`self.busy`) or a qualified global. A bare local dies with the frame,
        # so re-binding it is ordinary computation, not a missed reset.
        if not name or "." not in name:
            continue
        found.setdefault(name, []).append((node.lineno, node))
    return found


def _check_flag_not_reset_on_early_exit(tree: ast.AST) -> list[dict]:
    """A guard flag set at entry but reset only on the success path.

    `self.busy = True` ... early `return` ... `self.busy = False` at the end
    leaves the flag stuck for the object's lifetime, so every later call takes
    the "already busy" branch and silently does nothing. The correct form --
    `try: ... finally: self.busy = False` -- usually exists on a sibling method
    already (idlelib has five, e.g. `Debugger.run`'s `self.interacting`).
    """
    out: list[dict] = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # A finally that touches the flag discharges the obligation.
        guarded_in_finally: set[str] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Try):
                for stmt in node.finalbody:
                    for inner in ast.walk(stmt):
                        if isinstance(inner, ast.Assign):
                            for tgt in inner.targets:
                                nm = _dotted_name(tgt)
                                if nm:
                                    guarded_in_finally.add(nm)
        for name, assigns in _flag_assignments(fn).items():
            if name in guarded_in_finally or len(assigns) < 2:
                continue
            set_line, set_node = assigns[0]
            reset_line, _reset_node = assigns[-1]
            if reset_line <= set_line:
                continue
            # Different values: a set/reset pair, not two writes of the same value.
            values = {a[1].value.value for a in (assigns[0], assigns[-1])}  # type: ignore[attr-defined]
            if len(values) < 2:
                continue
            # An exit between them skips the reset.
            exits = [
                n
                for n in _walk_same_scope(fn)
                if isinstance(n, (ast.Return, ast.Raise))
                and set_line < n.lineno < reset_line
            ]
            if not exits:
                continue
            out.append(
                _finding(
                    "flag-not-reset-on-early-exit",
                    "FIX",
                    "high",
                    set_node,
                    f"`{name}` is set at line {set_line} but reset only at line "
                    f"{reset_line}; {len(exits)} earlier exit(s) skip the reset",
                    "the flag stays set for the object's lifetime, so every later "
                    "call takes the guarded branch and silently does nothing -- "
                    "use `try: ... finally:` to restore it on every path",
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
    "except-exception-too-broad": _check_except_exception_too_broad,
    "cleanup-only-on-success-path": _check_cleanup_only_on_success,
    "error-reported-below-warning": _check_error_reported_below_warning,
    "except-in-loop-without-exit": _check_except_in_loop_without_exit,
    "raise-without-from-in-except": _check_raise_without_from,
    "flag-not-reset-on-early-exit": _check_flag_not_reset_on_early_exit,
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
