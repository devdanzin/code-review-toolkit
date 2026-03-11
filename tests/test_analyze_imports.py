"""Tests for analyze_imports.py."""

import json
import unittest
from pathlib import Path

from helpers import TempProject, import_script

mod = import_script("analyze_imports")


class TestIsStdlib(unittest.TestCase):
    """Test stdlib detection."""

    def test_common_stdlib_modules(self):
        for name in ("os", "sys", "json", "pathlib", "ast", "unittest",
                      "collections", "typing", "functools", "itertools"):
            with self.subTest(name=name):
                self.assertTrue(mod._is_stdlib(name))

    def test_not_stdlib(self):
        for name in ("requests", "numpy", "yaml", "click", "flask"):
            with self.subTest(name=name):
                self.assertFalse(mod._is_stdlib(name))


class TestResolveRelativeImport(unittest.TestCase):
    """Test relative import resolution."""

    def _resolve(self, source_rel, level, module):
        root = Path("/project")
        source = root / source_rel
        return mod._resolve_relative_import(source, root, level, module)

    def test_level_1_with_module(self):
        # from .core import X  inside pkg/sub/file.py  →  pkg.sub.core
        # Actually: level=1, source is in pkg/sub/, so we go up 1 from
        # pkg/sub and get pkg, then append module.
        # Wait, let me trace the logic more carefully.
        # source_file = /project/pkg/sub/file.py
        # rel = pkg/sub/file.py
        # parts = [pkg, sub]  (directory components)
        # level=1: base_parts = parts[:len(parts)-1] = [pkg]
        # dotted = "pkg"
        # module = "core" → "pkg.core"
        result = self._resolve("pkg/sub/file.py", 1, "core")
        self.assertEqual(result, "pkg.core")

    def test_level_1_no_module(self):
        # from . import X  inside pkg/sub/file.py  →  pkg
        result = self._resolve("pkg/sub/file.py", 1, None)
        self.assertEqual(result, "pkg")

    def test_level_2(self):
        # from ..utils import X  inside pkg/sub/deep/file.py  →  pkg.utils
        result = self._resolve("pkg/sub/deep/file.py", 2, "utils")
        self.assertEqual(result, "pkg.utils")

    def test_level_exceeds_depth(self):
        # from ... import X  inside pkg/file.py  (only 1 dir level)
        result = self._resolve("pkg/file.py", 3, "something")
        self.assertIsNone(result)

    def test_top_level_relative(self):
        # from .sibling import X  inside pkg/file.py  →  sibling
        result = self._resolve("pkg/file.py", 1, "sibling")
        self.assertEqual(result, "sibling")


class TestAnalyzeFile(unittest.TestCase):
    """Test single-file analysis."""

    def test_basic_imports(self):
        with TempProject({
            "pkg/__init__.py": "",
            "pkg/core.py": (
                "import os\n"
                "import json\n"
                "from pathlib import Path\n"
                "import requests\n"
                "from . import utils\n"
            ),
            "pkg/utils.py": "",
        }) as root:
            result = mod.analyze_file(
                root / "pkg/core.py", root, {"pkg"}
            )
            self.assertIsNone(result["parse_error"])
            imports = result["imports"]
            self.assertEqual(len(imports), 5)

            # Check categories.
            categories = {i["module"] or i.get("resolved_module", ""): i["category"]
                          for i in imports}
            self.assertEqual(categories["os"], "stdlib")
            self.assertEqual(categories["json"], "stdlib")
            self.assertEqual(categories["pathlib"], "stdlib")
            self.assertEqual(categories["requests"], "external")

            # The relative import should be internal.
            relative_imports = [i for i in imports if i["is_relative"]]
            self.assertEqual(len(relative_imports), 1)
            self.assertEqual(relative_imports[0]["category"], "internal")

    def test_type_checking_detection(self):
        with TempProject({
            "pkg/__init__.py": "",
            "pkg/core.py": (
                "from __future__ import annotations\n"
                "from typing import TYPE_CHECKING\n"
                "\n"
                "if TYPE_CHECKING:\n"
                "    from pkg.models import SomeType\n"
                "\n"
                "import os\n"
            ),
        }) as root:
            result = mod.analyze_file(
                root / "pkg/core.py", root, {"pkg"}
            )
            imports = result["imports"]
            tc_imports = [i for i in imports if i["type_checking_only"]]
            non_tc = [i for i in imports if not i["type_checking_only"]]

            # "from pkg.models import SomeType" should be type-checking-only.
            self.assertEqual(len(tc_imports), 1)
            self.assertEqual(tc_imports[0]["module"], "pkg.models")

            # os and TYPE_CHECKING itself should not be type-checking-only.
            non_tc_modules = {i["module"] for i in non_tc}
            self.assertIn("os", non_tc_modules)

    def test_conditional_import_detection(self):
        with TempProject({
            "pkg/__init__.py": "",
            "pkg/core.py": (
                "try:\n"
                "    import rapidjson as json_mod\n"
                "except ImportError:\n"
                "    import json as json_mod\n"
            ),
        }) as root:
            result = mod.analyze_file(
                root / "pkg/core.py", root, {"pkg"}
            )
            conditional = [i for i in result["imports"] if i["conditional"]]
            # The "try" branch import should be conditional.
            self.assertTrue(len(conditional) >= 1)

    def test_all_declaration(self):
        with TempProject({
            "pkg/__init__.py": '__all__ = ["foo", "Bar"]\n',
        }) as root:
            result = mod.analyze_file(
                root / "pkg/__init__.py", root, {"pkg"}
            )
            self.assertEqual(result["all_declaration"], ["foo", "Bar"])
            self.assertTrue(result["is_init"])

    def test_syntax_error_handled(self):
        with TempProject({
            "bad.py": "def broken(\n",
        }) as root:
            result = mod.analyze_file(root / "bad.py", root, set())
            self.assertIsNotNone(result["parse_error"])
            self.assertEqual(result["imports"], [])


