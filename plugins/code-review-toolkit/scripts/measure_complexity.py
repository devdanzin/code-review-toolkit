#!/usr/bin/env python3
"""Measure per-function complexity metrics using AST analysis.

Outputs a JSON structure with per-function metrics:
- line_count (excluding blanks and comments)
- nesting_depth (maximum indentation level of control flow)
- parameter_count
- branch_count (if/elif/else/match-case/try-except branches)
- loop_count (for/while including nested)
- local_variable_count
- return_count (number of return statements)
- cognitive_complexity (weighted complexity score)

Usage:
    python measure_complexity.py [path]
"""

import ast
import json
import sys
from pathlib import Path


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
        if any(part.endswith(".egg-info") for part in p.relative_to(root).parts):
            continue
        results.append(p)
    return results


def find_project_root(start: Path) -> Path:
    """Walk upward to find project root."""
    markers = {"pyproject.toml", "setup.cfg", "setup.py", ".git"}
    current = start if start.is_dir() else start.parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return start if start.is_dir() else start.parent


class _NestingVisitor(ast.NodeVisitor):
    """Walk a function body tracking nesting depth of control flow."""

    def __init__(self) -> None:
        self.max_depth = 0
        self._depth = 0

    def _enter(self) -> None:
        self._depth += 1
        self.max_depth = max(self.max_depth, self._depth)

    def _exit(self) -> None:
        self._depth -= 1

    # Control flow nodes that increase nesting.
    def visit_If(self, node: ast.If) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_For(self, node: ast.For) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_While(self, node: ast.While) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_With(self, node: ast.With) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_Try(self, node: ast.Try) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_TryStar(self, node: ast.AST) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    def visit_Match(self, node: ast.AST) -> None:
        self._enter()
        self.generic_visit(node)
        self._exit()

    # Don't recurse into nested function/class definitions.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        pass

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        pass


class _CognitiveVisitor(ast.NodeVisitor):
    """Compute a cognitive complexity score.

    Increments for each control-flow break, with additional weight for nesting.
    Based on the SonarSource cognitive complexity specification (simplified).
    """

    def __init__(self) -> None:
        self.score = 0
        self._nesting = 0

    def _incr(self, nesting_penalty: bool = True) -> None:
        self.score += 1 + (self._nesting if nesting_penalty else 0)

    def visit_If(self, node: ast.If) -> None:
        self._incr()
        self._nesting += 1
        # Visit the body.
        for child in node.body:
            self.visit(child)
        self._nesting -= 1
        # elif / else: +1 each without nesting penalty.
        for child in node.orelse:
            if isinstance(child, ast.If):
                # elif
                self.score += 1  # no nesting penalty for elif
                self._nesting += 1
                for c in child.body:
                    self.visit(c)
                self._nesting -= 1
                # Continue with its orelse.
                for c in child.orelse:
                    if isinstance(c, ast.If):
                        self.visit_If(c)
                    else:
                        self.visit(c)
            else:
                self.score += 1  # else
                self.visit(child)

    def visit_For(self, node: ast.For) -> None:
        self._incr()
        self._nesting += 1
        self.generic_visit(node)
        self._nesting -= 1

    def visit_While(self, node: ast.While) -> None:
        self._incr()
        self._nesting += 1
        self.generic_visit(node)
        self._nesting -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self._incr()
        self._nesting += 1
        self.generic_visit(node)
        self._nesting -= 1

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Each boolean operator sequence adds 1.
        self.score += 1
        self.generic_visit(node)

    def visit_Break(self, node: ast.Break) -> None:
        self.score += 1

    def visit_Continue(self, node: ast.Continue) -> None:
        self.score += 1

    # Don't recurse into nested definitions.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        pass

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        pass


