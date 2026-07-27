"""Tests for build_informed_briefing.py -- the informed-explore briefing."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import TempProject, import_script

mod = import_script("build_informed_briefing")


class TestCatalogLoading(unittest.TestCase):
    """The shipped data files load and are well-formed."""

    def test_shapes_load(self):
        shapes = mod._load_shapes()
        self.assertGreater(len(shapes), 0)

    def test_every_shape_has_required_fields(self):
        required = {
            "id",
            "title",
            "agent",
            "severity",
            "pattern",
            "guarded_twin",
            "hunt",
            "expected",
            "caught_as",
            "validation",
        }
        for shape in mod._load_shapes():
            self.assertTrue(
                required <= set(shape),
                f"{shape.get('id')} missing {required - set(shape)}",
            )

    def test_shape_ids_are_unique(self):
        ids = [s["id"] for s in mod._load_shapes()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_severities_are_valid(self):
        for shape in mod._load_shapes():
            self.assertIn(
                shape["severity"], {"FIX", "CONSIDER", "POLICY", "ACCEPTABLE"}
            )

    def test_fp_taxonomy_loads(self):
        self.assertIn("false-positive", mod._load_fp_taxonomy().lower())


class TestGrouping(unittest.TestCase):
    """Shapes group under their owning agent."""

    def test_groups_by_agent(self):
        grouped = mod._shapes_by_agent(
            [
                {"id": "a", "agent": "x"},
                {"id": "b", "agent": "x"},
                {"id": "c", "agent": "y"},
            ]
        )
        self.assertEqual(len(grouped["x"]), 2)
        self.assertEqual(len(grouped["y"]), 1)

    def test_missing_agent_becomes_unassigned(self):
        grouped = mod._shapes_by_agent([{"id": "a"}])
        self.assertIn("unassigned", grouped)


class TestBuildBriefing(unittest.TestCase):
    """The briefing includes rules, shapes, and the FP taxonomy."""

    def _shape(self, **over):
        base = {
            "id": "demo-shape",
            "title": "Demo",
            "agent": "silent-failure-hunter",
            "severity": "FIX",
            "pattern": "P",
            "guarded_twin": "T",
            "hunt": "H",
            "expected": "E",
            "caught_as": "C",
            "validation": "documented",
        }
        base.update(over)
        return base

    def test_includes_triage_rules(self):
        out = mod.build_briefing([], "", [])
        self.assertIn("Guarded twin", out)
        self.assertIn("Cite or drop", out)

    def test_includes_shape_fields(self):
        out = mod.build_briefing([self._shape()], "", [])
        for token in (
            "demo-shape",
            "Guarded twin (the fix)",
            "Sibling hunt",
            "Surfaces as",
        ):
            self.assertIn(token, out)

    def test_agent_filter_scopes_shapes(self):
        shapes = [self._shape(), self._shape(id="other", agent="dead-code-finder")]
        out = mod.build_briefing(shapes, "", [], agent="silent-failure-hunter")
        self.assertIn("demo-shape", out)
        self.assertNotIn("other", out)

    def test_unknown_agent_yields_empty_notice(self):
        out = mod.build_briefing([self._shape()], "", [], agent="nope")
        self.assertIn("No shapes catalogued", out)

    def test_differential_rendered_as_do_not_flag(self):
        out = mod.build_briefing(
            [self._shape(differential="only when mutated")], "", []
        )
        self.assertIn("Do NOT flag when", out)

    def test_confirmed_examples_rendered(self):
        out = mod.build_briefing(
            [self._shape(confirmed_examples=["PROJ-1 (a.py:1)"])], "", []
        )
        self.assertIn("PROJ-1", out)

    def test_fp_taxonomy_appended(self):
        out = mod.build_briefing([], "# T\nintro\n---\n### 1. Thing\nbody", [])
        self.assertIn("Known false positives", out)
        self.assertIn("Thing", out)

    def test_no_findings_section_without_memory(self):
        self.assertNotIn("Already established", mod.build_briefing([], "", []))


class TestProjectMemory(unittest.TestCase):
    """Prior-run findings are folded in as confirm-don't-relitigate entries."""

    MEMORY = {
        "findings": [
            {
                "id": "CRT-0001",
                "severity": "FIX",
                "title": "Mutable default",
                "location": "a.py:1",
                "status": "confirmed",
            },
            {
                "id": "CRT-0002",
                "severity": "FIX",
                "title": "Unproven idea",
                "location": "b.py:2",
                "status": "candidate",
            },
        ]
    }

    def test_loads_memory_file(self):
        with TempProject(
            {".code-review/findings.json": json.dumps(self.MEMORY)}
        ) as root:
            self.assertEqual(len(mod._load_project_findings(str(root))), 2)

    def test_only_confirmed_are_listed(self):
        out = mod.build_briefing([], "", self.MEMORY["findings"])
        self.assertIn("CRT-0001", out)
        self.assertNotIn("CRT-0002", out)
        self.assertIn("1 confirmed of 2 recorded", out)

    def test_missing_memory_is_empty(self):
        with TempProject({"mod.py": ""}) as root:
            self.assertEqual(mod._load_project_findings(str(root)), [])

    def test_malformed_memory_is_empty_not_fatal(self):
        with TempProject({".code-review/findings.json": "{not json"}) as root:
            self.assertEqual(mod._load_project_findings(str(root)), [])

    def test_bare_list_schema_accepted(self):
        payload = json.dumps([{"id": "X", "status": "confirmed", "title": "t"}])
        with TempProject({".code-review/findings.json": payload}) as root:
            self.assertEqual(len(mod._load_project_findings(str(root))), 1)

    def test_file_target_resolves_to_its_directory(self):
        with TempProject(
            {"pkg.py": "x=1", ".code-review/findings.json": json.dumps(self.MEMORY)}
        ) as root:
            found = mod._load_project_findings(str(root / "pkg.py"))
            self.assertEqual(len(found), 2)


