"""Regression tests for SRK's deterministic Saturn MIDI playback contract."""

from __future__ import annotations

import unittest

from rikai_kotoba.core.midi_sequence import build_midi_playback_schedule
from rikai_kotoba.formats.midi import parse_midi_bytes
from rikai_kotoba.formats.midi_diagnostic import (
    SRK_MIDI_DIAGNOSTIC_END_TICK,
    SRK_MIDI_DIAGNOSTIC_TICKS_PER_QUARTER,
    build_srk_midi_diagnostic_bytes,
    srk_midi_diagnostic_sha256,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgramError,
    compile_saturn_midi_program,
    parse_saturn_midi_program_bytes,
    render_saturn_midi_program_c,
)


class SaturnMidiProgramTests(unittest.TestCase):
    def setUp(self):
        self.midi_bytes = build_srk_midi_diagnostic_bytes()
        self.midi = parse_midi_bytes(self.midi_bytes)
        self.program = compile_saturn_midi_program(self.midi)

    def test_diagnostic_asset_is_stable_format1_contract(self):
        self.assertEqual(len(self.midi_bytes), 217)
        self.assertEqual(
            srk_midi_diagnostic_sha256(),
            "9b5356bf8413de26438711b7adfc1a8c6349c31f53448d8496caf24b5adfd9dc",
        )
        self.assertEqual(self.midi.header.format_type, 1)
        self.assertEqual(self.midi.header.track_count, 3)
        self.assertEqual(
            self.midi.header.ticks_per_quarter,
            SRK_MIDI_DIAGNOSTIC_TICKS_PER_QUARTER,
        )
        self.assertEqual(SRK_MIDI_DIAGNOSTIC_END_TICK, 384)

    def test_diagnostic_schedule_exercises_timing_and_channel_state(self):
        schedule = build_midi_playback_schedule(self.midi)

        melody_g = next(
            item
            for item in schedule
            if item.track_index == 1
            and item.event.kind == "note_on"
            and item.event.data == (67, 92)
        )
        self.assertEqual(melody_g.time_us, 1000000)
        self.assertIsNotNone(melody_g.channel_state)
        self.assertEqual(melody_g.channel_state.bank_msb, 0)
        self.assertEqual(melody_g.channel_state.bank_lsb, 0)
        self.assertEqual(melody_g.channel_state.program, 1)
        self.assertEqual(melody_g.channel_state.volume, 100)
        self.assertEqual(melody_g.channel_state.pan, 96)

        harmony_g = next(
            item
            for item in schedule
            if item.track_index == 2
            and item.event.kind == "note_on"
            and item.event.data == (55, 84)
        )
        self.assertEqual(harmony_g.time_us, 1200000)
        self.assertIsNotNone(harmony_g.channel_state)
        self.assertEqual(harmony_g.channel_state.program, 2)
        self.assertEqual(harmony_g.channel_state.expression, 110)
        self.assertTrue(harmony_g.channel_state.sustain)
        self.assertEqual(harmony_g.channel_state.pitch_bend, 10240)

    def test_compiler_emits_expected_records_and_duration(self):
        self.assertEqual(len(self.program.records), 27)
        self.assertEqual(self.program.duration_us, 1800000)

        first = self.program.records[0]
        self.assertEqual(first.time_us, 0)
        self.assertEqual(first.opcode, SaturnMidiOpcode.CONTROL_CHANGE)
        self.assertEqual((first.channel, first.data0, first.data1), (0, 0, 0))

        last = self.program.records[-1]
        self.assertEqual(last.time_us, 1600000)
        self.assertEqual(last.opcode, SaturnMidiOpcode.CONTROL_CHANGE)
        self.assertEqual((last.channel, last.data0, last.data1), (1, 64, 0))

    def test_srkm_binary_round_trip_is_exact(self):
        payload = self.program.to_bytes()
        self.assertEqual(payload[:4], b"SRKM")
        self.assertEqual(payload[4], 1)
        self.assertEqual(payload[5], 8)
        self.assertEqual(len(payload), 16 + 27 * 8)
        self.assertEqual(parse_saturn_midi_program_bytes(payload), self.program)

    def test_srkm_parser_rejects_corruption(self):
        payload = bytearray(self.program.to_bytes())

        bad_magic = bytearray(payload)
        bad_magic[0] = ord("X")
        with self.assertRaisesRegex(SaturnMidiProgramError, "magic"):
            parse_saturn_midi_program_bytes(bytes(bad_magic))

        bad_reserved = bytearray(payload)
        bad_reserved[6] = 1
        with self.assertRaisesRegex(SaturnMidiProgramError, "reserved"):
            parse_saturn_midi_program_bytes(bytes(bad_reserved))

        bad_opcode = bytearray(payload)
        bad_opcode[20] = 0xFF
        with self.assertRaisesRegex(SaturnMidiProgramError, "opcode"):
            parse_saturn_midi_program_bytes(bytes(bad_opcode))

        with self.assertRaisesRegex(SaturnMidiProgramError, "size mismatch"):
            parse_saturn_midi_program_bytes(bytes(payload[:-1]))

    def test_c_renderer_is_c89_friendly_and_stable(self):
        rendered = render_saturn_midi_program_c(
            self.program,
            symbol_prefix="srk_midi_stage7",
        )
        self.assertIn("typedef struct SRK_MIDI_PROGRAM_EVENT", rendered)
        self.assertIn("{0UL, 4u, 0u, 0u, 0u},", rendered)
        self.assertIn("srk_midi_stage7_event_count = 27UL", rendered)
        self.assertIn("srk_midi_stage7_duration_us = 1800000UL", rendered)
        self.assertTrue(rendered.endswith("\n"))

        with self.assertRaisesRegex(SaturnMidiProgramError, "symbol prefix"):
            render_saturn_midi_program_c(self.program, symbol_prefix="not-valid!")

    def test_compiler_rejects_sysex_for_srkm_v1(self):
        track_body = bytes(
            (
                0x00,
                0xF0,
                0x01,
                0x7F,
                0x00,
                0xFF,
                0x2F,
                0x00,
            )
        )
        midi_bytes = (
            b"MThd"
            + (6).to_bytes(4, "big")
            + (0).to_bytes(2, "big")
            + (1).to_bytes(2, "big")
            + (96).to_bytes(2, "big")
            + b"MTrk"
            + len(track_body).to_bytes(4, "big")
            + track_body
        )
        midi = parse_midi_bytes(midi_bytes)
        with self.assertRaisesRegex(SaturnMidiProgramError, "SysEx"):
            compile_saturn_midi_program(midi)


if __name__ == "__main__":
    unittest.main()
