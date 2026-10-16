"""Keep the SBL MIDI calibration candidate on SRK's current diagnostics contract.

The physical calibration candidate deliberately starts from an older, already
validated standalone Saturn project because that baseline carries proven IP.BIN,
linker, packaging and private-SDK metadata.  Generated C sources are not the
source of truth, though: the current standalone builder compiles the current SRK
diagnostics set, including ``srk_diag_midi_test.c``.

This wrapper overlays the current repository diagnostics into the fresh staging
project immediately after the baseline is copied.  It prevents an older
validated baseline from silently omitting newer reusable diagnostic sources while
preserving the baseline's proven boot/link/package contract.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import sbl_midi_calibration_candidate as _candidate


SaturnSblMidiCalibrationCandidateError = (
    _candidate.SaturnSblMidiCalibrationCandidateError
)
SaturnSblMidiCalibrationCandidateResult = (
    _candidate.SaturnSblMidiCalibrationCandidateResult
)


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


def _legacy_c_text(payload: bytes) -> bytes:
    """Return C text accepted by the recorded legacy SH-GCC warning policy."""

    return payload if payload.endswith(b"\n") else payload + b"\n"


def _overlay_current_diagnostics(stage: Path) -> tuple[str, ...]:
    """Copy current diagnostics and guarantee legacy-C EOF termination."""

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
        destination.write_bytes(_legacy_c_text(source.read_bytes()))
        copied.append(filename)
    return tuple(copied)


@contextmanager
def _current_diagnostics_contract() -> Iterator[None]:
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
    melodic_tone_bank=None,
    drum_tone_bank=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build calibration candidate with current diagnostics over the proven baseline."""

    output = Path(output_directory).expanduser().resolve(strict=False)
    try:
        with _current_diagnostics_contract():
            return _candidate.build_saturn_sbl_midi_calibration_candidate(
                baseline_project,
                saturn_root,
                output,
                melodic_tone_bank=melodic_tone_bank,
                drum_tone_bank=drum_tone_bank,
                sound_driver=sound_driver,
            )
    except SaturnSblMidiCalibrationCandidateError as exc:
        tail = _build_log_tail(output)
        if tail:
            raise SaturnSblMidiCalibrationCandidateError(
                f"{exc}\n--- standalone build log tail ---\n{tail}"
            ) from exc
        raise
