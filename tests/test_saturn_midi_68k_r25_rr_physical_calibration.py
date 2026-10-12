"""Regression contracts for the R25 physical RR calibration source gate."""

import unittest

from rikai_kotoba.hardware.saturn import midi_68k_r25_resident_audio_service as _r25
from rikai_kotoba.hardware.saturn.midi_68k_r25_envelope import SaturnMidi68KR25EnvelopeError
from rikai_kotoba.hardware.saturn.midi_68k_r25_note_audit import SATURN_MIDI_68K_R25_TARGET_RELEASE_US
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_physical_calibration import (
    SATURN_MIDI_68K_R25_ACCEPTED_RR16_IMAGE_SHA256,
    SATURN_MIDI_68K_R25_CALIBRATION_END_US,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US,
    SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US,
    SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US,
    build_saturn_midi_68k_r25_rr_calibration_program,
    build_saturn_midi_68k_r25_rr_physical_calibration_plan,
    build_srk_saturn_midi_68k_r25_rr_calibration_service_image,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_source,
    validate_saturn_midi_68k_r25_production_rr16_anchor,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KR25RRPhysicalCalibrationTests(unittest.TestCase):
    def test_accepted_rr16_production_image_is_pinned(self):
        validate_saturn_midi_68k_r25_production_rr16_anchor()
        image = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=16
        )
        self.assertEqual(image.sha256, SATURN_MIDI_68K_R25_ACCEPTED_RR16_IMAGE_SHA256)
        self.assertEqual(_r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US, SATURN_MIDI_68K_R25_TARGET_RELEASE_US)

    def test_calibration_window_changes_only_calibration_render_and_restores_production(self):
        production_before = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=16
        )
        calibration = build_srk_saturn_midi_68k_r25_rr_calibration_service_image(
            release_rate=16
        )
        production_after = _r25.build_srk_saturn_midi_68k_r25_resident_audio_service_image(
            release_rate=16
        )
        self.assertEqual(production_before.sha256, SATURN_MIDI_68K_R25_ACCEPTED_RR16_IMAGE_SHA256)
        self.assertEqual(production_after, production_before)
        self.assertNotEqual(calibration.sha256, production_before.sha256)
        self.assertEqual(calibration.word_count, production_before.word_count)
        self.assertEqual(calibration.end_address, production_before.end_address)
        self.assertEqual(_r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US, SATURN_MIDI_68K_R25_TARGET_RELEASE_US)

    def test_calibration_header_names_two_second_window_and_explicit_rr(self):
        header = render_srk_saturn_midi_68k_r25_rr_calibration_service_header(
            release_rate=16
        )
        self.assertIn("R25_RELEASE_RATE 16u", header)
        self.assertIn("R25_EG2_WORD 0x3C10u", header)
        self.assertIn("R25_TARGET_RELEASE_US 2000000UL", header)
        production = _r25.render_srk_saturn_midi_68k_r25_resident_audio_service_header(
            release_rate=16
        )
        self.assertIn("R25_TARGET_RELEASE_US 120000UL", production)

    def test_calibration_program_is_one_a4_note_with_note_off_at_1250ms(self):
        program = build_saturn_midi_68k_r25_rr_calibration_program()
        self.assertEqual(len(program.records), 2)
        note_on, note_off = program.records
        self.assertEqual(note_on.opcode, SaturnMidiOpcode.NOTE_ON)
        self.assertEqual(note_off.opcode, SaturnMidiOpcode.NOTE_OFF)
        self.assertEqual(note_on.time_us, SATURN_MIDI_68K_R25_CALIBRATION_NOTE_ON_US)
        self.assertEqual(note_off.time_us, SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US)
        self.assertEqual(note_on.data0, SATURN_MIDI_68K_R25_CALIBRATION_NOTE)
        self.assertEqual(note_off.data0, SATURN_MIDI_68K_R25_CALIBRATION_NOTE)
        self.assertEqual(program.duration_us, SATURN_MIDI_68K_R25_CALIBRATION_NOTE_OFF_US)

    def test_plan_is_operator_observed_and_never_selects_production_rr(self):
        plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=16)
        self.assertEqual(plan.release_rate, 16)
        self.assertEqual(plan.note, 69)
        self.assertEqual(plan.observation_window_us, SATURN_MIDI_68K_R25_CALIBRATION_OBSERVATION_US)
        self.assertEqual(plan.observation_end_us, SATURN_MIDI_68K_R25_CALIBRATION_END_US)
        self.assertEqual(plan.record_count, 2)
        self.assertEqual(plan.batch_count, 1)
        self.assertFalse(plan.production_rr_selected)
        self.assertFalse(plan.envelope_readback_available)
        self.assertEqual(plan.measurement_mode, "operator-observed-audio")

    def test_rr_is_required_and_invalid_rr_fails_closed(self):
        with self.assertRaises(TypeError):
            build_saturn_midi_68k_r25_rr_physical_calibration_plan()  # type: ignore[call-arg]
        with self.assertRaisesRegex(SaturnMidi68KR25EnvelopeError, "RR"):
            build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=32)

    def test_calibration_source_remains_inert_constant_data(self):
        source = render_srk_saturn_midi_68k_r25_rr_calibration_service_source(
            release_rate=16
        )
        self.assertIn("srk_saturn_midi_68k_r25_resident_audio_service_program", source)
        self.assertNotIn("volatile", source)
        self.assertNotIn("main(", source)
        self.assertNotIn("0x25B00000", source)
        self.assertEqual(_r25.SATURN_MIDI_68K_R25_TARGET_RELEASE_US, SATURN_MIDI_68K_R25_TARGET_RELEASE_US)


if __name__ == "__main__":
    unittest.main()
