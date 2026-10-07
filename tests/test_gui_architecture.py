"""Guard SRK's Salix-first presentation/application separation."""

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "src"


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


class GuiArchitectureTests(unittest.TestCase):
    def test_srk_core_and_application_do_not_import_dearpygui(self):
        product = ROOT / "rikai_kotoba"
        checked = []
        for relative in ("core", "application"):
            for path in (product / relative).rglob("*.py"):
                checked.append(path)
                for module in _imports(path):
                    self.assertFalse(
                        module.startswith("dearpygui"),
                        f"{path} imports Dear PyGui directly",
                    )
        self.assertTrue(checked)

    def test_srk_core_does_not_depend_on_salix_engine(self):
        for path in (ROOT / "rikai_kotoba" / "core").rglob("*.py"):
            for module in _imports(path):
                self.assertFalse(
                    module.startswith("salix.engine"),
                    f"{path} couples domain core to presentation engine",
                )

    def test_salix_framework_and_runtime_are_product_neutral(self):
        checked = []
        for relative in ("framework", "runtime"):
            for path in (ROOT / "salix" / relative).rglob("*.py"):
                checked.append(path)
                for module in _imports(path):
                    self.assertFalse(
                        module.startswith("rikai_kotoba"),
                        f"{path} depends on SRK product code",
                    )
                    self.assertFalse(
                        module.startswith("dearpygui"),
                        f"{path} leaks Dear PyGui into backend-neutral Salix layer",
                    )
        self.assertTrue(checked)

    def test_product_does_not_reintroduce_parallel_runtime_or_engine(self):
        product = ROOT / "rikai_kotoba"
        self.assertFalse((product / "runtime").exists())
        self.assertFalse((product / "engine").exists())

    def test_dearpygui_adapter_code_lives_under_salix_engine(self):
        engine = ROOT / "salix" / "engine"
        dpg_importers = []
        for path in engine.rglob("*.py"):
            if any(module.startswith("dearpygui") for module in _imports(path)):
                dpg_importers.append(path)
        self.assertTrue(dpg_importers)


if __name__ == "__main__":
    unittest.main()
