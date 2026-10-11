"""Regression tests for the real-hardware stream/refill scheduler candidate."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate import (
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_stream_expected_words,
    build_srk_saturn_midi_68k_stream_physical_program,
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    derive_resident_stream_candidate_menu,
    render_srk_saturn_midi_68k_stream_physical_proof_header,
    render_srk_saturn_midi_68k_stream_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    build_srk_saturn_midi_stream_batches,
    simulate_srk_saturn_midi_stream_timeline,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KResidentStreamPhysicalCandidateTests(unittest.TestCase):
    def test_program_is_exactly_32_plus_8_and_covers_all_opcodes(self):
        program = build_srk_saturn_midi_68k_stream_physical_program()
        batches = build_srk_saturn_midi_stream_batches(program)
        self.assertEqual(len(program.records), SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS)
        self.assertEqual(
            tuple(len(batch.records) for batch in batches),
            (
                SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
                SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
            ),
        )
        self.assertEqual(tuple(batch.sequence for batch in batches), (1, 2))
        self.assertEqual(set(record.opcode for record in program.records), set(SaturnMidiOpcode))
        self.assertEqual(program.records[31].time_us, SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US)
        self.assertEqual(program.records[-1].time_us, SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US)

    def test_host_timeline_locks_scheduler_milestones(self):
        program = build_srk_saturn_midi_68k_stream_physical_program()
        snapshots = simulate_srk_saturn_midi_stream_timeline(
            program,
            (
                0,
                SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US,
                SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US,
                SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
            ),
        )
        self.assertEqual(tuple(item.total_processed_records for item in snapshots), (0, 15, 32, 40))
        self.assertEqual(tuple(item.acknowledged_sequence for item in snapshots), (0, 0, 1, 2))
        self.assertEqual(snapshots[1].read_index, 15)
        self.assertEqual(snapshots[2].read_index, 0)
        self.assertEqual(snapshots[-1].read_index, 8)
        self.assertEqual(snapshots[-1].batch_count, 2)

    def test_final_snapshot_proves_state_persisted_across_refill(self):
        snapshot = build_srk_saturn_midi_68k_stream_physical_snapshot()
        self.assertEqual(snapshot.cc74, 31)
        self.assertEqual(snapshot.program, 12)
        self.assertEqual(snapshot.pitch_bend, 10036)
        self.assertEqual(snapshot.active_note_count, 1)
        self.assertEqual(snapshot.final_note, 67)
        self.assertEqual(snapshot.final_velocity, 88)
        self.assertEqual(snapshot.total_records, 40)
        self.assertEqual(snapshot.batches, 2)

    def test_complete_state_surface_remains_256_1024_128_words(self):
        summary, controllers, active = build_srk_saturn_midi_68k_stream_expected_words()
        self.assertEqual((len(summary), len(controllers), len(active)), (256, 1024, 128))

    def test_generated_physical_source_contains_all_scheduler_boundaries(self):
        source = render_srk_saturn_midi_68k_stream_physical_proof_source()
        for marker in (
            "srk_saturn_midi_stream_clock_publish(0UL)",
            "srk_saturn_midi_stream_clock_publish(15000UL)",
            "srk_saturn_midi_stream_clock_publish(32000UL)",
            "srk_saturn_midi_stream_clock_publish(40000UL)",
            "current_index == 15u",
            "read_sequence == 1u",
            "read_sequence == 2u",
            "batch_count == 2u",
            "total_processed == 40u",
            "srk_stream_proof_verify_state",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("SCSP", source.upper())
        self.assertNotIn("0X25B", source.upper())

    def test_generated_header_exposes_generic_proof_shape(self):
        header = render_srk_saturn_midi_68k_stream_physical_proof_header()
        for marker in (
            "attempted",
            "runtime_status",
            "poll_count",
            "read_sequence",
            "read_index",
            "partial_15ms_pass",
            "refill_wait_pass",
            "state_verify_status",
            "final_cc74",
            "final_pitch",
        ):
            self.assertIn(marker, header)

    def test_menu_derivation_replaces_only_r21_state_label(self):
        menu = 'x\n"MIDI 68K State Proof"\ny\n'
        derived = derive_resident_stream_candidate_menu(menu)
        self.assertIn('"MIDI 68K Stream Proof"', derived)
        self.assertNotIn('"MIDI 68K State Proof"', derived)


if __name__ == "__main__":
    unittest.main()
