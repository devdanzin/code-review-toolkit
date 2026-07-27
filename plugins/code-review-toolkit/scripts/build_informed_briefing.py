#!/usr/bin/env python3
"""Assemble the informed-explore briefing from the project-independent catalogs.

Emits a **Markdown briefing** (to stdout) that every agent in the
``informed-explore`` command reads before its own analysis. It seeds each agent
with

  (a) the bug-SHAPE catalog (``data/python_bug_shapes.json``) as sibling-hunt
      templates, scoped to the shapes that agent owns,
  (b) the false-positive taxonomy (``data/python_non_bugs.md``) to suppress, and
  (c) the cross-cutting triage rules (guarded-twin, systemic-root,
      behavioural-divergence-outranks-stylistic, silent-beats-loud).

These are project-INDEPENDENT shapes, so one briefing applies to any Python
codebase. If the target carries a per-project findings memory at
``<target>/.code-review/findings.json`` (confirmed findings accumulated by prior
runs), those are folded in as "confirm, don't re-litigate" entries so a re-run of
the same project is genuinely informed rather than cold.

That findings file uses the same schema as the ``project-local/findings.json`` in
the ``*-review-findings`` companion repositories, so a project's accumulated
memory can be lifted into a findings repo without transformation -- and, via
``--catalog``, read straight back out of one.

Usage:
    python build_informed_briefing.py [path] [--agent NAME] [--catalog PATH]
                                      [--max-files N]

``--catalog`` accepts any of three things, so it can point at whatever level of a
findings repo is convenient:

  * a ``findings.json`` file,
  * a project directory containing ``project-local/findings.json``, or
  * a findings-repo root containing ``*/project-local/findings.json``.

Entries whose project matches the target are folded in as "verify, then move on".
Entries from OTHER projects are folded in separately as cross-project evidence:
they are not claims about this codebase, they are shapes confirmed elsewhere that
are worth hunting here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scan_common import emit, parse_common_args  # noqa: E402

_DATA = Path(__file__).resolve().parent.parent / "data"

# Findings whose status means "already established -- confirm, don't re-derive".
_CONFIRMED_STATUS = {"confirmed", "reported", "fixed"}

# Where a reviewed project accumulates its own findings memory between runs.
_PROJECT_MEMORY = Path(".code-review") / "findings.json"


def _load_shapes() -> list[dict]:
    """Load the bug-shape catalog; empty list if the data file is absent."""
    try:
        with (_DATA / "python_bug_shapes.json").open(encoding="utf-8") as handle:
            return json.load(handle).get("shapes", [])
    except (OSError, json.JSONDecodeError):
        return []


def _load_fp_taxonomy() -> str:
    """Load the false-positive taxonomy markdown; empty string if absent."""
    try:
        return (_DATA / "python_non_bugs.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def _catalog_findings_files(catalog: Path) -> list[Path]:
    """Every findings.json reachable from *catalog*, whatever level it names."""
    if catalog.is_file():
        return [catalog]
    direct = catalog / "project-local" / "findings.json"
    if direct.is_file():
        return [direct]
    return sorted(catalog.glob("*/project-local/findings.json"))


def _load_catalog_findings(catalog: str, target: str) -> tuple[list[dict], list[str]]:
    """Load an external findings catalog, tagging each entry with its project.

    Returns ``(findings, notes)``; *notes* records what was read and what could
    not be, because a catalog path that silently resolves to nothing would make
    the briefing look complete while carrying none of the memory it promised.
    """
    root = Path(catalog).expanduser()
    if not root.exists():
        return [], [f"catalog path does not exist: {root}"]

    files = _catalog_findings_files(root)
    if not files:
        return [], [f"no findings.json found under {root}"]

    target_name = Path(target).expanduser().resolve().name
    findings: list[dict] = []
    notes: list[str] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            notes.append(f"unreadable: {path} ({type(exc).__name__})")
            continue
        project = data.get("project") or path.parent.parent.name
        entries = data.get("findings", []) if isinstance(data, dict) else data
        entries = [f for f in entries if isinstance(f, dict)]
        for finding in entries:
            finding = dict(finding)
            finding["_project"] = project
            # A catalog project matches the target when either name contains the
            # other: `coveragepy` vs `coverage`, `cpython-idlelib` vs `idlelib`.
            finding["_is_target"] = (
                target_name in project or project in target_name
            ) and bool(target_name)
            findings.append(finding)
        notes.append(f"{project}: {len(entries)} finding(s) from {path}")
    return findings, notes


def _load_project_findings(target: str) -> list[dict]:
    """Load a target project's accumulated findings memory, if any."""
    path = Path(target).resolve()
    if path.is_file():
        path = path.parent
    try:
        with (path / _PROJECT_MEMORY).open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        findings = data
    elif isinstance(data, dict):
        findings = data.get("findings", [])
    else:
        findings = []
    return [f for f in findings if isinstance(f, dict)]


