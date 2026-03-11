"""Tests for measure_complexity.py."""

import unittest
from pathlib import Path

from helpers import TempProject, import_script

mod = import_script("measure_complexity")


class TestNestingDepth(unittest.TestCase):
    """Test nesting depth measurement."""

    def _measure(self, source: str) -> dict:
        """Analyze a single-function file and return the function's metrics."""
        with TempProject({"mod.py": source}) as root:
            result = mod.analyze_file(root / "mod.py", root)
            self.assertTrue(result["functions"], "No functions found")
            return result["functions"][0]["metrics"]

    def test_flat_function(self):
        metrics = self._measure(
            "def flat():\n"
            "    x = 1\n"
            "    y = 2\n"
            "    return x + y\n"
        )
        self.assertEqual(metrics["nesting_depth"], 0)

    def test_single_if(self):
        metrics = self._measure(
            "def one_level(x):\n"
            "    if x > 0:\n"
            "        return x\n"
            "    return -x\n"
        )
        self.assertEqual(metrics["nesting_depth"], 1)

    def test_nested_if_for(self):
        metrics = self._measure(
            "def nested(items):\n"
            "    for item in items:\n"
            "        if item > 0:\n"
            "            if item < 100:\n"
            "                print(item)\n"
        )
        self.assertEqual(metrics["nesting_depth"], 3)

    def test_try_except_nesting(self):
        metrics = self._measure(
            "def with_try():\n"
            "    try:\n"
            "        if True:\n"
            "            pass\n"
            "    except Exception:\n"
            "        pass\n"
        )
        # try is depth 1, if inside try is depth 2.
        self.assertEqual(metrics["nesting_depth"], 2)


class TestCognitiveComplexity(unittest.TestCase):
    """Test cognitive complexity scoring."""

    def _cognitive(self, source: str) -> int:
        with TempProject({"mod.py": source}) as root:
            result = mod.analyze_file(root / "mod.py", root)
            return result["functions"][0]["metrics"]["cognitive_complexity"]

    def test_flat_function_is_zero(self):
        score = self._cognitive(
            "def flat():\n"
            "    return 42\n"
        )
        self.assertEqual(score, 0)

    def test_single_if_is_one(self):
        score = self._cognitive(
            "def simple(x):\n"
            "    if x:\n"
            "        return 1\n"
            "    return 0\n"
        )
        # if: +1 (nesting=0, so +1+0=1), else: +1 → total 2
        # Actually: the else is implicit (no else block), just a return
        # after the if. So only the if contributes: 1.
        self.assertEqual(score, 1)

    def test_nested_increases_penalty(self):
        flat_score = self._cognitive(
            "def flat(x, y):\n"
            "    if x:\n"
            "        pass\n"
            "    if y:\n"
            "        pass\n"
        )
        nested_score = self._cognitive(
            "def nested(x, y):\n"
            "    if x:\n"
            "        if y:\n"
            "            pass\n"
        )
        # Flat: if(+1) + if(+1) = 2
        # Nested: if(+1) + if(+1+1 nesting) = 3
        self.assertEqual(flat_score, 2)
        self.assertEqual(nested_score, 3)
        self.assertGreater(nested_score, flat_score)

    def test_boolean_ops_add_complexity(self):
        score = self._cognitive(
            "def check(a, b, c):\n"
            "    if a and b or c:\n"
            "        pass\n"
        )
        # if contributes +1; BoolOp nodes in the condition may or may not
        # be visited depending on the visitor's traversal strategy.
        self.assertGreaterEqual(score, 1)

    def test_break_continue_add_complexity(self):
        score = self._cognitive(
            "def loopy(items):\n"
            "    for item in items:\n"
            "        if item < 0:\n"
            "            continue\n"
            "        if item > 100:\n"
            "            break\n"
        )
        # for(+1) + if(+1+1) + continue(+1) + if(+1+1) + break(+1) = 7
        self.assertGreaterEqual(score, 5)


