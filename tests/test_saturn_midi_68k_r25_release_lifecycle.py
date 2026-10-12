from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH,
    build_saturn_midi_68k_r24_song_profile,
)
from rikai_kotoba.hardware.saturn.midi_68k_r25_release_lifecycle import (
    SaturnMidi68KR25ReleaseLifecycleError,
    SaturnMidi68KR25SlotPhase,
    advance_saturn_midi_68k_r25_releases,
    build_saturn_midi_68k_r25_release_state,
    note_off_saturn_midi_68k_r25_release,
    note_on_saturn_midi_68k_r25_release,
    trace_saturn_midi_68k_r25_release_lifecycle,
)


_REFERENCE = Path(__file__).resolve().parents[1] / SATURN_MIDI_68K_R24_REFERENCE_RELATIVE_PATH


class SaturnMidi68KR25ReleaseLifecycleTests(unittest.TestCase):
    def test_note_off_moves_held_slot_to_releasing_without_freeing_it(self):
        state = build_saturn_midi_68k_r25_release_state()
        state = note_on_saturn_midi_68k_r25_release(
            state, now_us=1000, channel=2, note=72, velocity=90
        )
        state = note_off_saturn_midi_68k_r25_release(
            state, now_us=2000, channel=2, note=72, release_us=120_000
        )
        self.assertEqual(state.held_count, 0)
        self.assertEqual(state.releasing_count, 1)
        self.assertEqual(state.owned_count, 1)
        self.assertEqual(state.slots[0].phase, SaturnMidi68KR25SlotPhase.RELEASING)
        self.assertEqual(state.slots[0].release_deadline_us, 122_000)
        self.assertEqual(state.telemetry.release_started_count, 1)

    def test_release_retires_only_at_reviewed_deadline(self):
        state = build_saturn_midi_68k_r25_release_state()
        state = note_on_saturn_midi_68k_r25_release(
            state, now_us=0, channel=0, note=60, velocity=100
        )
        state = note_off_saturn_midi_68k_r25_release(
            state, now_us=100, channel=0, note=60, release_us=1000
        )
        state = advance_saturn_midi_68k_r25_releases(state, 1099)
        self.assertEqual(state.releasing_count, 1)
        state = advance_saturn_midi_68k_r25_releases(state, 1100)
        self.assertEqual(state.owned_count, 0)
        self.assertEqual(state.telemetry.release_completed_count, 1)

    def test_same_key_retrigger_reclaims_its_releasing_slot(self):
        state = build_saturn_midi_68k_r25_release_state()
        state = note_on_saturn_midi_68k_r25_release(
            state, now_us=0, channel=0, note=60, velocity=100
        )
        state = note_off_saturn_midi_68k_r25_release(
            state, now_us=10, channel=0, note=60, release_us=1000
        )
        state = note_on_saturn_midi_68k_r25_release(
            state, now_us=20, channel=0, note=60, velocity=70
        )
        self.assertEqual(state.held_count, 1)
        self.assertEqual(state.releasing_count, 0)
        self.assertEqual(state.slots[0].velocity, 70)
        self.assertEqual(state.telemetry.retrigger_count, 1)
        self.assertEqual(state.telemetry.release_cancelled_count, 1)

    def test_fifth_simultaneous_key_is_busy_without_stealing(self):
        state = build_saturn_midi_68k_r25_release_state()
        for note in range(60, 65):
            state = note_on_saturn_midi_68k_r25_release(
                state, now_us=note, channel=0, note=note, velocity=100
            )
        self.assertEqual(state.held_count, 4)
        self.assertEqual(state.telemetry.note_on_count, 5)
        self.assertEqual(state.telemetry.busy_count, 1)
        self.assertEqual(tuple(slot.note for slot in state.slots), (60, 61, 62, 63))

    def test_reference_song_completes_all_release_tails_without_busy_or_stuck_slot(self):
        profile = build_saturn_midi_68k_r24_song_profile(_REFERENCE)
        final = trace_saturn_midi_68k_r25_release_lifecycle(profile.program)[-1]
        self.assertEqual(final.telemetry.note_on_count, 140)
        self.assertEqual(final.telemetry.note_off_count, 140)
        self.assertEqual(final.telemetry.release_started_count, 140)
        self.assertEqual(final.telemetry.release_completed_count, 138)
        self.assertEqual(final.telemetry.release_cancelled_count, 2)
        self.assertEqual(
            final.telemetry.release_completed_count
            + final.telemetry.release_cancelled_count,
            final.telemetry.release_started_count,
        )
        self.assertEqual(final.telemetry.busy_count, 0)
        self.assertEqual(final.held_count, 0)
        self.assertEqual(final.releasing_count, 0)
        self.assertLessEqual(final.telemetry.peak_owned, 4)

    def test_backwards_clock_and_nonpositive_release_are_rejected(self):
        state = advance_saturn_midi_68k_r25_releases(
            build_saturn_midi_68k_r25_release_state(), 100
        )
        with self.assertRaisesRegex(SaturnMidi68KR25ReleaseLifecycleError, "backwards"):
            advance_saturn_midi_68k_r25_releases(state, 99)
        with self.assertRaisesRegex(SaturnMidi68KR25ReleaseLifecycleError, "positive"):
            note_off_saturn_midi_68k_r25_release(
                state, now_us=100, channel=0, note=60, release_us=0
            )


if __name__ == "__main__":
    unittest.main()