def _shapes_by_agent(shapes: list[dict]) -> dict[str, list[dict]]:
    """Group shapes under the agent that owns them."""
    grouped: dict[str, list[dict]] = {}
    for shape in shapes:
        grouped.setdefault(shape.get("agent", "unassigned"), []).append(shape)
    return grouped


# How each `detectability` value changes what the reading agent has to do.
_DETECTABILITY_NOTE = {
    "implemented": "a scanner check emits candidates for this — triage them, don't re-derive",
    "implementable": "AST-decidable but NOT yet implemented — hunt it by hand this run",
    "agent-only": "no scanner will ever hand you this — the sibling hunt below IS the method",
}


def _render_shape(shape: dict) -> str:
    """Render one bug shape as a briefing entry."""
    detectability = shape.get("detectability")
    lines = [
        f"#### `{shape.get('id', '?')}` — {shape.get('title', '')}",
        "",
        f"- **Default severity:** {shape.get('severity', 'CONSIDER')} "
        f"(before triage) · **grounding:** {shape.get('validation', 'unknown')}",
    ]
    if detectability:
        note = _DETECTABILITY_NOTE.get(detectability, "")
        lines.append(
            f"- **How you find it:** {detectability}" + (f" — {note}" if note else "")
        )
    lines += [
        f"- **Pattern:** {shape.get('pattern', '')}",
        f"- **Guarded twin (the fix):** {shape.get('guarded_twin', '')}",
        f"- **Sibling hunt:** {shape.get('hunt', '')}",
        f"- **Expected behaviour:** {shape.get('expected', '')}",
        f"- **Surfaces as:** {shape.get('caught_as', '')}",
    ]
    if shape.get("differential"):
        lines.append(f"- **Do NOT flag when:** {shape['differential']}")
    confirmed = shape.get("confirmed_examples") or []
    if confirmed:
        lines.append("- **Confirmed instances:** " + "; ".join(confirmed))
    return "\n".join(lines)


TRIAGE_RULES = """\
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
"""


def _render_catalog_section(
    catalog_findings: list[dict], owned_shapes: set[str] | None = None
) -> list[str]:
    """Render an external findings catalog, split by whether it is this project.

    When *owned_shapes* is given (a per-agent run), the OTHER-projects list is
    narrowed to shapes this agent owns -- that list is speculative "worth hunting
    here" material, so an entry the agent could not act on is pure noise. The
    THIS-project list is never narrowed: it is the do-not-re-derive set, and
    dropping an entry from it invites exactly the re-derivation it prevents.
    """
    if not catalog_findings:
        return []

    def line(finding: dict, with_project: bool) -> str:
        loc = finding.get("location") or finding.get("file") or "?"
        prefix = f"[{finding['_project']}] " if with_project else ""
        shape = finding.get("shape")
        shape_ref = f" · shape `{shape}`" if shape else ""
        return (
            f"- {prefix}**{finding.get('id', '?')}** "
            f"[{finding.get('severity', '?')}] {finding.get('title', '')} — "
            f"`{loc}`{shape_ref}"
        )

    mine = [f for f in catalog_findings if f.get("_is_target")]
    theirs = [f for f in catalog_findings if not f.get("_is_target")]
    dropped = 0
    if owned_shapes is not None:
        kept = [f for f in theirs if f.get("shape") in owned_shapes]
        dropped = len(theirs) - len(kept)
        theirs = kept
    parts: list[str] = []

    if mine:
        parts += [
            f"## Already recorded for THIS project in the findings catalog ({len(mine)})",
            "",
            "These are settled. Verify each still exists, then move on — do not "
            "re-derive them, and do not report them as new.",
            "",
            *[line(f, with_project=False) for f in mine],
            "",
        ]
    if theirs:
        shapes_seen = sorted({f["shape"] for f in theirs if f.get("shape")})
        parts += [
            f"## Confirmed in OTHER projects ({len(theirs)}) — hunt them here",
            "",
            "These are **not** claims about this codebase. Each is a shape that "
            "was confirmed somewhere else, which makes it worth a targeted look "
            "here. A hit is a new finding for this project; a miss is not a "
            "finding at all, so do not report absence.",
            "",
            *[line(f, with_project=True) for f in theirs],
            "",
        ]
        if shapes_seen:
            parts += [
                "Shapes represented above, in catalog terms: "
                + ", ".join(f"`{s}`" for s in shapes_seen),
                "",
            ]
    # Report the denominator: a narrowed list must not read as the whole catalog.
    if dropped:
        parts += [
            f"_{dropped} further cross-project finding(s) were omitted here "
            f"because they belong to shapes another agent owns._",
            "",
        ]
    return parts


