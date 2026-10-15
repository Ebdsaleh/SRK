"""Accepted Eridu anchors for R27 Space Spectre fidelity-pass pre-media review.

R27 keeps the physically accepted R26 FIX1 transport path and changes only the
resident fidelity surface plus diagnostic subtitle. This wrapper reuses the
reviewed R26 read-only verifier while substituting the exact R27 renderers and
Eridu-accepted build artifacts from the successful 2026-10-15 build.
"""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_pre_media_gate as _pre
from .midi_68k_r27_physical_candidate import derive_r27_fidelity_candidate_main
from .midi_68k_r27_resident_audio_service import (
    build_srk_saturn_midi_68k_r27_resident_audio_service_image,
    render_srk_saturn_midi_68k_r27_resident_audio_service_header,
    render_srk_saturn_midi_68k_r27_resident_audio_service_source,
)

ACCEPTED_R27_SOURCE_MIDI_SHA256 = _pre.ACCEPTED_R26_SOURCE_MIDI_SHA256
ACCEPTED_R27_RESIDENT_IMAGE_SHA256 = "663b029949b69b723105738cafe6c8cc3bc8c6c515b498f8bfe26ef4777ca3ef"
ACCEPTED_R27_RESIDENT_SOURCE_SHA256 = "aea7ef9c9dc62e517e94dd6b2c665912f2ce63cea1d4a82d964bf791c99bd060"
ACCEPTED_R27_RESIDENT_HEADER_SHA256 = "c89031bd588c40a892c919950af89cf91b2bc1b6a70694bb8d7ebe7957a60709"
ACCEPTED_R27_VOICE_HEADER_SHA256 = _pre.ACCEPTED_R26_VOICE_HEADER_SHA256
ACCEPTED_R27_PLAYER_SOURCE_SHA256 = _pre.ACCEPTED_R26_PLAYER_SOURCE_SHA256
ACCEPTED_R27_PLAYER_HEADER_SHA256 = _pre.ACCEPTED_R26_PLAYER_HEADER_SHA256
ACCEPTED_R27_PROOF_SOURCE_SHA256 = _pre.ACCEPTED_R26_PROOF_SOURCE_SHA256
ACCEPTED_R27_PROOF_HEADER_SHA256 = _pre.ACCEPTED_R26_PROOF_HEADER_SHA256
ACCEPTED_R27_MAIN_SHA256 = "b687746893ba2ab32fdadb7ba5d9576a52388361a38d37e0196a6d40fe0a20f7"
ACCEPTED_R27_MENU_SHA256 = _pre.ACCEPTED_R26_MENU_SHA256
ACCEPTED_R27_RUNTIME_SHA256 = "552776bc15aacf15c2d7f62e596f852ecab0c2642f2ab82aabea2411db1bcedd"

ACCEPTED_R27_BUILD_BIN_SIZE = 327872
ACCEPTED_R27_BUILD_BIN_SHA256 = "5492bbbed7b7cef0c72cb15906c54aaaf3c838746ab61259cb73a742c2c97838"
ACCEPTED_R27_BUILD_ISO_SIZE = 425984
ACCEPTED_R27_BUILD_ISO_SHA256 = "afde5fc68258b67febc2a2c61fb0840470a951ccdc84d023c6a59889cd533fa0"
ACCEPTED_R27_BUILD_MAP_SIZE = 72667
ACCEPTED_R27_BUILD_MAP_SHA256 = "15cb632aea64fc3f4cf244d98b72ad5b191c4e06397447d5571997422c0bbb7e"
ACCEPTED_R27_PACKAGED_PCM_SIZE = _pre.ACCEPTED_R26_PACKAGED_PCM_SIZE
ACCEPTED_R27_PACKAGED_PCM_SHA256 = _pre.ACCEPTED_R26_PACKAGED_PCM_SHA256
ACCEPTED_R27_BIN_SIZE = 489216
ACCEPTED_R27_BIN_SHA256 = "235b7ba69dc20016b9d87c6bf32fa35276b658064a46df57de19d0f448835092"
ACCEPTED_R27_CUE_SIZE = 81
ACCEPTED_R27_CUE_SHA256 = _pre.ACCEPTED_R26_CUE_SHA256
ACCEPTED_R27_SECTOR_COUNT = 208
ACCEPTED_R27_RAW_BYTES = 489216
ACCEPTED_R27_USER_BYTES = 425984