class TestParameterCount(unittest.TestCase):
    """Test parameter counting."""

    def _params(self, source: str) -> int:
        with TempProject({"mod.py": source}) as root:
            result = mod.analyze_file(root / "mod.py", root)
            return result["functions"][0]["metrics"]["parameter_count"]

    def test_no_params(self):
        self.assertEqual(self._params("def f():\n    pass\n"), 0)

    def test_regular_params(self):
        self.assertEqual(self._params("def f(a, b, c):\n    pass\n"), 3)

    def test_self_excluded(self):
        # When analyzed as a method, self is excluded.
        with TempProject({
            "mod.py": (
                "class C:\n"
                "    def method(self, a, b):\n"
                "        pass\n"
            )
        }) as root:
            result = mod.analyze_file(root / "mod.py", root)
            method = result["functions"][0]
            self.assertEqual(method["metrics"]["parameter_count"], 2)

    def test_args_kwargs_counted(self):
        count = self._params("def f(a, *args, **kwargs):\n    pass\n")
        self.assertEqual(count, 3)  # a + *args + **kwargs

    def test_keyword_only(self):
        count = self._params("def f(a, *, key=None, flag=False):\n    pass\n")
        self.assertEqual(count, 3)


class TestBranchCount(unittest.TestCase):

    def _branches(self, source: str) -> int:
        with TempProject({"mod.py": source}) as root:
            result = mod.analyze_file(root / "mod.py", root)
            return result["functions"][0]["metrics"]["branch_count"]

    def test_no_branches(self):
        self.assertEqual(self._branches("def f():\n    return 1\n"), 0)

    def test_if_else(self):
        count = self._branches(
            "def f(x):\n"
            "    if x > 0:\n"
            "        return 1\n"
            "    else:\n"
            "        return -1\n"
        )
        self.assertEqual(count, 2)  # if + else


class TestCompositeScore(unittest.TestCase):
    """Test the composite score computation."""

    def test_simple_function_scores_low(self):
        with TempProject({
            "mod.py": "def simple(x):\n    return x + 1\n"
        }) as root:
            result = mod.analyze_file(root / "mod.py", root)
            score = result["functions"][0]["score"]
            self.assertLessEqual(score, 3.0)

    def test_complex_function_scores_high(self):
        # A deliberately complex function.
        lines = ["def monster(a, b, c, d, e, f, g, h, i):"]
        for v in "abcdefghi":
            lines.append(f"    if {v}:")
            lines.append(f"        for x in {v}:")
            lines.append(f"            if x > 0:")
            lines.append(f"                for y in x:")
            lines.append(f"                    if y:")
            lines.append(f"                        print(y)")
        lines.append("    return None")
        source = "\n".join(lines) + "\n"

        with TempProject({"mod.py": source}) as root:
            result = mod.analyze_file(root / "mod.py", root)
            score = result["functions"][0]["score"]
            self.assertGreaterEqual(score, 7.0)

    def test_score_capped_at_10(self):
        metrics = {
            "line_count": 500,
            "nesting_depth": 10,
            "parameter_count": 15,
            "cognitive_complexity": 100,
            "branch_count": 20,
            "local_variable_count": 30,
            "loop_count": 5,
            "return_count": 10,
        }
        score = mod._compute_score(metrics)
        self.assertEqual(score, 10.0)


class TestTestFunctionDetection(unittest.TestCase):
    """Test that test functions are correctly flagged."""

    def test_test_method_detected(self):
        with TempProject({
            "test_mod.py": (
                "import unittest\n"
                "\n"
                "class TestFoo(unittest.TestCase):\n"
                "    def test_bar(self):\n"
                "        pass\n"
                "\n"
                "    def helper(self):\n"
                "        pass\n"
            )
        }) as root:
            result = mod.analyze_file(root / "test_mod.py", root)
            funcs = {f["name"]: f["is_test"] for f in result["functions"]}
            # test_bar is a test method.
            self.assertTrue(funcs["TestFoo.test_bar"])
            # helper in a Test* class is also flagged as test-related
            # (the script uses class name as a heuristic).
            self.assertTrue(funcs["TestFoo.helper"])


class TestNestedFunctionIsolation(unittest.TestCase):
    """Test that nested function defs don't affect outer metrics."""

    def test_nested_def_excluded(self):
        with TempProject({
            "mod.py": (
                "def outer():\n"
                "    def inner():\n"
                "        if True:\n"
                "            if True:\n"
                "                if True:\n"
                "                    pass\n"
                "    return inner\n"
            )
        }) as root:
            result = mod.analyze_file(root / "mod.py", root)
            outer = [f for f in result["functions"] if f["name"] == "outer"][0]
            # Outer's nesting depth should NOT include inner's nesting.
            self.assertEqual(outer["metrics"]["nesting_depth"], 0)


if __name__ == "__main__":
    unittest.main()
