"""Regression tests for multi-batch/refill and timestamp-scheduler semantics."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_stream_service import (
    SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS,
    SATURN_MIDI_68K_STREAM_SERVICE_END,
    SaturnMidi68KStreamBatch,
    SaturnMidi68KStreamServiceError,
    build_srk_saturn_midi_stream_batches,
    next_saturn_midi_stream_sequence,
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
    simulate_srk_saturn_midi_stream_timeline,
    validate_srk_saturn_midi_68k_stream_batches,
    validate_srk_saturn_midi_68k_stream_layout,
)
from rikai_kotoba.hardware.saturn.midi_program import (
    SaturnMidiOpcode,
    SaturnMidiProgram,
    SaturnMidiRecord,
)


def _program(count: int = 70) -> SaturnMidiProgram:
    records = []
    opcodes = tuple(SaturnMidiOpcode)
    for index in range(count):
        opcode = opcodes[index % len(opcodes)]
        channel = index % 16
        data0 = (36 + index) & 0x7F
        data1 = (64 + index) & 0x7F
        if opcode == SaturnMidiOpcode.PROGRAM_CHANGE:
            data1 = 0
        elif opcode == SaturnMidiOpcode.CHANNEL_PRESSURE:
            data1 = 0
        records.append(
            SaturnMidiRecord(
                time_us=(index + 1) * 1000,
                opcode=opcode,
                channel=channel,
                data0=data0,
                data1=data1,
            )
        )
    return SaturnMidiProgram(records=tuple(records), duration_us=records[-1].time_us)


class SaturnMidi68KStreamServiceTests(unittest.TestCase):
    def test_layout_uses_only_the_reviewed_pre_audio_gap(self):
        validate_srk_saturn_midi_68k_stream_layout()
        self.assertEqual(SATURN_MIDI_68K_STREAM_SERVICE_ADDRESS, 0x1E00)
        self.assertEqual(SATURN_MIDI_68K_STREAM_SERVICE_END, 0x2000)

    def test_partition_is_32_32_remainder_with_strict_sequences(self):
        batches = build_srk_saturn_midi_stream_batches(_program(70))
        self.assertEqual(tuple(len(batch.records) for batch in batches), (32, 32, 6))
        self.assertEqual(tuple(batch.sequence for batch in batches), (1, 2, 3))
        validate_srk_saturn_midi_stream_batches(batches)

    def test_sequence_wrap_skips_zero(self):
        self.assertEqual(next_saturn_midi_stream_sequence(0), 1)
        self.assertEqual(next_saturn_midi_stream_sequence(1), 2)
        self.assertEqual(next_saturn_midi_stream_sequence(0xFFFE), 0xFFFF)
        self.assertEqual(next_saturn_midi_stream_sequence(0xFFFF), 1)

    def test_scheduler_does_not_execute_future_records_and_acks_only_complete_batch(self):
        program = _program(40)
        snapshots = simulate_srk_saturn_midi_stream_timeline(
            program,
            (0, 15000, 31999, 32000, 33000, 40000),
        )
        self.assertEqual(snapshots[0].total_processed_records, 0)
        self.assertTrue(snapshots[0].waiting_for_time)
        self.assertEqual(snapshots[1].total_processed_records, 15)
        self.assertEqual(snapshots[1].acknowledged_sequence, 0)
        self.assertEqual(snapshots[2].total_processed_records, 31)
        self.assertEqual(snapshots[2].acknowledged_sequence, 0)
        self.assertEqual(snapshots[3].total_processed_records, 32)
        self.assertEqual(snapshots[3].acknowledged_sequence, 1)
        self.assertEqual(snapshots[3].batch_count, 1)
        self.assertEqual(snapshots[4].total_processed_records, 33)
        self.assertEqual(snapshots[4].acknowledged_sequence, 1)
        self.assertEqual(snapshots[-1].total_processed_records, 40)
        self.assertEqual(snapshots[-1].acknowledged_sequence, 2)
        self.assertEqual(snapshots[-1].batch_count, 2)
        self.assertTrue(snapshots[-1].waiting_for_batch)
        self.assertFalse(snapshots[-1].waiting_for_time)

    def test_state_persists_across_refill_boundaries(self):
        program = SaturnMidiProgram(
            records=tuple(
                [
                    SaturnMidiRecord((index + 1) * 1000, SaturnMidiOpcode.CONTROL_CHANGE, 3, 74, index & 0x7F)
                    for index in range(32)
                ]
                + [
                    SaturnMidiRecord(33000, SaturnMidiOpcode.PROGRAM_CHANGE, 3, 12, 0),
                    SaturnMidiRecord(34000, SaturnMidiOpcode.NOTE_ON, 3, 64, 100),
                    SaturnMidiRecord(35000, SaturnMidiOpcode.PITCH_BEND, 3, 52, 78),
                ]
            ),
            duration_us=35000,
        )
        final = simulate_srk_saturn_midi_stream_timeline(program, (35000,))[-1]
        channel = final.channels[3]
        self.assertEqual(final.acknowledged_sequence, 2)
        self.assertEqual(final.batch_count, 2)
        self.assertEqual(channel.controllers[74], 31)
        self.assertEqual(channel.program, 12)
        self.assertEqual(channel.note_velocities[64], 100)
        self.assertEqual(channel.pitch_bend, 10036)
        self.assertEqual(channel.event_count, 35)

    def test_invalid_sequence_and_cross_batch_timestamp_regression_fail_closed(self):
        batches = build_srk_saturn_midi_stream_batches(_program(33))
        bad_sequence = (
            batches[0],
            SaturnMidi68KStreamBatch(sequence=3, records=batches[1].records),
        )
        with self.assertRaisesRegex(SaturnMidi68KStreamServiceError, "expected stream sequence 2"):
            validate_srk_saturn_midi_stream_batches(bad_sequence)

        bad_record = SaturnMidiRecord(
            time_us=batches[0].records[-1].time_us - 1,
            opcode=SaturnMidiOpcode.NOTE_ON,
            channel=0,
            data0=60,
            data1=100,
        )
        bad_time = (
            batches[0],
            SaturnMidi68KStreamBatch(sequence=2, records=(bad_record,)),
        )
        with self.assertRaisesRegex(SaturnMidi68KStreamServiceError, "chronological"):
            validate_srk_saturn_midi_stream_batches(bad_time)

    def test_clock_must_be_monotonic(self):
        with self.assertRaisesRegex(SaturnMidi68KStreamServiceError, "clock must be monotonic"):
            simulate_srk_saturn_midi_stream_timeline(_program(2), (1000, 999))

    def test_generated_producer_contract_is_c89_and_has_no_scsp_or_smpc_access(self):
        header = render_srk_saturn_midi_68k_stream_service_header()
        source = render_srk_saturn_midi_68k_stream_service_source()
        self.assertIn("srk_saturn_midi_stream_clock_publish", header)
        self.assertIn("srk_saturn_midi_stream_batch_publish", header)
        self.assertIn("CLOCK_GENERATION", header)
        self.assertIn("generation", source)
        self.assertIn("SRK_MIDI_MAILBOX_FLAG_READY", source)
        combined = (header + source).upper()
        self.assertNotIn("SCSP", combined)
        self.assertNotIn("SMPC", combined)
        self.assertNotIn("0X25B", combined)


if __name__ == "__main__":
    unittest.main()