SaturnMidi68KR27PreMediaGateError = _pre.SaturnMidi68KR26PreMediaGateError
SaturnMidi68KR27PreMediaResult = _pre.SaturnMidi68KR26PreMediaResult

_PATCHED_PRE_CONSTANTS = (
    "ACCEPTED_R26_SOURCE_MIDI_SHA256",
    "ACCEPTED_R26_RESIDENT_IMAGE_SHA256",
    "ACCEPTED_R26_RESIDENT_SOURCE_SHA256",
    "ACCEPTED_R26_RESIDENT_HEADER_SHA256",
    "ACCEPTED_R26_VOICE_HEADER_SHA256",
    "ACCEPTED_R26_PLAYER_SOURCE_SHA256",
    "ACCEPTED_R26_PLAYER_HEADER_SHA256",
    "ACCEPTED_R26_PROOF_SOURCE_SHA256",
    "ACCEPTED_R26_PROOF_HEADER_SHA256",
    "ACCEPTED_R26_MAIN_SHA256",
    "ACCEPTED_R26_MENU_SHA256",
    "ACCEPTED_R26_RUNTIME_SHA256",
    "ACCEPTED_R26_BUILD_BIN_SIZE",
    "ACCEPTED_R26_BUILD_BIN_SHA256",
    "ACCEPTED_R26_BUILD_ISO_SIZE",
    "ACCEPTED_R26_BUILD_ISO_SHA256",
    "ACCEPTED_R26_BUILD_MAP_SIZE",
    "ACCEPTED_R26_BUILD_MAP_SHA256",
    "ACCEPTED_R26_PACKAGED_PCM_SIZE",
    "ACCEPTED_R26_PACKAGED_PCM_SHA256",
    "ACCEPTED_R26_BIN_SIZE",
    "ACCEPTED_R26_BIN_SHA256",
    "ACCEPTED_R26_CUE_SIZE",
    "ACCEPTED_R26_CUE_SHA256",
    "ACCEPTED_R26_SECTOR_COUNT",
    "ACCEPTED_R26_RAW_BYTES",
    "ACCEPTED_R26_USER_BYTES",
)

_R27_BY_R26_NAME = {
    "ACCEPTED_R26_SOURCE_MIDI_SHA256": ACCEPTED_R27_SOURCE_MIDI_SHA256,
    "ACCEPTED_R26_RESIDENT_IMAGE_SHA256": ACCEPTED_R27_RESIDENT_IMAGE_SHA256,
    "ACCEPTED_R26_RESIDENT_SOURCE_SHA256": ACCEPTED_R27_RESIDENT_SOURCE_SHA256,
    "ACCEPTED_R26_RESIDENT_HEADER_SHA256": ACCEPTED_R27_RESIDENT_HEADER_SHA256,
    "ACCEPTED_R26_VOICE_HEADER_SHA256": ACCEPTED_R27_VOICE_HEADER_SHA256,
    "ACCEPTED_R26_PLAYER_SOURCE_SHA256": ACCEPTED_R27_PLAYER_SOURCE_SHA256,
    "ACCEPTED_R26_PLAYER_HEADER_SHA256": ACCEPTED_R27_PLAYER_HEADER_SHA256,
    "ACCEPTED_R26_PROOF_SOURCE_SHA256": ACCEPTED_R27_PROOF_SOURCE_SHA256,
    "ACCEPTED_R26_PROOF_HEADER_SHA256": ACCEPTED_R27_PROOF_HEADER_SHA256,
    "ACCEPTED_R26_MAIN_SHA256": ACCEPTED_R27_MAIN_SHA256,
    "ACCEPTED_R26_MENU_SHA256": ACCEPTED_R27_MENU_SHA256,
    "ACCEPTED_R26_RUNTIME_SHA256": ACCEPTED_R27_RUNTIME_SHA256,
    "ACCEPTED_R26_BUILD_BIN_SIZE": ACCEPTED_R27_BUILD_BIN_SIZE,
    "ACCEPTED_R26_BUILD_BIN_SHA256": ACCEPTED_R27_BUILD_BIN_SHA256,
    "ACCEPTED_R26_BUILD_ISO_SIZE": ACCEPTED_R27_BUILD_ISO_SIZE,
    "ACCEPTED_R26_BUILD_ISO_SHA256": ACCEPTED_R27_BUILD_ISO_SHA256,
    "ACCEPTED_R26_BUILD_MAP_SIZE": ACCEPTED_R27_BUILD_MAP_SIZE,
    "ACCEPTED_R26_BUILD_MAP_SHA256": ACCEPTED_R27_BUILD_MAP_SHA256,
    "ACCEPTED_R26_PACKAGED_PCM_SIZE": ACCEPTED_R27_PACKAGED_PCM_SIZE,
    "ACCEPTED_R26_PACKAGED_PCM_SHA256": ACCEPTED_R27_PACKAGED_PCM_SHA256,
    "ACCEPTED_R26_BIN_SIZE": ACCEPTED_R27_BIN_SIZE,
    "ACCEPTED_R26_BIN_SHA256": ACCEPTED_R27_BIN_SHA256,
    "ACCEPTED_R26_CUE_SIZE": ACCEPTED_R27_CUE_SIZE,
    "ACCEPTED_R26_CUE_SHA256": ACCEPTED_R27_CUE_SHA256,
    "ACCEPTED_R26_SECTOR_COUNT": ACCEPTED_R27_SECTOR_COUNT,
    "ACCEPTED_R26_RAW_BYTES": ACCEPTED_R27_RAW_BYTES,
    "ACCEPTED_R26_USER_BYTES": ACCEPTED_R27_USER_BYTES,
}


