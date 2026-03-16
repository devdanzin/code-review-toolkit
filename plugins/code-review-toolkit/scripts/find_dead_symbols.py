#!/usr/bin/env python3
"""Find dead code: unused imports, unreferenced functions, and orphan files.

Uses AST analysis to build a reference graph and identify symbols that are
defined but never used. Accounts for dynamic dispatch, __all__, magic methods,
test discovery, and entry points.

Usage:
    python find_dead_symbols.py [path]
"""

import ast
import json
import re
import sys
from collections.abc import Generator
from pathlib import Path


def discover_python_files(root: Path) -> Generator[Path, None, None]:
    """Yield .py files under *root*, excluding common non-source dirs."""
    exclude = {".git", ".tox", ".venv", "venv", "__pycache__",
               "node_modules", ".eggs", "build", "dist"}
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for p in sorted(root.rglob("*.py")):
        parts = set(p.relative_to(root).parts)
        if parts & exclude:
            continue
        if any(
            part.endswith(".egg-info")
            for part in p.relative_to(root).parts
        ):
            continue
        yield p


def find_project_root(start: Path) -> Path:
    markers = {"pyproject.toml", "setup.cfg", "setup.py", ".git"}
    current = start if start.is_dir() else start.parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return start if start.is_dir() else start.parent


# Magic methods that are called implicitly by Python.
_MAGIC_METHODS = frozenset({
    "__init__", "__new__", "__del__", "__repr__", "__str__", "__bytes__",
    "__format__", "__lt__", "__le__", "__eq__", "__ne__", "__gt__", "__ge__",
    "__hash__", "__bool__", "__getattr__", "__getattribute__", "__setattr__",
    "__delattr__", "__dir__", "__get__", "__set__", "__delete__",
    "__set_name__", "__init_subclass__", "__class_getitem__",
    "__call__", "__len__", "__length_hint__", "__getitem__", "__setitem__",
    "__delitem__", "__missing__", "__iter__", "__next__", "__reversed__",
    "__contains__", "__add__", "__radd__", "__iadd__", "__sub__", "__rsub__",
    "__isub__", "__mul__", "__rmul__", "__imul__", "__matmul__", "__rmatmul__",
    "__imatmul__", "__truediv__", "__rtruediv__", "__itruediv__",
    "__floordiv__", "__rfloordiv__", "__ifloordiv__", "__mod__", "__rmod__",
    "__imod__", "__divmod__", "__rdivmod__", "__pow__", "__rpow__",
    "__ipow__", "__lshift__", "__rlshift__", "__ilshift__", "__rshift__",
    "__rrshift__", "__irshift__", "__and__", "__rand__", "__iand__",
    "__xor__", "__rxor__", "__ixor__", "__or__", "__ror__", "__ior__",
    "__neg__", "__pos__", "__abs__", "__invert__", "__complex__",
    "__int__", "__float__", "__index__", "__round__", "__trunc__",
    "__floor__", "__ceil__", "__enter__", "__exit__", "__aenter__",
    "__aexit__", "__aiter__", "__anext__", "__await__",
    "__fspath__", "__copy__", "__deepcopy__", "__reduce__", "__reduce_ex__",
    "__getnewargs__", "__getnewargs_ex__", "__getstate__", "__setstate__",
    "__post_init__",
})


