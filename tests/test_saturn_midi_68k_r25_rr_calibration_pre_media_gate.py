"""Regression contracts for the R25 RR16 read-only pre-media gate."""

from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

import rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_pre_media_gate as _gate
from rikai_kotoba.hardware.saturn.midi_68k_r25_rr_calibration_pre_media_gate import (
    SaturnMidi68KR25RRCalibrationPreMediaGateError,
    inspect_saturn_midi_68k_r25_rr_calibration_pre_media,
)


class SaturnMidi68KR25RRCalibrationPreMediaGateTests(unittest.TestCase):
    def test_eridu_acceptance_anchors_are_exact_sha256_values(self):
        values = (
            _gate.ACCEPTED_R25_MANIFEST_SHA256,
            _gate.ACCEPTED_R25_REPORT_SHA256,
            _gate.ACCEPTED_R25_IMAGE_SHA256,
            _gate.ACCEPTED_R25_RESIDENT_SOURCE_SHA256,
            _gate.ACCEPTED_R25_RESIDENT_HEADER_SHA256,
            _gate.ACCEPTED_R25_VOICE_HEADER_SHA256,
            _gate.ACCEPTED_R25_MAIN_SHA256,
            _gate.ACCEPTED_R25_MENU_SHA256,
            _gate.ACCEPTED_R25_RUNTIME_SHA256,
            _gate.ACCEPTED_R25_PROOF_HEADER_SHA256,
            _gate.ACCEPTED_R25_PROOF_SOURCE_SHA256,
            _gate.ACCEPTED_R25_BUILD_BIN_SHA256,
            _gate.ACCEPTED_R25_BUILD_ISO_SHA256,
            _gate.ACCEPTED_R25_BUILD_MAP_SHA256,
            _gate.ACCEPTED_R25_BIN_SHA256,
            _gate.ACCEPTED_R25_CUE_SHA256,
        )
        for value in values:
            self.assertEqual(len(value), 64)
            self.assertTrue(all(ch in "0123456789abcdef" for ch in value))
        self.assertEqual(
            _gate.ACCEPTED_R25_MANIFEST_SHA256,
            "5a282c2ea1077b95ca34bc1fd11593f34cef015baa6da1eb5c5cfe69f830cba9",
        )
        self.assertEqual(
            _gate.ACCEPTED_R25_REPORT_SHA256,
            "bcd65a3252e5b7980b2263b4134b8145405cbe043169bcbaacd196a1e708d991",
        )
        self.assertEqual(
            _gate.ACCEPTED_R25_BIN_SHA256,
            "a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71",
        )
        self.assertEqual(_gate.ACCEPTED_R25_SECTOR_COUNT, 144)
        self.assertEqual(_gate.ACCEPTED_R25_RAW_BYTES, 338688)
        self.assertEqual(_gate.ACCEPTED_R25_USER_BYTES, 294912)

    def test_current_rr16_renderers_reproduce_the_accepted_candidate(self):
        blobs, image_sha = _gate._render_current_r25()
        expected = {
            _gate._R25_AUDIO_SOURCE: _gate.ACCEPTED_R25_RESIDENT_SOURCE_SHA256,
            _gate._R25_AUDIO_HEADER: _gate.ACCEPTED_R25_RESIDENT_HEADER_SHA256,
            _gate._R25_VOICE_HEADER: _gate.ACCEPTED_R25_VOICE_HEADER_SHA256,
            _gate._R25_PROOF_SOURCE: _gate.ACCEPTED_R25_PROOF_SOURCE_SHA256,
            _gate._R25_PROOF_HEADER: _gate.ACCEPTED_R25_PROOF_HEADER_SHA256,
        }
        self.assertEqual(image_sha, _gate.ACCEPTED_R25_IMAGE_SHA256)
        for relative, accepted in expected.items():
            self.assertEqual(sha256(blobs[relative]).hexdigest(), accepted)

    def test_accepted_r24_constants_are_reused_instead_of_retyped(self):
        self.assertEqual(
            _gate._build.ACCEPTED_R24_MENU_SHA256,
            "7b36d84223c454999f3d2fecb7af2f17b368843f3dc24931dd1d958b92ad9e8e",
        )
        self.assertEqual(len(_gate._build.ACCEPTED_R24_MENU_SHA256), 64)
        self.assertEqual(
            _gate._build.ACCEPTED_R24_MANIFEST_SHA256,
            "669d85db980f5c7922c5198dcc1b597b1d85664e543423f2c8570eeafa01fca6",
        )

    def test_missing_candidate_fails_before_any_media_planning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-candidate"
            with self.assertRaisesRegex(
                SaturnMidi68KR25RRCalibrationPreMediaGateError,
                "candidate project is not a directory",
            ):
                inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
                    missing,
                    Path(temp_dir) / "CARD",
                    destination_name="SRK-Diagnostics-R25-RR16-CAL",
                    category="TEST",
                )


if __name__ == "__main__":
    unittest.main()
