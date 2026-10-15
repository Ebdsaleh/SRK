"""Resolve the SoundFont modulator hierarchy used by Space Spectre.

The whole-file modulator inventory is intentionally too broad for a playback
fix: GeneralUser GS contains thousands of pmod/imod records, most of which are
irrelevant to Space Spectre.  This audit follows the exact preset/instrument bag
path for every note selected by the current corrected tone policy and resolves
SoundFont modulator precedence for those zones only.

Important SoundFont hierarchy rules implemented here:

* instrument local modulators replace identical instrument-global modulators;
* an explicit instrument modulator identical to a default modulator replaces
  that default;
* preset local modulators replace identical preset-global modulators;
* effective preset modulators add to the instrument result, including when an
  identical modulator exists at instrument level.

The implicit default MIDI velocity -> initialAttenuation modulator is
0x0502 -> generator 48, amount +960 cB, amount source 0, transform 0.

Nothing is written to disk or SAROO media.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Mapping, Sequence

from . import sbl_soundfont_gm as _gm
from . import sbl_soundfont_channel10 as _policy
from .sbl_level_model_audit import (
    SF2_INITIAL_ATTENUATION_DESTINATION,
    Sf2ModulatorRecord,
    parse_sf2_modulators,
)
from .sbl_tone_revision_audit import (
    SaturnToneSemanticRow,
    audit_gate3e_to_current_tone_policy,
)


class SaturnModulatorScopeAuditError(RuntimeError):
    """Raised when an exact used-zone modulator path cannot be established."""


SF2_DEFAULT_VELOCITY_SOURCE = 0x0502
SF2_DEFAULT_VELOCITY_ATTENUATION_CB = 960
SF2_DEFAULT_AMOUNT_SOURCE = 0x0000
SF2_DEFAULT_TRANSFORM = 0x0000


@dataclass(frozen=True)
class Sf2BagRecord:
    generator_index: int
    modulator_index: int


@dataclass(frozen=True)
class Sf2ModulatorIdentity:
    source: int
    destination: int
    amount_source: int
    transform: int


@dataclass(frozen=True)
class EffectiveSf2Modulator:
    identity: Sf2ModulatorIdentity
    amount: int
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class SaturnModulatorScopeRow:
    kind: str
    program: int
    note: int
    velocity: int
    preset_bank: int
    preset_name: str
    preset_index: int
    preset_global_bag: int | None
    preset_local_bag: int
    instrument_index: int
    instrument_name: str
    instrument_global_bag: int | None
    instrument_local_bag: int
    sample_id: int
    sample_name: str
    velocity_attenuation_amount_cb: int
    attenuation_modulators: tuple[EffectiveSf2Modulator, ...]

    @property
    def key(self) -> tuple[str, int, int]:
        return self.kind, self.program, self.note

    @property
    def non_velocity_attenuation_modulators(self) -> tuple[EffectiveSf2Modulator, ...]:
        return tuple(
            mod
            for mod in self.attenuation_modulators
            if mod.identity != default_velocity_identity()
        )


@dataclass(frozen=True)
class SaturnModulatorScopeAudit:
    soundfont_path: Path
    historical_reproduced: bool
    rows: tuple[SaturnModulatorScopeRow, ...]

    @property
    def velocity_amounts(self) -> tuple[int, ...]:
        return tuple(sorted({row.velocity_attenuation_amount_cb for row in self.rows}))

    @property
    def rows_with_other_attenuation_modulators(self) -> tuple[SaturnModulatorScopeRow, ...]:
        return tuple(row for row in self.rows if row.non_velocity_attenuation_modulators)


def default_velocity_identity() -> Sf2ModulatorIdentity:
    return Sf2ModulatorIdentity(
        source=SF2_DEFAULT_VELOCITY_SOURCE,
        destination=SF2_INITIAL_ATTENUATION_DESTINATION,
        amount_source=SF2_DEFAULT_AMOUNT_SOURCE,
        transform=SF2_DEFAULT_TRANSFORM,
    )


def decode_modulator_source(source: int) -> str:
    """Return a compact description of one sfModulator source operator."""

    value = int(source) & 0xFFFF
    index = value & 0x7F
    is_cc = bool(value & 0x0080)
    direction = "negative" if value & 0x0100 else "positive"
    polarity = "bipolar" if value & 0x0200 else "unipolar"
    curve_code = (value >> 10) & 0x3F
    curve = {0: "linear", 1: "concave", 2: "convex", 3: "switch"}.get(
        curve_code, f"type{curve_code}"
    )
    if is_cc:
        controller = f"CC{index}"
    else:
        controller = {
            0: "none",
            2: "velocity",
            3: "key",
            10: "poly-pressure",
            13: "channel-pressure",
            14: "pitch-wheel",
            16: "pitch-wheel-sensitivity",
        }.get(index, f"general-{index}")
    return f"{controller}/{direction}/{polarity}/{curve}"


def _identity(record: Sf2ModulatorRecord) -> Sf2ModulatorIdentity:
    return Sf2ModulatorIdentity(
        source=record.source,
        destination=record.destination,
        amount_source=record.amount_source,
        transform=record.transform,
    )


def _bag_records(payload: bytes) -> tuple[Sf2BagRecord, ...]:
    if len(payload) % 4:
        raise SaturnModulatorScopeAuditError("SoundFont bag table is not 4-byte aligned")
    return tuple(
        Sf2BagRecord(*struct.unpack_from("<HH", payload, offset))
        for offset in range(0, len(payload), 4)
    )


def _slice_generators(
    bags: Sequence[Sf2BagRecord],
    generators: Sequence[tuple[int, int]],
    bag_index: int,
) -> dict[int, int]:
    if not 0 <= bag_index < len(bags):
        raise SaturnModulatorScopeAuditError(f"bag index is out of range: {bag_index}")
    start = bags[bag_index].generator_index
    end = bags[bag_index + 1].generator_index if bag_index + 1 < len(bags) else len(generators)
    if start > end or end > len(generators):
        raise SaturnModulatorScopeAuditError("SoundFont bag generator range is invalid")
    return _gm._zone_map(generators[start:end])


def _slice_modulators(
    bags: Sequence[Sf2BagRecord],
    modulators: Sequence[Sf2ModulatorRecord],
    bag_index: int,
) -> tuple[Sf2ModulatorRecord, ...]:
    if not 0 <= bag_index < len(bags):
        raise SaturnModulatorScopeAuditError(f"bag index is out of range: {bag_index}")
    start = bags[bag_index].modulator_index
    end = bags[bag_index + 1].modulator_index if bag_index + 1 < len(bags) else 0x10000
    if start > end:
        raise SaturnModulatorScopeAuditError("SoundFont bag modulator range is invalid")
    return tuple(record for record in modulators if start <= record.index < end)


def _last_by_identity(records: Sequence[Sf2ModulatorRecord]) -> dict[Sf2ModulatorIdentity, Sf2ModulatorRecord]:
    """Normalize one zone: a later identical record supersedes an earlier one."""

    result: dict[Sf2ModulatorIdentity, Sf2ModulatorRecord] = {}
    for record in records:
        result[_identity(record)] = record
    return result


def _global_local_scope(
    global_records: Sequence[Sf2ModulatorRecord],
    local_records: Sequence[Sf2ModulatorRecord],
    *,
    global_label: str,
    local_label: str,
) -> dict[Sf2ModulatorIdentity, EffectiveSf2Modulator]:
    """Apply local-over-global replacement for one SoundFont hierarchy level."""

    global_map = _last_by_identity(global_records)
    local_map = _last_by_identity(local_records)
    result: dict[Sf2ModulatorIdentity, EffectiveSf2Modulator] = {}
    for identity, record in global_map.items():
        if identity not in local_map:
            result[identity] = EffectiveSf2Modulator(identity, record.amount, (global_label,))
    for identity, record in local_map.items():
        result[identity] = EffectiveSf2Modulator(identity, record.amount, (local_label,))
    return result


def resolve_effective_modulators(
    instrument_global: Sequence[Sf2ModulatorRecord],
    instrument_local: Sequence[Sf2ModulatorRecord],
    preset_global: Sequence[Sf2ModulatorRecord],
    preset_local: Sequence[Sf2ModulatorRecord],
) -> tuple[EffectiveSf2Modulator, ...]:
    """Resolve defaults/instrument replacement, then additive preset modulators."""

    default_identity = default_velocity_identity()
    instrument = _global_local_scope(
        instrument_global,
        instrument_local,
        global_label="instrument-global",
        local_label="instrument-local",
    )

    effective: dict[Sf2ModulatorIdentity, EffectiveSf2Modulator] = {
        default_identity: EffectiveSf2Modulator(
            default_identity,
            SF2_DEFAULT_VELOCITY_ATTENUATION_CB,
            ("implicit-default",),
        )
    }
    for identity, modulator in instrument.items():
        # An identical explicit instrument modulator replaces the corresponding
        # implicit default. Other identities simply add another destination term.
        effective[identity] = modulator

    preset = _global_local_scope(
        preset_global,
        preset_local,
        global_label="preset-global",
        local_label="preset-local",
    )
    for identity, modulator in preset.items():
        previous = effective.get(identity)
        if previous is None:
            effective[identity] = modulator
        else:
            effective[identity] = EffectiveSf2Modulator(
                identity=identity,
                amount=previous.amount + modulator.amount,
                provenance=previous.provenance + modulator.provenance,
            )
    return tuple(
        effective[identity]
        for identity in sorted(
            effective,
            key=lambda item: (item.destination, item.source, item.amount_source, item.transform),
        )
    )


def _one_global_bag(
    bag_indices: Sequence[int],
    bags: Sequence[Sf2BagRecord],
    generators: Sequence[tuple[int, int]],
    *,
    index_operator: int,
    label: str,
) -> tuple[int | None, dict[int, int]]:
    globals_ = []
    for bag_index in bag_indices:
        mapping = _slice_generators(bags, generators, bag_index)
        if index_operator not in mapping:
            globals_.append((bag_index, mapping))
    if len(globals_) > 1:
        raise SaturnModulatorScopeAuditError(f"{label} has multiple global zones")
    return globals_[0] if globals_ else (None, {})


def _semantic_match(mapping: Mapping[int, int], row: SaturnToneSemanticRow) -> bool:
    root_raw = mapping.get(_gm._GEN_ROOT_KEY)
    root_key = None if root_raw is None or root_raw > 127 else root_raw
    return (
        mapping.get(_gm._GEN_SAMPLE_ID, -1) == row.sample_id
        and max(0, mapping.get(_gm._GEN_ATTENUATION, 0)) == row.attenuation_cb
        and mapping.get(_gm._GEN_COARSE_TUNE, 0) == row.zone_coarse
        and mapping.get(_gm._GEN_FINE_TUNE, 0) == row.zone_fine
        and root_key == row.zone_root
    )


def _range_distance(value: int, lo: int, hi: int) -> int:
    if lo <= value <= hi:
        return 0
    return min(abs(value - lo), abs(value - hi))


def _resolve_row(
    row: SaturnToneSemanticRow,
    *,
    phdr: Sequence[tuple[str, int, int, int]],
    inst: Sequence[tuple[str, int]],
    pbag: Sequence[Sf2BagRecord],
    ibag: Sequence[Sf2BagRecord],
    pgen: Sequence[tuple[int, int]],
    igen: Sequence[tuple[int, int]],
    pmod: Sequence[Sf2ModulatorRecord],
    imod: Sequence[Sf2ModulatorRecord],
    samples: Sequence[_gm.Sf2Sample],
) -> SaturnModulatorScopeRow:
    preset_indices = [
        index
        for index, (name, program, bank, _bag) in enumerate(phdr[:-1])
        if name == row.preset_name and program == row.program and bank == row.preset_bank
    ]
    if len(preset_indices) != 1:
        raise SaturnModulatorScopeAuditError(
            f"used preset {row.preset_bank}:{row.program} {row.preset_name!r} is not unique"
        )
    preset_index = preset_indices[0]
    preset_bag_indices = tuple(range(phdr[preset_index][3], phdr[preset_index + 1][3]))
    preset_global_bag, preset_global_map = _one_global_bag(
        preset_bag_indices,
        pbag,
        pgen,
        index_operator=_gm._GEN_INSTRUMENT,
        label=f"preset {row.preset_name!r}",
    )

    candidates = []
    for preset_local_bag in preset_bag_indices:
        preset_local_map = _slice_generators(pbag, pgen, preset_local_bag)
        if _gm._GEN_INSTRUMENT not in preset_local_map:
            continue
        preset_effective = _policy._resolve_global_local_zone(preset_global_map, preset_local_map)
        pkey_lo, pkey_hi = _gm._range(preset_effective.get(_gm._GEN_KEY_RANGE))
        if not pkey_lo <= row.note <= pkey_hi:
            continue
        inst_index = preset_local_map[_gm._GEN_INSTRUMENT]
        if not 0 <= inst_index < len(inst) - 1:
            continue
        inst_bag_indices = tuple(range(inst[inst_index][1], inst[inst_index + 1][1]))
        inst_global_bag, inst_global_map = _one_global_bag(
            inst_bag_indices,
            ibag,
            igen,
            index_operator=_gm._GEN_SAMPLE_ID,
            label=f"instrument {inst[inst_index][0]!r}",
        )
        for inst_local_bag in inst_bag_indices:
            inst_local_map = _slice_generators(ibag, igen, inst_local_bag)
            if _gm._GEN_SAMPLE_ID not in inst_local_map:
                continue
            merged = _policy._space_spectre_merge_zone_maps(
                preset_global_map,
                preset_local_map,
                inst_global_map,
                inst_local_map,
            )
            key_lo, key_hi = _gm._range(merged.get(_gm._GEN_KEY_RANGE))
            vel_lo, vel_hi = _gm._range(merged.get(_gm._GEN_VEL_RANGE))
            if not key_lo <= row.note <= key_hi:
                continue
            if not _semantic_match(merged, row):
                continue
            candidates.append(
                (
                    _range_distance(row.velocity, vel_lo, vel_hi),
                    key_hi - key_lo,
                    vel_hi - vel_lo,
                    preset_local_bag,
                    inst_index,
                    inst_global_bag,
                    inst_local_bag,
                )
            )

    if not candidates:
        raise SaturnModulatorScopeAuditError(f"no raw SoundFont zone path matches semantic row {row.key!r}")
    candidates.sort()
    best = candidates[0]
    if len(candidates) > 1 and candidates[1][:3] == best[:3] and candidates[1][4:] != best[4:]:
        raise SaturnModulatorScopeAuditError(f"raw SoundFont zone path is ambiguous for {row.key!r}")

    _, _, _, preset_local_bag, inst_index, inst_global_bag, inst_local_bag = best
    preset_global_mods = () if preset_global_bag is None else _slice_modulators(pbag, pmod, preset_global_bag)
    preset_local_mods = _slice_modulators(pbag, pmod, preset_local_bag)
    inst_global_mods = () if inst_global_bag is None else _slice_modulators(ibag, imod, inst_global_bag)
    inst_local_mods = _slice_modulators(ibag, imod, inst_local_bag)
    effective = resolve_effective_modulators(
        inst_global_mods,
        inst_local_mods,
        preset_global_mods,
        preset_local_mods,
    )
    attenuation = tuple(
        mod for mod in effective if mod.identity.destination == SF2_INITIAL_ATTENUATION_DESTINATION
    )
    velocity = next((mod for mod in attenuation if mod.identity == default_velocity_identity()), None)
    if velocity is None:
        raise SaturnModulatorScopeAuditError(f"default velocity identity vanished for {row.key!r}")

    if not 0 <= row.sample_id < len(samples):
        raise SaturnModulatorScopeAuditError(f"sample id is out of range for {row.key!r}")
    return SaturnModulatorScopeRow(
        kind=row.kind,
        program=row.program,
        note=row.note,
        velocity=row.velocity,
        preset_bank=row.preset_bank,
        preset_name=row.preset_name,
        preset_index=preset_index,
        preset_global_bag=preset_global_bag,
        preset_local_bag=preset_local_bag,
        instrument_index=inst_index,
        instrument_name=inst[inst_index][0],
        instrument_global_bag=inst_global_bag,
        instrument_local_bag=inst_local_bag,
        sample_id=row.sample_id,
        sample_name=samples[row.sample_id].name,
        velocity_attenuation_amount_cb=velocity.amount,
        attenuation_modulators=attenuation,
    )


def audit_space_spectre_modulator_scope(
    project_directory: Path | str,
    soundfont: Path | str | None = None,
    *,
    repository_root: Path | str | None = None,
) -> SaturnModulatorScopeAudit:
    """Resolve only attenuation modulators reachable by Space Spectre notes."""

    root = Path.cwd() if repository_root is None else Path(repository_root).expanduser().resolve(strict=False)
    revision = audit_gate3e_to_current_tone_policy(
        project_directory,
        soundfont,
        repository_root=root,
    )
    if not revision.historical_reproduced:
        raise SaturnModulatorScopeAuditError("historical GATE3E reproduction is not exact")

    source = revision.source_path
    payload = source.read_bytes()
    sections = _gm._sf2_sections(payload)
    required = (
        (b"pdta", b"phdr"), (b"pdta", b"pbag"), (b"pdta", b"pmod"),
        (b"pdta", b"pgen"), (b"pdta", b"inst"), (b"pdta", b"ibag"),
        (b"pdta", b"imod"), (b"pdta", b"igen"), (b"pdta", b"shdr"),
    )
    missing = [b"/".join(key).decode("ascii") for key in required if key not in sections]
    if missing:
        raise SaturnModulatorScopeAuditError("SoundFont missing chunks: " + ", ".join(missing))

    phdr = _gm._parse_preset_headers(sections[(b"pdta", b"phdr")])
    inst = _gm._parse_inst_headers(sections[(b"pdta", b"inst")])
    pbag = _bag_records(sections[(b"pdta", b"pbag")])
    ibag = _bag_records(sections[(b"pdta", b"ibag")])
    pgen = _gm._parse_generators(sections[(b"pdta", b"pgen")])
    igen = _gm._parse_generators(sections[(b"pdta", b"igen")])
    pmod = parse_sf2_modulators(sections[(b"pdta", b"pmod")], table="pmod")
    imod = parse_sf2_modulators(sections[(b"pdta", b"imod")], table="imod")
    samples = _gm._parse_samples(sections[(b"pdta", b"shdr")])

    rows = tuple(
        _resolve_row(
            row,
            phdr=phdr,
            inst=inst,
            pbag=pbag,
            ibag=ibag,
            pgen=pgen,
            igen=igen,
            pmod=pmod,
            imod=imod,
            samples=samples,
        )
        for row in revision.corrected.rows
    )
    if len({row.key for row in rows}) != len(rows):
        raise SaturnModulatorScopeAuditError("resolved rows are not unique")
    return SaturnModulatorScopeAudit(
        soundfont_path=source,
        historical_reproduced=True,
        rows=rows,
    )
