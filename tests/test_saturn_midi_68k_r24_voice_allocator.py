from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_voice_allocator import (
    SATURN_MIDI_68K_R24_OWNED_SLOTS,
    SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY,
    default_saturn_midi_68k_r24_voice_state,
    note_off_saturn_midi_68k_r24_voice,
    note_on_saturn_midi_68k_r24_voice,
    trace_saturn_midi_68k_r24_program_voices,
    validate_saturn_midi_68k_r24_reference_voice_trace,
)


class SaturnMidi68KR24VoiceAllocatorTests(unittest.TestCase):
    @staticmethod
    def _asset() -> Path:
        return (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "midi"
            / "cc0"
            / "melody-town-theme"
            / "Melody Town Theme.mid"
        )

    def test_reference_song_fits_exactly_two_owned_slots_without_stealing(self):
        profile = build_saturn_midi_68k_r24_song_profile(self._asset())
        validate_saturn_midi_68k_r24_reference_song(profile)
        trace = trace_saturn_midi_68k_r24_program_voices(profile.program)
        validate_saturn_midi_68k_r24_reference_voice_trace(trace)
        self.assertEqual(SATURN_MIDI_68K_R24_OWNED_SLOTS, 2)
        self.assertEqual(trace.peak_active, 2)
        self.assertEqual(trace.final_state.busy_count, 0)
        self.assertEqual(trace.final_state.key_on_count, 140)
        self.assertEqual(trace.final_state.key_off_count, 140)
        self.assertEqual(trace.final_state.active_count, 0)

    def test_allocator_uses_lowest_free_slot_then_second_slot(self):
        state = default_saturn_midi_68k_r24_voice_state()
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 76, 84)
        self.assertTrue(state.slots[0].active)
        self.assertFalse(state.slots[1].active)
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 79, 84)
        self.assertTrue(state.slots[0].active)
        self.assertTrue(state.slots[1].active)
        self.assertEqual((state.slots[0].note, state.slots[1].note), (76, 79))
        self.assertEqual(state.peak_active, 2)

    def test_third_simultaneous_note_is_rejected_not_stolen(self):
        state = default_saturn_midi_68k_r24_voice_state()
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 76, 84)
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 79, 84)
        before = state.slots
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 83, 84)
        self.assertEqual(state.slots, before)
        self.assertEqual(state.last_error, SATURN_MIDI_68K_R24_VOICE_ERROR_BUSY)
        self.assertEqual(state.busy_count, 1)

    def test_note_off_releases_only_matching_owner(self):
        state = default_saturn_midi_68k_r24_voice_state()
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 76, 84)
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 79, 84)
        unchanged = note_off_saturn_midi_68k_r24_voice(state, 0, 83)
        self.assertEqual(unchanged, state)
        state = note_off_saturn_midi_68k_r24_voice(state, 0, 76)
        self.assertFalse(state.slots[0].active)
        self.assertTrue(state.slots[1].active)
        state = note_off_saturn_midi_68k_r24_voice(state, 0, 79)
        self.assertEqual(state.active_count, 0)
        self.assertEqual(state.key_off_count, 2)

    def test_same_key_retrigger_reuses_owner_slot(self):
        state = default_saturn_midi_68k_r24_voice_state()
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 76, 80)
        first_generation = state.slots[0].generation
        state = note_on_saturn_midi_68k_r24_voice(state, 0, 76, 87)
        self.assertTrue(state.slots[0].active)
        self.assertFalse(state.slots[1].active)
        self.assertGreater(state.slots[0].generation, first_generation)
        self.assertEqual(state.slots[0].velocity, 87)
        self.assertEqual(state.key_on_count, 2)


if __name__ == "__main__":
    unittest.main()
