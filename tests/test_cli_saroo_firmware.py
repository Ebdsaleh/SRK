"""CLI coverage for safe SAROO Firm_Saturn source preparation."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.cli import main


MAKEFILE = """OBJ\t=\tobj/main.o  \\\n\t\tobj/sci_shell.o  \\\n\t\tobj/version.o\n"""

SHELL = """#include \"main.h\"\n#include \"smpc.h\"\n\nvoid sci_shell(void)\n{\n\tif(0){}\n\t\tCMD(q) {\n\t\t\tbreak;\n\t\t}\n}\n"""


class SarooFirmwareCLITests(unittest.TestCase):
    def test_prepare_saroo_firmware_creates_separate_build_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "SAROO"
            firm = source / "Firm_Saturn"
            firm.mkdir(parents=True)
            (firm / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
            (firm / "sci_shell.c").write_text(SHELL, encoding="utf-8", newline="\n")
            original_makefile = (firm / "Makefile").read_bytes()
            output = temp / "SAROO-SRK"
            stdout = io.StringIO()
            stderr = io.StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["prepare-saroo-firmware", str(source), str(output)])

            self.assertEqual(result, 0, stderr.getvalue())
            self.assertTrue((output / "Firm_Saturn" / "srk_capture_helper.c").is_file())
            self.assertTrue((output / "Firm_Saturn" / "srk_capture_helper.h").is_file())
            self.assertEqual((firm / "Makefile").read_bytes(), original_makefile)
            rendered = stdout.getvalue()
            self.assertIn("Original SAROO source was not modified.", rendered)
            self.assertIn("srkwl, srkwh", rendered)


if __name__ == "__main__":
    unittest.main()
