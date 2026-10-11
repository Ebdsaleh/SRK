"""Regression lock for the R22A physical-proof instrumentation correction."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn import midi_68k_resident_stream_candidate_prepare as base_prepare
from rikai_kotoba.hardware.saturn import midi_68k_resident_stream_physical_candidate_guarded_deployment as base_guard
from rikai_kotoba.hardware.saturn import midi_68k_resident_stream_physical_candidate_pre_media_gate as base_pre_media
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate import (
    render_srk_saturn_midi_68k_stream_physical_proof_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a import (
    R22_PHYSICAL_FAILURE_CODE,
    R22_PHYSICAL_FAILURE_FINAL_PITCH,
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    r22a_selected_state_addresses,
    render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_full_build_gate import (
    run_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_pre_media_gate import (
    inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media,
)
from rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment import (
    CONFIRMATION_TOKEN,
    apply_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment,
    prepare_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment,
)


class SaturnMidi68KResidentStreamPhysicalCandidateR22ATests(unittest.TestCase):
    def test_real_hardware_failure_signature_is_locked(self):
        self.assertEqual(R22_PHYSICAL_FAILURE_CODE, 0xE014)
        self.assertEqual(R22_PHYSICAL_FAILURE_FINAL_PITCH, 64)
        snapshot = build_srk_saturn_midi_68k_stream_physical_snapshot()
        self.assertEqual(snapshot.pitch_bend, 10036)
        self.assertEqual(snapshot.active_note_count, 1)

    def test_corrected_selected_state_byte_addresses_are_exact(self):
        self.assertEqual(r22a_selected_state_addresses(), (0x1260, 0x1270, 0x127A))

    def test_corrected_renderer_removes_r22_word_as_byte_defect(self):
        r22 = render_srk_saturn_midi_68k_stream_physical_proof_source()
        r22a = render_srk_saturn_midi_68k_stream_physical_proof_source_r22a()
        self.assertIn("#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x00001268UL", r22)
        self.assertIn("#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x0000126DUL", r22)
        self.assertIn("#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x00001270UL", r22a)
        self.assertIn("#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x0000127AUL", r22a)
        self.assertNotIn("#define SRK_STREAM_PROOF_PITCH_ADDRESS 0x00001268UL", r22a)
        self.assertNotIn("#define SRK_STREAM_PROOF_ACTIVE_COUNT_ADDRESS 0x0000126DUL", r22a)
        self.assertIn("srk_stream_proof_fail(state, 0xE014u)", r22a)
        self.assertNotIn("SCSP", r22a.upper())

    def test_r22a_full_build_gate_injects_corrected_renderer_and_restores_base(self):
        original = base_prepare.render_srk_saturn_midi_68k_stream_physical_proof_source
        prepared = SimpleNamespace(output_root=Path("candidate"))
        build = SimpleNamespace(successful=True)

        def fake_prepare(*args, **kwargs):
            self.assertIs(
                base_prepare.render_srk_saturn_midi_68k_stream_physical_proof_source,
                render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
            )
            return prepared

        with patch.object(base_prepare, "prepare_midi_68k_resident_stream_physical_candidate", side_effect=fake_prepare), patch(
            "rikai_kotoba.hardware.saturn.midi_68k_resident_stream_physical_candidate_r22a_full_build_gate.build_saturn_standalone_project",
            return_value=build,
        ):
            result = run_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate(
                "baseline", "candidate"
            )
        self.assertIs(result.prepared, prepared)
        self.assertIs(result.build, build)
        self.assertIs(base_prepare.render_srk_saturn_midi_68k_stream_physical_proof_source, original)

    def test_r22a_pre_media_injects_corrected_renderer_and_restores_base(self):
        original = base_pre_media.render_srk_saturn_midi_68k_stream_physical_proof_source
        sentinel = object()

        def fake_inspect(*args, **kwargs):
            self.assertIs(
                base_pre_media.render_srk_saturn_midi_68k_stream_physical_proof_source,
                render_srk_saturn_midi_68k_stream_physical_proof_source_r22a,
            )
            return sentinel

        with patch.object(
            base_pre_media,
            "inspect_midi_68k_resident_stream_physical_candidate_pre_media",
            side_effect=fake_inspect,
        ):
            result = inspect_midi_68k_resident_stream_physical_candidate_r22a_pre_media(
                "candidate", "card"
            )
        self.assertIs(result, sentinel)
        self.assertIs(base_pre_media.render_srk_saturn_midi_68k_stream_physical_proof_source, original)

    def test_r22a_guard_uses_new_token_and_restores_base(self):
        self.assertEqual(CONFIRMATION_TOKEN, "DEPLOY-R22A-STREAM-SCHEDULER-PROOF")
        original_token = base_guard.CONFIRMATION_TOKEN
        original_inspect = base_guard._inspect_pre_media
        sentinel_prepare = object()
        sentinel_apply = object()

        def fake_prepare(*args, **kwargs):
            self.assertEqual(base_guard.CONFIRMATION_TOKEN, CONFIRMATION_TOKEN)
            self.assertIsNot(base_guard._inspect_pre_media, original_inspect)
            return sentinel_prepare

        def fake_apply(*args, **kwargs):
            self.assertEqual(base_guard.CONFIRMATION_TOKEN, CONFIRMATION_TOKEN)
            self.assertIsNot(base_guard._inspect_pre_media, original_inspect)
            return sentinel_apply

        with patch.object(
            base_guard,
            "prepare_midi_68k_resident_stream_physical_candidate_guarded_deployment",
            side_effect=fake_prepare,
        ):
            result = prepare_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment(
                "candidate", "card", "guard"
            )
        self.assertIs(result, sentinel_prepare)
        self.assertEqual(base_guard.CONFIRMATION_TOKEN, original_token)
        self.assertIs(base_guard._inspect_pre_media, original_inspect)

        with patch.object(
            base_guard,
            "apply_midi_68k_resident_stream_physical_candidate_guarded_deployment",
            side_effect=fake_apply,
        ):
            result = apply_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment(
                "candidate", "card", "guard"
            )
        self.assertIs(result, sentinel_apply)
        self.assertEqual(base_guard.CONFIRMATION_TOKEN, original_token)
        self.assertIs(base_guard._inspect_pre_media, original_inspect)

    def test_r22a_cli_surfaces_correction_and_separate_deploy_token(self):
        from rikai_kotoba.tools import saturn_midi_68k_resident_stream_physical_candidate_r22a_full_build_gate as build_cli
        from rikai_kotoba.tools import saturn_midi_68k_resident_stream_physical_candidate_r22a_pre_media_gate as pre_cli
        from rikai_kotoba.tools import saturn_midi_68k_resident_stream_physical_candidate_r22a_guarded_deployment as guard_cli

        build_source = Path(build_cli.__file__).read_text(encoding="utf-8")
        pre_source = Path(pre_cli.__file__).read_text(encoding="utf-8")
        guard_source = Path(guard_cli.__file__).read_text(encoding="utf-8")
        self.assertIn("E014 selected-state capture seam", build_source)
        self.assertIn("Corrected capture proof", pre_source)
        self.assertNotIn("--apply", pre_source)
        self.assertEqual(guard_cli.CONFIRMATION_TOKEN, "DEPLOY-R22A-STREAM-SCHEDULER-PROOF")
        self.assertIn("READY FOR EXPLICIT R22A APPLY", guard_source)
        self.assertIn("R22A DEPLOYMENT VERIFIED", guard_source)


if __name__ == "__main__":
    unittest.main()
