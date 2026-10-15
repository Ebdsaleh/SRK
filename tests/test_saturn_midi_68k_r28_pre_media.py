from __future__ import annotations

from hashlib import sha256

from rikai_kotoba.hardware.saturn import midi_68k_r26_guard_prepare as r26_guard
from rikai_kotoba.hardware.saturn import midi_68k_r26_pre_media_gate as r26_pre
from rikai_kotoba.hardware.saturn import midi_68k_r28_pre_media_gate as r28_pre
from rikai_kotoba.hardware.saturn.midi_68k_r28_full_build_gate import (
    _render_r28_resident_header,
    _render_r28_resident_source,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_guard_prepare import (
    PREPARE_RECEIPT_SCHEMA,
    _patched_r28_guard_prepare,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_pre_media_gate import (
    ACCEPTED_R28_BIN_SHA256,
    ACCEPTED_R28_BUILD_BIN_SHA256,
    ACCEPTED_R28_BUILD_ISO_SHA256,
    ACCEPTED_R28_BUILD_MAP_SHA256,
    ACCEPTED_R28_MAIN_SHA256,
    ACCEPTED_R28_RESIDENT_HEADER_SHA256,
    ACCEPTED_R28_RESIDENT_IMAGE_SHA256,
    ACCEPTED_R28_RESIDENT_SOURCE_SHA256,
    ACCEPTED_R28_RUNTIME_SHA256,
    _patched_r28_pre_media,
)
from rikai_kotoba.hardware.saturn.midi_68k_r28_resident_audio_service import (
    build_srk_saturn_midi_68k_r28_resident_audio_service_image,
)


def test_r28_eridu_accepted_hashes_are_pinned():
    assert ACCEPTED_R28_RESIDENT_IMAGE_SHA256 == "48b92d0917925054f3b8c1e8a163601195eb8e3d0d1c24317ec478d90acc18b0"
    assert ACCEPTED_R28_RESIDENT_SOURCE_SHA256 == "c06403059f05813da5178001c6263280de908f4f678fafc12b2a153a7e394727"
    assert ACCEPTED_R28_RESIDENT_HEADER_SHA256 == "5cf7ee90e9ebf787d6be3b0c2cb5509d443aa6dffc1f4303daa4881646d16431"
    assert ACCEPTED_R28_MAIN_SHA256 == "fe0b35f34eaad6face8bbc89069f7ff4dd27a07598eb1570fab6202d55e9d41a"
    assert ACCEPTED_R28_RUNTIME_SHA256 == "d27b8069e4d38b9ca83ab2a2d80ad518884d6d00c379e6fe7232dd3000303a48"
    assert ACCEPTED_R28_BUILD_BIN_SHA256 == "5ff5fea4644a16f656e7da9fa4eb4b39a88fa3fcad8421714b94abf93d5bb6bb"
    assert ACCEPTED_R28_BUILD_ISO_SHA256 == "f3f603eae843cb8ec81a98a2e23666f1ef13d561ef90a54e8f4574973b3e790e"
    assert ACCEPTED_R28_BUILD_MAP_SHA256 == "0145b4ead9c24eafd4ae785adeeec3c657bb355bf70b633bacfa34c08e07cdf1"
    assert ACCEPTED_R28_BIN_SHA256 == "7b58950cba5e7da387913c69c1c715e56d20749e83f8f82d493a604717361e38"


def test_r28_current_resident_and_renderers_match_eridu_acceptance():
    image = build_srk_saturn_midi_68k_r28_resident_audio_service_image(release_rate=16)
    assert image.sha256 == ACCEPTED_R28_RESIDENT_IMAGE_SHA256
    source = _render_r28_resident_source(release_rate=16)
    header = _render_r28_resident_header(release_rate=16)
    assert sha256(source.encode("utf-8")).hexdigest() == ACCEPTED_R28_RESIDENT_SOURCE_SHA256
    assert sha256(header.encode("utf-8")).hexdigest() == ACCEPTED_R28_RESIDENT_HEADER_SHA256


def test_r28_pre_media_patch_is_scoped_and_restored():
    before = (
        r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image,
        r26_pre.derive_r26_double_impact_candidate_main,
        r26_pre.ACCEPTED_R26_BIN_SHA256,
        r26_pre._build.ACCEPTED_R26_IMAGE_SHA256,
    )
    with _patched_r28_pre_media():
        assert (
            r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image
            is build_srk_saturn_midi_68k_r28_resident_audio_service_image
        )
        assert r26_pre.ACCEPTED_R26_BIN_SHA256 == ACCEPTED_R28_BIN_SHA256
        assert r26_pre._build.ACCEPTED_R26_IMAGE_SHA256 == ACCEPTED_R28_RESIDENT_IMAGE_SHA256
    after = (
        r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image,
        r26_pre.derive_r26_double_impact_candidate_main,
        r26_pre.ACCEPTED_R26_BIN_SHA256,
        r26_pre._build.ACCEPTED_R26_IMAGE_SHA256,
    )
    assert after == before


def test_r28_guard_wrapper_exposes_r26_compatibility_anchors_only_in_context():
    assert not hasattr(r28_pre, "ACCEPTED_R26_RESIDENT_IMAGE_SHA256")
    original_pre = r26_guard._pre
    original_schema = r26_guard.PREPARE_RECEIPT_SCHEMA

    with _patched_r28_guard_prepare():
        assert r26_guard._pre is r28_pre
        assert r26_guard.PREPARE_RECEIPT_SCHEMA == PREPARE_RECEIPT_SCHEMA
        assert r28_pre.ACCEPTED_R26_RESIDENT_IMAGE_SHA256 == ACCEPTED_R28_RESIDENT_IMAGE_SHA256
        assert r28_pre.ACCEPTED_R26_BIN_SHA256 == ACCEPTED_R28_BIN_SHA256
        assert r28_pre.ACCEPTED_R26_SECTOR_COUNT == r28_pre.ACCEPTED_R28_SECTOR_COUNT

    assert r26_guard._pre is original_pre
    assert r26_guard.PREPARE_RECEIPT_SCHEMA == original_schema
    assert not hasattr(r28_pre, "ACCEPTED_R26_RESIDENT_IMAGE_SHA256")