def _count_branches(func_node: ast.AST) -> int:
    """Count if/elif/else/match-case/except branches in a function body."""
    count = 0
    for node in ast.walk(func_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not func_node:
                continue
        if isinstance(node, ast.If):
            count += 1  # if
            if node.orelse:
                count += 1  # else or elif (each elif becomes another If)
        elif isinstance(node, ast.ExceptHandler):
            count += 1
        elif isinstance(node, ast.Match):
            count += len(getattr(node, "cases", []))

    return count


def _count_loops(func_node: ast.AST) -> int:
    """Count for/while loops (including nested)."""
    count = 0
    for node in ast.walk(func_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not func_node:
                continue
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            count += 1
    return count


def _count_returns(func_node: ast.AST) -> int:
    """Count return statements."""
    count = 0
    for node in ast.walk(func_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not func_node:
                continue
        if isinstance(node, ast.Return):
            count += 1
    return count


def _count_local_variables(func_node: ast.AST) -> int:
    """Count unique variable names assigned in the function body."""
    names: set[str] = set()
    for node in ast.walk(func_node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node is not func_node:
                continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names.add(elt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
            elif isinstance(node.target, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        names.add(elt.id)
    return len(names)


def _effective_line_count(source_lines: list[str]) -> int:
    """Count non-blank, non-comment lines."""
    count = 0
    in_docstring = False
    docstring_quote: str | None = None
    for line in source_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Handle multiline strings (rough heuristic).
        if in_docstring:
            if docstring_quote and docstring_quote in stripped:
                in_docstring = False
            continue

        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            # Single-line docstring.
            if stripped.count(quote) >= 2:
                continue
            in_docstring = True
            docstring_quote = quote
            continue

        if stripped.startswith("#"):
            continue

        count += 1
    return count


def _param_count(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count parameters excluding 'self' and 'cls'."""
    args = func_node.args
    count = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
    # Subtract self/cls.
    if args.args and args.args[0].arg in ("self", "cls"):
        count -= 1
    if args.vararg:
        count += 1
    if args.kwarg:
        count += 1
    return count


def _compute_score(metrics: dict) -> float:
    """Compute an overall complexity score (1-10) from individual metrics."""
    score = 1.0

    # Line count contribution (>50 is notable, >100 is high, >200 is critical).
    lc = metrics["line_count"]
    if lc > 200:
        score += 3.0
    elif lc > 100:
        score += 2.0
    elif lc > 50:
        score += 1.0

    # Nesting depth (>3 is notable, >5 is high).
    nd = metrics["nesting_depth"]
    if nd > 5:
        score += 2.5
    elif nd > 3:
        score += 1.5
    elif nd > 2:
        score += 0.5

    # Parameter count (>5 is notable, >8 is high).
    pc = metrics["parameter_count"]
    if pc > 8:
        score += 2.0
    elif pc > 5:
        score += 1.0

    # Cognitive complexity (>15 is notable, >30 is high, >50 is critical).
    cc = metrics["cognitive_complexity"]
    if cc > 50:
        score += 3.0
    elif cc > 30:
        score += 2.0
    elif cc > 15:
        score += 1.0

    # Branch count (>10 is notable).
    if metrics["branch_count"] > 10:
        score += 1.0

    # Local variables (>10 is notable).
    if metrics["local_variable_count"] > 10:
        score += 0.5

    return min(score, 10.0)


def analyze_file(filepath: Path, project_root: Path) -> dict:
    """Analyze all functions/methods in a file."""
    rel = str(filepath.relative_to(project_root))
    result: dict = {
        "file": rel,
        "functions": [],
        "parse_error": None,
    }

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as exc:
        result["parse_error"] = f"SyntaxError: {exc.msg} (line {exc.lineno})"
        return result

    source_lines = source.splitlines()

    def _process_func(
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str | None = None,
    ) -> dict:
        start = node.lineno
        end = node.end_lineno or node.lineno
        func_lines = source_lines[start - 1 : end]
        effective_lines = _effective_line_count(func_lines)

        nesting_v = _NestingVisitor()
        for child in ast.iter_child_nodes(node):
            nesting_v.visit(child)

        cognitive_v = _CognitiveVisitor()
        for child in ast.iter_child_nodes(node):
            cognitive_v.visit(child)

        name = f"{class_name}.{node.name}" if class_name else node.name

        metrics = {
            "line_count": effective_lines,
            "total_lines": end - start + 1,
            "nesting_depth": nesting_v.max_depth,
            "parameter_count": _param_count(node),
            "branch_count": _count_branches(node),
            "loop_count": _count_loops(node),
            "return_count": _count_returns(node),
            "local_variable_count": _count_local_variables(node),
            "cognitive_complexity": cognitive_v.score,
        }

        return {
            "name": name,
            "qualified_name": f"{rel}::{name}",
            "line_start": start,
            "line_end": end,
            "is_method": class_name is not None,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "is_test": node.name.startswith("test") or (
                class_name is not None and class_name.startswith("Test")
            ),
            "has_decorators": len(node.decorator_list) > 0,
            "decorator_count": len(node.decorator_list),
            "metrics": metrics,
            "score": round(_compute_score(metrics), 1),
        }

    # Walk top-level and class-level definitions.
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(_process_func(node))
        elif isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result["functions"].append(_process_func(child, node.name))

    return result


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    target = target.resolve()

    project_root = find_project_root(target)
    scan_root = target if target.is_dir() else project_root
    files = discover_python_files(scan_root)

    file_analyses = [analyze_file(f, project_root) for f in files]

    # Collect all functions and rank by score.
    all_functions = []
    for fa in file_analyses:
        for func in fa["functions"]:
            all_functions.append(func)

    all_functions.sort(key=lambda f: -f["score"])

    # Summary statistics.
    scores = [f["score"] for f in all_functions]
    source_funcs = [f for f in all_functions if not f["is_test"]]
    test_funcs = [f for f in all_functions if f["is_test"]]

    hotspots = [f for f in source_funcs if f["score"] >= 5.0]

    output = {
        "project_root": str(project_root),
        "scan_root": str(scan_root),
        "summary": {
            "total_functions": len(all_functions),
            "source_functions": len(source_funcs),
            "test_functions": len(test_funcs),
            "hotspots_score_5_plus": len(hotspots),
            "hotspots_score_8_plus": len([f for f in hotspots if f["score"] >= 8.0]),
            "avg_score_source": (
                round(sum(f["score"] for f in source_funcs) / len(source_funcs), 1)
                if source_funcs else 0
            ),
            "avg_cognitive_complexity_source": (
                round(
                    sum(f["metrics"]["cognitive_complexity"] for f in source_funcs)
                    / len(source_funcs),
                    1,
                )
                if source_funcs else 0
            ),
        },
        "hotspots": hotspots[:30],  # Top 30 hotspots.
        "files": file_analyses,
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
