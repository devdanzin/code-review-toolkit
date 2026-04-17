"""Tests for scan_common.py — shared triage/annotation helpers."""

import unittest

from helpers import import_script

mod = import_script("scan_common")


class TestExtractNearbyComments(unittest.TestCase):
    """Tests for extract_nearby_comments."""

    def test_finds_comment_on_same_line(self):
        source = "x = 1  # inline comment\n"
        comments = mod.extract_nearby_comments(source, 1, radius=0)
        self.assertIn("inline comment", comments)

    def test_finds_comments_in_window(self):
        source = (
            "# before\n"        # line 1
            "x = 1\n"           # line 2
            "# after\n"         # line 3
            "y = 2\n"           # line 4
            "# far below\n"     # line 5
        )
        comments = mod.extract_nearby_comments(source, 2, radius=1)
        self.assertIn("before", comments)
        self.assertIn("after", comments)
        # "far below" is 3 lines away, outside radius=1.
        self.assertNotIn("far below", comments)

    def test_ignores_out_of_range(self):
        source = (
            "# top\n"              # line 1
            "x = 1\n"              # line 2
            "y = 2\n"              # line 3
            "z = 3\n"              # line 4
            "# way down\n"         # line 5
        )
        # Scan around line 1 with small radius -- "way down" must NOT appear.
        comments = mod.extract_nearby_comments(source, 1, radius=2)
        self.assertIn("top", comments)
        self.assertNotIn("way down", comments)

    def test_strips_hash_and_whitespace(self):
        source = "#   SAFETY: reviewed\nx = 1\n"
        comments = mod.extract_nearby_comments(source, 1, radius=0)
        self.assertEqual(comments, ["SAFETY: reviewed"])

    def test_empty_source(self):
        self.assertEqual(mod.extract_nearby_comments("", 1), [])

    def test_broken_source_falls_back_to_line_scan(self):
        # Unterminated string -> tokenize will raise; fallback should still
        # find line-based comments.
        source = (
            "# safety: reviewed\n"
            "x = 'unterminated\n"
        )
        comments = mod.extract_nearby_comments(source, 1, radius=0)
        # Fallback path should still surface the leading comment.
        self.assertTrue(
            any("safety" in c.lower() for c in comments),
            f"expected a safety comment, got {comments!r}",
        )

    def test_line_zero_clamped(self):
        source = "# top\nx = 1\n"
        comments = mod.extract_nearby_comments(source, 0, radius=2)
        self.assertIn("top", comments)


class TestHasSafetyAnnotation(unittest.TestCase):
    """Tests for has_safety_annotation."""

    def test_true_for_safety_colon(self):
        self.assertTrue(mod.has_safety_annotation(["SAFETY: reviewed by ada"]))

    def test_true_case_insensitive(self):
        self.assertTrue(mod.has_safety_annotation(["safety: ok"]))
        self.assertTrue(mod.has_safety_annotation(["SAFE BECAUSE x"]))

    def test_true_for_nolint(self):
        self.assertTrue(mod.has_safety_annotation(["nolint"]))

    def test_true_for_noqa(self):
        self.assertTrue(mod.has_safety_annotation(["noqa"]))
        self.assertTrue(mod.has_safety_annotation(["noqa: F401"]))

    def test_true_for_by_design(self):
        self.assertTrue(mod.has_safety_annotation(["this is by design"]))

    def test_true_for_intentional(self):
        self.assertTrue(mod.has_safety_annotation(["intentional"]))

    def test_true_for_deliberately(self):
        self.assertTrue(
            mod.has_safety_annotation(["deliberately unhandled"]),
        )

    def test_false_for_random_comment(self):
        self.assertFalse(mod.has_safety_annotation(["random comment"]))

    def test_false_for_empty(self):
        self.assertFalse(mod.has_safety_annotation([]))
        self.assertFalse(mod.has_safety_annotation([""]))

    def test_false_for_unrelated(self):
        self.assertFalse(
            mod.has_safety_annotation(["TODO: refactor later", "cleanup"]),
        )

    def test_any_of_many_matches(self):
        self.assertTrue(
            mod.has_safety_annotation(
                ["first", "second", "checked: by review"],
            ),
        )


class TestMakeFinding(unittest.TestCase):
    """Tests for make_finding."""

    def test_consistent_keys(self):
        f = mod.make_finding(
            "unused-import",
            file="foo.py",
            line=10,
            function="bar",
            classification="FIX",
            severity="high",
            detail="imported but not used",
        )
        # Required keys all present.
        expected = {
            "type", "file", "line", "function", "classification",
            "severity", "confidence", "detail",
        }
        self.assertTrue(expected.issubset(f.keys()))
        self.assertEqual(f["type"], "unused-import")
        self.assertEqual(f["file"], "foo.py")
        self.assertEqual(f["line"], 10)
        self.assertEqual(f["classification"], "FIX")
        self.assertEqual(f["severity"], "high")
        # Default confidence.
        self.assertEqual(f["confidence"], "high")

    def test_defaults(self):
        f = mod.make_finding(
            "debt",
            classification="CONSIDER",
            severity="low",
            detail="foo",
        )
        self.assertEqual(f["file"], "")
        self.assertEqual(f["line"], 0)
        self.assertEqual(f["function"], "")

    def test_extra_fields_merged(self):
        f = mod.make_finding(
            "dead-code",
            classification="FIX",
            severity="medium",
            detail="unreferenced",
            module="pkg.foo",
            name="helper",
        )
        self.assertEqual(f["module"], "pkg.foo")
        self.assertEqual(f["name"], "helper")

    def test_custom_confidence(self):
        f = mod.make_finding(
            "x",
            classification="CONSIDER",
            severity="low",
            detail="d",
            confidence="low",
        )
        self.assertEqual(f["confidence"], "low")


if __name__ == "__main__":
    unittest.main()
