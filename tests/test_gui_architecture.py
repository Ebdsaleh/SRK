"""Guard SRK's presentation/application separation."""

import ast
from pathlib import Path
import unittest


class GuiArchitectureTests(unittest.TestCase):
    def test_core_application_and_runtime_do_not_import_dearpygui(self):
        root = Path(__file__).resolve().parents[1] / "src" / "rikai_kotoba"
        checked = []
        for relative in ("core", "application", "runtime"):
            for path in (root / relative).rglob("*.py"):
                checked.append(path)
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("dearpygui"):
                                self.fail(f"{path} imports Dear PyGui directly")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module.startswith("dearpygui"):
                            self.fail(f"{path} imports Dear PyGui directly")
        self.assertTrue(checked)


if __name__ == "__main__":
    unittest.main()
