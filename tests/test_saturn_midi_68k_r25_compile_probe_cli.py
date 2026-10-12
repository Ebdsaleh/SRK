"""CLI contracts for the R25 inert RR compiler matrix."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.tools.saturn_midi_68k_r25_compile_probe import main


class SaturnMidi68KR25CompileProbeCliTests(unittest.TestCase):
    def test_successful_probe_returns_zero(self):
        result = SimpleNamespace(
            compiler=Path("sh-elf-gcc"),
            entries=tuple(range(32)),
            report_path=Path("report.json"),
            successful=True,
        )
        with patch(
            "rikai_kotoba.tools.saturn_midi_68k_r25_compile_probe."
            "probe_saturn_midi_68k_r25_rr_compile_matrix",
            return_value=result,
        ):
            self.assertEqual(main(["--saturn-root", "sdk", "--output", "out"]), 0)


if __name__ == "__main__":
    unittest.main()
