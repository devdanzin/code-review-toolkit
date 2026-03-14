#!/usr/bin/env python3
"""Build a dependency graph from Python imports using AST parsing.

Outputs a JSON structure with:
- files: per-file import details
- internal_graph: edges between project modules
- external_deps: third-party and stdlib imports
- metrics: fan-in/fan-out per module
- cycles: detected circular dependencies
- re_exports: __init__.py re-exports and __all__ declarations

Usage:
    python analyze_imports.py [path]

    path: directory, file, or omitted for current directory
"""

import ast
import json
import sys
from pathlib import Path


# Comprehensive stdlib module list (Python 3.10+).  Used to distinguish
# stdlib imports from third-party imports when we cannot rely on
# importlib.metadata or sys.stdlib_module_names being available.
_STDLIB_TOP_LEVEL = frozenset({
    "__future__", "_thread", "abc", "aifc", "argparse", "array", "ast",
    "asynchat", "asyncio", "asyncore", "atexit", "audioop", "base64",
    "bdb", "binascii", "binhex", "bisect", "builtins", "bz2", "calendar",
    "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop",
    "collections", "colorsys", "compileall", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt",
    "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
    "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
    "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imghdr",
    "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
    "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue",
    "quopri", "random", "re", "readline", "reprlib", "resource",
    "rlcompleter", "runpy", "sched", "secrets", "select", "selectors",
    "shelve", "shlex", "shutil", "signal", "site", "smtpd", "smtplib",
    "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "sre_compile",
    "sre_constants", "sre_parse", "ssl", "stat", "statistics", "string",
    "stringprep", "struct", "subprocess", "sunau", "symtable", "sys",
    "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile",
    "termios", "test", "textwrap", "threading", "time", "timeit",
    "tkinter", "token", "tokenize", "tomllib", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "zoneinfo", "_ast", "_collections_abc", "_compat_pickle", "_compression",
    "_markupbase", "_osx_support", "_pydecimal", "_pyio", "_sitebuiltins",
    "_strptime", "_threading_local", "_weakrefset", "antigravity", "this",
})


def _is_stdlib(top_level_name: str) -> bool:
    """Check whether a top-level module name belongs to the stdlib."""
    # Try the canonical set first (Python 3.10+).
    if hasattr(sys, "stdlib_module_names"):
        return top_level_name in sys.stdlib_module_names
    return top_level_name in _STDLIB_TOP_LEVEL


def discover_python_files(root: Path) -> list[Path]:
    """Find all .py files under *root*, excluding common non-source dirs."""
    exclude = {".git", ".tox", ".venv", "venv", "__pycache__", "node_modules",
               ".eggs", "build", "dist"}
    results: list[Path] = []
    if root.is_file():
        if root.suffix == ".py":
            return [root]
        return []
    for p in sorted(root.rglob("*.py")):
        parts = set(p.relative_to(root).parts)
        if parts & exclude:
            continue
        # Skip egg-info directories (glob pattern matching).
        if any(part.endswith(".egg-info") for part in p.relative_to(root).parts):
            continue
        results.append(p)
    return results


def _resolve_relative_import(
    source_file: Path, project_root: Path, level: int, module: str | None
) -> str | None:
    """Resolve a relative import to a dotted module path within the project.

    Returns None if resolution fails (e.g. goes above the project root).
    """
    # Start from the package containing source_file.
    try:
        rel = source_file.relative_to(project_root)
    except ValueError:
        return None

    parts = list(rel.parts[:-1])  # directory components (package path)

    # Go up *level* packages.
    if level > len(parts):
        return None
    base_parts = parts[: len(parts) - level + 1] if level <= len(parts) else []
    if level > 0:
        base_parts = parts[: len(parts) - level]
        # For level=1 inside a package, base_parts is the parent package.
        # For level=2, we go two levels up, etc.

    dotted = ".".join(base_parts)
    if module:
        return f"{dotted}.{module}" if dotted else module
    return dotted or None


