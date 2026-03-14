"""Tests for count_types.py."""

import unittest

from helpers import TempProject, import_script

mod = import_script("count_types")


class TestAnnotationCoverage(unittest.TestCase):
    """Test function annotation detection."""

    def _analyze(self, source: str) -> dict:
        with TempProject({"mod.py": source}) as root:
            return mod.analyze_file(root / "mod.py", root)

    def test_fully_annotated(self):
        result = self._analyze(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        func = result["functions"][0]
        self.assertTrue(func["fully_annotated"])
        self.assertEqual(func["annotated_params"], 2)
        self.assertTrue(func["has_return_annotation"])

    def test_partially_annotated(self):
        result = self._analyze(
            "def add(a: int, b) -> int:\n"
            "    return a + b\n"
        )
        func = result["functions"][0]
        self.assertFalse(func["fully_annotated"])
        self.assertEqual(func["annotated_params"], 1)
        self.assertEqual(func["total_params"], 2)

    def test_no_annotations(self):
        result = self._analyze(
            "def add(a, b):\n"
            "    return a + b\n"
        )
        func = result["functions"][0]
        self.assertFalse(func["fully_annotated"])
        self.assertEqual(func["annotated_params"], 0)
        self.assertFalse(func["has_return_annotation"])

    def test_no_params_with_return(self):
        result = self._analyze(
            "def get_value() -> int:\n"
            "    return 42\n"
        )
        func = result["functions"][0]
        self.assertTrue(func["fully_annotated"])

    def test_self_excluded_from_count(self):
        result = self._analyze(
            "class C:\n"
            "    def method(self, x: int) -> None:\n"
            "        pass\n"
        )
        cls = result["classes"][0]
        method = cls["methods"][0]
        self.assertEqual(method["total_params"], 1)  # x only, not self
        self.assertTrue(method["fully_annotated"])

    def test_public_detection(self):
        result = self._analyze(
            "def public_func(): pass\n"
            "def _private_func(): pass\n"
        )
        funcs = {f["name"]: f["is_public"] for f in result["functions"]}
        self.assertTrue(funcs["public_func"])
        self.assertFalse(funcs["_private_func"])


class TestAnyDetection(unittest.TestCase):
    """Test detection of Any in annotations."""

    def _analyze(self, source: str) -> dict:
        with TempProject({"mod.py": source}) as root:
            return mod.analyze_file(root / "mod.py", root)

    def test_any_in_param(self):
        result = self._analyze(
            "from typing import Any\n"
            "\n"
            "def process(data: Any) -> None:\n"
            "    pass\n"
        )
        self.assertTrue(len(result["any_usages"]) > 0)

    def test_any_in_return(self):
        result = self._analyze(
            "from typing import Any\n"
            "\n"
            "def get_data() -> Any:\n"
            "    pass\n"
        )
        func = result["functions"][0]
        self.assertTrue(func["any_in_return"])

    def test_any_nested_in_dict(self):
        result = self._analyze(
            "from typing import Any\n"
            "\n"
            "def process(data: dict[str, Any]) -> None:\n"
            "    pass\n"
        )
        func = result["functions"][0]
        self.assertTrue(len(func["any_in_params"]) > 0)

    def test_no_any(self):
        result = self._analyze(
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n"
        )
        self.assertEqual(len(result["any_usages"]), 0)


class TestContainerTypeDetection(unittest.TestCase):
    """Test detection of dataclass, TypedDict, NamedTuple, etc."""

    def _analyze(self, source: str) -> dict:
        with TempProject({"mod.py": source}) as root:
            return mod.analyze_file(root / "mod.py", root)

    def test_dataclass(self):
        result = self._analyze(
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass\n"
            "class Point:\n"
            "    x: float\n"
            "    y: float\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "dataclass")

    def test_frozen_dataclass(self):
        result = self._analyze(
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass(frozen=True)\n"
            "class Point:\n"
            "    x: float\n"
            "    y: float\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "dataclass")
        self.assertTrue(cls["frozen"])

    def test_typed_dict(self):
        result = self._analyze(
            "from typing import TypedDict\n"
            "\n"
            "class Config(TypedDict):\n"
            "    name: str\n"
            "    value: int\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "TypedDict")

    def test_named_tuple(self):
        result = self._analyze(
            "from typing import NamedTuple\n"
            "\n"
            "class Point(NamedTuple):\n"
            "    x: float\n"
            "    y: float\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "NamedTuple")

    def test_protocol(self):
        result = self._analyze(
            "from typing import Protocol\n"
            "\n"
            "class Renderable(Protocol):\n"
            "    def render(self) -> str: ...\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "Protocol")

    def test_enum(self):
        result = self._analyze(
            "from enum import Enum\n"
            "\n"
            "class Color(Enum):\n"
            "    RED = 1\n"
            "    GREEN = 2\n"
        )
        cls = result["classes"][0]
        self.assertEqual(cls["container_type"], "Enum")

    def test_plain_class(self):
        result = self._analyze(
            "class Regular:\n"
            "    def __init__(self):\n"
            "        self.x = 1\n"
        )
        cls = result["classes"][0]
        self.assertIsNone(cls["container_type"])


class TestClassAttributes(unittest.TestCase):

    def test_annotated_vs_unannotated(self):
        with TempProject({
            "mod.py": (
                "class Foo:\n"
                "    typed: int\n"
                "    also_typed: str = 'hello'\n"
                "    untyped = 42\n"
            ),
        }) as root:
            result = mod.analyze_file(root / "mod.py", root)
            cls = result["classes"][0]
            self.assertEqual(len(cls["annotated_attributes"]), 2)
            self.assertEqual(len(cls["unannotated_attributes"]), 1)
            self.assertEqual(cls["unannotated_attributes"][0], "untyped")


class TestTypeIgnoreCount(unittest.TestCase):

    def test_counts_type_ignore(self):
        with TempProject({
            "mod.py": (
                "x = foo()  # type: ignore\n"
                "y = bar()  # type: ignore[assignment]\n"
                "z = baz()  # this is fine\n"
            ),
        }) as root:
            result = mod.analyze_file(root / "mod.py", root)
            self.assertEqual(result["type_ignore_count"], 2)


if __name__ == "__main__":
    unittest.main()
