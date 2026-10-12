import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_clock import (
    SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS,
    SaturnMidi68KR24ClockCalibration,
    SaturnMidi68KR24ClockError,
    SaturnMidi68KR24FRTClockState,
    r24_frt_ticks_to_microseconds,
    sample_saturn_midi_68k_r24_frt_clock,
    validate_saturn_midi_68k_r24_clock_contract,
)


class SaturnMidi68KR24ClockTests(unittest.TestCase):
    def setUp(self):
        self.calibration = SaturnMidi68KR24ClockCalibration(26_874_100)

    def test_register_and_wrap_contract_validates(self):
        validate_saturn_midi_68k_r24_clock_contract()
        self.assertGreater(float(self.calibration.wrap_period_us), 250_000.0)
        self.assertLess(float(self.calibration.wrap_period_us), 400_000.0)

    def test_single_wrap_extends_monotonically(self):
        state = sample_saturn_midi_68k_r24_frt_clock(
            SaturnMidi68KR24FRTClockState(), 0xFFF0, self.calibration
        )
        state = sample_saturn_midi_68k_r24_frt_clock(state, 0x0010, self.calibration)
        self.assertEqual(state.extended_ticks - state.origin_ticks, 0x20)
        self.assertGreater(state.elapsed_us, 0)
        before = state.elapsed_us
        state = sample_saturn_midi_68k_r24_frt_clock(state, 0x1010, self.calibration)
        self.assertGreater(state.elapsed_us, before)

    def test_repeated_frame_sized_samples_can_span_full_reference_song(self):
        # Exercise the 16-bit extension for longer than the 108.151354-second
        # reference song.  Each synthetic poll advances 3000 FRT ticks, safely
        # below one wrap, like a normal high-frequency producer poll.
        state = SaturnMidi68KR24FRTClockState()
        raw = 0
        state = sample_saturn_midi_68k_r24_frt_clock(state, raw, self.calibration)
        while state.elapsed_us <= 109_000_000:
            raw = (raw + 3000) % SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS
            state = sample_saturn_midi_68k_r24_frt_clock(state, raw, self.calibration)
        self.assertGreater(state.elapsed_us, 108_151_354)
        self.assertGreater(state.sample_count, 1000)

    def test_tick_conversion_is_integer_and_monotonic(self):
        values = [r24_frt_ticks_to_microseconds(ticks, self.calibration) for ticks in range(0, 10000, 137)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 0)
        self.assertGreater(values[-1], 0)

    def test_rejects_invalid_samples_and_calibration(self):
        with self.assertRaises(SaturnMidi68KR24ClockError):
            sample_saturn_midi_68k_r24_frt_clock(
                SaturnMidi68KR24FRTClockState(),
                -1,
                self.calibration,
            )
        with self.assertRaises(SaturnMidi68KR24ClockError):
            sample_saturn_midi_68k_r24_frt_clock(
                SaturnMidi68KR24FRTClockState(),
                SATURN_MIDI_68K_R24_FRT_COUNTER_MODULUS,
                self.calibration,
            )
        with self.assertRaises(SaturnMidi68KR24ClockError):
            SaturnMidi68KR24ClockCalibration(0).validate()


if __name__ == "__main__":
    unittest.main()
