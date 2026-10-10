"""Regression tests for the guarded real-Saturn silent full-batch MIDI/68K binding."""

from __future__ import annotations

from pathlib import Path
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_STANDALONE = _ROOT / "integrations" / "saturn" / "standalone"


def _read(name: str) -> str:
    return (_STANDALONE / name).read_text(encoding="utf-8")


class SaturnMidi68KSilentBatchPhysicalBindingTests(unittest.TestCase):
    def test_installer_writes_complete_batch_image_before_reset_vectors(self):
        source = _read("srk_saturn_midi_68k_silent_batch_installer.c")
        self.assertIn("SRK_MIDI_68K_SILENT_BATCH_PROGRAM_WORD_COUNT", source)
        self.assertIn("SRK_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS", source)
        self.assertIn("SRK_MIDI_68K_SILENT_BATCH_STACK_ADDRESS", source)
        loop = source.index("for(index=0UL;")
        ssp = source.index("SRK_MIDI_68K_RESET_SSP_VECTOR_ADDRESS", loop)
        pc = source.index("SRK_MIDI_68K_RESET_PC_VECTOR_ADDRESS", ssp)
        self.assertLess(loop, ssp)
        self.assertLess(ssp, pc)
        self.assertNotIn("0x25B", source)

    def test_batch_runtime_reuses_proven_adapter_ops_but_substitutes_installer(self):
        source = _read("srk_saturn_midi_68k_silent_batch_runtime.c")
        self.assertIn("ops->stop_sound_cpu()", source)
        self.assertIn("srk_saturn_midi_68k_silent_batch_install_while_stopped()", source)
        self.assertIn("ops->publish_preload()", source)
        self.assertIn("ops->verify_preload()", source)
        self.assertIn("ops->start_sound_cpu()", source)
        self.assertNotIn("ops->install_program()", source)
        self.assertNotIn("read_sound_word", source)
        self.assertNotIn("0x201000", source)
        self.assertNotIn("0x25A00000", source)

    def test_batch_runtime_acknowledges_only_full_public_mailbox_contract(self):
        source = _read("srk_saturn_midi_68k_silent_batch_runtime.c")
        header = _read("srk_saturn_midi_68k_silent_batch_runtime.h")
        self.assertIn("SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS 27u", header)
        self.assertIn("read_sequence == SRK_MIDI_PRELOAD_WRITE_SEQUENCE", source)
        self.assertIn("read_index == SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS", source)
        self.assertIn("if(last_error != 0u)", source)
        self.assertIn("SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR", source)
        self.assertIn("SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED", source)

    def test_shared_proof_controller_exposes_batch_path_without_new_hardware_adapter(self):
        source = _read("srk_saturn_midi_68k_physical_proof.c")
        header = _read("srk_saturn_midi_68k_physical_proof.h")
        self.assertIn("SRK_SATURN_MIDI_68K_SILENT_BATCH_PHYSICAL_PROOF_STATE", header)
        self.assertIn("srk_saturn_midi_68k_silent_batch_protocol_begin", source)
        self.assertIn("srk_saturn_midi_68k_silent_batch_protocol_poll", source)
        self.assertIn("srk_saturn_midi_68k_hardware_adapter_ops()", source)
        self.assertNotIn("silent_batch_hardware_adapter_ops()", source)

    def test_guarded_ui_preserves_release_a_interlock_and_requires_index_27(self):
        main = _read("srk_saturn_main.c")
        self.assertIn("SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE", main)
        self.assertIn("SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u", main)
        self.assertIn('"MIDI / 68K BATCH PROOF"', main)
        self.assertIn('"27 records - no MIDI SCSP note"', main)
        self.assertIn('"Success: sequence=1 index=27 error=0"', main)
        self.assertIn("Release A to arm proof action", main)
        self.assertIn("A ignored while proof is RUNNING", main)
        self.assertIn("SRK_MIDI_68K_PROOF_POLL(&srk_midi_68k_proof)", main)


if __name__ == "__main__":
    unittest.main()
