#!/usr/bin/env python3
"""Shared utilities for code-review-toolkit analysis scripts."""
from __future__ import annotations

import ast
from typing import Iterable


_SAFETY_KEYWORDS = frozenset({
    "safety:", "safe because", "intentional", "by design", "nolint",
    "checked:", "correct because", "this is safe", "not a bug",
    "deliberately", "expected", "noqa",
})


def extract_nearby_comments(source: str, line: int, radius: int = 5) -> list[str]:
    """Extract `#` comments within +/- radius of the 1-based line number.

    Pure-source scan (no AST): Python comments aren't in the AST, so we
    tokenize. Returns stripped comment text (without the `#`).
    """
    import tokenize, io
    comments: list[str] = []
    min_line = max(1, line - radius)
    max_line = line + radius
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT and min_line <= tok.start[0] <= max_line:
                text = tok.string.lstrip("#").strip()
                comments.append(text)
    except (tokenize.TokenizeError, IndentationError):
        # Fall back to line-based scan on broken input.
        lines = source.splitlines()
        for i in range(min_line - 1, min(max_line, len(lines))):
            stripped = lines[i].lstrip()
            if stripped.startswith("#"):
                comments.append(stripped[1:].strip())
    return comments


def has_safety_annotation(comments: Iterable[str]) -> bool:
    """Return True if any comment contains a safety-annotation keyword."""
    for comment in comments:
        lower = comment.lower()
        if any(kw in lower for kw in _SAFETY_KEYWORDS):
            return True
    return False


def make_finding(
    finding_type: str,
    *,
    file: str = "",
    line: int = 0,
    function: str = "",
    classification: str,
    severity: str,
    confidence: str = "high",
    detail: str,
    **extra,
) -> dict:
    """Create a finding dict with consistent key naming."""
    finding: dict = {
        "type": finding_type,
        "file": file,
        "line": line,
        "function": function,
        "classification": classification,
        "severity": severity,
        "confidence": confidence,
        "detail": detail,
    }
    finding.update(extra)
    return finding
