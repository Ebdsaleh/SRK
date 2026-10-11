"""Regression tests for the R23 real-hardware MIDI->SCSP candidate."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate import (
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
    SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_r23_expected_midi_words,
    build_srk_saturn_midi_68k_r23_physical_program,
    build_srk_saturn_midi_68k_r23_physical_snapshot,
    derive_resident_audio_candidate_menu,
    render_srk_saturn_midi_68k_r23_physical_proof_header,
    render_srk_saturn_midi_68k_r23_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    build_srk_saturn_midi_stream_batches,
    simulate_srk_saturn_midi_stream_timeline,
)
from rikai_kotoba.hardware.saturn.midi_68k_voice_allocator import (
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_CONTROL_KYONB,
    build_srk_saturn_midi_68k_r23_first_note_snapshot,
    pack_srk_saturn_midi_68k_voice_state_words,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KResidentAudioPhysicalCandidateTests(unittest.TestCase):
    def test_program_is_exactly_32_plus_2_with_one_second_audio_pair(self):
        program = build_srk_saturn_midi_68k_r23_physical_program()
        batches = build_srk_saturn_midi_stream_batches(program)
        self.assertEqual(len(program.records), SATURN_MIDI_68K_R23_PHYSICAL_RECORDS)
        self.assertEqual(
            tuple(len(batch.records) for batch in batches),
            (
                SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
                SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
            ),
        )
        self.assertEqual(tuple(batch.sequence for batch in batches), (1, 2))
        self.assertEqual(program.records[31].time_us, SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US)
        note_on, note_off = program.records[-2:]
        self.assertEqual(note_on.opcode, SaturnMidiOpcode.NOTE_ON)
        self.assertEqual(note_on.channel, SATURN_MIDI_68K_R23_CHANNEL)
        self.assertEqual((note_on.data0, note_on.data1), (SATURN_MIDI_68K_R23_NOTE, SATURN_MIDI_68K_R23_VELOCITY))
        self.assertEqual(note_on.time_us, SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US)
        self.assertEqual(note_off.opcode, SaturnMidiOpcode.NOTE_OFF)
        self.assertEqual(note_off.time_us, SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US)
        self.assertEqual(note_off.time_us - note_on.time_us, 1_000_000)

    def test_host_timeline_reproves_refill_before_audio(self):
        snapshots = simulate_srk_saturn_midi_stream_timeline(
            build_srk_saturn_midi_68k_r23_physical_program(),
            (
                0,
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
                SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
            ),
        )
        self.assertEqual(
            tuple(item.total_processed_records for item in snapshots),
            (0, 15, 32, 33, 34),
        )
        self.assertEqual(
            tuple(item.acknowledged_sequence for item in snapshots),
            (0, 0, 1, 1, 2),
        )
        self.assertEqual(snapshots[-1].read_index, 2)
        self.assertEqual(snapshots[-1].batch_count, 2)

    def test_final_snapshot_proves_refill_state_and_voice_release(self):
        snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()
        self.assertEqual(snapshot.cc74, 31)
        self.assertEqual(snapshot.final_active_note_count, 0)
        self.assertEqual(snapshot.total_records, 34)
        self.assertEqual(snapshot.batches, 2)
        self.assertEqual(snapshot.voice_key_on_count, 1)
        self.assertEqual(snapshot.voice_key_off_count, 1)

    def test_complete_midi_and_voice_surfaces_are_locked(self):
        summary, controllers, active = build_srk_saturn_midi_68k_r23_expected_midi_words()
        self.assertEqual((len(summary), len(controllers), len(active)), (256, 1024, 128))
        voice = build_srk_saturn_midi_68k_r23_first_note_snapshot()
        self.assertEqual(len(pack_srk_saturn_midi_68k_voice_state_words(voice.after_note_on)), 15)
        self.assertEqual(len(pack_srk_saturn_midi_68k_voice_state_words(voice.after_note_off)), 15)
        self.assertTrue(voice.after_note_on.owned_slot.control & SATURN_MIDI_68K_SCSP_CONTROL_KYONB)
        self.assertFalse(voice.after_note_off.owned_slot.control & SATURN_MIDI_68K_SCSP_CONTROL_KYONB)

    def test_generated_source_requires_real_scsp_key_on_hold_and_key_off(self):
        source = render_srk_saturn_midi_68k_r23_physical_proof_source()
        for marker in (
            "0x25B00000UL",
            "srk_saturn_midi_stream_clock_publish(0UL)",
            "srk_saturn_midi_stream_clock_publish(15000UL)",
            "srk_saturn_midi_stream_clock_publish(32000UL)",
            "srk_saturn_midi_stream_clock_publish(33000UL)",
            "srk_saturn_midi_stream_clock_publish(1033000UL)",
            "current_index == 15u",
            "total_processed == 33u",
            "read_sequence == 2u",
            "total_processed == 34u",
            "srk_r23_verify_scsp_on",
            "srk_r23_verify_scsp_off",
            f"audible_hold_polls >= {SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS}u",
            "srk_r23_verify_final_midi_state",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("SAROO", source.upper())

    def test_generated_header_exposes_audio_observation_telemetry(self):
        header = render_srk_saturn_midi_68k_r23_physical_proof_header()
        for marker in (
            "key_on_pass",
            "audible_hold_polls",
            "key_off_pass",
            "voice_key_on_count",
            "voice_key_off_count",
            "scsp_control",
            "scsp_pitch",
            "scsp_mixer",
            "state_verify_status",
        ):
            self.assertIn(marker, header)

    def test_menu_derivation_replaces_only_stream_label(self):
        menu = 'x\n"MIDI 68K Stream Proof"\ny\n'
        derived = derive_resident_audio_candidate_menu(menu)
        self.assertIn('"MIDI 68K Audio Proof"', derived)
        self.assertNotIn('"MIDI 68K Stream Proof"', derived)


if __name__ == "__main__":
    unittest.main()
