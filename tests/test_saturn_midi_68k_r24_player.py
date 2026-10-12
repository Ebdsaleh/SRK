from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_r24_player import (
    SATURN_MIDI_68K_R24_PLAYER_ERROR_CLOCK_BACKWARDS,
    default_saturn_midi_68k_r24_player_state,
    render_saturn_midi_68k_r24_player_header,
    render_saturn_midi_68k_r24_player_source,
    step_saturn_midi_68k_r24_player,
    validate_saturn_midi_68k_r24_complete_player,
)
from rikai_kotoba.hardware.saturn.midi_68k_r24_song import (
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)


class SaturnMidi68KR24PlayerTests(unittest.TestCase):
    @staticmethod
    def _profile():
        source = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "midi"
            / "cc0"
            / "melody-town-theme"
            / "Melody Town Theme.mid"
        )
        profile = build_saturn_midi_68k_r24_song_profile(source)
        validate_saturn_midi_68k_r24_reference_song(profile)
        return profile

    def test_complete_reference_song_publishes_sequences_one_through_ten(self):
        profile = self._profile()
        validate_saturn_midi_68k_r24_complete_player(profile.program)
        state = default_saturn_midi_68k_r24_player_state(profile.program)
        acknowledged = 0
        publications = []
        while not state.complete:
            step = step_saturn_midi_68k_r24_player(
                state,
                profile.duration_us,
                acknowledged,
            )
            state = step.state
            if step.publish_sequence is not None:
                publications.append(step.publish_sequence)
                acknowledged = step.publish_sequence
        self.assertEqual(publications, list(range(1, 11)))
        self.assertEqual(state.published_sequence, 10)
        self.assertTrue(state.complete)
        self.assertEqual(state.error, 0)

    def test_player_waits_for_ack_before_next_refill(self):
        profile = self._profile()
        state = default_saturn_midi_68k_r24_player_state(profile.program)
        first = step_saturn_midi_68k_r24_player(state, 0, 0)
        self.assertEqual(first.publish_sequence, 1)
        waiting = step_saturn_midi_68k_r24_player(first.state, 1_000_000, 0)
        self.assertIsNone(waiting.publish_sequence)
        self.assertEqual(waiting.state.next_batch_index, 1)
        second = step_saturn_midi_68k_r24_player(waiting.state, 7_000_000, 1)
        self.assertEqual(second.publish_sequence, 2)

    def test_player_rejects_backwards_clock(self):
        profile = self._profile()
        state = default_saturn_midi_68k_r24_player_state(profile.program)
        state = step_saturn_midi_68k_r24_player(state, 1000, 0).state
        failed = step_saturn_midi_68k_r24_player(state, 999, 0).state
        self.assertEqual(failed.error, SATURN_MIDI_68K_R24_PLAYER_ERROR_CLOCK_BACKWARDS)

    def test_c_renderer_contains_all_real_batches_and_no_fake_timer(self):
        profile = self._profile()
        header = render_saturn_midi_68k_r24_player_header()
        source = render_saturn_midi_68k_r24_player_source(profile.program)
        self.assertIn("SRK_MIDI_R24_PLAYER_STATE", header)
        self.assertIn("SRK_R24_BATCH_COUNT 10u", source)
        self.assertIn("SRK_R24_DURATION_US 108151354UL", source)
        self.assertEqual(source.count("static const SRK_SATURN_MIDI_EVENT srk_r24_song_batch_"), 10)
        self.assertIn("srk_saturn_midi_stream_clock_publish(now_us)", source)
        self.assertIn("srk_saturn_midi_stream_batch_acknowledged", source)
        self.assertNotIn("SS_TIMER", source)
        self.assertNotIn("FFFFFE12", source)


if __name__ == "__main__":
    unittest.main()
