"""Read-only artifact-level PCM/TL balance audit for failed GATE3E.

This audit exists to explain the physical result in amplitude terms rather than
by inspection of tone metadata alone.  It reads the exact failed GATE3E
SCSPBIN banks, decodes the embedded signed PCM used by each required Space
Spectre layer, and combines raw PCM level with the SCSP TL register's documented
bit attenuation.  Velocity/envelope processing is intentionally excluded, so
``post_tl_*`` is a pre-velocity/pre-EG upper-bound level rather than a complete
runtime mixer prediction.

No file is modified and no SAROO media is accessed.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
import struct
from statistics import median

from .midi_68k_r26_double_impact import build_srk_saturn_midi_68k_r26_space_spectre_profile
from .sbl_fidelity_audit import SaturnScspLayerAudit, parse_scspbin_tone_bank
from .sbl_soundfont_gm import derive_midi_tone_requirements
from .sbl_tone_revision_audit import GATE3E_DRUM_SHA256, GATE3E_MELODIC_SHA256


class SaturnPcmBalanceAuditError(RuntimeError):
    """Raised when the locked failed artifacts cannot be audited safely."""


# SCSP User's Manual, TL[7:0]: attenuation contributed by each set bit.
# Bit 0 through bit 7 respectively.
SCSP_TL_BIT_DB = (0.4, 0.8, 1.5, 3.0, 6.0, 12.0, 24.0, 48.0)
TONE_EDITOR_TOTAL_LEVEL_MAX = 127
_PCM8_FLAG = 0x00100000


@dataclass(frozen=True)
class SaturnPcmBalanceRow:
    kind: str
    program: int
    note: int
    representative_velocity: int
    layer_index: int
    sample_address: int
    sample_count: int
    pcm8: bool
    total_level: int
    tl_attenuation_db: float
    pcm_peak_dbfs: float
    pcm_rms_dbfs: float
    post_tl_peak_dbfs: float
    post_tl_rms_dbfs: float

    @property
    def tone_editor_range_exceeded(self) -> bool:
        return self.total_level > TONE_EDITOR_TOTAL_LEVEL_MAX


@dataclass(frozen=True)
class SaturnProgramBalanceSummary:
    program: int
    row_count: int
    tl_min: int
    tl_max: int
    post_tl_rms_min_dbfs: float
    post_tl_rms_median_dbfs: float
    post_tl_rms_max_dbfs: float
    tone_editor_range_exceeded: int


@dataclass(frozen=True)
class SaturnPcmBalanceReport:
    melodic_sha256: str
    drum_sha256: str
    melodic_rows: tuple[SaturnPcmBalanceRow, ...]
    drum_rows: tuple[SaturnPcmBalanceRow, ...]
    melodic_programs: tuple[SaturnProgramBalanceSummary, ...]
    drum_static_spread_db: float


def scsp_tl_attenuation_db(total_level: int) -> float:
    if not 0 <= int(total_level) <= 0xFF:
        raise SaturnPcmBalanceAuditError(f"SCSP TL is outside 8-bit range: {total_level}")
    value = int(total_level)
    return sum(weight for bit, weight in enumerate(SCSP_TL_BIT_DB) if value & (1 << bit))


def _dbfs(value: float) -> float:
    if value <= 0.0:
        return float("-inf")
    return 20.0 * math.log10(value)


def _pcm_metrics(payload: bytes, layer: SaturnScspLayerAudit) -> tuple[int, bool, float, float]:
    pcm8 = bool(layer.raw_sa & _PCM8_FLAG)
    count = int(layer.loop_end)
    if count <= 0:
        raise SaturnPcmBalanceAuditError(
            f"layer {layer.index} has no usable PCM sample count: LEA={layer.loop_end}"
        )
    width = 1 if pcm8 else 2
    start = int(layer.sample_address)
    end = start + count * width
    if end > len(payload):
        raise SaturnPcmBalanceAuditError(
            f"layer {layer.index} PCM range 0x{start:X}..0x{end:X} exceeds {len(payload)} bytes"
        )

    if pcm8:
        values = struct.unpack_from(f">{count}b", payload, start)
        scale = 128.0
    else:
        values = struct.unpack_from(f">{count}h", payload, start)
        scale = 32768.0

    peak = max(abs(value) for value in values) / scale
    rms = math.sqrt(sum(float(value) * float(value) for value in values) / count) / scale
    return count, pcm8, _dbfs(peak), _dbfs(rms)


def _unique_layer_for_note(layers: tuple[SaturnScspLayerAudit, ...], note: int) -> SaturnScspLayerAudit:
    matches = tuple(layer for layer in layers if layer.start_note <= note <= layer.end_note)
    if len(matches) != 1:
        raise SaturnPcmBalanceAuditError(
            f"note {note} resolves to {len(matches)} layers; expected exactly one in GATE3E"
        )
    return matches[0]


def _row(
    *,
    kind: str,
    program: int,
    note: int,
    velocity: int,
    payload: bytes,
    layer: SaturnScspLayerAudit,
) -> SaturnPcmBalanceRow:
    count, pcm8, peak_dbfs, rms_dbfs = _pcm_metrics(payload, layer)
    tl_db = scsp_tl_attenuation_db(layer.total_level)
    return SaturnPcmBalanceRow(
        kind=kind,
        program=program,
        note=note,
        representative_velocity=velocity,
        layer_index=layer.index,
        sample_address=layer.sample_address,
        sample_count=count,
        pcm8=pcm8,
        total_level=layer.total_level,
        tl_attenuation_db=tl_db,
        pcm_peak_dbfs=peak_dbfs,
        pcm_rms_dbfs=rms_dbfs,
        post_tl_peak_dbfs=peak_dbfs - tl_db,
        post_tl_rms_dbfs=rms_dbfs - tl_db,
    )


def _program_summary(program: int, rows: tuple[SaturnPcmBalanceRow, ...]) -> SaturnProgramBalanceSummary:
    selected = tuple(row for row in rows if row.program == program)
    if not selected:
        raise SaturnPcmBalanceAuditError(f"no melodic rows for program {program}")
    rms = [row.post_tl_rms_dbfs for row in selected]
    tls = [row.total_level for row in selected]
    return SaturnProgramBalanceSummary(
        program=program,
        row_count=len(selected),
        tl_min=min(tls),
        tl_max=max(tls),
        post_tl_rms_min_dbfs=min(rms),
        post_tl_rms_median_dbfs=float(median(rms)),
        post_tl_rms_max_dbfs=max(rms),
        tone_editor_range_exceeded=sum(row.tone_editor_range_exceeded for row in selected),
    )


def audit_gate3e_pcm_balance(
    project_directory: Path | str,
    *,
    repository_root: Path | str | None = None,
) -> SaturnPcmBalanceReport:
    project = Path(project_directory).expanduser().resolve(strict=False)
    melodic_path = project / "cd" / "SRKGM.BIN"
    drum_path = project / "cd" / "SRKDRUM.BIN"
    if not melodic_path.is_file() or not drum_path.is_file():
        raise SaturnPcmBalanceAuditError("project is missing cd/SRKGM.BIN or cd/SRKDRUM.BIN")

    melodic_payload = melodic_path.read_bytes()
    drum_payload = drum_path.read_bytes()
    melodic_sha = sha256(melodic_payload).hexdigest()
    drum_sha = sha256(drum_payload).hexdigest()
    if melodic_sha != GATE3E_MELODIC_SHA256 or drum_sha != GATE3E_DRUM_SHA256:
        raise SaturnPcmBalanceAuditError("project is not the locked physically failed GATE3E bank pair")

    melodic_bank = parse_scspbin_tone_bank(melodic_path)
    drum_bank = parse_scspbin_tone_bank(drum_path)
    root = Path.cwd() if repository_root is None else Path(repository_root).expanduser().resolve(strict=False)
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(root)
    requirements = derive_midi_tone_requirements(profile.program)

    melodic_rows: list[SaturnPcmBalanceRow] = []
    for program, notes in requirements.melodic_notes:
        if program >= melodic_bank.voice_count:
            raise SaturnPcmBalanceAuditError(f"melodic program {program} is missing from GATE3E bank")
        voice = melodic_bank.voices[program]
        for note, velocity in notes:
            layer = _unique_layer_for_note(voice.layers, note)
            melodic_rows.append(
                _row(
                    kind="melodic",
                    program=program,
                    note=note,
                    velocity=velocity,
                    payload=melodic_payload,
                    layer=layer,
                )
            )

    if not drum_bank.voices:
        raise SaturnPcmBalanceAuditError("GATE3E drum bank has no voice 0")
    drum_voice = drum_bank.voices[0]
    drum_rows = tuple(
        _row(
            kind="drum",
            program=0,
            note=note,
            velocity=velocity,
            payload=drum_payload,
            layer=_unique_layer_for_note(drum_voice.layers, note),
        )
        for note, velocity in requirements.drum_notes
    )

    melodic_tuple = tuple(melodic_rows)
    summaries = tuple(_program_summary(program, melodic_tuple) for program in requirements.programs)
    drum_levels = [row.post_tl_rms_dbfs for row in drum_rows]
    spread = max(drum_levels) - min(drum_levels) if drum_levels else 0.0
    return SaturnPcmBalanceReport(
        melodic_sha256=melodic_sha,
        drum_sha256=drum_sha,
        melodic_rows=melodic_tuple,
        drum_rows=drum_rows,
        melodic_programs=summaries,
        drum_static_spread_db=spread,
    )
