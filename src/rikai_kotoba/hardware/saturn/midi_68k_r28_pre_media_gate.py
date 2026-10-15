"""Accepted Eridu anchors for R28 Space Spectre percussion-pass pre-media review.

R28 keeps the physically accepted R26 FIX1 transport and R27 melodic/mixer
path, changing channel-10 percussion semantics only. This wrapper reuses the
reviewed R26 read-only verifier while substituting the exact R28 renderers and
Eridu-accepted build artifacts from the successful 2026-10-15 build.
"""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_pre_media_gate as _pre
from .midi_68k_r28_full_build_gate import (
    _render_r28_resident_header,
    _render_r28_resident_source,
)
from .midi_68k_r28_physical_candidate import derive_r28_percussion_candidate_main
from .midi_68k_r28_resident_audio_service import (
    build_srk_saturn_midi_68k_r28_resident_audio_service_image,
)

ACCEPTED_R28_SOURCE_MIDI_SHA256 = _pre.ACCEPTED_R26_SOURCE_MIDI_SHA256
ACCEPTED_R28_RESIDENT_IMAGE_SHA256 = "48b92d0917925054f3b8c1e8a163601195eb8e3d0d1c24317ec478d90acc18b0"
ACCEPTED_R28_RESIDENT_SOURCE_SHA256 = "c06403059f05813da5178001c6263280de908f4f678fafc12b2a153a7e394727"
ACCEPTED_R28_RESIDENT_HEADER_SHA256 = "5cf7ee90e9ebf787d6be3b0c2cb5509d443aa6dffc1f4303daa4881646d16431"
ACCEPTED_R28_VOICE_HEADER_SHA256 = _pre.ACCEPTED_R26_VOICE_HEADER_SHA256
ACCEPTED_R28_PLAYER_SOURCE_SHA256 = _pre.ACCEPTED_R26_PLAYER_SOURCE_SHA256
ACCEPTED_R28_PLAYER_HEADER_SHA256 = _pre.ACCEPTED_R26_PLAYER_HEADER_SHA256
ACCEPTED_R28_PROOF_SOURCE_SHA256 = _pre.ACCEPTED_R26_PROOF_SOURCE_SHA256
ACCEPTED_R28_PROOF_HEADER_SHA256 = _pre.ACCEPTED_R26_PROOF_HEADER_SHA256
ACCEPTED_R28_MAIN_SHA256 = "fe0b35f34eaad6face8bbc89069f7ff4dd27a07598eb1570fab6202d55e9d41a"
ACCEPTED_R28_MENU_SHA256 = _pre.ACCEPTED_R26_MENU_SHA256
ACCEPTED_R28_RUNTIME_SHA256 = "d27b8069e4d38b9ca83ab2a2d80ad518884d6d00c379e6fe7232dd3000303a48"

ACCEPTED_R28_BUILD_BIN_SIZE = 332400
ACCEPTED_R28_BUILD_BIN_SHA256 = "5ff5fea4644a16f656e7da9fa4eb4b39a88fa3fcad8421714b94abf93d5bb6bb"
ACCEPTED_R28_BUILD_ISO_SIZE = 425984
ACCEPTED_R28_BUILD_ISO_SHA256 = "f3f603eae843cb8ec81a98a2e23666f1ef13d561ef90a54e8f4574973b3e790e"
ACCEPTED_R28_BUILD_MAP_SIZE = 72667
ACCEPTED_R28_BUILD_MAP_SHA256 = "0145b4ead9c24eafd4ae785adeeec3c657bb355bf70b633bacfa34c08e07cdf1"
ACCEPTED_R28_PACKAGED_PCM_SIZE = _pre.ACCEPTED_R26_PACKAGED_PCM_SIZE
ACCEPTED_R28_PACKAGED_PCM_SHA256 = _pre.ACCEPTED_R26_PACKAGED_PCM_SHA256
ACCEPTED_R28_BIN_SIZE = 489216
ACCEPTED_R28_BIN_SHA256 = "7b58950cba5e7da387913c69c1c715e56d20749e83f8f82d493a604717361e38"
ACCEPTED_R28_CUE_SIZE = 81
ACCEPTED_R28_CUE_SHA256 = _pre.ACCEPTED_R26_CUE_SHA256
ACCEPTED_R28_SECTOR_COUNT = 208
ACCEPTED_R28_RAW_BYTES = 489216
ACCEPTED_R28_USER_BYTES = 425984

SaturnMidi68KR28PreMediaGateError = _pre.SaturnMidi68KR26PreMediaGateError
SaturnMidi68KR28PreMediaResult = _pre.SaturnMidi68KR26PreMediaResult

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

