from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r26_fix1_guard_prepare as guard
from rikai_kotoba.hardware.saturn import midi_68k_r26_fix1_pre_media_gate as gate
from rikai_kotoba.hardware.saturn import midi_68k_r26_pre_media_gate as base


def test_fix1_pre_media_pins_eridu_accepted_artifacts():
    assert gate.ACCEPTED_R26_RESIDENT_IMAGE_SHA256 == (
        "e0f63142179f1dbd0ad8a18133dc4aa47046d46ef69c4db6574aa9ecef52267d"
    )
    assert gate.ACCEPTED_R26_RESIDENT_SOURCE_SHA256 == (
        "eafae3960270b15bd392e871a45ad58314774fcd7e5cf2d063c8d294a844f5e4"
    )
    assert gate.ACCEPTED_R26_RESIDENT_HEADER_SHA256 == (
        "d3483aac77563c42f3cf229846b1215a1c26b561c2695994176d26832c0e5553"
    )
    assert gate.ACCEPTED_R26_MAIN_SHA256 == (
        "8831dd24909cb458f26e13fd9b830ed8170116be904badc98df7cacf3c58bb52"
    )
    assert gate.ACCEPTED_R26_RUNTIME_SHA256 == (
        "97575fc7abf5338dc98987147a928a657a2403be04432ba29957689c392c3035"
    )
    assert gate.ACCEPTED_R26_BUILD_BIN_SIZE == 321696
    assert gate.ACCEPTED_R26_BUILD_BIN_SHA256 == (
        "81b7f3cf7d495585390c35a9e7a691bb6ec2cb08efedef18469f020cd3fbae3f"
    )
    assert gate.ACCEPTED_R26_BUILD_ISO_SHA256 == (
        "8b4d5af4df95e5d93a92a851e68a36d91f51f6441dd556b7dd86805fcf401c07"
    )
    assert gate.ACCEPTED_R26_BUILD_MAP_SHA256 == (
        "be68b3e2d67dee8ffa599a86330d361de9044638c561e66987d386d50097cc51"
    )
    assert gate.ACCEPTED_R26_BIN_SHA256 == (
        "c6700f5ed499b7c410ca7c250abd0a16c9bd5d8409f7b5c764cb49f16b03efae"
    )
    assert gate.ACCEPTED_R26_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )


def test_fix1_pre_media_keeps_unmodified_r26_surfaces_locked():
    assert gate.ACCEPTED_R26_SOURCE_MIDI_SHA256 == base.ACCEPTED_R26_SOURCE_MIDI_SHA256
    assert gate.ACCEPTED_R26_VOICE_HEADER_SHA256 == base.ACCEPTED_R26_VOICE_HEADER_SHA256
    assert gate.ACCEPTED_R26_PLAYER_SOURCE_SHA256 == base.ACCEPTED_R26_PLAYER_SOURCE_SHA256
    assert gate.ACCEPTED_R26_PLAYER_HEADER_SHA256 == base.ACCEPTED_R26_PLAYER_HEADER_SHA256
    assert gate.ACCEPTED_R26_PROOF_SOURCE_SHA256 == base.ACCEPTED_R26_PROOF_SOURCE_SHA256
    assert gate.ACCEPTED_R26_PROOF_HEADER_SHA256 == base.ACCEPTED_R26_PROOF_HEADER_SHA256
    assert gate.ACCEPTED_R26_MENU_SHA256 == base.ACCEPTED_R26_MENU_SHA256
    assert gate.ACCEPTED_R26_PACKAGED_PCM_SHA256 == base.ACCEPTED_R26_PACKAGED_PCM_SHA256


def test_fix1_pre_media_patch_restores_original_r26_gate():
    old_image = base.ACCEPTED_R26_RESIDENT_IMAGE_SHA256
    old_main = base.ACCEPTED_R26_MAIN_SHA256
    old_builder = base.build_srk_saturn_midi_68k_r26_resident_audio_service_image
    with gate._patched_fix1_pre_media():
        assert base.ACCEPTED_R26_RESIDENT_IMAGE_SHA256 == gate.ACCEPTED_R26_RESIDENT_IMAGE_SHA256
        assert base.ACCEPTED_R26_MAIN_SHA256 == gate.ACCEPTED_R26_MAIN_SHA256
        assert base.build_srk_saturn_midi_68k_r26_resident_audio_service_image is (
            gate.build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image
        )
    assert base.ACCEPTED_R26_RESIDENT_IMAGE_SHA256 == old_image
    assert base.ACCEPTED_R26_MAIN_SHA256 == old_main
    assert base.build_srk_saturn_midi_68k_r26_resident_audio_service_image is old_builder


def test_fix1_guard_receipt_schema_is_distinct():
    assert guard.PREPARE_RECEIPT_SCHEMA == (
        "srk.saturn.midi-68k-r26-space-spectre-fix1-guard-prepare-receipt.v1"
    )
