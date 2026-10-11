"""Regression tests for R23 whole-card guarded deployment boundaries."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.midi_68k_resident_audio_physical_candidate_guarded_deployment import (
    CONFIRMATION_TOKEN,
    SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentError,
    _allowed_paths,
    _saroo_guard_key,
    apply_midi_68k_resident_audio_physical_candidate_guarded_deployment,
    prepare_midi_68k_resident_audio_physical_candidate_guarded_deployment,
)


class SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentTests(unittest.TestCase):
    def test_confirmation_token_is_r23_specific(self):
        self.assertEqual(CONFIRMATION_TOKEN, "DEPLOY-R23-MIDI-SCSP-FIRST-NOTE")

    def test_wrong_confirmation_is_rejected_before_any_media_access(self):
        with self.assertRaisesRegex(
            SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentError,
            "confirmation token",
        ):
            apply_midi_68k_resident_audio_physical_candidate_guarded_deployment(
                "missing-project",
                "missing-card",
                "missing-guard.json",
                expected_guard_manifest_sha256="1" * 64,
                expected_image_sha256="2" * 64,
                expected_resident_source_sha256="3" * 64,
                expected_resident_header_sha256="4" * 64,
                expected_voice_header_sha256="5" * 64,
                expected_producer_source_sha256="6" * 64,
                expected_producer_header_sha256="7" * 64,
                expected_resident_object_sha256="8" * 64,
                expected_producer_object_sha256="9" * 64,
                expected_bin_sha256="a" * 64,
                expected_cue_sha256="b" * 64,
                destination_name="SRK-Diagnostics-R23",
                category="TEST",
                confirmation="WRONG",
            )

    def test_prepare_rejects_guard_manifest_inside_card_before_pre_media(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            card = Path(temp_dir) / "CARD"
            card.mkdir()
            guard = card / "guard.json"
            with self.assertRaisesRegex(
                SaturnMidi68KResidentAudioPhysicalCandidateGuardedDeploymentError,
                "outside the mounted SAROO card",
            ):
                prepare_midi_68k_resident_audio_physical_candidate_guarded_deployment(
                    "missing-project",
                    card,
                    guard,
                    expected_image_sha256="2" * 64,
                    expected_resident_source_sha256="3" * 64,
                    expected_resident_header_sha256="4" * 64,
                    expected_voice_header_sha256="5" * 64,
                    expected_producer_source_sha256="6" * 64,
                    expected_producer_header_sha256="7" * 64,
                    expected_resident_object_sha256="8" * 64,
                    expected_producer_object_sha256="9" * 64,
                    expected_bin_sha256="a" * 64,
                    expected_cue_sha256="b" * 64,
                    destination_name="SRK-Diagnostics-R23",
                    category="TEST",
                )

    def test_saroo_guard_key_is_scoped_to_iso_suffix(self):
        path = Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.bin")
        self.assertEqual(
            _saroo_guard_key(path),
            "saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.bin",
        )

    def test_allowed_paths_are_exactly_directory_bin_and_cue(self):
        destination = Path("D:/saroo/ISO/TEST/SRK-Diagnostics-R23")
        deployment = SimpleNamespace(
            plan=SimpleNamespace(destination_directory=destination),
            destination_bin=destination / "SRK-Diagnostics.bin",
            destination_cue=destination / "SRK-Diagnostics.cue",
        )
        self.assertEqual(
            _allowed_paths(deployment),
            (
                "saroo/ISO/TEST/SRK-Diagnostics-R23",
                "saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.bin",
                "saroo/ISO/TEST/SRK-Diagnostics-R23/SRK-Diagnostics.cue",
            ),
        )


if __name__ == "__main__":
    unittest.main()
