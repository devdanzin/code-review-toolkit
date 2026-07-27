#!/usr/bin/env python3
"""Measure how much of a findings repo maps to a catalogued bug shape.

This is Phase 0's success metric, and it decays silently: every finding written
with an ad-hoc shape name that never reaches the catalog drops the ratio, and
nothing else in the toolkit notices. Run it after any batch of new findings.

    python tools/shape_coverage.py ~/projects/code-review-findings

Baseline history:
    2026-07-26  catalog=40  used=64  stranded=43  covered=40/111  (36%)
    2026-07-27  catalog=89  used=71  stranded=0   covered=111/111 (100%)
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

_CATALOG = (
    Path(__file__).resolve().parent.parent
    / "plugins/code-review-toolkit/data/python_bug_shapes.json"
)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    findings_repo = Path(sys.argv[1]).expanduser()
    catalog = json.loads(_CATALOG.read_text(encoding="utf-8"))
    known = {s["id"] for s in catalog["shapes"]}
    aliases = {a for s in catalog["shapes"] for a in s.get("aliases", [])}

    used: dict[str, list[str]] = defaultdict(list)
    unshaped: list[str] = []
    for path in sorted(findings_repo.glob("*/project-local/findings.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for finding in data.get("findings", []):
            shape = finding.get("shape")
            if not shape:
                unshaped.append(finding.get("id", "?"))
            else:
                used[shape].append(finding.get("id", "?"))

    total = sum(len(v) for v in used.values()) + len(unshaped)
    covered = sum(len(v) for s, v in used.items() if s in known)
    stranded = {s: v for s, v in used.items() if s not in known}

    print(f"catalog shapes        {len(known)}")
    print(f"distinct shapes used  {len(used)}")
    print(f"stranded              {len(stranded)}")
    print(f"unshaped findings     {len(unshaped)}")
    pct = f"{covered / total:.0%}" if total else "n/a"
    print(f"covered               {covered}/{total}  ({pct})")

    for shape, ids in sorted(stranded.items(), key=lambda kv: -len(kv[1])):
        hint = " (an alias -- update the finding)" if shape in aliases else ""
        print(f"  STRANDED  {shape}{hint}: {', '.join(ids)}")
    for fid in unshaped:
        print(f"  UNSHAPED  {fid}")

    return 1 if stranded or unshaped else 0


if __name__ == "__main__":
    sys.exit(main())
