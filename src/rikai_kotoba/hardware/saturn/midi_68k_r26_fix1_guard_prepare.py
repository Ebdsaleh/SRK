"""Read-only whole-card PREPARE wrapper for the accepted R26 FIX1 candidate."""

from __future__ import annotations

from contextlib import contextmanager
import os

from . import midi_68k_r26_guard_prepare as _guard
from . import midi_68k_r26_fix1_pre_media_gate as _pre


PREPARE_RECEIPT_SCHEMA = (
    "srk.saturn.midi-68k-r26-space-spectre-fix1-guard-prepare-receipt.v1"
)

SaturnMidi68KR26Fix1GuardPrepareError = _guard.SaturnMidi68KR26GuardPrepareError
SaturnMidi68KR26Fix1GuardPrepareResult = _guard.SaturnMidi68KR26GuardPrepareResult


@contextmanager
def _patched_fix1_guard_prepare():
    original_pre_module = _guard._pre
    original_inspect = _guard.inspect_saturn_midi_68k_r26_pre_media
    original_schema = _guard.PREPARE_RECEIPT_SCHEMA
    try:
        _guard._pre = _pre
        _guard.inspect_saturn_midi_68k_r26_pre_media = (
            _pre.inspect_saturn_midi_68k_r26_fix1_pre_media
        )
        _guard.PREPARE_RECEIPT_SCHEMA = PREPARE_RECEIPT_SCHEMA
        yield
    finally:
        _guard._pre = original_pre_module
        _guard.inspect_saturn_midi_68k_r26_pre_media = original_inspect
        _guard.PREPARE_RECEIPT_SCHEMA = original_schema


def prepare_saturn_midi_68k_r26_space_spectre_fix1_guard(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    receipt_path: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR26Fix1GuardPrepareResult:
    """Revalidate FIX1 and bind it to a fresh read-only whole-card snapshot."""
    with _patched_fix1_guard_prepare():
        return _guard.prepare_saturn_midi_68k_r26_space_spectre_guard(
            project_directory,
            repository_root,
            card_root,
            guard_manifest,
            receipt_path,
            destination_name=destination_name,
            category=category,
        )
