"""Read-only conformance audit for Sega Saturn SCSPBIN layer tuning.

Sega's Tone Editor layer format constrains Fine Tune to -63..+63.  This module
checks already-built tone banks against that published range so a physically
failed candidate can be diagnosed without rebuilding or touching SAROO media.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .sbl_fidelity_audit import SaturnScspBankAudit, parse_scspbin_tone_bank
from .sbl_soundfont_channel10 import SEGA_FINE_TUNE_MAX, SEGA_FINE_TUNE_MIN


@dataclass(frozen=True)
class SaturnFineTuneViolation:
    voice: int
    layer: int
    start_note: int
    end_note: int
    base_note: int
    fine_tune: int


@dataclass(frozen=True)
class SaturnFineTuneBankReport:
    bank: SaturnScspBankAudit
    layer_count: int
    minimum: int
    maximum: int
    violations: tuple[SaturnFineTuneViolation, ...]

    @property
    def conforming(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class SaturnFineTuneConformanceReport:
    melodic: SaturnFineTuneBankReport
    drums: SaturnFineTuneBankReport
    reference: SaturnFineTuneBankReport | None

    @property
    def conforming(self) -> bool:
        return self.melodic.conforming and self.drums.conforming


def audit_fine_tune_bank(path: Path | str) -> SaturnFineTuneBankReport:
    bank = parse_scspbin_tone_bank(Path(path))
    values: list[int] = []
    violations: list[SaturnFineTuneViolation] = []
    for voice in bank.voices:
        for layer in voice.layers:
            values.append(layer.fine_tune)
            if not SEGA_FINE_TUNE_MIN <= layer.fine_tune <= SEGA_FINE_TUNE_MAX:
                violations.append(
                    SaturnFineTuneViolation(
                        voice=voice.index,
                        layer=layer.index,
                        start_note=layer.start_note,
                        end_note=layer.end_note,
                        base_note=layer.base_note,
                        fine_tune=layer.fine_tune,
                    )
                )
    if not values:
        raise ValueError(f"SCSPBIN tone bank has no layers: {bank.path}")
    return SaturnFineTuneBankReport(
        bank=bank,
        layer_count=len(values),
        minimum=min(values),
        maximum=max(values),
        violations=tuple(violations),
    )


def audit_space_spectre_fine_tuning(
    project_directory: Path | str,
    *,
    reference_tone_bank: Path | str | None = None,
) -> SaturnFineTuneConformanceReport:
    project = Path(project_directory).expanduser().resolve(strict=False)
    melodic = audit_fine_tune_bank(project / "cd" / "SRKGM.BIN")
    drums = audit_fine_tune_bank(project / "cd" / "SRKDRUM.BIN")
    reference = (
        audit_fine_tune_bank(reference_tone_bank)
        if reference_tone_bank is not None
        else None
    )
    return SaturnFineTuneConformanceReport(
        melodic=melodic,
        drums=drums,
        reference=reference,
    )
