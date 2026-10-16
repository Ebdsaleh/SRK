"""Read-only proof for corrected multi-table Space Spectre TON authoring."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct

from . import sbl_soundfont_gm as _gm
from .sbl_fidelity_audit import audit_space_spectre_m6
from .sbl_fidelity_tone_authoring import build_space_spectre_fidelity_tone_banks
from .sbl_level_model_audit import audit_gate3e_level_model
from .sbl_modulator_scope_audit import audit_space_spectre_modulator_scope
from .sbl_tone_revision_audit import _requirements, audit_gate3e_to_current_tone_policy


class SaturnFidelityToneBuildAuditError(RuntimeError):
    """Raised when the corrected in-memory bank cannot be proven faithful."""


@dataclass(frozen=True)
class SaturnPackedToneRow:
    kind: str
    program: int
    note: int
    total_level: int
    base_note: int
    fine_tune: int
    velocity_table: int

    @property
    def key(self) -> tuple[str, int, int]:
        return self.kind, self.program, self.note


@dataclass(frozen=True)
class SaturnPackedBankAudit:
    voice_count: int
    velocity_offset: int
    peg_offset: int
    velocity_tables: tuple[bytes, ...]
    rows: tuple[SaturnPackedToneRow, ...]


@dataclass(frozen=True)
class SaturnFidelityToneBuildAudit:
    source_path: Path
    historical_reproduced: bool
    m6_exact: bool
    row_count: int
    melodic_sha256: str
    drum_sha256: str
    melodic_bytes: int
    drum_bytes: int
    melodic_table_amounts: tuple[int, ...]
    drum_table_amounts: tuple[int, ...]
    melodic_velocity_tables: tuple[bytes, ...]
    drum_velocity_tables: tuple[bytes, ...]
    pcm_identity_preserved: bool
    pitch_identity_preserved: bool
    static_total_levels_exact: bool
    packed_assignments_exact: bool


def _parse_bank(
    payload: bytes,
    *,
    kind: str,
    required_keys: set[tuple[str, int, int]],
) -> SaturnPackedBankAudit:
    if len(payload) < 10:
        raise SaturnFidelityToneBuildAuditError("generated TON bank is truncated")
    mixer, velocity, peg, plfo = struct.unpack_from(">HHHH", payload, 0)
    if mixer < 10 or (mixer - 8) % 2:
        raise SaturnFidelityToneBuildAuditError("generated TON voice table boundary is invalid")
    voice_count = (mixer - 8) // 2
    if not (mixer <= velocity < peg <= plfo <= len(payload)):
        raise SaturnFidelityToneBuildAuditError("generated TON table offsets are invalid")
    velocity_bytes = peg - velocity
    if velocity_bytes <= 0 or velocity_bytes % 10:
        raise SaturnFidelityToneBuildAuditError(
            f"generated TON velocity-table region is {velocity_bytes} bytes"
        )
    tables = tuple(payload[offset : offset + 10] for offset in range(velocity, peg, 10))

    rows: list[SaturnPackedToneRow] = []
    for voice_index in range(voice_count):
        voice_off = int.from_bytes(payload[8 + 2 * voice_index : 10 + 2 * voice_index], "big")
        if voice_off + 4 > len(payload):
            raise SaturnFidelityToneBuildAuditError(
                f"generated TON voice {voice_index} is outside the bank"
            )
        layer_count = payload[voice_off + 2] + 1
        end = voice_off + 4 + 32 * layer_count
        if end > len(payload):
            raise SaturnFidelityToneBuildAuditError(
                f"generated TON voice {voice_index} layer data is truncated"
            )
        program = voice_index if kind == "melodic" else 0
        for layer_index in range(layer_count):
            off = voice_off + 4 + 32 * layer_index
            start_note = payload[off]
            end_note = payload[off + 1]
            key = (kind, program, start_note)
            if key not in required_keys or end_note != start_note:
                continue
            fine = struct.unpack_from("b", payload, off + 0x1A)[0]
            rows.append(
                SaturnPackedToneRow(
                    kind=kind,
                    program=program,
                    note=start_note,
                    total_level=payload[off + 0x0F],
                    base_note=payload[off + 0x19],
                    fine_tune=fine,
                    velocity_table=payload[off + 0x1D],
                )
            )
    return SaturnPackedBankAudit(
        voice_count=voice_count,
        velocity_offset=velocity,
        peg_offset=peg,
        velocity_tables=tables,
        rows=tuple(rows),
    )


def _requirements_from_scope(scope_rows) -> _gm.MidiToneRequirements:
    melodic: dict[int, list[tuple[int, int]]] = {}
    drums: list[tuple[int, int]] = []
    for row in scope_rows:
        if row.kind == "melodic":
            melodic.setdefault(row.program, []).append((row.note, row.velocity))
        elif row.kind == "drum":
            drums.append((row.note, row.velocity))
        else:
            raise SaturnFidelityToneBuildAuditError(f"unknown scope row kind: {row.kind!r}")
    return _gm.MidiToneRequirements(
        melodic_notes=tuple(
            (program, tuple(sorted(notes))) for program, notes in sorted(melodic.items())
        ),
        drum_notes=tuple(sorted(drums)),
    )


def _row_map(rows):
    result = {}
    for row in rows:
        if row.key in result:
            raise SaturnFidelityToneBuildAuditError(f"duplicate tone row {row.key!r}")
        result[row.key] = row
    return result


def audit_space_spectre_fidelity_tone_build(
    project_directory: Path | str,
    soundfont: Path | str | None = None,
    *,
    repository_root: Path | str | None = None,
) -> SaturnFidelityToneBuildAudit:
    """Build corrected TON data in memory and decode it back for proof."""

    project = Path(project_directory).expanduser().resolve(strict=True)
    root = Path.cwd() if repository_root is None else Path(repository_root).expanduser().resolve(strict=False)

    scope = audit_space_spectre_modulator_scope(project, soundfont, repository_root=root)
    if not scope.historical_reproduced:
        raise SaturnFidelityToneBuildAuditError("historical GATE3E reproduction is not exact")
    if scope.rows_with_other_attenuation_modulators:
        raise SaturnFidelityToneBuildAuditError(
            "used zones still contain non-velocity destination-48 modulators"
        )

    revision = audit_gate3e_to_current_tone_policy(project, soundfont, repository_root=root)
    if not revision.historical_reproduced:
        raise SaturnFidelityToneBuildAuditError("tone revision audit lost historical reproduction")

    requirements = _requirements_from_scope(scope.rows)
    canonical_requirements = _requirements(root)
    if requirements != canonical_requirements:
        raise SaturnFidelityToneBuildAuditError(
            "resolved scope requirements differ from locked Space Spectre MIDI requirements"
        )

    velocity_mapping = {row.key: row.velocity_attenuation_amount_cb for row in scope.rows}
    build = build_space_spectre_fidelity_tone_banks(
        scope.soundfont_path,
        requirements,
        velocity_mapping,
    )

    built_rows = _row_map(build.rows)
    semantic_rows = _row_map(revision.corrected.rows)
    if built_rows.keys() != semantic_rows.keys():
        raise SaturnFidelityToneBuildAuditError("built and corrected semantic row keys differ")

    level = audit_gate3e_level_model(project, soundfont, repository_root=root)
    projected_rows = _row_map(level.rows)
    if projected_rows.keys() != built_rows.keys():
        raise SaturnFidelityToneBuildAuditError("level-model row keys differ from built rows")

    pcm_identity = all(
        built_rows[key].pcm_sha256 == semantic_rows[key].pcm_sha256 for key in built_rows
    )
    pitch_identity = all(
        (built_rows[key].base_note, built_rows[key].fine_tune)
        == (semantic_rows[key].base_note, semantic_rows[key].fine_tune)
        for key in built_rows
    )
    static_tl = all(
        built_rows[key].total_level == projected_rows[key].projected_total_level
        for key in built_rows
    )
    if not pcm_identity:
        raise SaturnFidelityToneBuildAuditError("corrected authoring changed PCM identity")
    if not pitch_identity:
        raise SaturnFidelityToneBuildAuditError("corrected authoring changed BASE/FINE pitch")
    if not static_tl:
        raise SaturnFidelityToneBuildAuditError(
            "corrected authoring did not emit projected static TL"
        )

    required_keys = set(built_rows)
    melodic = _parse_bank(
        build.banks.melodic_bytes,
        kind="melodic",
        required_keys=required_keys,
    )
    drums = _parse_bank(
        build.banks.drum_bytes,
        kind="drum",
        required_keys=required_keys,
    )
    if melodic.velocity_tables != build.melodic_velocity_tables:
        raise SaturnFidelityToneBuildAuditError(
            "packed melodic velocity tables differ from authored catalog"
        )
    if drums.velocity_tables != build.drum_velocity_tables:
        raise SaturnFidelityToneBuildAuditError(
            "packed drum velocity tables differ from authored catalog"
        )

    packed_rows = _row_map(melodic.rows + drums.rows)
    if packed_rows.keys() != built_rows.keys():
        missing = sorted(built_rows.keys() - packed_rows.keys())
        extra = sorted(packed_rows.keys() - built_rows.keys())
        raise SaturnFidelityToneBuildAuditError(
            f"packed TON rows differ from authored rows; missing={missing!r} extra={extra!r}"
        )

    packed_exact = True
    for key, authored in built_rows.items():
        packed = packed_rows[key]
        observed = (
            packed.total_level,
            packed.base_note,
            packed.fine_tune,
            packed.velocity_table,
        )
        expected = (
            authored.total_level,
            authored.base_note,
            authored.fine_tune,
            authored.velocity_table,
        )
        if observed != expected:
            packed_exact = False
            raise SaturnFidelityToneBuildAuditError(
                f"packed TON row {key!r} differs: {observed!r} != {expected!r}"
            )

    sequence_directory = project.parent / "SRK-Space-Spectre-NATIVE-SEQ-GATE3B"
    m6 = audit_space_spectre_m6(sequence_directory, repository_root=root)
    if not m6.exact:
        raise SaturnFidelityToneBuildAuditError("M6 event fidelity is no longer exact")

    return SaturnFidelityToneBuildAudit(
        source_path=scope.soundfont_path,
        historical_reproduced=True,
        m6_exact=True,
        row_count=len(built_rows),
        melodic_sha256=sha256(build.banks.melodic_bytes).hexdigest(),
        drum_sha256=sha256(build.banks.drum_bytes).hexdigest(),
        melodic_bytes=len(build.banks.melodic_bytes),
        drum_bytes=len(build.banks.drum_bytes),
        melodic_table_amounts=build.melodic_table_amounts,
        drum_table_amounts=build.drum_table_amounts,
        melodic_velocity_tables=build.melodic_velocity_tables,
        drum_velocity_tables=build.drum_velocity_tables,
        pcm_identity_preserved=pcm_identity,
        pitch_identity_preserved=pitch_identity,
        static_total_levels_exact=static_tl,
        packed_assignments_exact=packed_exact,
    )