def analyze_file(filepath: Path, project_root: Path) -> dict:
    """Analyze a file for defined symbols and their usage."""
    rel = str(filepath.relative_to(project_root))
    result: dict = {
        "file": rel,
        "imports": [],
        "defined_symbols": [],
        "referenced_names": set(),
        "all_declaration": None,
        "is_init": filepath.name == "__init__.py",
        "is_test": (
            filepath.name.startswith("test_")
            or filepath.name.endswith("_test.py")
            or "test" in filepath.relative_to(project_root).parts[:-1]
            or "tests" in filepath.relative_to(project_root).parts[:-1]
        ),
        "has_main_guard": False,
        "parse_error": None,
    }

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        result["parse_error"] = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        return result

    # Check for __all__.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            result["all_declaration"] = [
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]

    # Check for if __name__ == "__main__" guard.
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
            ):
                result["has_main_guard"] = True

    # Collect imports (what names are imported).
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".")[0]
                result["imports"].append({
                    "local_name": local_name,
                    "module": alias.name,
                    "line": node.lineno,
                    "is_from": False,
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                result["imports"].append({
                    "local_name": local_name,
                    "module": f"{node.module or ''}.{alias.name}",
                    "line": node.lineno,
                    "is_from": True,
                })

    # Collect defined symbols (top-level and class-level).
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["defined_symbols"].append({
                "name": node.name,
                "type": "function",
                "line": node.lineno,
                "is_public": not node.name.startswith("_"),
                "is_test_method": node.name.startswith("test"),
                "is_magic": node.name in _MAGIC_METHODS,
            })
        elif isinstance(node, ast.ClassDef):
            result["defined_symbols"].append({
                "name": node.name,
                "type": "class",
                "line": node.lineno,
                "is_public": not node.name.startswith("_"),
            })
            # Class methods.
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result["defined_symbols"].append({
                        "name": f"{node.name}.{child.name}",
                        "type": "method",
                        "line": child.lineno,
                        "is_public": not child.name.startswith("_"),
                        "is_test_method": child.name.startswith("test"),
                        "is_magic": child.name in _MAGIC_METHODS,
                        "class": node.name,
                    })

    # Collect all referenced names (everything used, not just defined).
    class _NameCollector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.names: set[str] = set()

        def visit_Name(self, node: ast.Name) -> None:
            self.names.add(node.id)
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            self.names.add(node.attr)
            self.generic_visit(node)

    collector = _NameCollector()
    collector.visit(tree)
    result["referenced_names"] = collector.names

    return result


def find_unused_imports(file_analysis: dict) -> list[dict]:
    """Find imports whose local names are never referenced in the file."""
    unused = []
    refs = file_analysis["referenced_names"]
    all_decl = file_analysis["all_declaration"]

    for imp in file_analysis["imports"]:
        local_name = imp["local_name"]
        # Check if name is used in the file body.
        if local_name in refs:
            continue
        # Check if it's in __all__ (re-export).
        if all_decl and local_name in all_decl:
            continue
        # In __init__.py, imports may be re-exports even without __all__.
        if file_analysis["is_init"]:
            continue

        unused.append({
            "file": file_analysis["file"],
            "line": imp["line"],
            "name": local_name,
            "module": imp["module"],
            "confidence": "high",
        })

    return unused


def find_unreferenced_symbols(
    all_files: list[dict],
) -> list[dict]:
    """Find functions/classes that are defined but never referenced anywhere."""
    # Build a set of all names referenced across all files.
    global_refs: set[str] = set()
    for fa in all_files:
        global_refs |= fa["referenced_names"]

    # Also collect all imported names to mark as "referenced".
    for fa in all_files:
        for imp in fa["imports"]:
            # The target name being imported counts as a reference.
            if imp["is_from"]:
                # from X import Y — Y is referenced.
                parts = imp["module"].rsplit(".", 1)
                if len(parts) > 1:
                    global_refs.add(parts[1])

    unreferenced = []
    for fa in all_files:
        all_decl = fa["all_declaration"]
        for sym in fa["defined_symbols"]:
            name = sym["name"]
            bare_name = name.split(".")[-1]  # For methods, just the method name.

            # Skip magic methods — called implicitly.
            if sym.get("is_magic"):
                continue
            # Skip test methods — called by test runner.
            if sym.get("is_test_method"):
                continue
            # Skip if in __all__.
            if all_decl and bare_name in all_decl:
                continue
            # Skip setUp/tearDown/setUpClass/tearDownClass.
            if bare_name in (
                "setUp", "tearDown", "setUpClass", "tearDownClass",
                "setUpModule", "tearDownModule",
            ):
                continue
            # Skip if it's a method — we only flag unreferenced top-level
            # functions and classes (method-level is too noisy).
            if sym["type"] == "method":
                continue
            # Skip if the file has a __main__ guard and this could be an entry point.
            if fa["has_main_guard"] and sym["type"] == "function":
                continue

            # Check if name appears anywhere in the codebase.
            if bare_name not in global_refs:
                confidence = "high"
                # Lower confidence if the name looks like it could be
                # dynamically dispatched.
                if sym["type"] == "class" and sym["is_public"]:
                    confidence = "medium"  # Classes may be instantiated dynamically.

                unreferenced.append({
                    "file": fa["file"],
                    "line": sym["line"],
                    "name": name,
                    "type": sym["type"],
                    "is_public": sym.get("is_public", False),
                    "confidence": confidence,
                })

    return unreferenced


def find_orphan_files(
    all_files: list[dict], project_root: Path
) -> list[dict]:
    """Find Python files that are never imported by any other file."""
    # Collect all modules that are imported from.
    imported_modules: set[str] = set()
    for fa in all_files:
        for imp in fa["imports"]:
            imported_modules.add(imp["module"])
            # Add partial paths.
            parts = imp["module"].split(".")
            for i in range(1, len(parts) + 1):
                imported_modules.add(".".join(parts[:i]))

    orphans = []
    for fa in all_files:
        rel = fa["file"]
        # Convert file path to module path.
        mod = rel.replace("/", ".").replace("\\", ".")
        if mod.endswith(".py"):
            mod = mod[:-3]
        if mod.endswith(".__init__"):
            mod = mod[:-9]

        # Skip files that are likely entry points.
        if fa["has_main_guard"]:
            continue
        if fa["is_test"]:
            continue  # Test files are run by test runners.
        if rel.endswith("__init__.py"):
            continue  # __init__.py files are imported with the package.
        if rel in ("setup.py", "conftest.py"):
            continue

        # Check if any variant of this module is imported.
        is_imported = any(
            mod == m or mod.endswith("." + m) or m.endswith("." + mod)
            or m.startswith(mod + ".")
            for m in imported_modules
        )

        if not is_imported:
            orphans.append({
                "file": rel,
                "module": mod,
                "confidence": "medium",  # Could be entry point or dynamic.
            })

    return orphans


def find_commented_code(filepath: Path, project_root: Path) -> list[dict]:
    """Find blocks of commented-out code (not documentation comments)."""
    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    rel = str(filepath.relative_to(project_root))
    blocks: list[dict] = []

    # Heuristic: consecutive comment lines that look like code.
    _CODE_PATTERNS = re.compile(
        r"^#\s*(def |class |import |from |if |for |while |return |raise |"
        r"try:|except |with |yield |assert |self\.|print\(|"
        r"\w+\s*=\s*|^\s*#\s*\w+\()"
    )

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if _CODE_PATTERNS.match(line):
            # Start of a potential commented-out code block.
            block_start = i + 1
            block_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith("#") and len(next_line) > 1:
                    block_lines.append(next_line)
                    j += 1
                else:
                    break
            if len(block_lines) >= 3:  # At least 3 consecutive lines.
                blocks.append({
                    "file": rel,
                    "line_start": block_start,
                    "line_end": block_start + len(block_lines) - 1,
                    "line_count": len(block_lines),
                    "preview": block_lines[0][:80],
                })
            i = j
        else:
            i += 1

    return blocks


def main() -> None:
    max_files = 0  # 0 = no limit
    positional: list[str] = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--max-files" and i + 1 < len(argv):
            max_files = int(argv[i + 1])
            i += 2
        elif argv[i].startswith("--"):
            i += 1
        else:
            positional.append(argv[i])
            i += 1
    target = Path(positional[0]) if positional else Path(".")
    target = target.resolve()

    project_root = find_project_root(target)
    scan_root = target if target.is_dir() else project_root
    all_files = sorted(discover_python_files(scan_root))
    files_total = len(all_files)
    if max_files > 0 and files_total > max_files:
        all_files = all_files[:max_files]

    file_analyses = [analyze_file(f, project_root) for f in all_files]

    # Find issues (before converting sets to lists).
    unused_imports: list[dict] = []
    for fa in file_analyses:
        unused_imports.extend(find_unused_imports(fa))

    unreferenced = find_unreferenced_symbols(file_analyses)

    # Drop per-file referenced_names to free memory.
    for fa in file_analyses:
        fa.pop("referenced_names", None)

    orphans = find_orphan_files(file_analyses, project_root)

    commented_code: list[dict] = []
    for f in all_files:
        commented_code.extend(find_commented_code(f, project_root))

    # Summary.
    high_confidence = (
        [u for u in unused_imports if u["confidence"] == "high"]
        + [u for u in unreferenced if u["confidence"] == "high"]
    )
    medium_confidence = (
        [u for u in unused_imports if u["confidence"] == "medium"]
        + [u for u in unreferenced if u["confidence"] == "medium"]
        + orphans
    )

    output = {
        "project_root": str(project_root),
        "scan_root": str(scan_root),
        "files_total": files_total,
        "files_analyzed": len(all_files),
        "files_capped": max_files > 0 and files_total > max_files,
        "summary": {
            "unused_imports": len(unused_imports),
            "unreferenced_symbols": len(unreferenced),
            "orphan_files": len(orphans),
            "commented_code_blocks": len(commented_code),
            "high_confidence_items": len(high_confidence),
            "medium_confidence_items": len(medium_confidence),
        },
        "unused_imports": unused_imports,
        "unreferenced_symbols": unreferenced,
        "orphan_files": orphans,
        "commented_code_blocks": commented_code,
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
