from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_note_audit import (
    SATURN_MIDI_68K_R25_OWNED_SLOTS,
    SATURN_MIDI_68K_R25_RELEASE_CAPACITY_AUDIT_US,
    SATURN_MIDI_68K_R25_TARGET_RELEASE_US,
    SaturnMidi68KR25NoteAuditError,
    audit_saturn_midi_68k_r25_note_spans,
    build_saturn_midi_68k_r25_note_spans,
    peak_saturn_midi_68k_r25_voice_pressure,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)


_ROOT = Path(__file__).resolve().parents[1]
_REFERENCE = _ROOT / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


class SaturnMidi68KR25NoteAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = build_saturn_midi_68k_r24_song_profile(_REFERENCE)
        validate_saturn_midi_68k_r24_reference_song(cls.profile)

    def test_reference_song_forms_exact_note_span_count(self):
        spans = build_saturn_midi_68k_r25_note_spans(self.profile.program)
        self.assertEqual(len(spans), SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON)
        self.assertEqual(len(spans), SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF)
        self.assertEqual(spans[0].start_us, 0)
        self.assertTrue(all(span.duration_us > 0 for span in spans))

    def test_reference_song_contains_genuinely_short_notes(self):
        audit = audit_saturn_midi_68k_r25_note_spans(self.profile.program)
        self.assertLess(audit.minimum_duration_us, 250_000)
        self.assertGreater(audit.shorter_than_250ms, 0)
        self.assertGreater(audit.maximum_duration_us, 2_000_000)
        self.assertGreater(audit.median_duration_us, 0)

    def test_four_slots_cover_target_and_half_second_release_tail_pressure(self):
        audit = audit_saturn_midi_68k_r25_note_spans(self.profile.program)
        self.assertEqual(audit.release_target_us, SATURN_MIDI_68K_R25_TARGET_RELEASE_US)
        self.assertEqual(
            audit.release_capacity_audit_us,
            SATURN_MIDI_68K_R25_RELEASE_CAPACITY_AUDIT_US,
        )
        self.assertLessEqual(audit.peak_with_release_target, SATURN_MIDI_68K_R25_OWNED_SLOTS)
        self.assertLessEqual(
            audit.peak_with_release_capacity_audit,
            SATURN_MIDI_68K_R25_OWNED_SLOTS,
        )

    def test_negative_release_window_is_rejected(self):
        spans = build_saturn_midi_68k_r25_note_spans(self.profile.program)
        with self.assertRaisesRegex(SaturnMidi68KR25NoteAuditError, "non-negative"):
            peak_saturn_midi_68k_r25_voice_pressure(spans, release_us=-1)

    def test_orphan_note_off_is_rejected(self):
        program = SaturnMidiProgram(
            records=(
                SaturnMidiRecord(
                    time_us=100,
                    opcode=SaturnMidiOpcode.NOTE_OFF,
                    channel=0,
                    data0=60,
                    data1=64,
                ),
            ),
            duration_us=100,
        )
        with self.assertRaisesRegex(SaturnMidi68KR25NoteAuditError, "orphan Note Off"):
            build_saturn_midi_68k_r25_note_spans(program)


if __name__ == "__main__":
    unittest.main()
