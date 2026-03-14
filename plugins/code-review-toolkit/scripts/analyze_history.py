#!/usr/bin/env python3
"""Analyze git history for churn metrics, commit classification, and co-change data.

Queries git history and produces structured JSON with file/function churn,
commit classification, recent fixes/features/refactors, and co-change clusters.

Usage:
    python analyze_history.py [path] [options]

Options:
    --days N          Analyze last N days (default: 90)
    --since DATE      Start date (ISO format, overrides --days)
    --until DATE      End date (ISO format, default: today)
    --last N          Analyze exactly the last N commits (overrides time range)
    --max-commits N   Cap total commits analyzed (default: 2000)
    --no-function     Skip function-level churn (file-level only, faster)
"""

import ast
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Commit classification rules — first match wins.
CLASSIFICATION_RULES: list[tuple[str, list[str]]] = [
    ("fix", ["fix", "bug", "patch", "resolve", "issue", "crash",
             "error", "broken", "repair", "correct", "regression",
             "workaround", "hotfix"]),
    ("docs", ["doc", "readme", "comment", "typo", "spelling",
              "changelog", "documentation"]),
    ("test", ["test", "coverage", "assert", "mock", "fixture",
              "unittest", "pytest"]),
    ("refactor", ["refactor", "clean", "simplify", "reorganize",
                  "restructure", "rename", "move", "extract",
                  "deduplicate", "inline"]),
    ("chore", ["bump", "dependency", "update", "upgrade", "ci",
               "config", "lint", "format", "version", "release",
               "merge", "revert"]),
    ("feature", ["add", "implement", "new", "feature", "introduce",
                 "support", "enable", "create"]),
]

_GIT_TIMEOUT = 30
_SCRIPT_START: float = 0.0
_SCRIPT_TIMEOUT = 300  # 5 minutes
_MAX_DIFF_LINES_FIX = 150
_MAX_DIFF_LINES_REFACTOR = 80
_FUNCTION_COUNT_THRESHOLD = 500


def find_project_root(start: Path) -> Path:
    """Walk up to find the project root (directory containing .git)."""
    markers = {"pyproject.toml", "setup.cfg", "setup.py", ".git"}
    current = start if start.is_dir() else start.parent
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return start if start.is_dir() else start.parent


def classify_commit(message: str) -> str:
    """Classify a commit message using keyword matching. First match wins."""
    msg_lower = message.lower()
    for category, keywords in CLASSIFICATION_RULES:
        for keyword in keywords:
            if keyword in msg_lower:
                return category
    return "unknown"


