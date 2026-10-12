"""Compiler-facing contracts for the R24 Saturn SH-2 FRT backend."""

import re
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_frt_backend import (
    render_saturn_midi_68k_r24_frt_backend_header,
    render_saturn_midi_68k_r24_frt_backend_source,
    validate_saturn_midi_68k_r24_frt_backend_contract,
)


class SaturnMidi68KR24FRTBackendTests(unittest.TestCase):
    def test_contract_validates(self):
        validate_saturn_midi_68k_r24_frt_backend_contract()

    def test_header_exposes_state_and_explicit_source_frequency(self):
        header = render_saturn_midi_68k_r24_frt_backend_header()
        self.assertIn("SRK_MIDI_R24_FRT_CLOCK", header)
        self.assertIn("srk_saturn_midi_r24_frt_configure_div128", header)
        self.assertIn("unsigned long source_hz", header)

    def test_source_uses_only_reviewed_sh2_frt_registers(self):
        source = render_saturn_midi_68k_r24_frt_backend_source()
        self.assertIn("0xFFFFFE12UL", source)
        self.assertIn("0xFFFFFE13UL", source)
        self.assertIn("0xFFFFFE16UL", source)
        self.assertNotIn("SS_TIMER", source)
        self.assertNotIn("0x25A00000", source)
        self.assertNotIn("0x25B00000", source)

    def test_source_extends_wrap_and_uses_64_bit_conversion_intermediate(self):
        source = render_saturn_midi_68k_r24_frt_backend_source()
        self.assertIn("65536UL -", source)
        self.assertIn("unsigned long long numerator", source)
        self.assertIn("1000000ULL", source)
        self.assertIn("SRK_R24_FRT_DIVIDER", source)

    def test_renderer_does_not_guess_physical_saturn_clock_frequency(self):
        source = render_saturn_midi_68k_r24_frt_backend_source()
        self.assertNotIn("26874100", source)
        self.assertNotIn("28636360", source)
        # Equality is expected in the guard `source_hz == 0UL`; reject only a
        # single-equals assignment/default such as `source_hz = 26874100UL`.
        self.assertIsNone(re.search(r"\bsource_hz\s*=(?!=)", source))


if __name__ == "__main__":
    unittest.main()
