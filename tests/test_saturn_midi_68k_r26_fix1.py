"""Regression tests for the physical R26 Space Spectre FIX1 repair."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from rikai_kotoba.hardware.saturn import midi_68k_r25_resident_audio_service as r25
from rikai_kotoba.hardware.saturn import midi_68k_r26_physical_candidate as r26_physical
from rikai_kotoba.hardware.saturn import midi_68k_r26_physical_candidate_full_build_gate as r26_gate
from rikai_kotoba.hardware.saturn import midi_68k_r26_resident_audio_service as r26
from rikai_kotoba.hardware.saturn.midi_68k_r26_fix1_full_build_gate import _patched_fix1_gate
from rikai_kotoba.hardware.saturn.midi_68k_r26_fix1_physical_candidate import (
    derive_r26_fix1_candidate_main,
)
from rikai_kotoba.hardware.saturn.midi_68k_r26_fix1_resident_audio_service import (
    SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS,
    SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD,
    _emit_r26_fix1_wait_until_due,
    build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image,
    validate_srk_saturn_midi_68k_r26_fix1_layout,
)


class _RecordingAssembler:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def move_dn_absw(self, *args) -> None:
        self.calls.append(("move_dn_absw",) + args)

    def move_imm_absw(self, *args) -> None:
        self.calls.append(("move_imm_absw",) + args)

    def label(self, *args) -> None:
        self.calls.append(("label",) + args)

    def move_absw_to_dn(self, *args) -> None:
        self.calls.append(("move_absw_to_dn",) + args)

    def cmp_dn_w(self, *args) -> None:
        self.calls.append(("cmp_dn_w",) + args)

    def branch_word(self, *args) -> None:
        self.calls.append(("branch_word",) + args)


class SaturnMidi68KR26Fix1Tests(unittest.TestCase):
    def test_fix1_scratch_is_unused_r26_global_space(self):
        validate_srk_saturn_midi_68k_r26_fix1_layout()
        self.assertEqual(SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD, 23)
        self.assertLess(
            SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD,
            r25.SATURN_MIDI_68K_R25_SLOT_BASE_WORD,
        )
        self.assertGreater(
            SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_WORD,
            r25.SATURN_MIDI_68K_R25_VOICE_RELEASE_US_LO_WORD,
        )

    def test_wait_hook_saves_d4_before_retire_and_restores_before_dispatch(self):
        asm = _RecordingAssembler()

        def clock_read(value, prefix):
            value.calls.append(("clock_read", prefix))

        def retire(value, prefix):
            value.calls.append(("retire", prefix))

        with (
            patch.object(r25, "_emit_prefixed_clock_read", side_effect=clock_read),
            patch.object(r25, "_emit_retire_expired", side_effect=retire),
        ):
            _emit_r26_fix1_wait_until_due(asm)

        save = ("move_dn_absw", 4, SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS)
        restore = ("move_absw_to_dn", SATURN_MIDI_68K_R26_FIX1_WAIT_CHANNEL_SCRATCH_ADDRESS, 4)
        self.assertIn(save, asm.calls)
        self.assertIn(("retire", "r25_wait"), asm.calls)
        self.assertIn(restore, asm.calls)
        self.assertLess(asm.calls.index(save), asm.calls.index(("retire", "r25_wait")))
        self.assertLess(asm.calls.index(("retire", "r25_wait")), asm.calls.index(restore))
        self.assertLess(asm.calls.index(("label", "scheduler_due")), asm.calls.index(restore))

    def test_fix1_image_is_deterministic_changed_and_restores_r25_callback(self):
        original_wait = r25._emit_r25_wait_until_due
        old = r26.build_srk_saturn_midi_68k_r26_resident_audio_service_image(release_rate=16)
        first = build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(release_rate=16)
        second = build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(release_rate=16)
        self.assertEqual(first.sha256, second.sha256)
        self.assertEqual(first.words, second.words)
        self.assertNotEqual(first.sha256, old.sha256)
        self.assertGreater(first.word_count, old.word_count)
        self.assertIs(r25._emit_r25_wait_until_due, original_wait)

    def test_fix1_gate_patch_is_scoped_and_restored(self):
        original_build = r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image
        original_main = r26_gate.derive_r26_double_impact_candidate_main
        with _patched_fix1_gate(release_rate=16) as image:
            self.assertIs(
                r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image,
                build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image,
            )
            self.assertIs(r26_gate.derive_r26_double_impact_candidate_main, derive_r26_fix1_candidate_main)
            self.assertEqual(r26_gate.ACCEPTED_R26_IMAGE_SHA256, image.sha256)
            self.assertEqual(r26_gate.ACCEPTED_R26_IMAGE_WORDS, image.word_count)
            self.assertEqual(r26_gate.ACCEPTED_R26_IMAGE_BYTES, image.byte_size)
        self.assertIs(r26_gate.build_srk_saturn_midi_68k_r26_resident_audio_service_image, original_build)
        self.assertIs(r26_gate.derive_r26_double_impact_candidate_main, original_main)

    def test_fix1_status_line_never_renders_pass_unconditionally(self):
        old_subtitle = '#define SRK_MIDI_68K_PROOF_SUBTITLE "Space Spectre - 9154 events / 16v"'
        old_status = "\n".join(
            (
                "#ifdef SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE",
                "    srk_midi_68k_draw_field(2, 25, 38, SRK_MIDI_68K_PROOF_SUCCESS);",
                "#elif defined(SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE)",
            )
        )
        synthetic = old_subtitle + "\n" + old_status + "\n"
        with patch.object(
            r26_physical,
            "derive_r26_double_impact_candidate_main",
            return_value=synthetic,
        ):
            fixed = derive_r26_fix1_candidate_main("ignored")
        self.assertIn("Space Spectre FIX1 - 9154 events / 16v", fixed)
        self.assertIn("telemetry.phase == 5u", fixed)
        self.assertIn("telemetry.phase == 6u", fixed)
        self.assertIn("Space Spectre ERROR - see telemetry", fixed)
        self.assertIn("Space Spectre running - wait", fixed)
        self.assertNotIn(old_status, fixed)


if __name__ == "__main__":
    unittest.main()