class TestDetectCycles(unittest.TestCase):
    """Test circular dependency detection."""

    def test_direct_cycle(self):
        graph = {
            "a.py": [{"target": "b", "type_checking_only": False, "conditional": False}],
            "b.py": [{"target": "a", "type_checking_only": False, "conditional": False}],
        }
        cycles = mod.detect_cycles(graph)
        self.assertEqual(len(cycles), 1)
        # Cycle should contain both files.
        cycle_set = set(cycles[0])
        self.assertEqual(cycle_set, {"a.py", "b.py"})

    def test_no_cycles(self):
        graph = {
            "a.py": [{"target": "b", "type_checking_only": False, "conditional": False}],
            "b.py": [{"target": "c", "type_checking_only": False, "conditional": False}],
        }
        cycles = mod.detect_cycles(graph)
        self.assertEqual(len(cycles), 0)

    def test_indirect_cycle(self):
        graph = {
            "a.py": [{"target": "b", "type_checking_only": False, "conditional": False}],
            "b.py": [{"target": "c", "type_checking_only": False, "conditional": False}],
            "c.py": [{"target": "a", "type_checking_only": False, "conditional": False}],
        }
        cycles = mod.detect_cycles(graph)
        self.assertGreaterEqual(len(cycles), 1)
        # All three files should appear in the cycle.
        all_nodes = set()
        for cycle in cycles:
            all_nodes.update(cycle)
        self.assertIn("a.py", all_nodes)
        self.assertIn("b.py", all_nodes)
        self.assertIn("c.py", all_nodes)


class TestIdentifyProjectPackages(unittest.TestCase):
    """Test project package discovery."""

    def test_finds_packages_with_init(self):
        with TempProject({
            "mypkg/__init__.py": "",
            "mypkg/core.py": "",
            "other/__init__.py": "",
        }) as root:
            packages = mod.identify_project_packages(root)
            self.assertIn("mypkg", packages)
            self.assertIn("other", packages)

    def test_ignores_test_dirs(self):
        with TempProject({
            "mypkg/__init__.py": "",
            "tests/__init__.py": "",
        }) as root:
            packages = mod.identify_project_packages(root)
            self.assertIn("mypkg", packages)
            self.assertNotIn("tests", packages)

    def test_src_layout(self):
        with TempProject({
            "src/mypkg/__init__.py": "",
            "src/mypkg/core.py": "",
        }) as root:
            packages = mod.identify_project_packages(root)
            self.assertIn("mypkg", packages)


class TestEndToEnd(unittest.TestCase):
    """Integration test: full pipeline on a small project."""

    def test_small_project(self):
        with TempProject({
            "mypkg/__init__.py": "from .core import main\n",
            "mypkg/core.py": (
                "import os\n"
                "from .utils import helper\n"
                "\n"
                "def main():\n"
                "    return helper(os.getcwd())\n"
            ),
            "mypkg/utils.py": (
                "def helper(path):\n"
                "    return str(path)\n"
            ),
            "tests/test_core.py": (
                "import unittest\n"
                "from mypkg.core import main\n"
                "\n"
                "class TestCore(unittest.TestCase):\n"
                "    def test_main(self):\n"
                "        self.assertIsNotNone(main())\n"
            ),
        }) as root:
            files = mod.discover_python_files(root)
            project_packages = mod.identify_project_packages(root)
            analyses = [mod.analyze_file(f, root, project_packages) for f in files]

            self.assertEqual(len(analyses), 4)

            graph = mod.build_internal_graph(analyses)
            # mypkg/core.py should depend on mypkg/utils.
            core_edges = graph.get("mypkg/core.py", [])
            targets = {e["target"] for e in core_edges}
            self.assertTrue(
                any("utils" in t for t in targets),
                f"Expected utils dependency, got {targets}"
            )

            # No cycles in this project.
            cycles = mod.detect_cycles(graph)
            self.assertEqual(len(cycles), 0)


if __name__ == "__main__":
    unittest.main()
