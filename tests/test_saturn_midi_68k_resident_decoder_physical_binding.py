"""Regression tests for the generated seven-record resident-decoder proof binding."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_binding import (
    render_resident_decoder_installer_header,
    render_resident_decoder_installer_source,
    render_resident_decoder_proof_header,
    render_resident_decoder_proof_source,
    render_resident_decoder_runtime_header,
    render_resident_decoder_runtime_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
    build_srk_saturn_midi_68k_resident_decoder_proof_program,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_decoder_physical_candidate_full_build_gate import (
    prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_mailbox import pack_saturn_midi_queue_words
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


class SaturnMidi68KResidentDecoderPhysicalBindingTests(unittest.TestCase):
    def test_seven_record_program_is_non_r19_and_covers_every_opcode_once(self):
        program = build_srk_saturn_midi_68k_resident_decoder_proof_program()
        self.assertEqual(SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS, 7)
        self.assertEqual(len(program.records), 7)
        self.assertEqual(program.duration_us, SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US)
        self.assertEqual(program.duration_us, 7000)
        self.assertEqual(tuple(record.opcode for record in program.records), tuple(SaturnMidiOpcode))
        self.assertEqual(tuple(record.channel for record in program.records), tuple(range(7)))
        self.assertEqual(len(pack_saturn_midi_queue_words(program)), 28)

    def test_preload_publishes_ready_last_and_verifies_exact_seven_record_queue(self):
        header = render_srk_saturn_midi_68k_resident_decoder_proof_preload_header()
        source = render_srk_saturn_midi_68k_resident_decoder_proof_preload_source()
        self.assertIn("PROOF_RECORDS 7u", header)
        self.assertIn("PROOF_QUEUE_WORDS 28u", header)
        self.assertIn("PROOF_FINAL_TIME_US 7000UL", header)
        first_ready = source.find("SRK_MIDI_MAILBOX_FLAG_READY")
        queue_write = source.find("srk_saturn_midi_68k_resident_proof_queue_words[index]")
        self.assertGreater(first_ready, queue_write)
        self.assertIn("SRK_MIDI_MB_WRITE_INDEX", source)
        self.assertIn("SRK_MIDI_MB_QUEUE_COUNT", source)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_proof_preload_verify", source)

    def test_installer_preserves_program_first_vectors_last_rule(self):
        header = render_resident_decoder_installer_header()
        source = render_resident_decoder_installer_source()
        self.assertIn("install_while_stopped", header)
        program_loop = source.find("SRK_MIDI_68K_RESIDENT_DECODER_PROGRAM_WORD_COUNT")
        ssp = source.find("SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS", program_loop)
        pc = source.find("SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS", ssp)
        self.assertGreater(program_loop, -1)
        self.assertGreater(ssp, program_loop)
        self.assertGreater(pc, ssp)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_verify_install", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)

    def test_runtime_requires_mailbox_and_decoder_telemetry_for_ack(self):
        header = render_resident_decoder_runtime_header()
        source = render_resident_decoder_runtime_source()
        self.assertIn("decoder_magic", header)
        self.assertIn("decoder_ready", header)
        self.assertIn("read_index == 7u", source)
        self.assertIn("processed == 7u", source)
        self.assertIn("current_record == 7u", source)
        self.assertIn("final_time_hi == 0u", source)
        self.assertIn("final_time_lo == 7000u", source)
        self.assertIn("decoder_ready == 1u", source)
        self.assertIn("TELEMETRY_MAGIC", source)
        self.assertIn("TELEMETRY_VERSION", source)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_install_while_stopped", source)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_proof_preload_publish", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("0x2010001F", source)

    def test_proof_controller_reuses_proven_r19_hardware_adapter(self):
        header = render_resident_decoder_proof_header()
        source = render_resident_decoder_proof_source()
        self.assertIn("SRK_SATURN_MIDI_68K_RESIDENT_DECODER_PHYSICAL_PROOF_STATE", header)
        self.assertIn("srk_saturn_midi_68k_hardware_adapter_ops()", source)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_protocol_begin", source)
        self.assertIn("srk_saturn_midi_68k_resident_decoder_protocol_poll", source)
        self.assertNotIn("0x2010001F", source)
        self.assertNotIn("SNDON", source)
        self.assertNotIn("SNDOFF", source)

    def test_physical_candidate_full_build_prepare_api_is_enabled(self):
        self.assertTrue(callable(prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate))


if __name__ == "__main__":
    unittest.main()