class TestAnalyze(unittest.TestCase):
    """The analyze() entry point reports what went into the briefing."""

    def test_returns_counts_and_markdown(self):
        with TempProject({"m.py": ""}) as root:
            result = mod.analyze(str(root))
        self.assertGreater(result["shapes_total"], 0)
        self.assertTrue(result["has_fp_taxonomy"])
        self.assertIn("Informed-review briefing", result["briefing_markdown"])

    def test_agent_filter_reduces_included_count(self):
        with TempProject({"m.py": ""}) as root:
            everything = mod.analyze(str(root))
            scoped = mod.analyze(str(root), agent="silent-failure-hunter")
        self.assertLessEqual(scoped["shapes_included"], everything["shapes_total"])


class TestArgExtraction(unittest.TestCase):
    """--agent and --catalog are stripped before the shared arg parser sees argv."""

    def test_extracts_agent(self):
        rest, agent, catalog = mod._extract_flags(
            ["path", "--agent", "x", "--max-files", "5"]
        )
        self.assertEqual(agent, "x")
        self.assertIsNone(catalog)
        self.assertEqual(rest, ["path", "--max-files", "5"])

    def test_absent_flags_are_none(self):
        rest, agent, catalog = mod._extract_flags(["path"])
        self.assertIsNone(agent)
        self.assertIsNone(catalog)
        self.assertEqual(rest, ["path"])

    def test_extracts_catalog(self):
        rest, agent, catalog = mod._extract_flags(["p", "--catalog", "/some/where"])
        self.assertEqual(catalog, "/some/where")
        self.assertEqual(rest, ["p"])

    def test_catalog_dir_is_accepted_as_a_synonym(self):
        # The plan named the flag --catalog-dir; informed-explore.md documents
        # --catalog. Both work so neither document is wrong.
        _, _, catalog = mod._extract_flags(["p", "--catalog-dir", "/some/where"])
        self.assertEqual(catalog, "/some/where")


class TestExternalCatalog(unittest.TestCase):
    """--catalog folds an external findings repo into the briefing."""

    def _repo(self, root: Path) -> None:
        for project, fid, title in (
            ("coveragepy", "CRF-COVPY-0001", "A coverage finding"),
            ("cpython-idlelib", "CRF-IDLELIB-0001", "An idlelib finding"),
        ):
            path = root / project / "project-local"
            path.mkdir(parents=True)
            (path / "findings.json").write_text(
                json.dumps(
                    {
                        "project": project,
                        "findings": [
                            {
                                "id": fid,
                                "title": title,
                                "severity": "FIX",
                                "status": "reproduced",
                                "location": "mod.py:1",
                                "shape": "mutable-default-argument",
                            }
                        ],
                    }
                )
            )

    def test_repo_root_finds_every_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            findings, notes = mod._load_catalog_findings(str(root), "/x/coveragepy")
            self.assertEqual(len(findings), 2)
            self.assertEqual(len(notes), 2)

    def test_target_project_is_distinguished_from_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            findings, _ = mod._load_catalog_findings(str(root), "/src/coverage")
            mine = [f for f in findings if f["_is_target"]]
            self.assertEqual([f["_project"] for f in mine], ["coveragepy"])

    def test_a_single_project_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._repo(root)
            findings, notes = mod._load_catalog_findings(
                str(root / "coveragepy"), "/x/coveragepy"
            )
            self.assertEqual(len(findings), 1)

    def test_a_missing_catalog_is_reported_not_silently_empty(self):
        findings, notes = mod._load_catalog_findings("/no/such/path", "/x/y")
        self.assertEqual(findings, [])
        self.assertTrue(any("does not exist" in n for n in notes))

    def test_a_directory_with_no_findings_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings, notes = mod._load_catalog_findings(tmp, "/x/y")
            self.assertEqual(findings, [])
            self.assertTrue(any("no findings.json" in n for n in notes))

    def test_other_projects_are_narrowed_to_the_agent_shapes(self):
        theirs = [
            {"_is_target": False, "_project": "p", "id": "A", "shape": "mine"},
            {"_is_target": False, "_project": "p", "id": "B", "shape": "someone-elses"},
        ]
        rendered = "\n".join(mod._render_catalog_section(theirs, {"mine"}))
        self.assertIn("**A**", rendered)
        self.assertNotIn("**B**", rendered)
        # The dropped count must be stated, not silently omitted.
        self.assertIn("1 further cross-project finding(s) were omitted", rendered)

    def test_target_findings_are_never_narrowed_by_agent(self):
        mine = [{"_is_target": True, "_project": "p", "id": "A", "shape": "not-owned"}]
        rendered = "\n".join(mod._render_catalog_section(mine, {"something-else"}))
        self.assertIn("**A**", rendered)


if __name__ == "__main__":
    unittest.main()