_R28_BY_R26_NAME = {
    "ACCEPTED_R26_SOURCE_MIDI_SHA256": ACCEPTED_R28_SOURCE_MIDI_SHA256,
    "ACCEPTED_R26_RESIDENT_IMAGE_SHA256": ACCEPTED_R28_RESIDENT_IMAGE_SHA256,
    "ACCEPTED_R26_RESIDENT_SOURCE_SHA256": ACCEPTED_R28_RESIDENT_SOURCE_SHA256,
    "ACCEPTED_R26_RESIDENT_HEADER_SHA256": ACCEPTED_R28_RESIDENT_HEADER_SHA256,
    "ACCEPTED_R26_VOICE_HEADER_SHA256": ACCEPTED_R28_VOICE_HEADER_SHA256,
    "ACCEPTED_R26_PLAYER_SOURCE_SHA256": ACCEPTED_R28_PLAYER_SOURCE_SHA256,
    "ACCEPTED_R26_PLAYER_HEADER_SHA256": ACCEPTED_R28_PLAYER_HEADER_SHA256,
    "ACCEPTED_R26_PROOF_SOURCE_SHA256": ACCEPTED_R28_PROOF_SOURCE_SHA256,
    "ACCEPTED_R26_PROOF_HEADER_SHA256": ACCEPTED_R28_PROOF_HEADER_SHA256,
    "ACCEPTED_R26_MAIN_SHA256": ACCEPTED_R28_MAIN_SHA256,
    "ACCEPTED_R26_MENU_SHA256": ACCEPTED_R28_MENU_SHA256,
    "ACCEPTED_R26_RUNTIME_SHA256": ACCEPTED_R28_RUNTIME_SHA256,
    "ACCEPTED_R26_BUILD_BIN_SIZE": ACCEPTED_R28_BUILD_BIN_SIZE,
    "ACCEPTED_R26_BUILD_BIN_SHA256": ACCEPTED_R28_BUILD_BIN_SHA256,
    "ACCEPTED_R26_BUILD_ISO_SIZE": ACCEPTED_R28_BUILD_ISO_SIZE,
    "ACCEPTED_R26_BUILD_ISO_SHA256": ACCEPTED_R28_BUILD_ISO_SHA256,
    "ACCEPTED_R26_BUILD_MAP_SIZE": ACCEPTED_R28_BUILD_MAP_SIZE,
    "ACCEPTED_R26_BUILD_MAP_SHA256": ACCEPTED_R28_BUILD_MAP_SHA256,
    "ACCEPTED_R26_PACKAGED_PCM_SIZE": ACCEPTED_R28_PACKAGED_PCM_SIZE,
    "ACCEPTED_R26_PACKAGED_PCM_SHA256": ACCEPTED_R28_PACKAGED_PCM_SHA256,
    "ACCEPTED_R26_BIN_SIZE": ACCEPTED_R28_BIN_SIZE,
    "ACCEPTED_R26_BIN_SHA256": ACCEPTED_R28_BIN_SHA256,
    "ACCEPTED_R26_CUE_SIZE": ACCEPTED_R28_CUE_SIZE,
    "ACCEPTED_R26_CUE_SHA256": ACCEPTED_R28_CUE_SHA256,
    "ACCEPTED_R26_SECTOR_COUNT": ACCEPTED_R28_SECTOR_COUNT,
    "ACCEPTED_R26_RAW_BYTES": ACCEPTED_R28_RAW_BYTES,
    "ACCEPTED_R26_USER_BYTES": ACCEPTED_R28_USER_BYTES,
}


@contextmanager
def _patched_r28_pre_media():
    image = build_srk_saturn_midi_68k_r28_resident_audio_service_image(
        release_rate=_pre._build.ACCEPTED_R26_RELEASE_RATE
    )
    if image.sha256 != ACCEPTED_R28_RESIDENT_IMAGE_SHA256:
        raise SaturnMidi68KR28PreMediaGateError(
            "current R28 resident image no longer matches Eridu acceptance"
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
            build_srk_saturn_midi_68k_r28_resident_audio_service_image
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_header = (
            _render_r28_resident_header
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_source = (
            _render_r28_resident_source
        )
        _pre.derive_r26_double_impact_candidate_main = derive_r28_percussion_candidate_main
        for name, value in _R28_BY_R26_NAME.items():
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


def inspect_saturn_midi_68k_r28_pre_media(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR28PreMediaResult:
    """Revalidate R28 and return only a read-only fresh SAROO destination plan."""
    with _patched_r28_pre_media():
        return _pre.inspect_saturn_midi_68k_r26_pre_media(
            project_directory,
            repository_root,
            card_root,
            destination_name=destination_name,
            category=category,
        )
