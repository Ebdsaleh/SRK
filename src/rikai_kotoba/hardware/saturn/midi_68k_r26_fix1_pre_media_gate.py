"""Accepted FIX1 anchors for the R26 Space Spectre pre-media review.

The original R26 pre-media gate remains immutable failure evidence. This thin
wrapper reuses that reviewed read-only verifier while substituting only the
Eridu-accepted FIX1 resident/main/runtime/build artifacts and FIX1 renderers.
"""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_pre_media_gate as _pre
from .midi_68k_r26_fix1_physical_candidate import derive_r26_fix1_candidate_main
from .midi_68k_r26_fix1_resident_audio_service import (
    build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image,
    render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_header,
    render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_source,
)

ACCEPTED_R26_SOURCE_MIDI_SHA256 = _pre.ACCEPTED_R26_SOURCE_MIDI_SHA256
ACCEPTED_R26_RESIDENT_IMAGE_SHA256 = "e0f63142179f1dbd0ad8a18133dc4aa47046d46ef69c4db6574aa9ecef52267d"
ACCEPTED_R26_RESIDENT_SOURCE_SHA256 = "eafae3960270b15bd392e871a45ad58314774fcd7e5cf2d063c8d294a844f5e4"
ACCEPTED_R26_RESIDENT_HEADER_SHA256 = "d3483aac77563c42f3cf229846b1215a1c26b561c2695994176d26832c0e5553"
ACCEPTED_R26_VOICE_HEADER_SHA256 = _pre.ACCEPTED_R26_VOICE_HEADER_SHA256
ACCEPTED_R26_PLAYER_SOURCE_SHA256 = _pre.ACCEPTED_R26_PLAYER_SOURCE_SHA256
ACCEPTED_R26_PLAYER_HEADER_SHA256 = _pre.ACCEPTED_R26_PLAYER_HEADER_SHA256
ACCEPTED_R26_PROOF_SOURCE_SHA256 = _pre.ACCEPTED_R26_PROOF_SOURCE_SHA256
ACCEPTED_R26_PROOF_HEADER_SHA256 = _pre.ACCEPTED_R26_PROOF_HEADER_SHA256
ACCEPTED_R26_MAIN_SHA256 = "8831dd24909cb458f26e13fd9b830ed8170116be904badc98df7cacf3c58bb52"
ACCEPTED_R26_MENU_SHA256 = _pre.ACCEPTED_R26_MENU_SHA256
ACCEPTED_R26_RUNTIME_SHA256 = "97575fc7abf5338dc98987147a928a657a2403be04432ba29957689c392c3035"

ACCEPTED_R26_BUILD_BIN_SIZE = 321696
ACCEPTED_R26_BUILD_BIN_SHA256 = "81b7f3cf7d495585390c35a9e7a691bb6ec2cb08efedef18469f020cd3fbae3f"
ACCEPTED_R26_BUILD_ISO_SIZE = 425984
ACCEPTED_R26_BUILD_ISO_SHA256 = "8b4d5af4df95e5d93a92a851e68a36d91f51f6441dd556b7dd86805fcf401c07"
ACCEPTED_R26_BUILD_MAP_SIZE = 72667
ACCEPTED_R26_BUILD_MAP_SHA256 = "be68b3e2d67dee8ffa599a86330d361de9044638c561e66987d386d50097cc51"
ACCEPTED_R26_PACKAGED_PCM_SIZE = _pre.ACCEPTED_R26_PACKAGED_PCM_SIZE
ACCEPTED_R26_PACKAGED_PCM_SHA256 = _pre.ACCEPTED_R26_PACKAGED_PCM_SHA256
ACCEPTED_R26_BIN_SIZE = 489216
ACCEPTED_R26_BIN_SHA256 = "c6700f5ed499b7c410ca7c250abd0a16c9bd5d8409f7b5c764cb49f16b03efae"
ACCEPTED_R26_CUE_SIZE = 81
ACCEPTED_R26_CUE_SHA256 = _pre.ACCEPTED_R26_CUE_SHA256
ACCEPTED_R26_SECTOR_COUNT = 208
ACCEPTED_R26_RAW_BYTES = 489216
ACCEPTED_R26_USER_BYTES = 425984

SaturnMidi68KR26Fix1PreMediaGateError = _pre.SaturnMidi68KR26PreMediaGateError
SaturnMidi68KR26Fix1PreMediaResult = _pre.SaturnMidi68KR26PreMediaResult

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


@contextmanager
def _patched_fix1_pre_media():
    image = build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image(
        release_rate=_pre._build.ACCEPTED_R26_RELEASE_RATE
    )
    if image.sha256 != ACCEPTED_R26_RESIDENT_IMAGE_SHA256:
        raise SaturnMidi68KR26Fix1PreMediaGateError(
            "current FIX1 resident image no longer matches Eridu acceptance"
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
            build_srk_saturn_midi_68k_r26_fix1_resident_audio_service_image
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_header = (
            render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_header
        )
        _pre.render_srk_saturn_midi_68k_r26_resident_audio_service_source = (
            render_srk_saturn_midi_68k_r26_fix1_resident_audio_service_source
        )
        _pre.derive_r26_double_impact_candidate_main = derive_r26_fix1_candidate_main
        for name in _PATCHED_PRE_CONSTANTS:
            setattr(_pre, name, globals()[name])
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


def inspect_saturn_midi_68k_r26_fix1_pre_media(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR26Fix1PreMediaResult:
    """Run the reviewed R26 pre-media verifier against accepted FIX1 evidence."""
    with _patched_fix1_pre_media():
        return _pre.inspect_saturn_midi_68k_r26_pre_media(
            project_directory,
            repository_root,
            card_root,
            destination_name=destination_name,
            category=category,
        )