def build_briefing(
    shapes: list[dict],
    fp_taxonomy: str,
    project_findings: list[dict],
    agent: str | None = None,
    catalog_findings: list[dict] | None = None,
) -> str:
    """Assemble the full Markdown briefing."""
    grouped = _shapes_by_agent(shapes)
    if agent:
        grouped = {agent: grouped.get(agent, [])}

    parts: list[str] = [
        "# Informed-review briefing",
        "",
        "Read this before your own analysis. It exists so you **confirm without "
        "re-litigating**, **suppress known false positives**, and spend the run "
        "hunting un-found siblings of established shapes rather than "
        "rediscovering the basics from scratch.",
        "",
        "## Cross-cutting triage rules",
        "",
        TRIAGE_RULES,
    ]

    total = sum(len(v) for v in grouped.values())
    parts += [
        "## Bug-shape templates" + (f" for `{agent}`" if agent else "") + f" ({total})",
        "",
        "Each shape is a reusable *pattern*, not a location. For each one, hunt "
        "this codebase for instances, then follow the sibling-hunt directive to "
        "find the ones a cold pass would miss.",
        "",
    ]
    if not total:
        parts.append("_No shapes catalogued for this agent yet._\n")
    for owner, owned in sorted(grouped.items()):
        if not owned:
            continue
        if not agent:
            parts.append(f"### Owned by `{owner}`")
            parts.append("")
        for shape in owned:
            parts.append(_render_shape(shape))
            parts.append("")

    if project_findings:
        confirmed = [
            f
            for f in project_findings
            if str(f.get("status", "")).lower() in _CONFIRMED_STATUS
        ]
        parts += [
            "## Already established in this project "
            f"({len(confirmed)} confirmed of {len(project_findings)} recorded)",
            "",
            "From prior runs' accumulated memory (`.code-review/findings.json`). "
            "Verify these still exist, then move on — do not re-derive them.",
            "",
        ]
        for finding in confirmed:
            loc = finding.get("location") or finding.get("file") or "?"
            parts.append(
                f"- **{finding.get('id', '?')}** [{finding.get('severity', '?')}] "
                f"{finding.get('title', '')} — `{loc}`"
            )
        parts.append("")

    owned_shapes = (
        {s["id"] for owned in grouped.values() for s in owned} if agent else None
    )
    parts += _render_catalog_section(catalog_findings or [], owned_shapes)

    if fp_taxonomy:
        parts += [
            "## Known false positives — suppress these",
            "",
            "If a candidate matches one of these classes, dismiss it *with the "
            "stated reason* rather than reporting it. Each entry also states what "
            "the REAL bug looks like, so a genuine instance is never suppressed.",
            "",
            fp_taxonomy.split("---", 1)[-1].strip()
            if "---" in fp_taxonomy
            else fp_taxonomy.strip(),
            "",
        ]

    return "\n".join(parts) + "\n"


def analyze(
    target: str,
    *,
    max_files: int = 0,
    agent: str | None = None,
    catalog: str | None = None,
) -> dict:
    """Build the briefing for *target*. ``max_files`` is accepted for interface
    parity with the other scripts; this script does not walk the file tree."""
    shapes = _load_shapes()
    fp_taxonomy = _load_fp_taxonomy()
    project_findings = _load_project_findings(target)
    catalog_findings, catalog_notes = (
        _load_catalog_findings(catalog, target) if catalog else ([], [])
    )
    briefing = build_briefing(
        shapes, fp_taxonomy, project_findings, agent, catalog_findings
    )
    return {
        "target": target,
        "shapes_total": len(shapes),
        "shapes_included": (
            len(_shapes_by_agent(shapes).get(agent, [])) if agent else len(shapes)
        ),
        "project_findings": len(project_findings),
        "catalog": catalog,
        "catalog_findings": len(catalog_findings),
        "catalog_findings_this_project": sum(
            1 for f in catalog_findings if f.get("_is_target")
        ),
        "catalog_notes": catalog_notes,
        "has_fp_taxonomy": bool(fp_taxonomy),
        "briefing_markdown": briefing,
    }


def _extract_flags(argv: list[str]) -> tuple[list[str], str | None, str | None]:
    """Pull ``--agent NAME`` and ``--catalog PATH`` out of argv."""
    rest: list[str] = []
    agent: str | None = None
    catalog: str | None = None
    i = 0
    while i < len(argv):
        if argv[i] == "--agent" and i + 1 < len(argv):
            agent = argv[i + 1]
            i += 2
        elif argv[i] in ("--catalog", "--catalog-dir") and i + 1 < len(argv):
            catalog = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return rest, agent, catalog


def main() -> None:
    try:
        argv, agent, catalog = _extract_flags(sys.argv[1:])
        target, max_files = parse_common_args(argv)
        result = analyze(target, max_files=max_files, agent=agent, catalog=catalog)
        # Markdown, not JSON: the output IS the agent briefing. Catalog problems
        # go to stderr so a path that resolved to nothing is visible without
        # corrupting the briefing on stdout.
        for note in result["catalog_notes"]:
            print(f"catalog: {note}", file=sys.stderr)
        sys.stdout.write(result["briefing_markdown"])
    except Exception as exc:  # noqa: BLE001 -- top-level guard
        emit({"error": str(exc), "type": type(exc).__name__})
        sys.exit(1)


if __name__ == "__main__":
    main()
