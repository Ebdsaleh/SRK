"""Read-only closure audit for Space Spectre SoundFont-to-SCSP level semantics.

The physically failed GATE3E banks proved that the song and PCM selection are
stable, but their static SCSP Total Level values catastrophically bury the
Distortion Guitar and most of the required drum kit.  This module projects the
widely implemented Creative/E-MU SoundFont compatibility rule for the static
``initialAttenuation`` generator (40 percent of its nominal centibel value)
onto the exact measured GATE3E PCM while keeping the corrected SF2 hierarchy.

It also inventories explicit SoundFont ``pmod``/``imod`` records whose
destination is ``initialAttenuation`` so SRK does not silently declare the level
model closed while custom attenuation modulators remain unmodelled.

Nothing is written to disk or SAROO media.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import struct
from statistics import median

from . import sbl_soundfont_gm as _gm
from .sbl_pcm_balance_audit import audit_gate3e_pcm_balance, scsp_tl_attenuation_db
from .sbl_tone_revision_audit import audit_gate3e_to_current_tone_policy


class SaturnLevelModelAuditError(RuntimeError):
    """Raised when the level-model projection cannot be trusted."""


SF2_INITIAL_ATTENUATION_DESTINATION = 48
SF2_STATIC_ATTENUATION_COMPATIBILITY_SCALE = 0.40


@dataclass(frozen=True)
class Sf2ModulatorRecord:
    table: str
    index: int
    source: int
    destination: int
    amount: int
    amount_source: int
    transform: int


@dataclass(frozen=True)
class SaturnProjectedLevelRow:
    kind: str
    program: int
    note: int
    attenuation_cb: int
    old_total_level: int
    old_attenuation_db: float
    old_post_tl_rms_dbfs: float
    projected_total_level: int
    projected_attenuation_db: float
    projected_post_tl_rms_dbfs: float


@dataclass(frozen=True)
class SaturnProjectedProgramSummary:
    program: int
    row_count: int
    old_median_rms_dbfs: float
    projected_median_rms_dbfs: float
    projected_tl_min: int
    projected_tl_max: int


@dataclass(frozen=True)
class SaturnLevelModelAudit:
    soundfont_path: Path
    historical_reproduced: bool
    sample_identity_preserved: bool
    rows: tuple[SaturnProjectedLevelRow, ...]
    melodic_programs: tuple[SaturnProjectedProgramSummary, ...]
    old_drum_spread_db: float
    projected_drum_spread_db: float
    pmod_records: tuple[Sf2ModulatorRecord, ...]
    imod_records: tuple[Sf2ModulatorRecord, ...]
    attenuation_modulators: tuple[Sf2ModulatorRecord, ...]
    destination_counts: tuple[tuple[int, int], ...]


def soundfont_static_attenuation_db(centibels: int) -> float:
    """Return the compatibility attenuation for the static SF2 generator.

    Real-world SoundFonts were historically authored against Creative/E-MU
    behavior where one nominal SoundFont centibel contributes 0.04 dB rather
    than 0.1 dB for the static ``initialAttenuation`` generator.  Modulator
    amounts are deliberately not scaled here.
    """

    return max(0, int(centibels)) * 0.04


def nearest_scsp_total_level(target_db: float) -> tuple[int, float]:
    """Quantize a target attenuation to the closest SCSP TL byte."""

    target = max(0.0, float(target_db))
    level = min(
        range(256),
        key=lambda value: (abs(scsp_tl_attenuation_db(value) - target), value),
    )
    return level, scsp_tl_attenuation_db(level)


def parse_sf2_modulators(payload: bytes, *, table: str) -> tuple[Sf2ModulatorRecord, ...]:
    """Parse one SoundFont modulator chunk; ignore the terminal all-zero record."""

    if len(payload) % 10:
        raise SaturnLevelModelAuditError(
            f"SoundFont {table} chunk is not aligned to 10-byte modulator records"
        )
    records = []
    for index, offset in enumerate(range(0, len(payload), 10)):
        source, destination, amount, amount_source, transform = struct.unpack_from(
            "<HHhHH", payload, offset
        )
        if source == destination == amount == amount_source == transform == 0:
            continue
        records.append(
            Sf2ModulatorRecord(
                table=table,
                index=index,
                source=source,
                destination=destination,
                amount=amount,
                amount_source=amount_source,
                transform=transform,
            )
        )
    return tuple(records)


def _modulator_inventory(soundfont: Path) -> tuple[
    tuple[Sf2ModulatorRecord, ...],
    tuple[Sf2ModulatorRecord, ...],
    tuple[Sf2ModulatorRecord, ...],
    tuple[tuple[int, int], ...],
]:
    payload = soundfont.read_bytes()
    sections = _gm._sf2_sections(payload)
    pmod = parse_sf2_modulators(sections.get((b"pdta", b"pmod"), b""), table="pmod")
    imod = parse_sf2_modulators(sections.get((b"pdta", b"imod"), b""), table="imod")
    all_records = pmod + imod
    attenuation = tuple(
        record
        for record in all_records
        if record.destination == SF2_INITIAL_ATTENUATION_DESTINATION
    )
    counts = tuple(sorted(Counter(record.destination for record in all_records).items()))
    return pmod, imod, attenuation, counts


def audit_gate3e_level_model(
    project_directory: Path | str,
    soundfont: Path | str | None = None,
    *,
    repository_root: Path | str | None = None,
) -> SaturnLevelModelAudit:
    """Project corrected SF2 static levels onto exact GATE3E PCM amplitudes."""

    root = Path.cwd() if repository_root is None else Path(repository_root).expanduser().resolve(strict=False)
    revision = audit_gate3e_to_current_tone_policy(
        project_directory,
        soundfont,
        repository_root=root,
    )
    if not revision.historical_reproduced:
        raise SaturnLevelModelAuditError(
            "historical GATE3E banks were not reproduced exactly; projection is not trustworthy"
        )

    historical = {row.key: row for row in revision.historical.rows}
    corrected = {row.key: row for row in revision.corrected.rows}
    if historical.keys() != corrected.keys():
        raise SaturnLevelModelAuditError("historical/corrected tone row keys differ")

    for key in historical:
        old = historical[key]
        new = corrected[key]
        if (
            old.sample_id != new.sample_id
            or old.sample_name != new.sample_name
            or old.pcm_sha256 != new.pcm_sha256
        ):
            raise SaturnLevelModelAuditError(
                f"tone row {key!r} changed PCM identity; GATE3E PCM cannot be reused for projection"
            )

    balance = audit_gate3e_pcm_balance(project_directory, repository_root=root)
    measured = {
        (row.kind, row.program, row.note): row
        for row in balance.melodic_rows + balance.drum_rows
    }
    if measured.keys() != corrected.keys():
        raise SaturnLevelModelAuditError("PCM balance rows do not match corrected tone rows")

    projected_rows = []
    for key in sorted(corrected):
        semantic = corrected[key]
        pcm = measured[key]
        target_db = soundfont_static_attenuation_db(semantic.attenuation_cb)
        projected_tl, projected_db = nearest_scsp_total_level(target_db)
        projected_rows.append(
            SaturnProjectedLevelRow(
                kind=semantic.kind,
                program=semantic.program,
                note=semantic.note,
                attenuation_cb=semantic.attenuation_cb,
                old_total_level=pcm.total_level,
                old_attenuation_db=pcm.tl_attenuation_db,
                old_post_tl_rms_dbfs=pcm.post_tl_rms_dbfs,
                projected_total_level=projected_tl,
                projected_attenuation_db=projected_db,
                projected_post_tl_rms_dbfs=pcm.pcm_rms_dbfs - projected_db,
            )
        )

    rows = tuple(projected_rows)
    program_summaries = []
    melodic_programs = sorted({row.program for row in rows if row.kind == "melodic"})
    for program in melodic_programs:
        selected = tuple(row for row in rows if row.kind == "melodic" and row.program == program)
        program_summaries.append(
            SaturnProjectedProgramSummary(
                program=program,
                row_count=len(selected),
                old_median_rms_dbfs=float(median(row.old_post_tl_rms_dbfs for row in selected)),
                projected_median_rms_dbfs=float(
                    median(row.projected_post_tl_rms_dbfs for row in selected)
                ),
                projected_tl_min=min(row.projected_total_level for row in selected),
                projected_tl_max=max(row.projected_total_level for row in selected),
            )
        )

    drums = tuple(row for row in rows if row.kind == "drum")
    projected_spread = (
        max(row.projected_post_tl_rms_dbfs for row in drums)
        - min(row.projected_post_tl_rms_dbfs for row in drums)
        if drums
        else 0.0
    )

    source = revision.source_path
    pmod, imod, attenuation_modulators, destination_counts = _modulator_inventory(source)
    return SaturnLevelModelAudit(
        soundfont_path=source,
        historical_reproduced=True,
        sample_identity_preserved=True,
        rows=rows,
        melodic_programs=tuple(program_summaries),
        old_drum_spread_db=balance.drum_static_spread_db,
        projected_drum_spread_db=projected_spread,
        pmod_records=pmod,
        imod_records=imod,
        attenuation_modulators=attenuation_modulators,
        destination_counts=destination_counts,
    )
