from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.toolchain import SAROO_TOOL_REQUIREMENTS
from rikai_kotoba.tools.saroo_toolchain import main


class SarooToolchainCLITests(unittest.TestCase):
    def _populate(self, root: Path) -> None:
        bin_dir = root / "toolchain" / "bin"
        bin_dir.mkdir(parents=True)
        for requirement in SAROO_TOOL_REQUIREMENTS:
            filename = (
                "make.exe"
                if requirement.name == "make"
                else requirement.name + ".exe"
            )
            (bin_dir / filename).write_bytes(b"synthetic-tool")

    def test_ready_report_returns_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._populate(root)
            output = StringIO()
            with redirect_stdout(output):
                result = main(["--toolchain-root", str(root)])

            self.assertEqual(result, 0)
            text = output.getvalue()
            self.assertIn("Discovery result: READY", text)
            self.assertIn("sh-elf-gcc", text)
            self.assertIn("PATH is not modified", text)

    def test_missing_report_returns_nonzero_without_building(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = StringIO()
            with redirect_stdout(output):
                result = main(["--toolchain-root", str(root)])

            self.assertEqual(result, 2)
            text = output.getvalue()
            self.assertIn("Discovery result: NOT READY", text)
            self.assertIn("[MISSING]", text)

    def test_invalid_root_is_reported_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"
            error = StringIO()
            with redirect_stderr(error):
                result = main(["--toolchain-root", str(missing)])

            self.assertEqual(result, 2)
            self.assertIn("SarooToolchainError", error.getvalue())


if __name__ == "__main__":
    unittest.main()
