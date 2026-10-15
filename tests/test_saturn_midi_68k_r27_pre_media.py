from __future__ import annotations

from rikai_kotoba.hardware.saturn import midi_68k_r26_pre_media_gate as r26_pre
from rikai_kotoba.hardware.saturn.midi_68k_r27_pre_media_gate import (
    ACCEPTED_R27_BIN_SHA256,
    ACCEPTED_R27_BUILD_BIN_SHA256,
    ACCEPTED_R27_BUILD_ISO_SHA256,
    ACCEPTED_R27_BUILD_MAP_SHA256,
    ACCEPTED_R27_MAIN_SHA256,
    ACCEPTED_R27_RESIDENT_HEADER_SHA256,
    ACCEPTED_R27_RESIDENT_IMAGE_SHA256,
    ACCEPTED_R27_RESIDENT_SOURCE_SHA256,
    ACCEPTED_R27_RUNTIME_SHA256,
    _patched_r27_pre_media,
)
from rikai_kotoba.hardware.saturn.midi_68k_r27_resident_audio_service import (
    build_srk_saturn_midi_68k_r27_resident_audio_service_image,
)


def test_r27_eridu_accepted_hashes_are_pinned():
    assert ACCEPTED_R27_RESIDENT_IMAGE_SHA256 == "663b029949b69b723105738cafe6c8cc3bc8c6c515b498f8bfe26ef4777ca3ef"
    assert ACCEPTED_R27_RESIDENT_SOURCE_SHA256 == "aea7ef9c9dc62e517e94dd6b2c665912f2ce63cea1d4a82d964bf791c99bd060"
    assert ACCEPTED_R27_RESIDENT_HEADER_SHA256 == "c89031bd588c40a892c919950af89cf91b2bc1b6a70694bb8d7ebe7957a60709"
    assert ACCEPTED_R27_MAIN_SHA256 == "b687746893ba2ab32fdadb7ba5d9576a52388361a38d37e0196a6d40fe0a20f7"
    assert ACCEPTED_R27_RUNTIME_SHA256 == "552776bc15aacf15c2d7f62e596f852ecab0c2642f2ab82aabea2411db1bcedd"
    assert ACCEPTED_R27_BUILD_BIN_SHA256 == "5492bbbed7b7cef0c72cb15906c54aaaf3c838746ab61259cb73a742c2c97838"
    assert ACCEPTED_R27_BUILD_ISO_SHA256 == "afde5fc68258b67febc2a2c61fb0840470a951ccdc84d023c6a59889cd533fa0"
    assert ACCEPTED_R27_BUILD_MAP_SHA256 == "15cb632aea64fc3f4cf244d98b72ad5b191c4e06397447d5571997422c0bbb7e"
    assert ACCEPTED_R27_BIN_SHA256 == "235b7ba69dc20016b9d87c6bf32fa35276b658064a46df57de19d0f448835092"


def test_r27_current_resident_matches_eridu_acceptance():
    image = build_srk_saturn_midi_68k_r27_resident_audio_service_image(release_rate=16)
    assert image.sha256 == ACCEPTED_R27_RESIDENT_IMAGE_SHA256


def test_r27_pre_media_patch_is_scoped_and_restored():
    before = (
        r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image,
        r26_pre.derive_r26_double_impact_candidate_main,
        r26_pre.ACCEPTED_R26_BIN_SHA256,
        r26_pre._build.ACCEPTED_R26_IMAGE_SHA256,
    )
    with _patched_r27_pre_media():
        assert (
            r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image
            is build_srk_saturn_midi_68k_r27_resident_audio_service_image
        )
        assert r26_pre.ACCEPTED_R26_BIN_SHA256 == ACCEPTED_R27_BIN_SHA256
        assert r26_pre._build.ACCEPTED_R26_IMAGE_SHA256 == ACCEPTED_R27_RESIDENT_IMAGE_SHA256
    after = (
        r26_pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image,
        r26_pre.derive_r26_double_impact_candidate_main,
        r26_pre.ACCEPTED_R26_BIN_SHA256,
        r26_pre._build.ACCEPTED_R26_IMAGE_SHA256,
    )
    assert after == before
