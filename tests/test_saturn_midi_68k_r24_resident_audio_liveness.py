"""Register-liveness regression for R24 audio telemetry inside the R23 scheduler."""

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_resident_audio_service import (
    _emit_r24_active_increment,
)


class _TraceAssembler:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name, args))
        return record


class SaturnMidi68KR24ResidentAudioLivenessTests(unittest.TestCase):
    def test_peak_telemetry_does_not_clobber_live_timestamp_d2_d3(self):
        asm = _TraceAssembler()
        _emit_r24_active_increment(asm, prefix="probe")
        data_register_operands = []
        for name, args in asm.calls:
            if name == "move_absw_to_dn":
                data_register_operands.append(args[1])
            elif name == "addq_w":
                data_register_operands.append(args[1])
            elif name == "move_dn_absw":
                data_register_operands.append(args[0])
            elif name == "cmp_dn_w":
                data_register_operands.extend(args)
        self.assertNotIn(2, data_register_operands)
        self.assertNotIn(3, data_register_operands)
        self.assertIn(4, data_register_operands)

    def test_peak_compare_uses_scratch_d4_against_active_d0(self):
        asm = _TraceAssembler()
        _emit_r24_active_increment(asm, prefix="probe")
        self.assertIn(("cmp_dn_w", (4, 0)), asm.calls)
        self.assertIn(("branch_word", (0x6300, "probe_peak_done")), asm.calls)


if __name__ == "__main__":
    unittest.main()
