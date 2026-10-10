"""Regression tests for the silent multi-record MC68EC000 MIDI command engine."""

from __future__ import annotations

from pathlib import Path
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_command_engine import (
    SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS,
    SATURN_MIDI_68K_ACTIVE_NOTES_BYTES,
    SATURN_MIDI_68K_AUDIO_BOUNDARY,
    SATURN_MIDI_68K_CHANNEL_COUNT,
    SATURN_MIDI_68K_CHANNEL_STATE_WORDS,
    SATURN_MIDI_68K_CONTROLLER_ADDRESS,
    SATURN_MIDI_68K_CONTROLLER_BYTES,
    SATURN_MIDI_68K_STATE_ADDRESS,
    SATURN_MIDI_68K_STATE_END,
    SATURN_MIDI_68K_TELEMETRY_ADDRESS,
    SATURN_MIDI_68K_TELEMETRY_BYTES,
    SaturnMidi68KCommandEngineError,
    pack_srk_saturn_midi_68k_active_note_bitmap,
    pack_srk_saturn_midi_68k_controller_bytes,
    pack_srk_saturn_midi_68k_state_words,
    render_srk_saturn_midi_68k_command_state_header,
    simulate_srk_saturn_midi_68k_command_engine,
    validate_srk_saturn_midi_68k_command_layout,
)
from rikai_kotoba.hardware.saturn.midi_bridge import build_srk_saturn_midi_bridge_assets
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _REPO_ROOT / "integrations" / "saturn" / "standalone"


