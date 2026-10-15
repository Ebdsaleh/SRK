"""Read-only old-vs-corrected Space Spectre Saturn tone-bank audit.

The physical GATE3E failure used a specific generation policy: canonical MIDI
channel-10 percussion plus Sega's BOOTTONE velocity curve, but *before* SRK
corrected SoundFont local/global inheritance and Sega Fine Tune conformance.

This module reproduces that historical policy entirely in memory and requires
its hashes to match the actual failed GATE3E files.  Only then does it build the
current corrected policy and report the exact semantic changes.  Nothing is
written to disk or SAROO media.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator

from . import sbl_soundfont_gm as _gm
from . import sbl_soundfont_channel10 as _policy
from .midi_68k_r26_double_impact import build_srk_saturn_midi_68k_r26_space_spectre_profile


GATE3E_MELODIC_SHA256 = "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
GATE3E_DRUM_SHA256 = "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"


class SaturnToneRevisionAuditError(RuntimeError):
    """Raised when the read-only comparison cannot be trusted."""


@dataclass(frozen=True)
class SaturnToneSemanticRow:
    kind: str
    program: int
    note: int
    velocity: int
    preset_bank: int
    preset_name: str
    sample_id: int
    sample_name: str
    source_rate: int
    source_root: int
    pitch_correction: int
    zone_root: int | None
    zone_coarse: int
    zone_fine: int
    attenuation_cb: int
    base_note: int
    fine_tune: int
    total_level: int
    attack_rate: int
    decay_rate: int
    decay_level: int
    release_rate: int
    loop_enabled: bool
    loop_start: int
    loop_end: int
    pcm_sha256: str

    @property
    def key(self) -> tuple[str, int, int]:
        return self.kind, self.program, self.note


@dataclass(frozen=True)
class SaturnTonePolicyModel:
    label: str
    melodic_sha256: str
    drum_sha256: str
    melodic_bytes: int
    drum_bytes: int
    sample_rate: int
    pcm8: bool
    rows: tuple[SaturnToneSemanticRow, ...]


@dataclass(frozen=True)
class SaturnToneRevisionAudit:
    source_path: Path
    source_blob_sha1: str
    actual_melodic_sha256: str
    actual_drum_sha256: str
    historical: SaturnTonePolicyModel
    corrected: SaturnTonePolicyModel
    historical_reproduced: bool
    changed_rows: tuple[tuple[SaturnToneSemanticRow, SaturnToneSemanticRow, tuple[str, ...]], ...]


@contextmanager
def _gate3e_policy() -> Iterator[None]:
    """Reproduce GATE3E policy: channel-10 selection only, no later fixes."""

    original_selector = _gm._select_drum_preset

    def selector(sf2: _gm.Sf2Data) -> _gm.Sf2Preset:
        return _policy.select_channel10_drum_preset(sf2, fallback=original_selector)

    _gm._select_drum_preset = selector
    try:
        yield
    finally:
        _gm._select_drum_preset = original_selector


def _requirements(repository_root: Path) -> _gm.MidiToneRequirements:
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(repository_root)
    return _gm.derive_midi_tone_requirements(profile.program)


def _row(
    sf2: _gm.Sf2Data,
    preset: _gm.Sf2Preset,
    note: int,
    velocity: int,
    *,
    target_rate: int,
    pcm8: bool,
    kind: str,
    program: int,
) -> SaturnToneSemanticRow:
    zone = _gm._choose_zone(preset, note, velocity)
    sample = sf2.samples[zone.sample_id]
    layer, pcm = _gm._materialize_layer(
        sf2,
        zone,
        note,
        target_rate=target_rate,
        pcm8=pcm8,
    )
    return SaturnToneSemanticRow(
        kind=kind,
        program=program,
        note=note,
        velocity=velocity,
        preset_bank=preset.bank,
        preset_name=preset.name,
        sample_id=zone.sample_id,
        sample_name=sample.name,
        source_rate=sample.sample_rate,
        source_root=sample.original_key,
        pitch_correction=sample.pitch_correction,
        zone_root=zone.root_key,
        zone_coarse=zone.coarse_tune,
        zone_fine=zone.fine_tune,
        attenuation_cb=zone.attenuation_cb,
        base_note=layer.base_note,
        fine_tune=layer.fine_tune,
        total_level=layer.total_level,
        attack_rate=layer.attack_rate,
        decay_rate=layer.decay_rate,
        decay_level=layer.decay_level,
        release_rate=layer.release_rate,
        loop_enabled=layer.loop_enabled,
        loop_start=layer.loop_start,
        loop_end=layer.loop_end,
        pcm_sha256=sha256(pcm.data).hexdigest(),
    )


def _collect_rows(
    sf2: _gm.Sf2Data,
    requirements: _gm.MidiToneRequirements,
    *,
    target_rate: int,
    pcm8: bool,
) -> tuple[SaturnToneSemanticRow, ...]:
    rows: list[SaturnToneSemanticRow] = []
    for program, notes in requirements.melodic_notes:
        preset = _gm._select_melodic_preset(sf2, program)
        for note, velocity in notes:
            rows.append(
                _row(
                    sf2,
                    preset,
                    note,
                    velocity,
                    target_rate=target_rate,
                    pcm8=pcm8,
                    kind="melodic",
                    program=program,
                )
            )

    drums = _gm._select_drum_preset(sf2)
    for note, velocity in requirements.drum_notes:
        rows.append(
            _row(
                sf2,
                drums,
                note,
                velocity,
                target_rate=target_rate,
                pcm8=pcm8,
                kind="drum",
                program=0,
            )
        )
    return tuple(rows)


def _model(
    label: str,
    soundfont: Path,
    requirements: _gm.MidiToneRequirements,
    *,
    corrected: bool,
) -> SaturnTonePolicyModel:
    context = _policy._channel10_selector() if corrected else _gate3e_policy()
    with context:
        payload = soundfont.read_bytes()
        sf2 = _gm.parse_soundfont_bytes(payload)
        banks = _gm.build_compact_saturn_gm_banks(soundfont, requirements)
        rows = _collect_rows(
            sf2,
            requirements,
            target_rate=banks.sample_rate,
            pcm8=banks.pcm8,
        )

    melodic = _policy.normalize_sega_velocity_curve_bytes(banks.melodic_bytes)
    drums = _policy.normalize_sega_velocity_curve_bytes(banks.drum_bytes)
    return SaturnTonePolicyModel(
        label=label,
        melodic_sha256=sha256(melodic).hexdigest(),
        drum_sha256=sha256(drums).hexdigest(),
        melodic_bytes=len(melodic),
        drum_bytes=len(drums),
        sample_rate=banks.sample_rate,
        pcm8=banks.pcm8,
        rows=rows,
    )


_COMPARE_FIELDS = (
    "preset_bank",
    "preset_name",
    "sample_id",
    "sample_name",
    "source_rate",
    "source_root",
    "pitch_correction",
    "zone_root",
    "zone_coarse",
    "zone_fine",
    "attenuation_cb",
    "base_note",
    "fine_tune",
    "total_level",
    "attack_rate",
    "decay_rate",
    "decay_level",
    "release_rate",
    "loop_enabled",
    "loop_start",
    "loop_end",
    "pcm_sha256",
)


def _changed_rows(
    old: SaturnTonePolicyModel,
    new: SaturnTonePolicyModel,
) -> tuple[tuple[SaturnToneSemanticRow, SaturnToneSemanticRow, tuple[str, ...]], ...]:
    old_map = {row.key: row for row in old.rows}
    new_map = {row.key: row for row in new.rows}
    if old_map.keys() != new_map.keys():
        raise SaturnToneRevisionAuditError("old/new semantic row keys differ")
    result = []
    for key in sorted(old_map):
        before = old_map[key]
        after = new_map[key]
        fields = tuple(
            field for field in _COMPARE_FIELDS
            if getattr(before, field) != getattr(after, field)
        )
        if fields:
            result.append((before, after, fields))
    return tuple(result)


def audit_gate3e_to_current_tone_policy(
    project_directory: Path | str,
    soundfont: Path | str | None = None,
    *,
    repository_root: Path | str | None = None,
) -> SaturnToneRevisionAudit:
    """Reproduce failed GATE3E, then compare it with current policy in memory."""

    project = Path(project_directory).expanduser().resolve(strict=False)
    melodic_path = project / "cd" / "SRKGM.BIN"
    drum_path = project / "cd" / "SRKDRUM.BIN"
    if not melodic_path.is_file() or not drum_path.is_file():
        raise SaturnToneRevisionAuditError("project is missing cd/SRKGM.BIN or cd/SRKDRUM.BIN")

    actual_melodic = sha256(melodic_path.read_bytes()).hexdigest()
    actual_drums = sha256(drum_path.read_bytes()).hexdigest()
    if actual_melodic != GATE3E_MELODIC_SHA256 or actual_drums != GATE3E_DRUM_SHA256:
        raise SaturnToneRevisionAuditError(
            "project is not the locked failed GATE3E tone-bank pair"
        )

    source = (
        _gm.default_soundfont_cache()
        if soundfont is None
        else Path(soundfont).expanduser().resolve(strict=False)
    )
    if not source.is_file():
        raise SaturnToneRevisionAuditError(
            f"pinned GeneralUser SoundFont is not present locally: {source}"
        )
    if source.stat().st_size != _gm.GENERALUSER_BYTES:
        raise SaturnToneRevisionAuditError("GeneralUser SoundFont size does not match pinned source")
    blob_sha = _gm._git_blob_sha1_file(source)
    if blob_sha != _gm.GENERALUSER_BLOB_SHA1:
        raise SaturnToneRevisionAuditError("GeneralUser SoundFont blob hash does not match pinned source")

    root = Path.cwd() if repository_root is None else Path(repository_root).expanduser().resolve(strict=False)
    requirements = _requirements(root)
    historical = _model("GATE3E historical policy", source, requirements, corrected=False)
    corrected = _model("current corrected policy", source, requirements, corrected=True)
    reproduced = (
        historical.melodic_sha256 == actual_melodic
        and historical.drum_sha256 == actual_drums
    )
    changes = _changed_rows(historical, corrected)
    return SaturnToneRevisionAudit(
        source_path=source,
        source_blob_sha1=blob_sha,
        actual_melodic_sha256=actual_melodic,
        actual_drum_sha256=actual_drums,
        historical=historical,
        corrected=corrected,
        historical_reproduced=reproduced,
        changed_rows=changes,
    )
