"""Read-only whole-card PREPARE wrapper for the accepted R27 fidelity candidate."""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_guard_prepare as _guard
from . import midi_68k_r27_pre_media_gate as _pre

PREPARE_RECEIPT_SCHEMA = (
    "srk.saturn.midi-68k-r27-space-spectre-fidelity-p1-guard-prepare-receipt.v1"
)

SaturnMidi68KR27GuardPrepareError = _guard.SaturnMidi68KR26GuardPrepareError
SaturnMidi68KR27GuardPrepareResult = _guard.SaturnMidi68KR26GuardPrepareResult

# The reviewed R26 guard is intentionally reused for R27, but that guard reads
# its accepted anchors through historical ACCEPTED_R26_* attribute names on its
# active pre-media module.  R27 keeps native ACCEPTED_R27_* names.  Bridge those
# names only while the R27 guard context is active, then restore the module
# exactly.  This is deliberately scoped so the accepted R26 verifier remains
# immutable outside this wrapper.
_R26_COMPAT_ANCHORS = (
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
    "ACCEPTED_R26_BUILD_BIN_SHA256",
    "ACCEPTED_R26_BUILD_ISO_SHA256",
    "ACCEPTED_R26_BUILD_MAP_SHA256",
    "ACCEPTED_R26_BIN_SHA256",
    "ACCEPTED_R26_CUE_SHA256",
    "ACCEPTED_R26_SECTOR_COUNT",
    "ACCEPTED_R26_RAW_BYTES",
    "ACCEPTED_R26_USER_BYTES",
)
_MISSING = object()


@contextmanager
def _patched_r27_guard_prepare():
    original_pre_module = _guard._pre
    original_inspect = _guard.inspect_saturn_midi_68k_r26_pre_media
    original_schema = _guard.PREPARE_RECEIPT_SCHEMA
    original_compat = {
        name: getattr(_pre, name, _MISSING) for name in _R26_COMPAT_ANCHORS
    }
    try:
        for r26_name in _R26_COMPAT_ANCHORS:
            r27_name = r26_name.replace("ACCEPTED_R26_", "ACCEPTED_R27_", 1)
            setattr(_pre, r26_name, getattr(_pre, r27_name))
        _guard._pre = _pre
        _guard.inspect_saturn_midi_68k_r26_pre_media = _pre.inspect_saturn_midi_68k_r27_pre_media
        _guard.PREPARE_RECEIPT_SCHEMA = PREPARE_RECEIPT_SCHEMA
        yield
    finally:
        _guard._pre = original_pre_module
        _guard.inspect_saturn_midi_68k_r26_pre_media = original_inspect
        _guard.PREPARE_RECEIPT_SCHEMA = original_schema
        for name, value in original_compat.items():
            if value is _MISSING:
                try:
                    delattr(_pre, name)
                except AttributeError:
                    pass
            else:
                setattr(_pre, name, value)


def prepare_saturn_midi_68k_r27_space_spectre_guard(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    receipt_path: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR27GuardPrepareResult:
    """Revalidate R27 and bind it to a fresh read-only whole-card snapshot."""
    with _patched_r27_guard_prepare():
        return _guard.prepare_saturn_midi_68k_r26_space_spectre_guard(
            project_directory,
            repository_root,
            card_root,
            guard_manifest,
            receipt_path,
            destination_name=destination_name,
            category=category,
        )