class SaturnMidi68KCommandEngineTests(unittest.TestCase):
    def test_layout_is_bounded_between_queue_and_existing_audio(self):
        validate_srk_saturn_midi_68k_command_layout()
        self.assertEqual(SATURN_MIDI_68K_STATE_ADDRESS, 0x00001200)
        self.assertEqual(SATURN_MIDI_68K_CONTROLLER_ADDRESS, 0x00001400)
        self.assertEqual(SATURN_MIDI_68K_ACTIVE_NOTES_ADDRESS, 0x00001C00)
        self.assertEqual(SATURN_MIDI_68K_TELEMETRY_ADDRESS, 0x00001D00)
        self.assertEqual(SATURN_MIDI_68K_TELEMETRY_BYTES, 0x100)
        self.assertEqual(SATURN_MIDI_68K_STATE_END, 0x00001E00)
        self.assertLessEqual(SATURN_MIDI_68K_STATE_END, SATURN_MIDI_68K_AUDIO_BOUNDARY)

    def test_canonical_batch_consumes_all_records_and_acknowledges_once(self):
        program = build_srk_saturn_midi_bridge_assets().program
        result = simulate_srk_saturn_midi_68k_command_engine(program)

        self.assertEqual(len(program.records), 27)
        self.assertEqual(result.processed_records, 27)
        self.assertEqual(result.read_index, 27)
        self.assertEqual(result.read_sequence, 1)
        self.assertEqual(result.last_error, 0)
        self.assertEqual(len(result.channels), SATURN_MIDI_68K_CHANNEL_COUNT)

    def test_canonical_batch_leaves_expected_channel_state(self):
        program = build_srk_saturn_midi_bridge_assets().program
        result = simulate_srk_saturn_midi_68k_command_engine(program)
        melody = result.channels[0]
        harmony = result.channels[1]

        self.assertEqual(
            (
                melody.bank_msb,
                melody.bank_lsb,
                melody.program,
                melody.volume,
                melody.pan,
                melody.expression,
                melody.sustain,
                melody.pitch_bend,
                melody.event_count,
            ),
            (0, 0, 1, 100, 96, 127, 0, 0x2000, 13),
        )
        self.assertEqual((melody.last_note, melody.last_velocity), (67, 48))
        self.assertEqual(melody.active_notes, ())

        self.assertEqual(
            (
                harmony.bank_msb,
                harmony.bank_lsb,
                harmony.program,
                harmony.volume,
                harmony.pan,
                harmony.expression,
                harmony.sustain,
                harmony.pitch_bend,
                harmony.event_count,
            ),
            (0, 0, 2, 90, 96, 110, 0, 0x2000, 14),
        )
        self.assertEqual((harmony.last_note, harmony.last_velocity), (55, 40))
        self.assertEqual(harmony.active_notes, ())

    def test_velocity_zero_note_on_is_a_logical_note_release(self):
        program = SaturnMidiProgram(
            records=(
                SaturnMidiRecord(0, SaturnMidiOpcode.NOTE_ON, 3, 60, 100),
                SaturnMidiRecord(1, SaturnMidiOpcode.NOTE_ON, 3, 60, 0),
            ),
            duration_us=1,
        )
        result = simulate_srk_saturn_midi_68k_command_engine(program)
        channel = result.channels[3]

        self.assertEqual(channel.active_notes, ())
        self.assertEqual(channel.note_velocities[60], 0)
        self.assertEqual((channel.last_note, channel.last_velocity), (60, 0))
        self.assertEqual(channel.event_count, 2)

    def test_every_srkm_opcode_updates_silent_state_without_audio(self):
        program = SaturnMidiProgram(
            records=(
                SaturnMidiRecord(0, SaturnMidiOpcode.NOTE_ON, 2, 60, 100),
                SaturnMidiRecord(1, SaturnMidiOpcode.POLY_AFTERTOUCH, 2, 60, 70),
                SaturnMidiRecord(2, SaturnMidiOpcode.CONTROL_CHANGE, 2, 7, 80),
                SaturnMidiRecord(3, SaturnMidiOpcode.PROGRAM_CHANGE, 2, 5, 0),
                SaturnMidiRecord(4, SaturnMidiOpcode.CHANNEL_PRESSURE, 2, 90, 0),
                SaturnMidiRecord(5, SaturnMidiOpcode.PITCH_BEND, 2, 1, 64),
                SaturnMidiRecord(6, SaturnMidiOpcode.NOTE_OFF, 2, 60, 64),
            ),
            duration_us=6,
        )
        result = simulate_srk_saturn_midi_68k_command_engine(program, write_sequence=9)
        channel = result.channels[2]

        self.assertEqual(result.read_sequence, 9)
        self.assertEqual(result.read_index, 7)
        self.assertEqual(channel.volume, 80)
        self.assertEqual(channel.controllers[7], 80)
        self.assertEqual(channel.program, 5)
        self.assertEqual(channel.channel_pressure, 90)
        self.assertEqual(channel.pitch_bend, 0x2001)
        self.assertEqual((channel.last_poly_note, channel.last_poly_pressure), (60, 70))
        self.assertEqual(channel.active_notes, ())
        self.assertEqual(channel.event_count, 7)

    def test_packed_state_contract_and_committed_header_are_stable_and_inert(self):
        result = simulate_srk_saturn_midi_68k_command_engine(
            build_srk_saturn_midi_bridge_assets().program
        )
        words = pack_srk_saturn_midi_68k_state_words(result)
        controllers = pack_srk_saturn_midi_68k_controller_bytes(result)
        active_notes = pack_srk_saturn_midi_68k_active_note_bitmap(result)

        self.assertEqual(len(words), SATURN_MIDI_68K_CHANNEL_COUNT * SATURN_MIDI_68K_CHANNEL_STATE_WORDS)
        self.assertEqual(len(controllers), SATURN_MIDI_68K_CONTROLLER_BYTES)
        self.assertEqual(len(active_notes), SATURN_MIDI_68K_ACTIVE_NOTES_BYTES)
        self.assertEqual(active_notes, bytes(SATURN_MIDI_68K_ACTIVE_NOTES_BYTES))

        committed = (_STANDALONE / "srk_saturn_midi_68k_command_state.h").read_text(encoding="utf-8")
        self.assertEqual(committed, render_srk_saturn_midi_68k_command_state_header())
        self.assertIn("No SCSP voice writes are enabled", committed)
        self.assertNotIn("volatile", committed)
        self.assertNotIn("0x25B00000", committed)
        self.assertNotIn("0x2010001F", committed)

    def test_rejects_queue_overflow_bad_order_and_bad_sequence(self):
        overflow = SaturnMidiProgram(
            records=tuple(
                SaturnMidiRecord(index, SaturnMidiOpcode.NOTE_ON, 0, 60, 1)
                for index in range(33)
            ),
            duration_us=32,
        )
        with self.assertRaisesRegex(SaturnMidi68KCommandEngineError, "exceeds"):
            simulate_srk_saturn_midi_68k_command_engine(overflow)

        bad_order = SaturnMidiProgram(
            records=(
                SaturnMidiRecord(2, SaturnMidiOpcode.NOTE_ON, 0, 60, 1),
                SaturnMidiRecord(1, SaturnMidiOpcode.NOTE_OFF, 0, 60, 0),
            ),
            duration_us=2,
        )
        with self.assertRaisesRegex(SaturnMidi68KCommandEngineError, "chronological"):
            simulate_srk_saturn_midi_68k_command_engine(bad_order)

        one = SaturnMidiProgram(
            records=(SaturnMidiRecord(0, SaturnMidiOpcode.NOTE_ON, 0, 60, 1),),
            duration_us=0,
        )
        with self.assertRaisesRegex(SaturnMidi68KCommandEngineError, "sequence"):
            simulate_srk_saturn_midi_68k_command_engine(one, write_sequence=0)


if __name__ == "__main__":
    unittest.main()
