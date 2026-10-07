"""Synthetic tests for safe SRK -> SAROO Firm_Saturn source preparation."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo import (
    SarooFirmwareIntegrationError,
    prepare_firm_saturn_tree,
)


MAKEFILE = """OBJ\t=\tobj/main.o  \\
\t\tobj/sci_shell.o  \\
\t\tobj/version.o\n"""

MAKEFILE_WITH_SUPPORT = """CC\t=\tsh-elf-gcc
AS\t=\tsh-elf-as
OBJDUMP = sh-elf-objdump
OBJCOPY = sh-elf-objcopy

EXE\t=\tssfirm.elf

OBJ\t=\tobj/main.o  \\
\t\tobj/sci_shell.o  \\
\t\tobj/version.o

define ECHO_CMD
\t$(if $(V), , @echo \"    \"$(1)\" \" $(2))
\t$(if $(V), $(3), @$(3))
endef

all\t: obj BUILD_VER $(EXE)

obj:
\t$(call ECHO_CMD, \"MKDIR  \" , obj, mkdir obj)

BUILD_VER:
\t$(call ECHO_CMD, \"TOUCH  \" , version.c, touch version.c)

$(EXE)\t: $(OBJ)
\t$(call ECHO_CMD, \"OBJDUMP\", dump.txt, $(OBJDUMP) -xd $(EXE) > dump.txt)
\t$(call ECHO_CMD, \"OBJCOPY\", tmp.bin, $(OBJCOPY) -O binary $(EXE) tmp.bin)
\t$(call ECHO_CMD, \"CAT    \" , ssfirm.bin, cat tmp.bin font_cjk.bin >ssfirm.bin)
\t$(call ECHO_CMD, \"RM     \" , tmp.bin,  rm -f tmp.bin)

clean\t:
\t\trm -f obj/*.o
\t\trm -f $(EXE) ssfirm.bin dump.txt
""".replace('"MKDIR  " ,', '"MKDIR  ",').replace('"TOUCH  " ,', '"TOUCH  ",').replace('"CAT    " ,', '"CAT    ",').replace('"RM     " ,', '"RM     ",')

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
            self.assertTrue(result.build_support_path.is_file())
            self.assertTrue((output / "SRK_INTEGRATION.txt").is_file())

            patched_makefile = result.makefile_path.read_text(encoding="utf-8")
            patched_shell = result.shell_path.read_text(encoding="utf-8")
            self.assertEqual(patched_makefile.count("obj/srk_capture_helper.o"), 1)
            self.assertEqual(patched_shell.count('#include "srk_capture_helper.h"'), 1)
            self.assertEqual(patched_shell.count("CMD(srkwl)"), 1)
            self.assertEqual(patched_shell.count("CMD(srkwh)"), 1)
            self.assertIn("/SAROO/SRK_WRAML.BIN", patched_shell)
            self.assertIn("/SAROO/SRK_WRAMH.BIN", patched_shell)

    def test_upstream_unix_file_recipes_are_replaced_by_portable_helper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = self._make_source(temp, makefile=MAKEFILE_WITH_SUPPORT)
            original_makefile = (source / "Firm_Saturn" / "Makefile").read_bytes()
            output = temp / "SAROO-SRK"

            result = prepare_firm_saturn_tree(source, output)

            self.assertEqual(
                (source / "Firm_Saturn" / "Makefile").read_bytes(),
                original_makefile,
            )
            patched = result.makefile_path.read_text(encoding="utf-8")
            self.assertIn("PYTHON ?= python", patched)
            self.assertIn("srk_build_support.py touch version.c", patched)
            self.assertIn(
                "srk_build_support.py concat ssfirm.bin tmp.bin font_cjk.bin",
                patched,
            )
            self.assertIn("srk_build_support.py remove tmp.bin", patched)
            self.assertIn("srk_build_support.py remove obj/*.o", patched)
            self.assertIn(
                "srk_build_support.py remove $(EXE) ssfirm.bin dump.txt",
                patched,
            )
            self.assertNotIn("version.c, touch version.c)", patched)
            self.assertNotIn("cat tmp.bin font_cjk.bin >ssfirm.bin", patched)
            self.assertNotIn("rm -f tmp.bin", patched)
            self.assertNotIn("\t\trm -f obj/*.o", patched)
            self.assertNotIn("\t\trm -f $(EXE) ssfirm.bin dump.txt", patched)

            firm = result.firm_saturn_directory
            first = firm / "first.bin"
            second = firm / "second.bin"
            joined = firm / "joined.bin"
            first.write_bytes(b"abc")
            second.write_bytes(b"DEF")

            subprocess.run(
                [
                    sys.executable,
                    str(result.build_support_path),
                    "concat",
                    joined.name,
                    first.name,
                    second.name,
                ],
                cwd=firm,
                check=True,
            )
            self.assertEqual(joined.read_bytes(), b"abcDEF")

            subprocess.run(
                [sys.executable, str(result.build_support_path), "remove", joined.name],
                cwd=firm,
                check=True,
            )
            self.assertFalse(joined.exists())

            obj_dir = firm / "obj"
            obj_dir.mkdir()
            object_a = obj_dir / "a.o"
            object_b = obj_dir / "b.o"
            extra = firm / "extra.bin"
            object_a.write_bytes(b"A")
            object_b.write_bytes(b"B")
            extra.write_bytes(b"extra")
            subprocess.run(
                [
                    sys.executable,
                    str(result.build_support_path),
                    "remove",
                    "obj/*.o",
                    extra.name,
                    "missing.bin",
                ],
                cwd=firm,
                check=True,
            )
            self.assertEqual(list(obj_dir.glob("*.o")), [])
            self.assertFalse(extra.exists())

            version = firm / "version.c"
            self.assertFalse(version.exists())
            subprocess.run(
                [sys.executable, str(result.build_support_path), "touch", version.name],
                cwd=firm,
                check=True,
            )
            self.assertTrue(version.is_file())

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
