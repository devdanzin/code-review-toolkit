"""Tests for check_typing.py -- mypy integrity, not mypy coverage."""

import unittest

from helpers import import_script

mod = import_script("check_typing")


class TestParseOutput(unittest.TestCase):
    def test_parses_an_error_with_a_code(self):
        findings, stats = mod.parse_output(
            'src/a.py:12:5: error: Item "None" has no attribute "x" '
            "[union-attr]\n"
            "Found 1 error in 1 file (checked 45 source files)\n"
        )
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual((f["file"], f["line"], f["column"]), ("src/a.py", 12, 5))
        self.assertEqual(f["code"], "union-attr")
        self.assertEqual(f["kind"], "defect")
        self.assertEqual(stats["files_checked"], 45)

    def test_ansi_coloured_output_still_parses(self):
        """mypy honours FORCE_COLOR even when piped, and the codes land between
        `file:line:` and `error:`. Before --no-color-output this parsed to ZERO
        findings while the summary line still read 3 -- a confident "0 type
        errors" on any machine with FORCE_COLOR set. Found on coverage.py, where
        it hid three real `no-any-unimported` errors."""
        coloured = (
            "coverage/html.py:134: \x1b[1m\x1b[31merror:\x1b(B\x1b[m Argument 2 to "
            '\x1b[1m"data_for_file"\x1b(B\x1b[m becomes \x1b[1m"Any"\x1b(B\x1b[m '
            "due to an unfollowed import  \x1b(B\x1b[33m[no-any-unimported]\x1b(B\x1b[m\n"
            "\x1b[1m\x1b[31mFound 1 error in 1 file (checked 45 source files)\x1b(B\x1b[m\n"
        )
        findings, stats = mod.parse_output(coloured)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "no-any-unimported")
        self.assertEqual(findings[0]["line"], 134)
        # The whole point: our count must agree with mypy's own.
        self.assertEqual(len(findings), stats["errors"])

    def test_run_mypy_forces_colour_off(self):
        """Two independent belts: the flag and the environment."""
        import inspect

        src = inspect.getsource(mod._run_mypy)
        self.assertIn("--no-color-output", src)
        self.assertIn("FORCE_COLOR", src)

    def test_parses_the_clean_summary(self):
        _, stats = mod.parse_output("Success: no issues found in 45 source files\n")
        self.assertEqual(
            stats, {"errors": 0, "files_with_errors": 0, "files_checked": 45}
        )

    def test_notes_are_not_findings(self):
        findings, _ = mod.parse_output(
            'src/a.py:1: note: Revealed type is "builtins.int"\n'
        )
        self.assertEqual(findings, [])

    def test_defect_and_annotation_codes_are_distinguished(self):
        findings, _ = mod.parse_output(
            "a.py:1: error: bad [arg-type]\n"
            "a.py:2: error: missing [no-untyped-def]\n"
            "a.py:3: error: other [some-new-code]\n"
        )
        self.assertEqual(
            [f["kind"] for f in findings],
            ["defect", "missing-annotation", "other"],
        )


class TestFailureIsNeverClean(unittest.TestCase):
    """The single most important behaviour: analyzed-nothing is not clean."""

    def test_stdlib_shadowing_is_diagnosed(self):
        reason = mod._diagnose_failure(
            'mypy: "Lib/abc.py" shadows library module "abc"', "", 2
        )
        self.assertIn("shadows a stdlib module", reason)
        self.assertIn("--no-namespace-packages", reason)

    def test_duplicate_module_is_diagnosed(self):
        reason = mod._diagnose_failure("Duplicate module named 'a'", "", 2)
        self.assertIn("same module name", reason)

    def test_unresolved_imports_are_diagnosed(self):
        reason = mod._diagnose_failure(
            "Cannot find implementation or library stub for module named 'x'", "", 2
        )
        self.assertIn("outside the project's environment", reason)

    def test_timeout_is_diagnosed(self):
        self.assertIn("did not run to completion", mod._diagnose_failure("", "", None))

    def test_unknown_failure_still_says_no_information(self):
        reason = mod._diagnose_failure("something odd", "", 2)
        self.assertIn("no information", reason)
        self.assertNotIn("clean", reason.replace("not as clean", ""))


class TestMissingMypy(unittest.TestCase):
    def test_absent_binary_is_FAILED(self):
        result = mod.analyze(".", mypy_bin="definitely-not-a-real-mypy-binary")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["findings"], [])


class TestConfigDiscovery(unittest.TestCase):
    def test_pyproject_without_a_mypy_section_is_not_a_config(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
            self.assertIsNone(mod.find_mypy_config(root))

    def test_pyproject_with_a_mypy_section_is_a_config(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")
            self.assertEqual(mod.find_mypy_config(root), str(root / "pyproject.toml"))

    def test_mypy_ini_wins_over_pyproject(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "mypy.ini").write_text("[mypy]\n")
            (root / "pyproject.toml").write_text("[tool.mypy]\n")
            self.assertEqual(mod.find_mypy_config(root), str(root / "mypy.ini"))


if __name__ == "__main__":
    unittest.main()
