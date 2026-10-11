"""Regression tests for independent R23 MIDI->SCSP pre-media review."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate import (
    build_srk_saturn_midi_68k_r23_physical_snapshot,
    render_srk_saturn_midi_68k_r23_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_pre_media_gate import (
    SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError,
    _require_sha,
    _verify_proof_contract,
    inspect_midi_68k_resident_audio_physical_candidate_pre_media,
)


class SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateTests(unittest.TestCase):
    def test_proof_contract_rederives_all_verification_surfaces(self):
        self.assertEqual(_verify_proof_contract(), (256, 1024, 128, 15))

    def test_final_snapshot_remains_exact_first_audio_contract(self):
        snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()
        self.assertEqual(
            (
                snapshot.cc74,
                snapshot.final_active_note_count,
                snapshot.total_records,
                snapshot.batches,
                snapshot.voice_key_on_count,
                snapshot.voice_key_off_count,
            ),
            (31, 0, 34, 2, 1, 1),
        )

    def test_proof_renderer_contains_scsp_keying_and_scheduled_release(self):
        source = render_srk_saturn_midi_68k_r23_physical_proof_source()
        for marker in (
            "SRK_R23_PROOF_SCSP",
            "srk_r23_verify_scsp_on",
            "srk_r23_verify_scsp_off",
            "srk_r23_expected_voice_on",
            "srk_r23_expected_voice_off",
            "srk_saturn_midi_stream_clock_publish(33000UL)",
            "srk_saturn_midi_stream_clock_publish(1033000UL)",
            "srk_r23_verify_final_midi_state",
        ):
            self.assertIn(marker, source)

    def test_sha_gate_rejects_non_sha_input(self):
        with self.assertRaises(SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError):
            _require_sha("not-a-sha", "test")

    def test_missing_candidate_directory_is_rejected_before_card_planning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing"
            with self.assertRaisesRegex(
                SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError,
                "not a directory",
            ):
                inspect_midi_68k_resident_audio_physical_candidate_pre_media(
                    missing,
                    Path(temp_dir) / "CARD",
                    expected_image_sha256="1" * 64,
                    expected_resident_source_sha256="2" * 64,
                    expected_resident_header_sha256="3" * 64,
                    expected_voice_header_sha256="4" * 64,
                    expected_producer_source_sha256="5" * 64,
                    expected_producer_header_sha256="6" * 64,
                    expected_resident_object_sha256="7" * 64,
                    expected_producer_object_sha256="8" * 64,
                    expected_bin_sha256="9" * 64,
                    expected_cue_sha256="a" * 64,
                    destination_name="SRK-Diagnostics-R23",
                    category="TEST",
                )


if __name__ == "__main__":
    unittest.main()
