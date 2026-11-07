"""Regression coverage for the Windows PyInstaller desktop build.

The Windows desktop workflow (``.github/workflows/desktop.yml``) builds
``packaging/eclipse-desktop.spec`` with PyInstaller; a ``hiddenimport`` that does
not resolve to a real module fails the whole Windows build and blocks the PR
merge gate. The PR #16 recovery added ``src/eclipse/core/runtime.py``, which
``eclipse.core`` imports, so the spec must list it explicitly. These tests pin
that every hiddenimport in the spec resolves to a real module under ``src/`` and
that the branch-added module is packaged.
"""

from __future__ import annotations

from tests import _bootstrap  # noqa: F401

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "eclipse-desktop.spec"
SRC = ROOT / "src"


def hiddenimports_from_spec(spec: Path) -> list[str]:
    tree = ast.parse(spec.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Analysis"
        ):
            for keyword in node.keywords:
                if keyword.arg == "hiddenimports":
                    return list(ast.literal_eval(keyword.value))
    raise AssertionError("no Analysis(hiddenimports=...) found in the spec")


def resolve_module_path(module: str) -> Path:
    relative = module.replace(".", "/")
    module_file = SRC / f"{relative}.py"
    package_file = SRC / relative / "__init__.py"
    return module_file if module_file.is_file() else package_file


class PackagingSpecTests(unittest.TestCase):
    def test_spec_exists(self) -> None:
        self.assertTrue(SPEC.is_file(), "packaging/eclipse-desktop.spec is missing")

    def test_every_hiddenimport_resolves_to_a_module(self) -> None:
        for module in hiddenimports_from_spec(SPEC):
            with self.subTest(module=module):
                self.assertTrue(
                    resolve_module_path(module).is_file(),
                    f"hiddenimport {module!r} does not resolve under src/",
                )

    def test_branch_added_core_runtime_is_packaged(self) -> None:
        self.assertIn("eclipse.core.runtime", hiddenimports_from_spec(SPEC))


if __name__ == "__main__":
    unittest.main()