@contextmanager
def _patched_r27_pre_media():
    image = build_srk_saturn_midi_68k_r27_resident_audio_service_image(
        release_rate=_pre._build.ACCEPTED_R26_RELEASE_RATE
    )
    if image.sha256 != ACCEPTED_R27_RESIDENT_IMAGE_SHA256:
        raise SaturnMidi68KR27PreMediaGateError(
            "current R27 resident image no longer matches Eridu acceptance"
        )

    function_names = (
        "build_srk_saturn_midi_68k_r26_resident_audio_service_image",
        "render_srk_saturn_midi_68k_r26_resident_audio_service_header",
        "render_srk_saturn_midi_68k_r26_resident_audio_service_source",
        "derive_r26_double_impact_candidate_main",
    )
    original_functions = {name: getattr(_pre, name) for name in function_names}
    original_constants = {name: getattr(_pre, name) for name in _PATCHED_PRE_CONSTANTS}
    build_names = (
        "ACCEPTED_R26_IMAGE_SHA256",
        "ACCEPTED_R26_IMAGE_WORDS",
        "ACCEPTED_R26_IMAGE_BYTES",
    )
    original_build = {name: getattr(_pre._build, name) for name in build_names}
    try:
        _pre.build_srk_saturn_midi_68k_r26_resident_audio_service_image = (
            build_srk_saturn_midi_68k_r27_resident_audio_service_image
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_header = (
            render_srk_saturn_midi_68k_r27_resident_audio_service_header
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_source = (
            render_srk_saturn_midi_68k_r27_resident_audio_service_source
        )
        _pre.derive_r26_double_impact_candidate_main = derive_r27_fidelity_candidate_main
        for name, value in _R27_BY_R26_NAME.items():
            setattr(_pre, name, value)
        _pre._build.ACCEPTED_R26_IMAGE_SHA256 = image.sha256
        _pre._build.ACCEPTED_R26_IMAGE_WORDS = image.word_count
        _pre._build.ACCEPTED_R26_IMAGE_BYTES = image.byte_size
        yield
    finally:
        for name, value in original_functions.items():
            setattr(_pre, name, value)
        for name, value in original_constants.items():
            setattr(_pre, name, value)
        for name, value in original_build.items():
            setattr(_pre._build, name, value)


def inspect_saturn_midi_68k_r27_pre_media(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR27PreMediaResult:
    """Revalidate R27 and return only a read-only fresh SAROO destination plan."""
    with _patched_r27_pre_media():
        return _pre.inspect_saturn_midi_68k_r26_pre_media(
            project_directory,
            repository_root,
            card_root,
            destination_name=destination_name,
            category=category,
        )
