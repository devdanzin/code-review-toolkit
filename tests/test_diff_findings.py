"""Tests for diff_findings.py -- the false-positive regression gate."""

import json
import tempfile
import unittest
from pathlib import Path

from helpers import import_script

mod = import_script("diff_findings")


def _write(root: Path, script: str, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{script}.json").write_text(json.dumps(payload))


def _pitfalls(findings: list[dict]) -> dict:
    return {"project_root": "/p", "scan_root": "/p", "findings": findings}


def _finding(file: str, shape: str, line: int, message: str = "m") -> dict:
    return {
        "file": file,
        "shape": shape,
        "type": shape,
        "severity": "FIX",
        "confidence": "high",
        "line": line,
        "message": message,
    }


class TestDiff(unittest.TestCase):
    def _run(self, old: dict, new: dict, *extra: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "v1", Path(tmp) / "v2"
            _write(a, "scan_python_pitfalls", _pitfalls(old["findings"]))
            _write(b, "scan_python_pitfalls", _pitfalls(new["findings"]))
            return mod.analyze([str(a), str(b), *extra])

    def test_identical_runs_are_stable(self):
        f = [_finding("a.py", "s1", 10)]
        result = self._run({"findings": f}, {"findings": list(f)})
        self.assertEqual(result["summary"]["added"], 0)
        self.assertEqual(result["summary"]["gone"], 0)
        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertIn("stable", result["verdict"])

    def test_a_new_finding_is_added(self):
        result = self._run(
            {"findings": [_finding("a.py", "s1", 10)]},
            {"findings": [_finding("a.py", "s1", 10), _finding("b.py", "s2", 3)]},
        )
        self.assertEqual(result["summary"]["added"], 1)
        self.assertEqual(result["summary"]["gone"], 0)
        by = result["by_source"]["scan_python_pitfalls.findings"]
        self.assertEqual(by["added"][0]["file"], "b.py")

    def test_a_removed_finding_is_gone(self):
        result = self._run(
            {"findings": [_finding("a.py", "s1", 10), _finding("b.py", "s2", 3)]},
            {"findings": [_finding("a.py", "s1", 10)]},
        )
        self.assertEqual(result["summary"]["gone"], 1)
        self.assertEqual(result["summary"]["added"], 0)

    def test_a_shifted_line_is_moved_not_added_and_gone(self):
        # The whole point of keying without line numbers: inserting a line above
        # a finding must not read as one regression plus one fix.
        result = self._run(
            {"findings": [_finding("a.py", "s1", 10)]},
            {"findings": [_finding("a.py", "s1", 42)]},
        )
        self.assertEqual(result["summary"]["added"], 0)
        self.assertEqual(result["summary"]["gone"], 0)
        self.assertEqual(result["summary"]["moved"], 1)
        moved = result["by_source"]["scan_python_pitfalls.findings"]["moved"][0]
        self.assertEqual((moved["line_was"], moved["line"]), (10, 42))

    def test_duplicate_findings_are_counted_not_collapsed(self):
        # Two findings identical in every keyed field are still two findings;
        # losing one must show as `gone`.
        dup = [_finding("a.py", "s1", 10), _finding("a.py", "s1", 20)]
        result = self._run({"findings": dup}, {"findings": [dup[0]]})
        self.assertEqual(result["summary"]["gone"], 1)

    def test_severity_filter(self):
        low = {**_finding("b.py", "s2", 3), "severity": "CONSIDER"}
        result = self._run(
            {"findings": [_finding("a.py", "s1", 10)]},
            {"findings": [_finding("a.py", "s1", 10), low]},
            "--severity",
            "FIX",
        )
        self.assertEqual(result["summary"]["added"], 0)


class TestReportProblemsAreVisible(unittest.TestCase):
    """A report that could not be compared must never read as 'no change'."""

    def test_unparseable_report_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "v1", Path(tmp) / "v2"
            _write(a, "scan_python_pitfalls", _pitfalls([]))
            b.mkdir(parents=True)
            # Exactly the corruption seen in reports/coveragepy_v1: a warning
            # captured ahead of the JSON body.
            (b / "scan_python_pitfalls.json").write_text("ResourceWarning: oops\n{}")
            result = mod.analyze([str(a), str(b)])
            self.assertTrue(
                any("unparseable" in n for n in result["notes"]), result["notes"]
            )

    def test_missing_report_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "v1", Path(tmp) / "v2"
            _write(a, "scan_python_pitfalls", _pitfalls([_finding("a.py", "s", 1)]))
            b.mkdir(parents=True)
            result = mod.analyze([str(a), str(b)])
            self.assertTrue(any("missing" in n for n in result["notes"]))
            # And it must not be silently scored as a clean run.
            self.assertEqual(result["summary"]["gone"], 0)

    def test_unregistered_script_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "v1", Path(tmp) / "v2"
            for d in (a, b):
                _write(d, "correlate_tests", {"source_coverage": []})
            result = mod.analyze([str(a), str(b)])
            self.assertTrue(
                any("no finding lists registered" in n for n in result["notes"])
            )

    def test_missing_directory_is_an_error(self):
        result = mod.analyze(["/no/such/dir", "/also/not/here"])
        self.assertIn("error", result)

    def test_too_few_arguments_is_an_error(self):
        self.assertIn("error", mod.analyze(["only-one"]))


class TestSequenceFindings(unittest.TestCase):
    """Import cycles are lists, not dicts, and need their own key."""

    def test_cycles_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "v1", Path(tmp) / "v2"
            _write(a, "analyze_imports", {"cycles": [["x.py", "y.py"]]})
            _write(
                b,
                "analyze_imports",
                {"cycles": [["x.py", "y.py"], ["p.py", "q.py"]]},
            )
            result = mod.analyze([str(a), str(b)])
            by = result["by_source"]["analyze_imports.cycles"]
            self.assertEqual(len(by["added"]), 1)
            self.assertEqual(by["added"][0]["cycle"], ["p.py", "q.py"])
            self.assertEqual(by["unchanged"], 1)


class TestAgainstRealReports(unittest.TestCase):
    """The shipped idlelib benchmarks are the calibration this tool exists for."""

    def test_idlelib_v1_to_v2_reproduces_the_recorded_numbers(self):
        root = Path(__file__).resolve().parent.parent / "reports"
        v1, v2 = root / "idlelib_v1", root / "idlelib_v2"
        if not (v1.is_dir() and v2.is_dir()):
            self.skipTest("benchmark reports not present")
        result = mod.analyze([str(v1), str(v2)])
        by = result["by_source"]["scan_python_pitfalls.findings"]
        # docs/decision-log.md D-02: 100 -> 101, unchanged 100, gone 0, added 1.
        self.assertEqual((by["old_count"], by["new_count"]), (100, 101))
        self.assertEqual(len(by["added"]), 1)
        self.assertEqual(len(by["gone"]), 0)
        self.assertEqual(by["unchanged"], 100)


if __name__ == "__main__":
    unittest.main()
