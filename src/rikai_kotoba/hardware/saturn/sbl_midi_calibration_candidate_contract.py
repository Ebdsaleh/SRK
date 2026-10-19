"""Keep SBL MIDI calibration builds on SRK's current diagnostics contract.

The current public calibration command routes through the SDDRV Ver 2.10
screen-owned Sega Direct-MIDI one-shot contract, explicit 0..15 master-volume
control, read-only SDDRV210 voice-allocation telemetry, word-safe Sound-RAM
probing, and complete 128-program family bank author. Historical GATE3/GATE4 reproduction code still passes explicit
melodic/drum banks; that legacy signature is intentionally preserved and routed
to the historical builder so prior physical evidence remains reproducible.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import sbl_midi_calibration_candidate as _legacy_candidate
from . import sbl_midi_calibration_consolidated as _candidate
from . import sbl_midi_calibration_sddrv210_voice_probe_wordbus as _sddrv210_probe


SaturnSblMidiCalibrationCandidateError = _sddrv210_probe.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _sddrv210_probe.SaturnSblMidiCalibrationCandidateResult


_CURRENT_DIAGNOSTIC_FILES = (
    "srk_diag_app.c",
    "srk_diag_app.h",
    "srk_diag_audio.c",
    "srk_diag_audio.h",
    "srk_diag_flight_recorder.c",
    "srk_diag_flight_recorder.h",
    "srk_diag_host.h",
    "srk_diag_input.c",
    "srk_diag_input.h",
    "srk_diag_menu.c",
    "srk_diag_menu.h",
    "srk_diag_midi_test.c",
    "srk_diag_midi_test.h",
    "srk_diag_vdp1.c",
    "srk_diag_vdp1.h",
    "srk_diag_video.c",
    "srk_diag_video.h",
)
_LEGACY_SOURCE_SUFFIXES = {".c", ".h", ".S"}


def _legacy_c_text(payload: bytes) -> bytes:
    """Return source text accepted by the recorded legacy SH toolchain."""

    return payload if payload.endswith(b"\n") else payload + b"\n"


def _normalize_staged_legacy_sources(source_root: Path) -> tuple[str, ...]:
    """Guarantee EOF termination for every staged C/header/assembly source."""

    normalized: list[str] = []
    for path in sorted(source_root.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.suffix not in _LEGACY_SOURCE_SUFFIXES:
            continue
        payload = path.read_bytes()
        legacy_payload = _legacy_c_text(payload)
        if legacy_payload != payload:
            path.write_bytes(legacy_payload)
        normalized.append(path.name)
    return tuple(normalized)


def _overlay_current_diagnostics(stage: Path) -> tuple[str, ...]:
    """Copy current diagnostics and normalize all staged legacy source text."""

    repo = _candidate._gm._root()
    source_root = repo / "integrations" / "saturn" / "diagnostics"
    destination_root = stage / "src"
    destination_root.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for filename in _CURRENT_DIAGNOSTIC_FILES:
        source = source_root / filename
        if not source.is_file():
            raise SaturnSblMidiCalibrationCandidateError(
                f"current diagnostic source is missing: {source}"
            )
        destination = destination_root / filename
        destination.write_bytes(source.read_bytes())
        copied.append(filename)

    _normalize_staged_legacy_sources(destination_root)
    return tuple(copied)


@contextmanager
def _current_diagnostics_contract() -> Iterator[None]:
    # Historical and SDDRV210 builders share the same consolidated helper module.
    original_copy_baseline = _candidate._gm._copy_baseline

    def copy_baseline_with_current_diagnostics(baseline, stage, manifest):
        original_copy_baseline(baseline, stage, manifest)
        _overlay_current_diagnostics(stage)

    _candidate._gm._copy_baseline = copy_baseline_with_current_diagnostics
    try:
        yield
    finally:
        _candidate._gm._copy_baseline = original_copy_baseline


def _build_log_tail(output_directory: Path, limit: int = 6000) -> str:
    """Return the preserved standalone build tail for an actionable failure."""

    log_path = output_directory / "SRK_STANDALONE_BUILD_LOG.txt"
    if not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:].strip()


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    melodic_tone_bank=None,
    drum_tone_bank=None,
    sound_driver=None,
):
    """Build current SDDRV210 calibration, or reproduce historical explicit-bank candidates."""

    output = Path(output_directory).expanduser().resolve(strict=False)
    historical = melodic_tone_bank is not None or drum_tone_bank is not None
    if historical and soundfont is not None:
        raise SaturnSblMidiCalibrationCandidateError(
            "soundfont cannot be combined with historical explicit tone-bank inputs"
        )
    if historical and (melodic_tone_bank is None or drum_tone_bank is None):
        raise SaturnSblMidiCalibrationCandidateError(
            "historical calibration reproduction requires both melodic and drum banks"
        )

    try:
        with _current_diagnostics_contract():
            if historical:
                return _legacy_candidate.build_saturn_sbl_midi_calibration_candidate(
                    baseline_project,
                    saturn_root,
                    output,
                    melodic_tone_bank=melodic_tone_bank,
                    drum_tone_bank=drum_tone_bank,
                    sound_driver=sound_driver,
                )
            return _sddrv210_probe.build_saturn_sbl_midi_calibration_candidate(
                baseline_project,
                saturn_root,
                output,
                soundfont=soundfont,
                sound_driver=sound_driver,
            )
    except (
        SaturnSblMidiCalibrationCandidateError,
        _legacy_candidate.SaturnSblMidiCalibrationCandidateError,
    ) as exc:
        tail = _build_log_tail(output)
        if tail:
            raise SaturnSblMidiCalibrationCandidateError(
                f"{exc}\n--- standalone build log tail ---\n{tail}"
            ) from exc
        if isinstance(exc, SaturnSblMidiCalibrationCandidateError):
            raise
        raise SaturnSblMidiCalibrationCandidateError(str(exc)) from exc
