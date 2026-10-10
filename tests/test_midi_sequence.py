"""Regression tests for SRK's deterministic MIDI playback scheduler."""

from __future__ import annotations

import unittest

from rikai_kotoba.core.midi_sequence import (
    MIDI_DEFAULT_TEMPO_US_PER_QUARTER,
    MIDI_PITCH_BEND_CENTER,
    MidiTimingError,
    build_midi_playback_schedule,
    build_midi_tempo_map,
    midi_tick_to_microseconds,
)
from rikai_kotoba.formats.midi import MidiEvent, MidiFile, MidiHeader, MidiTrack


def _midi(*events: MidiEvent, division: int = 480, format_type: int = 0) -> MidiFile:
    return MidiFile(
        header=MidiHeader(
            format_type=format_type,
            track_count=1,
            division=division,
        ),
        tracks=(MidiTrack(events=tuple(events)),),
    )


class MidiSequenceTests(unittest.TestCase):
    def test_default_tempo_maps_one_quarter_note_to_half_a_second(self):
        midi = _midi(
            MidiEvent(480, 480, "note_on", 0x90, channel=0, data=(60, 100)),
            MidiEvent(0, 480, "end_of_track", 0xFF, meta_type=0x2F),
        )

        tempo_map = build_midi_tempo_map(midi)

        self.assertEqual(len(tempo_map.points), 1)
        self.assertEqual(
            tempo_map.points[0].us_per_quarter,
            MIDI_DEFAULT_TEMPO_US_PER_QUARTER,
        )
        self.assertEqual(midi_tick_to_microseconds(tempo_map, 480), 500000)

    def test_tempo_change_preserves_exact_piecewise_timing(self):
        midi = _midi(
            MidiEvent(
                480,
                480,
                "set_tempo",
                0xFF,
                meta_type=0x51,
                payload=(250000).to_bytes(3, "big"),
            ),
            MidiEvent(480, 960, "note_on", 0x90, channel=0, data=(64, 90)),
            MidiEvent(0, 960, "end_of_track", 0xFF, meta_type=0x2F),
        )

        tempo_map = build_midi_tempo_map(midi)

        self.assertEqual([point.tick for point in tempo_map.points], [0, 480])
        self.assertEqual(tempo_map.points[1].time_us, 500000)
        self.assertEqual(midi_tick_to_microseconds(tempo_map, 960), 750000)

    def test_last_tempo_event_at_same_tick_owns_following_segment(self):
        midi = _midi(
            MidiEvent(
                0,
                0,
                "set_tempo",
                0xFF,
                meta_type=0x51,
                payload=(600000).to_bytes(3, "big"),
            ),
            MidiEvent(
                0,
                0,
                "set_tempo",
                0xFF,
                meta_type=0x51,
                payload=(300000).to_bytes(3, "big"),
            ),
            MidiEvent(480, 480, "end_of_track", 0xFF, meta_type=0x2F),
        )

        tempo_map = build_midi_tempo_map(midi)

        self.assertEqual(len(tempo_map.points), 1)
        self.assertEqual(tempo_map.points[0].us_per_quarter, 300000)
        self.assertEqual(midi_tick_to_microseconds(tempo_map, 480), 300000)

    def test_schedule_tracks_explicit_bank_program_mix_and_note_state(self):
        midi = _midi(
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(0, 2)),
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(32, 5)),
            MidiEvent(0, 0, "program_change", 0xC0, channel=0, data=(17,)),
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(7, 100)),
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(10, 32)),
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(11, 110)),
            MidiEvent(120, 120, "note_on", 0x90, channel=0, data=(60, 96)),
            MidiEvent(0, 120, "end_of_track", 0xFF, meta_type=0x2F),
        )

        schedule = build_midi_playback_schedule(midi)
        note = next(item for item in schedule if item.event.kind == "note_on")

        self.assertEqual(note.time_us, 125000)
        self.assertIsNotNone(note.channel_state)
        assert note.channel_state is not None
        self.assertEqual(note.channel_state.bank_msb, 2)
        self.assertEqual(note.channel_state.bank_lsb, 5)
        self.assertEqual(note.channel_state.program, 17)
        self.assertEqual(note.channel_state.volume, 100)
        self.assertEqual(note.channel_state.pan, 32)
        self.assertEqual(note.channel_state.expression, 110)
        self.assertEqual(note.channel_state.pitch_bend, MIDI_PITCH_BEND_CENTER)
        self.assertFalse(note.channel_state.sustain)

    def test_channel_state_is_isolated_between_midi_channels(self):
        midi = _midi(
            MidiEvent(0, 0, "program_change", 0xC0, channel=0, data=(3,)),
            MidiEvent(0, 0, "program_change", 0xC1, channel=1, data=(9,)),
            MidiEvent(0, 0, "note_on", 0x90, channel=0, data=(60, 80)),
            MidiEvent(0, 0, "note_on", 0x91, channel=1, data=(67, 90)),
            MidiEvent(0, 0, "end_of_track", 0xFF, meta_type=0x2F),
        )

        notes = [
            item for item in build_midi_playback_schedule(midi)
            if item.event.kind == "note_on"
        ]

        self.assertEqual(notes[0].channel_state.program, 3)
        self.assertEqual(notes[1].channel_state.program, 9)

    def test_sustain_and_pitch_bend_are_normalized_before_note_event(self):
        midi = _midi(
            MidiEvent(0, 0, "control_change", 0xB0, channel=0, data=(64, 127)),
            MidiEvent(0, 0, "pitch_bend", 0xE0, channel=0, data=(0, 96)),
            MidiEvent(0, 0, "note_on", 0x90, channel=0, data=(72, 100)),
            MidiEvent(0, 0, "end_of_track", 0xFF, meta_type=0x2F),
        )

        note = next(
            item for item in build_midi_playback_schedule(midi)
            if item.event.kind == "note_on"
        )

        self.assertTrue(note.channel_state.sustain)
        self.assertEqual(note.channel_state.pitch_bend, 12288)

    def test_rejects_smpte_and_format2_as_single_merged_playback_timeline(self):
        smpte = _midi(
            MidiEvent(0, 0, "end_of_track", 0xFF, meta_type=0x2F),
            division=0xE728,
        )
        with self.assertRaisesRegex(MidiTimingError, "SMPTE"):
            build_midi_playback_schedule(smpte)

        format2 = _midi(
            MidiEvent(0, 0, "end_of_track", 0xFF, meta_type=0x2F),
            format_type=2,
        )
        with self.assertRaisesRegex(MidiTimingError, "format 2"):
            build_midi_playback_schedule(format2)


if __name__ == "__main__":
    unittest.main()