def analyze_file(
    filepath: Path, project_root: Path, project_packages: set[str]
) -> dict:
    """Parse a single Python file and extract import information."""
    result: dict = {
        "file": str(filepath.relative_to(project_root)),
        "imports": [],
        "all_declaration": None,
        "is_init": filepath.name == "__init__.py",
        "parse_error": None,
    }

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        result["parse_error"] = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        return result

    # Detect TYPE_CHECKING guard ranges.
    type_checking_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            is_tc = False
            if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                is_tc = True
            elif isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                is_tc = True
            if is_tc:
                start = node.body[0].lineno if node.body else node.lineno
                end = max(
                    (getattr(n, "end_lineno", None) or getattr(n, "lineno", start))
                    for n in node.body
                )
                type_checking_ranges.append((start, end))

    def _in_type_checking(lineno: int) -> bool:
        return any(s <= lineno <= e for s, e in type_checking_ranges)

    # Detect try/except ImportError blocks (conditional imports).
    conditional_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.type is None:
                    continue
                names: list[str] = []
                if isinstance(handler.type, ast.Name):
                    names = [handler.type.id]
                elif isinstance(handler.type, ast.Tuple):
                    names = [
                        e.id for e in handler.type.elts if isinstance(e, ast.Name)
                    ]
                if any(n in ("ImportError", "ModuleNotFoundError") for n in names):
                    start = node.body[0].lineno if node.body else node.lineno
                    end = node.end_lineno or node.lineno
                    conditional_ranges.append((start, end))

    def _is_conditional(lineno: int) -> bool:
        return any(s <= lineno <= e for s, e in conditional_ranges)

    # Extract __all__.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        ):
            if isinstance(node.value, (ast.List, ast.Tuple)):
                result["all_declaration"] = [
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]

    # Extract imports.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                category = "stdlib" if _is_stdlib(top) else (
                    "internal" if top in project_packages else "external"
                )
                result["imports"].append({
                    "module": alias.name,
                    "names": None,
                    "alias": alias.asname,
                    "top_level": top,
                    "category": category,
                    "line": node.lineno,
                    "is_relative": False,
                    "relative_level": 0,
                    "type_checking_only": _in_type_checking(node.lineno),
                    "conditional": _is_conditional(node.lineno),
                })
        elif isinstance(node, ast.ImportFrom):
            names_imported = [
                {"name": a.name, "alias": a.asname} for a in node.names
            ]
            level = node.level or 0
            module_str = node.module or ""
            is_relative = level > 0

            if is_relative:
                resolved = _resolve_relative_import(
                    filepath, project_root, level, node.module
                )
                top = resolved.split(".")[0] if resolved else None
                category = "internal"
            else:
                top = module_str.split(".")[0] if module_str else None
                category = "stdlib" if (top and _is_stdlib(top)) else (
                    "internal" if top in project_packages else "external"
                )

            result["imports"].append({
                "module": module_str,
                "names": names_imported,
                "alias": None,
                "top_level": top,
                "category": category,
                "line": node.lineno,
                "is_relative": is_relative,
                "relative_level": level,
                "resolved_module": (
                    _resolve_relative_import(filepath, project_root, level, node.module)
                    if is_relative else None
                ),
                "type_checking_only": _in_type_checking(node.lineno),
                "conditional": _is_conditional(node.lineno),
            })

    return result


def find_project_root(start: Path) -> Path:
    """Walk upward to find project root (dir with pyproject.toml, setup.cfg, .git)."""
    markers = {"pyproject.toml", "setup.cfg", "setup.py", ".git"}
    current = start if start.is_dir() else start.parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return start if start.is_dir() else start.parent


def identify_project_packages(root: Path) -> set[str]:
    """Identify top-level Python packages in the project."""
    packages: set[str] = set()
    # Look for directories with __init__.py.
    for item in root.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            if item.name not in {"test", "tests", ".git", "__pycache__"}:
                packages.add(item.name)
        # Also consider top-level .py files as modules.
        if item.is_file() and item.suffix == ".py" and item.name != "setup.py":
            packages.add(item.stem)
    # Check src/ layout.
    src = root / "src"
    if src.is_dir():
        for item in src.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                packages.add(item.name)
    return packages


def build_internal_graph(
    file_analyses: list[dict],
) -> dict[str, list[dict]]:
    """Build a graph of internal module dependencies."""
    graph: dict[str, list[dict]] = {}
    for fa in file_analyses:
        source = fa["file"]
        edges: list[dict] = []
        for imp in fa["imports"]:
            if imp["category"] != "internal":
                continue
            target_module = imp.get("resolved_module") or imp["module"]
            edges.append({
                "target": target_module,
                "names": imp.get("names"),
                "line": imp["line"],
                "type_checking_only": imp["type_checking_only"],
                "conditional": imp["conditional"],
            })
        if edges:
            graph[source] = edges
    return graph


def compute_metrics(graph: dict[str, list[dict]], all_files: list[str]) -> dict:
    """Compute fan-in and fan-out per file."""
    fan_out: dict[str, int] = {}
    fan_in: dict[str, int] = {}

    for f in all_files:
        fan_out[f] = 0
        fan_in[f] = 0

    for source, edges in graph.items():
        targets = {e["target"] for e in edges}
        fan_out[source] = len(targets)
        for t in targets:
            # Fan-in: find files that match this target module path.
            for f in all_files:
                # Rough match: does the file path correspond to the target?
                f_module = f.replace("/", ".").replace("\\", ".")
                if f_module.endswith(".py"):
                    f_module = f_module[:-3]
                if f_module.endswith(".__init__"):
                    f_module = f_module[:-9]
                if f_module == t or t.startswith(f_module + "."):
                    fan_in[f] = fan_in.get(f, 0) + 1

    return {
        "fan_out": dict(sorted(fan_out.items(), key=lambda x: -x[1])),
        "fan_in": dict(sorted(fan_in.items(), key=lambda x: -x[1])),
    }


