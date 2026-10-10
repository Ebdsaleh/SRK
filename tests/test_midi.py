"""Regression tests for SRK's platform-neutral Standard MIDI File parser."""

from __future__ import annotations

import unittest

from rikai_kotoba.formats.midi import (
    MidiFormatError,
    merge_midi_events,
    parse_midi_bytes,
)


def _be16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _be32(value: int) -> bytes:
    return value.to_bytes(4, "big")


def _vlq(value: int) -> bytes:
    if value < 0 or value > 0x0FFFFFFF:
        raise ValueError(value)
    encoded = [value & 0x7F]
    value >>= 7
    while value:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.reverse()
    return bytes(encoded)


def _track(payload: bytes) -> bytes:
    return b"MTrk" + _be32(len(payload)) + payload


def _midi(format_type: int, division: int, *tracks: bytes) -> bytes:
    header = b"MThd" + _be32(6) + _be16(format_type) + _be16(len(tracks)) + _be16(division)
    return header + b"".join(_track(track) for track in tracks)


class MidiFormatTests(unittest.TestCase):
    def test_format0_decodes_playback_events_running_status_and_tempo(self):
        track = b"".join(
            (
                _vlq(0) + bytes((0xC0, 0x05)),
                _vlq(0) + bytes((0xB0, 0x00, 0x02)),
                _vlq(0) + bytes((0x90, 0x3C, 0x64)),
                _vlq(96) + bytes((0x3C, 0x00)),
                _vlq(0) + bytes((0xE0, 0x00, 0x40)),
                _vlq(0) + bytes((0xFF, 0x51, 0x03, 0x07, 0xA1, 0x20)),
                _vlq(0) + bytes((0xFF, 0x2F, 0x00)),
            )
        )

        midi = parse_midi_bytes(_midi(0, 96, track))

        self.assertEqual(midi.header.format_type, 0)
        self.assertEqual(midi.header.track_count, 1)
        self.assertEqual(midi.header.ticks_per_quarter, 96)
        self.assertFalse(midi.header.uses_smpte_timing)

        events = midi.tracks[0].events
        self.assertEqual(
            [event.kind for event in events],
            [
                "program_change",
                "control_change",
                "note_on",
                "note_off",
                "pitch_bend",
                "set_tempo",
                "end_of_track",
            ],
        )
        self.assertEqual(events[0].channel, 0)
        self.assertEqual(events[0].data, (5,))
        self.assertEqual(events[1].data, (0, 2))
        self.assertEqual(events[2].data, (60, 100))
        self.assertEqual(events[3].tick, 96)
        self.assertEqual(events[3].status, 0x90)
        self.assertEqual(events[3].data, (60, 0))
        self.assertEqual(events[4].pitch_bend, 8192)
        self.assertEqual(events[5].tempo_us_per_quarter, 500000)

    def test_format1_merges_tracks_in_deterministic_absolute_tick_order(self):
        conductor = b"".join(
            (
                _vlq(0) + bytes((0xFF, 0x51, 0x03, 0x07, 0xA1, 0x20)),
                _vlq(192) + bytes((0xFF, 0x2F, 0x00)),
            )
        )
        notes = b"".join(
            (
                _vlq(48) + bytes((0x90, 60, 90)),
                _vlq(96) + bytes((0x80, 60, 40)),
                _vlq(0) + bytes((0xFF, 0x2F, 0x00)),
            )
        )

        midi = parse_midi_bytes(_midi(1, 96, conductor, notes))
        merged = merge_midi_events(midi)

        self.assertEqual(midi.header.track_count, 2)
        self.assertEqual(
            [(item.track_index, item.event.tick, item.event.kind) for item in merged],
            [
                (0, 0, "set_tempo"),
                (1, 48, "note_on"),
                (1, 144, "note_off"),
                (1, 144, "end_of_track"),
                (0, 192, "end_of_track"),
            ],
        )

    def test_sysex_and_common_metadata_are_preserved_without_interpretation_loss(self):
        track = b"".join(
            (
                _vlq(0) + bytes((0xFF, 0x03, 0x04)) + b"Test",
                _vlq(0) + bytes((0xF0, 0x03, 0x43, 0x12, 0xF7)),
                _vlq(0) + bytes((0xFF, 0x58, 0x04, 0x04, 0x02, 0x18, 0x08)),
                _vlq(0) + bytes((0xFF, 0x2F, 0x00)),
            )
        )

        events = parse_midi_bytes(_midi(0, 480, track)).tracks[0].events

        self.assertEqual(events[0].kind, "track_name")
        self.assertEqual(events[0].payload, b"Test")
        self.assertEqual(events[1].kind, "sysex")
        self.assertEqual(events[1].payload, bytes((0x43, 0x12, 0xF7)))
        self.assertEqual(events[2].kind, "time_signature")
        self.assertEqual(events[2].payload, bytes((0x04, 0x02, 0x18, 0x08)))

    def test_smpte_division_is_preserved_for_later_timing_policy(self):
        track = _vlq(0) + bytes((0xFF, 0x2F, 0x00))
        midi = parse_midi_bytes(_midi(0, 0xE728, track))

        self.assertTrue(midi.header.uses_smpte_timing)
        self.assertIsNone(midi.header.ticks_per_quarter)
        self.assertEqual(midi.header.division, 0xE728)

    def test_rejects_running_status_without_preceding_channel_status(self):
        track = _vlq(0) + bytes((60, 100)) + _vlq(0) + bytes((0xFF, 0x2F, 0x00))
        with self.assertRaisesRegex(MidiFormatError, "running status"):
            parse_midi_bytes(_midi(0, 96, track))

    def test_rejects_structural_corruption_and_missing_end_of_track(self):
        with self.assertRaisesRegex(MidiFormatError, "MThd"):
            parse_midi_bytes(b"NOT MIDI DATA!!")

        missing_end = _vlq(0) + bytes((0x90, 60, 100))
        with self.assertRaisesRegex(MidiFormatError, "missing end-of-track"):
            parse_midi_bytes(_midi(0, 96, missing_end))

        bad_tempo = b"".join(
            (
                _vlq(0) + bytes((0xFF, 0x51, 0x02, 0x07, 0xA1)),
                _vlq(0) + bytes((0xFF, 0x2F, 0x00)),
            )
        )
        with self.assertRaisesRegex(MidiFormatError, "set-tempo"):
            parse_midi_bytes(_midi(0, 96, bad_tempo))


if __name__ == "__main__":
    unittest.main()
