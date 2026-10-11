"""CLI surface regressions for the continuous MIDI 68K service milestone."""

from __future__ import annotations

from pathlib import Path
import unittest

import rikai_kotoba.tools.saturn_midi_68k_resident_stream_compile_probe as compile_cli
import rikai_kotoba.tools.saturn_midi_68k_resident_stream_full_build_gate as build_cli


class SaturnMidi68KResidentStreamCLITests(unittest.TestCase):
    def test_compile_cli_surfaces_refill_scheduler_and_both_object_hashes(self):
        source = Path(compile_cli.__file__).read_text(encoding="utf-8")
        self.assertIn("multi-batch/timestamp service compiler gate", source)
        self.assertIn("Queue refill", source)
        self.assertIn("Timestamp scheduler", source)
        self.assertIn("Clock publication", source)
        self.assertIn("Resident object SHA-256", source)
        self.assertIn("Producer object SHA-256", source)
        self.assertIn("MIDI-driven SCSP", source)

    def test_full_build_cli_keeps_r21_callable_and_new_service_inert(self):
        source = Path(build_cli.__file__).read_text(encoding="utf-8")
        self.assertIn("Accepted R21 baseline", source)
        self.assertIn("Existing R21 binding", source)
        self.assertIn("PRESERVED", source)
        self.assertIn("Resident stream installed", source)
        self.assertIn("Resident stream executed", source)
        self.assertIn("Stream producer invoked", source)
        self.assertIn("Do not deploy this inert integration image", source)


if __name__ == "__main__":
    unittest.main()
