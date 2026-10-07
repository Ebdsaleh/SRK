"""Synthetic tests for safe SRK -> SAROO Firm_Saturn source preparation."""

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    SarooFirmwareIntegrationError,
    prepare_firm_saturn_tree,
)


MAKEFILE = """OBJ\t=\tobj/main.o  \\\n\t\tobj/sci_shell.o  \\\n\t\tobj/version.o\n"""

SHELL = """#include \"main.h\"\n#include \"smpc.h\"\n\nvoid sci_shell(void)\n{\n\tchar *cmd = 0;\n\tif(0){}\n\t\tCMD(q) {\n\t\t\tbreak;\n\t\t}\n}\n"""


class SarooFirmwareIntegrationTests(unittest.TestCase):
    @staticmethod
    def _make_source(root: Path, *, makefile: str = MAKEFILE, shell: str = SHELL) -> Path:
        source = root / "SAROO"
        firm = source / "Firm_Saturn"
        firm.mkdir(parents=True)
        (firm / "Makefile").write_text(makefile, encoding="utf-8", newline="\n")
        (firm / "sci_shell.c").write_text(shell, encoding="utf-8", newline="\n")
        (firm / "main.h").write_text("/* synthetic */\n", encoding="utf-8")
        return source

    def test_generates_separate_tree_and_leaves_source_untouched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = self._make_source(temp)
            original_makefile = (source / "Firm_Saturn" / "Makefile").read_bytes()
            original_shell = (source / "Firm_Saturn" / "sci_shell.c").read_bytes()
            output = temp / "SAROO-SRK"

            result = prepare_firm_saturn_tree(source, output)

            self.assertEqual(
                (source / "Firm_Saturn" / "Makefile").read_bytes(),
                original_makefile,
            )
            self.assertEqual(
                (source / "Firm_Saturn" / "sci_shell.c").read_bytes(),
                original_shell,
            )
            self.assertTrue(result.helper_source_path.is_file())
            self.assertTrue(result.helper_header_path.is_file())
            self.assertTrue((output / "SRK_INTEGRATION.txt").is_file())

            patched_makefile = result.makefile_path.read_text(encoding="utf-8")
            patched_shell = result.shell_path.read_text(encoding="utf-8")
            self.assertEqual(patched_makefile.count("obj/srk_capture_helper.o"), 1)
            self.assertEqual(patched_shell.count('#include "srk_capture_helper.h"'), 1)
            self.assertEqual(patched_shell.count("CMD(srkwl)"), 1)
            self.assertEqual(patched_shell.count("CMD(srkwh)"), 1)
            self.assertIn("/SAROO/SRK_WRAML.BIN", patched_shell)
            self.assertIn("/SAROO/SRK_WRAMH.BIN", patched_shell)

    def test_existing_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = self._make_source(temp)
            output = temp / "already-there"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(SarooFirmwareIntegrationError, "already exists"):
                prepare_firm_saturn_tree(source, output)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_incompatible_source_is_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = self._make_source(temp, makefile="OBJ = obj/main.o\n")
            output = temp / "out"

            with self.assertRaisesRegex(SarooFirmwareIntegrationError, "Makefile"):
                prepare_firm_saturn_tree(source, output)

            self.assertFalse(output.exists())

    def test_output_inside_source_checkout_is_refused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = self._make_source(temp)
            output = source / "generated"

            with self.assertRaisesRegex(SarooFirmwareIntegrationError, "outside"):
                prepare_firm_saturn_tree(source, output)

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