def _run_git(
    args: list[str],
    cwd: Path,
    timeout: int = _GIT_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    """Run a git command with timeout handling."""
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=timeout,
    )


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = _run_git(["rev-parse", "--is-inside-work-tree"], path, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_script_timeout() -> bool:
    """Return True if the script has exceeded its timeout."""
    return (time.monotonic() - _SCRIPT_START) > _SCRIPT_TIMEOUT


def parse_git_log(
    project_root: Path,
    scan_root: Path,
    since: str,
    until: str,
    max_commits: int,
    last_n: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """Parse git log with numstat to get commits and per-file stats.

    Returns (commits, file_stats) where commits is a list of commit dicts
    and file_stats is accumulated per-file change data.
    """
    args = ["log", "--numstat", "--format=COMMIT:%H|%aI|%an|%s"]
    if last_n is not None:
        args.append(f"-{last_n}")
    else:
        args.extend([f"--since={since}", f"--until={until}"])
    args.append("--")
    rel = _relative_scope(scan_root, project_root)
    if rel != ".":
        args.append(rel)

    result = _run_git(args, project_root)
    if result.returncode != 0:
        return [], []

    commits: list[dict] = []
    file_changes: dict[str, dict] = {}
    current_commit: dict | None = None
    commit_count = 0

    for line in result.stdout.splitlines():
        if line.startswith("COMMIT:"):
            if current_commit is not None:
                commits.append(current_commit)
            commit_count += 1
            if commit_count > max_commits:
                break
            parts = line[7:].split("|", 3)
            if len(parts) < 4:
                current_commit = None
                continue
            commit_hash, date_str, author, message = parts
            current_commit = {
                "hash": commit_hash,
                "date": date_str,
                "author": author,
                "message": message,
                "type": classify_commit(message),
                "files": [],
                "stats": [],
            }
        elif line.strip() and current_commit is not None:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                added_str, removed_str, filepath = parts
                try:
                    added = int(added_str) if added_str != "-" else 0
                    removed = int(removed_str) if removed_str != "-" else 0
                except ValueError:
                    continue
                current_commit["files"].append(filepath)
                current_commit["stats"].append({
                    "file": filepath,
                    "added": added,
                    "removed": removed,
                })
                if filepath not in file_changes:
                    file_changes[filepath] = {
                        "commits": 0,
                        "lines_added": 0,
                        "lines_removed": 0,
                        "authors": set(),
                        "first_date": date_str,
                        "last_date": date_str,
                    }
                fc = file_changes[filepath]
                fc["commits"] += 1
                fc["lines_added"] += added
                fc["lines_removed"] += removed
                fc["authors"].add(author)
                # Track date range.
                if date_str < fc["first_date"]:
                    fc["first_date"] = date_str
                if date_str > fc["last_date"]:
                    fc["last_date"] = date_str

    if current_commit is not None and commit_count <= max_commits:
        commits.append(current_commit)

    # Build file_stats list.
    file_stats: list[dict] = []
    for filepath, fc in file_changes.items():
        line_count = _get_file_line_count(project_root / filepath)
        churn_rate = (
            round((fc["lines_added"] + fc["lines_removed"]) / line_count, 2)
            if line_count > 0
            else 0.0
        )
        file_stats.append({
            "file": filepath,
            "commits": fc["commits"],
            "lines_added": fc["lines_added"],
            "lines_removed": fc["lines_removed"],
            "churn_rate": churn_rate,
            "authors": len(fc["authors"]),
            "first_commit_in_range": fc["first_date"],
            "last_modified": fc["last_date"],
        })

    # Sort by commits descending.
    file_stats.sort(key=lambda x: x["commits"], reverse=True)
    return commits, file_stats


def _get_file_line_count(filepath: Path) -> int:
    """Count lines in a file, returning 0 if file doesn't exist."""
    try:
        return len(filepath.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _relative_scope(scan_root: Path, project_root: Path) -> str:
    """Get the relative path of scan_root from project_root."""
    try:
        rel = scan_root.resolve().relative_to(project_root.resolve())
        return str(rel) if str(rel) != "." else "."
    except ValueError:
        return "."


def get_function_boundaries(filepath: Path) -> list[dict]:
    """Parse a Python file with AST and return function/method boundaries."""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, OSError):
        return []

    functions: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", node.lineno)
            functions.append({
                "name": node.name,
                "line_start": node.lineno,
                "line_end": end_lineno,
            })
    return functions


def compute_function_churn_level2(
    commits: list[dict],
    scan_root: Path,
    project_root: Path,
) -> list[dict]:
    """Level 2: Map diff hunks to function boundaries using AST.

    Analyzes already-parsed commits to map file changes to functions.
    """
    # Build function boundaries for all Python files in scope.
    file_functions: dict[str, list[dict]] = {}
    if scan_root.is_file():
        py_files = [scan_root] if scan_root.suffix == ".py" else []
    else:
        py_files = sorted(scan_root.rglob("*.py"))

    exclude = {".git", ".tox", ".venv", "venv", "__pycache__",
               "node_modules", ".eggs", "build", "dist"}
    for pf in py_files:
        try:
            rel_parts = set(pf.relative_to(project_root).parts)
        except ValueError:
            continue
        if rel_parts & exclude:
            continue
        if any(part.endswith(".egg-info") for part in pf.relative_to(project_root).parts):
            continue
        rel_path = str(pf.relative_to(project_root))
        boundaries = get_function_boundaries(pf)
        if boundaries:
            file_functions[rel_path] = boundaries

    if not file_functions:
        return []

    # For each commit, get the diff and map hunks to functions.
    func_commits: dict[tuple[str, str], set[str]] = defaultdict(set)

    for commit in commits:
        if _check_script_timeout():
            break
        for file_path in commit["files"]:
            if file_path not in file_functions:
                continue
            try:
                diff_result = _run_git(
                    ["show", "--format=", "-U0", commit["hash"], "--", file_path],
                    project_root,
                )
                if diff_result.returncode != 0:
                    continue
            except subprocess.TimeoutExpired:
                continue

            # Parse diff hunks to find changed line ranges.
            changed_lines: set[int] = set()
            for line in diff_result.stdout.splitlines():
                hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
                if hunk_match:
                    start = int(hunk_match.group(1))
                    count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                    changed_lines.update(range(start, start + count))

            # Map changed lines to functions.
            for func in file_functions[file_path]:
                func_range = set(range(func["line_start"], func["line_end"] + 1))
                if changed_lines & func_range:
                    key = (file_path, func["name"])
                    func_commits[key].add(commit["hash"])

    # Build result.
    results: list[dict] = []
    for (file_path, func_name), commit_hashes in func_commits.items():
        # Find function boundaries in current version.
        boundaries = file_functions.get(file_path, [])
        func_info = next((f for f in boundaries if f["name"] == func_name), None)
        lines_changed = 0
        if func_info:
            lines_changed = func_info["line_end"] - func_info["line_start"] + 1
        results.append({
            "function": func_name,
            "file": file_path,
            "line_start": func_info["line_start"] if func_info else 0,
            "line_end": func_info["line_end"] if func_info else 0,
            "commits": len(commit_hashes),
            "lines_changed": lines_changed,
        })

    results.sort(key=lambda x: x["commits"], reverse=True)
    return results


def _truncate_diff(diff_text: str, max_lines: int) -> str:
    """Truncate a diff to max_lines, adding a notice if truncated."""
    lines = diff_text.splitlines()
    if len(lines) <= max_lines:
        return diff_text
    truncated = "\n".join(lines[:max_lines])
    return truncated + "\n[diff truncated, full diff available via git show HASH]"


def get_commit_details(
    commits: list[dict],
    commit_type: str,
    project_root: Path,
    scan_root: Path,
    max_diff_lines: int,
) -> list[dict]:
    """Get detailed info for commits of a specific type."""
    typed_commits = [c for c in commits if c["type"] == commit_type]
    results: list[dict] = []

    rel_scope = _relative_scope(scan_root, project_root)

    for commit in typed_commits:
        if _check_script_timeout():
            break
        # Get the diff.
        diff_args = ["show", "--format=", "--patch", commit["hash"], "--"]
        if rel_scope != ".":
            diff_args.append(rel_scope)
        try:
            diff_result = _run_git(diff_args, project_root)
            diff_text = diff_result.stdout if diff_result.returncode == 0 else ""
        except subprocess.TimeoutExpired:
            diff_text = "[diff unavailable: git show timed out]"

        diff_text = _truncate_diff(diff_text, max_diff_lines)

        # Map to functions if possible.
        functions_modified: list[dict] = []
        for file_path in commit["files"]:
            full_path = project_root / file_path
            if full_path.suffix == ".py" and full_path.exists():
                boundaries = get_function_boundaries(full_path)
                # Parse the diff to find which functions were modified.
                try:
                    func_diff = _run_git(
                        ["show", "--format=", "-U0", commit["hash"], "--", file_path],
                        project_root,
                    )
                    if func_diff.returncode == 0:
                        changed_lines: set[int] = set()
                        for line in func_diff.stdout.splitlines():
                            hunk = re.match(
                                r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line
                            )
                            if hunk:
                                start = int(hunk.group(1))
                                count = int(hunk.group(2)) if hunk.group(2) else 1
                                changed_lines.update(range(start, start + count))
                        for func in boundaries:
                            func_range = set(
                                range(func["line_start"], func["line_end"] + 1)
                            )
                            if changed_lines & func_range:
                                functions_modified.append({
                                    "function": func["name"],
                                    "file": file_path,
                                })
                except subprocess.TimeoutExpired:
                    pass

        results.append({
            "commit": commit["hash"],
            "commit_short": commit["hash"][:7],
            "message": commit["message"],
            "date": commit["date"],
            "author": commit["author"],
            "files": commit["files"],
            "functions_modified": functions_modified,
            "diff": diff_text,
        })

    return results


def compute_co_change_clusters(
    commits: list[dict],
    min_co_changes: int = 3,
    max_pairs: int = 30,
) -> list[dict]:
    """Detect file pairs that frequently change together."""
    # Count per-file commits.
    file_commit_counts: dict[str, int] = defaultdict(int)
    # Count co-occurrences.
    co_changes: dict[tuple[str, str], int] = defaultdict(int)

    for commit in commits:
        files = sorted(set(commit["files"]))
        for f in files:
            file_commit_counts[f] += 1
        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                pair = (files[i], files[j])
                co_changes[pair] += 1

    # Filter and sort.
    results: list[dict] = []
    for (file_a, file_b), count in co_changes.items():
        if count >= min_co_changes:
            results.append({
                "file_a": file_a,
                "file_b": file_b,
                "co_change_count": count,
                "total_commits_a": file_commit_counts[file_a],
                "total_commits_b": file_commit_counts[file_b],
            })

    results.sort(key=lambda x: x["co_change_count"], reverse=True)
    return results[:max_pairs]


def parse_args(argv: list[str]) -> dict:
    """Parse command-line arguments."""
    args: dict = {
        "path": ".",
        "days": 90,
        "since": None,
        "until": None,
        "last": None,
        "max_commits": 2000,
        "no_function": False,
    }

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--days" and i + 1 < len(argv):
            try:
                args["days"] = int(argv[i + 1])
            except ValueError:
                print(f"Error: --days requires an integer, got '{argv[i + 1]}'",
                      file=sys.stderr)
                sys.exit(2)
            i += 2
        elif arg == "--since" and i + 1 < len(argv):
            args["since"] = argv[i + 1]
            i += 2
        elif arg == "--until" and i + 1 < len(argv):
            args["until"] = argv[i + 1]
            i += 2
        elif arg == "--last" and i + 1 < len(argv):
            try:
                args["last"] = int(argv[i + 1])
            except ValueError:
                print(f"Error: --last requires an integer, got '{argv[i + 1]}'",
                      file=sys.stderr)
                sys.exit(2)
            i += 2
        elif arg == "--max-commits" and i + 1 < len(argv):
            try:
                args["max_commits"] = int(argv[i + 1])
            except ValueError:
                print(
                    f"Error: --max-commits requires an integer, got '{argv[i + 1]}'",
                    file=sys.stderr,
                )
                sys.exit(2)
            i += 2
        elif arg == "--no-function":
            args["no_function"] = True
            i += 1
        elif not arg.startswith("-"):
            args["path"] = arg
            i += 1
        else:
            print(f"Warning: unknown flag '{arg}', ignoring", file=sys.stderr)
            i += 1

    return args


def analyze(argv: list[str] | None = None) -> dict:
    """Main analysis function. Returns the result dict."""
    global _SCRIPT_START
    _SCRIPT_START = time.monotonic()

    if argv is None:
        argv = sys.argv[1:]
    args = parse_args(argv)

    scan_root = Path(args["path"]).resolve()
    project_root = find_project_root(scan_root)

    if not _is_git_repo(project_root):
        return {"error": "Not a git repository", "project_root": str(project_root)}

    # Determine time range.
    now = datetime.now(timezone.utc)
    if args["since"]:
        since = args["since"]
    else:
        since = (now - timedelta(days=args["days"])).isoformat()
    until = args["until"] if args["until"] else now.isoformat()

    last_n = args["last"]
    max_commits = args["max_commits"]

    # Parse git log.
    commits, file_churn = parse_git_log(
        project_root, scan_root, since, until, max_commits, last_n
    )

    # If using --last, derive time range from actual commits.
    commit_cap_applied = len(commits) >= max_commits
    if last_n is not None and commits:
        since = commits[-1]["date"]
        until = commits[0]["date"]
        # Calculate days.
        try:
            start_dt = datetime.fromisoformat(since)
            end_dt = datetime.fromisoformat(until)
            days = max(1, (end_dt - start_dt).days)
        except ValueError:
            days = args["days"]
    else:
        days = args["days"]

    # Classify commits.
    commits_by_type: dict[str, int] = defaultdict(int)
    authors: set[str] = set()
    for commit in commits:
        commits_by_type[commit["type"]] += 1
        authors.add(commit["author"])

    # Function-level churn.
    function_churn: list[dict] = []
    function_churn_note: str | None = None
    if args["no_function"] or _check_script_timeout():
        function_churn_note = (
            "Function-level churn skipped (--no-function flag or performance fallback)"
        )
    else:
        # Count total functions to decide strategy.
        function_churn = compute_function_churn_level2(
            commits, scan_root, project_root
        )
        if _check_script_timeout():
            function_churn_note = (
                "Function-level churn partially computed (script timeout)"
            )

    # Get recent fixes, features, refactors.
    recent_fixes = get_commit_details(
        commits, "fix", project_root, scan_root, _MAX_DIFF_LINES_FIX
    )
    recent_features = get_commit_details(
        commits, "feature", project_root, scan_root, _MAX_DIFF_LINES_FIX
    )
    recent_refactors = get_commit_details(
        commits, "refactor", project_root, scan_root, _MAX_DIFF_LINES_REFACTOR
    )

    # Co-change clusters.
    co_change_clusters = compute_co_change_clusters(commits)

    # Build result.
    result: dict = {
        "project_root": str(project_root),
        "scan_root": str(scan_root),
        "time_range": {
            "start": since,
            "end": until,
            "days": days,
            "commit_cap_applied": commit_cap_applied,
        },
        "summary": {
            "total_commits": len(commits),
            "commits_by_type": dict(commits_by_type),
            "files_changed": len(file_churn),
            "functions_changed": len(function_churn),
            "authors": len(authors),
        },
        "file_churn": file_churn,
        "function_churn": function_churn,
        "recent_fixes": recent_fixes,
        "recent_features": recent_features,
        "recent_refactors": recent_refactors,
        "co_change_clusters": co_change_clusters,
    }

    if function_churn_note:
        result["function_churn_note"] = function_churn_note

    return result


def main() -> None:
    """Entry point."""
    result = analyze()
    if "error" in result:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