def detect_cycles(graph: dict[str, list[dict]]) -> list[list[str]]:
    """Detect circular dependencies using DFS.

    Normalises targets to file paths so that cycles between files can be
    detected even when the graph edges use dotted module names.
    """
    # Build a simplified adjacency list: file -> set of target module strings.
    adj: dict[str, set[str]] = {}
    for source, edges in graph.items():
        adj[source] = {e["target"] for e in edges}

    # Collect all known file-stem identifiers so we can map dotted targets
    # back to concrete files.
    file_to_module: dict[str, str] = {}
    module_to_file: dict[str, str] = {}
    for f in adj:
        mod = f.replace("/", ".").replace("\\", ".")
        if mod.endswith(".py"):
            mod = mod[:-3]
        if mod.endswith(".__init__"):
            mod = mod[:-9]
        file_to_module[f] = mod
        module_to_file[mod] = f

    # Resolve adjacency to file-level.
    file_adj: dict[str, set[str]] = {}
    for f, targets in adj.items():
        resolved: set[str] = set()
        for t in targets:
            if t in module_to_file:
                resolved.add(module_to_file[t])
            else:
                # Try prefix match.
                for mod, mf in module_to_file.items():
                    if t.startswith(mod + ".") or mod.startswith(t + "."):
                        resolved.add(mf)
        resolved.discard(f)  # ignore self-imports
        file_adj[f] = resolved

    # Standard cycle detection with DFS.
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {f: WHITE for f in file_adj}
    parent: dict[str, str | None] = {f: None for f in file_adj}
    cycles: list[list[str]] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in file_adj.get(u, set()):
            if v not in color:
                color[v] = WHITE
            if color[v] == GRAY:
                # Found a cycle — reconstruct it.
                cycle = [v, u]
                node = u
                while node != v and parent.get(node) is not None:
                    node = parent[node]  # type: ignore[assignment]
                    cycle.append(node)
                cycle.reverse()
                # Normalise: start from the lexicographically smallest element.
                min_idx = cycle.index(min(cycle))
                cycle = cycle[min_idx:] + cycle[:min_idx]
                if cycle not in cycles:
                    cycles.append(cycle)
            elif color[v] == WHITE:
                parent[v] = u
                dfs(v)
        color[u] = BLACK

    for f in file_adj:
        if color.get(f, WHITE) == WHITE:
            dfs(f)

    return cycles


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target = target.resolve()

    project_root = find_project_root(target)
    project_packages = identify_project_packages(project_root)

    scan_root = target if target.is_dir() else project_root
    files = discover_python_files(scan_root)

    file_analyses = [analyze_file(f, project_root, project_packages) for f in files]

    all_file_paths = [fa["file"] for fa in file_analyses]
    internal_graph = build_internal_graph(file_analyses)
    metrics = compute_metrics(internal_graph, all_file_paths)
    cycles = detect_cycles(internal_graph)

    # Collect external dependencies.
    external: dict[str, list[str]] = {}
    for fa in file_analyses:
        for imp in fa["imports"]:
            if imp["category"] == "external" and imp["top_level"]:
                external.setdefault(imp["top_level"], []).append(fa["file"])

    # Collect re-exports.
    re_exports: list[dict] = []
    for fa in file_analyses:
        if fa["is_init"] and fa["all_declaration"] is not None:
            re_exports.append({
                "file": fa["file"],
                "all": fa["all_declaration"],
            })
        elif fa["is_init"]:
            # __init__.py without __all__ — list what it imports.
            init_imports = [
                imp["module"] or (imp.get("resolved_module") or "")
                for imp in fa["imports"]
                if imp["category"] == "internal"
            ]
            if init_imports:
                re_exports.append({
                    "file": fa["file"],
                    "all": None,
                    "re_imported_modules": init_imports,
                })

    output = {
        "project_root": str(project_root),
        "scan_root": str(scan_root),
        "project_packages": sorted(project_packages),
        "file_count": len(file_analyses),
        "files": file_analyses,
        "internal_graph": internal_graph,
        "external_dependencies": {
            k: sorted(set(v)) for k, v in sorted(external.items())
        },
        "metrics": metrics,
        "cycles": cycles,
        "re_exports": re_exports,
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
