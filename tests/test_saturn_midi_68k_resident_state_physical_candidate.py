"""Regression tests for the Phase-B full-state physical proof contract."""

from __future__ import annotations

import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_candidate_ui import (
    derive_resident_state_candidate_main,
    derive_resident_state_candidate_menu,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_physical_binding import (
    render_resident_state_decoder_installer_source,
    render_resident_state_decoder_proof_source,
    render_resident_state_decoder_runtime_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_state_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS,
    SATURN_MIDI_68K_STATE_VERIFY_PASS,
    build_srk_saturn_midi_68k_resident_state_expected_words,
    build_srk_saturn_midi_68k_resident_state_proof_program,
    build_srk_saturn_midi_68k_resident_state_proof_snapshot,
    render_srk_saturn_midi_68k_resident_state_proof_preload_source,
    render_srk_saturn_midi_68k_resident_state_verifier_header,
    render_srk_saturn_midi_68k_resident_state_verifier_source,
)
from rikai_kotoba.hardware.saturn.midi_program import SaturnMidiOpcode


def _r20_main_fixture() -> str:
    slash = chr(92)
    guard = (
        "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || "
        + slash
        + "\n    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE) || "
        + slash
        + "\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)"
    )
    return (
        "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1\n"
        + guard
        + "\n#include \"srk_saturn_midi_68k_physical_proof.h\"\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "#include \"srk_saturn_midi_68k_resident_decoder_physical_proof.h\"\n"
        + "#endif\n#endif\n\n"
        + guard
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "typedef OLD_STATE SRK_MIDI_68K_ACTIVE_PROOF_STATE;\n"
        + "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u\n"
        + "#define SRK_MIDI_68K_PROOF_TITLE \"MIDI / 68K DECODER PROOF\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUBTITLE \"7 runtime records - no MIDI SCSP note\"\n"
        + "#define SRK_MIDI_68K_PROOF_SUCCESS \"Success: sequence=1 index=7 error=0\"\n"
        + "#define SRK_MIDI_68K_PROOF_RESET old_reset\n"
        + "#define SRK_MIDI_68K_PROOF_BEGIN old_begin\n"
        + "#define SRK_MIDI_68K_PROOF_POLL old_poll\n"
        + "#elif defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)\n"
        + "#endif\n"
        + "static void render(void){\n    char number[11];\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.last_error);\n"
        + "    srk_midi_68k_draw_field(2, 11, 14, \"Last error:\");\n"
        + "    srk_midi_68k_draw_field(16, 11, 10, number);\n\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.processed);\n"
        + "    srk_midi_68k_draw_field(2, 12, 14, \"Processed:\");\n"
        + "    srk_midi_68k_draw_field(16, 12, 10, number);\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.current_record);\n"
        + "    srk_midi_68k_draw_field(2, 13, 14, \"Current:\");\n"
        + "    srk_midi_68k_draw_field(16, 13, 10, number);\n"
        + "    srk_midi_68k_u32(number, (srk_u32)srk_midi_68k_proof.telemetry.decoder_ready);\n"
        + "    srk_midi_68k_draw_field(2, 14, 14, \"Decoder ready:\");\n"
        + "    srk_midi_68k_draw_field(16, 14, 10, number);\n"
        + "#endif\n"
        + "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE\n"
        + "    srk_midi_68k_draw_field(2, 15, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        + "#else\n"
        + "    srk_midi_68k_draw_field(2, 14, 36, SRK_MIDI_68K_PROOF_SUCCESS);\n"
        + "#endif\n"
        + "    srk_midi_68k_draw_field(2, 17, 36, \"Release A to arm proof action\");\n"
        + "}\n#endif\n"
    )


class SaturnMidi68KResidentStatePhysicalProofTests(unittest.TestCase):
    def test_richer_program_has_twenty_records_and_all_opcodes(self):
        program = build_srk_saturn_midi_68k_resident_state_proof_program()
        self.assertEqual(len(program.records), SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS)
        self.assertEqual(program.duration_us, SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US)
        self.assertEqual(set(record.opcode for record in program.records), set(SaturnMidiOpcode))
        self.assertEqual({record.channel for record in program.records}, {3, 9})

    def test_expected_snapshot_is_human_readable_and_non_default(self):
        value = build_srk_saturn_midi_68k_resident_state_proof_snapshot()
        self.assertEqual(
            (
                value.ch3_program, value.ch3_bank_msb, value.ch3_bank_lsb,
                value.ch3_volume, value.ch3_pan, value.ch3_expression,
                value.ch3_sustain, value.ch3_channel_pressure, value.ch3_pitch_bend,
            ),
            (12, 5, 9, 91, 73, 101, 1, 70, 10036),
        )
        self.assertEqual(
            (
                value.ch3_last_note, value.ch3_last_velocity,
                value.ch3_last_poly_note, value.ch3_last_poly_pressure,
                value.ch3_active_note_count, value.ch3_cc74,
                value.ch3_active_bitmap_byte,
            ),
            (64, 77, 64, 55, 1, 66, 1),
        )
        self.assertEqual(
            (
                value.ch9_program, value.ch9_volume, value.ch9_pitch_bend,
                value.ch9_last_note, value.ch9_last_velocity,
                value.ch9_active_note_count, value.ch9_active_bitmap_byte,
            ),
            (33, 84, 4096, 48, 96, 1, 1),
        )

    def test_full_state_verification_surface_is_complete(self):
        summaries, controllers, active = build_srk_saturn_midi_68k_resident_state_expected_words()
        self.assertEqual(len(summaries), 256)
        self.assertEqual(len(controllers), 1024)
        self.assertEqual(len(active), 128)

    def test_preload_is_ready_last_and_verifies_exact_runtime_batch(self):
        source = render_srk_saturn_midi_68k_resident_state_proof_preload_source()
        queue_pos = source.index("for(index=0UL; index<SRK_MIDI_68K_RESIDENT_STATE_PROOF_QUEUE_WORDS")
        ready_pos = source.index("SRK_MIDI_MAILBOX_FLAG_READY);", queue_pos)
        self.assertGreater(ready_pos, queue_pos)
        self.assertIn("SRK_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS", source)
        self.assertIn("proof_queue_words[index]", source)

    def test_state_verifier_checks_all_three_regions_and_remains_silent(self):
        header = render_srk_saturn_midi_68k_resident_state_verifier_header()
        source = render_srk_saturn_midi_68k_resident_state_verifier_source()
        self.assertIn(f"SRK_MIDI_68K_STATE_VERIFY_PASS {SATURN_MIDI_68K_STATE_VERIFY_PASS}u", header)
        self.assertIn("expected_summary_words", source)
        self.assertIn("expected_controller_words", source)
        self.assertIn("expected_active_words", source)
        self.assertIn("SUMMARY_MISMATCH", source)
        self.assertIn("CONTROLLER_MISMATCH", source)
        self.assertIn("ACTIVE_NOTE_MISMATCH", source)
        self.assertNotIn("0x25B00000", source)
        self.assertNotIn("SCSP", source.upper())

    def test_runtime_requires_complete_state_match_before_acknowledgement(self):
        source = render_resident_state_decoder_runtime_source()
        verify_pos = source.index("srk_saturn_midi_68k_resident_state_verify(&current.state_verify)")
        ack_pos = source.index("SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED", verify_pos)
        self.assertLess(verify_pos, ack_pos)
        self.assertIn("current.read_index == 20u", source)
        self.assertIn("current.decoder_magic == SRK_MIDI_68K_RESIDENT_STATE_TELEMETRY_MAGIC", source)

    def test_installer_is_program_first_vectors_last_and_proof_reuses_adapter(self):
        installer = render_resident_state_decoder_installer_source()
        proof = render_resident_state_decoder_proof_source()
        program_pos = installer.index("SRK_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS +")
        ssp_pos = installer.index("SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS", program_pos)
        pc_pos = installer.index("SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS", ssp_pos)
        self.assertLess(program_pos, ssp_pos)
        self.assertLess(ssp_pos, pc_pos)
        self.assertIn("srk_saturn_midi_68k_hardware_adapter_ops()", proof)

    def test_ui_derivation_exposes_state_values_and_preserves_fresh_a_interlock(self):
        main = derive_resident_state_candidate_main(_r20_main_fixture())
        menu = derive_resident_state_candidate_menu('entry("MIDI 68K Decoder Proof");\n')
        self.assertTrue(main.startswith("#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE 1"))
        self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u", main)
        self.assertIn("State verify:", main)
        self.assertIn("CH3 program:", main)
        self.assertIn("CH3 CC74:", main)
        self.assertIn("CH9 program:", main)
        self.assertIn("Release A to arm proof action", main)
        self.assertIn("MIDI 68K State Proof", menu)


if __name__ == "__main__":
    unittest.main()
