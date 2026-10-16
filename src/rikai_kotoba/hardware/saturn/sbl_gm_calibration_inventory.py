"""Read-only 128-program General MIDI calibration inventory for Saturn.

The interactive MIDI test must not assume that Space Spectre's three velocity
curves describe the complete GeneralUser GS library.  This audit resolves one
representative C4/velocity-100 row for every GM program through the corrected
SoundFont hierarchy and then walks the raw pbag/pmod/ibag/imod path to recover
the effective velocity->initialAttenuation modulator actually authored for that
zone.

Nothing is written and no Saturn/SAROO hardware is touched.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import sbl_soundfont_gm as _gm
from . import sbl_soundfont_channel10 as _policy
from . import sbl_modulator_scope_audit as _scope
from . import sbl_tone_revision_audit as _revision


GM_PROGRAM_COUNT = 128
GM_FAMILY_SIZE = 8
GM_CALIBRATION_NOTE = 60
GM_CALIBRATION_VELOCITY = 100


class SaturnGmCalibrationInventoryError(RuntimeError):
    """Raised when the complete GM calibration map cannot be resolved exactly."""


@dataclass(frozen=True)
class SaturnGmCalibrationRow:
    program: int
    family: int
    preset_name: str
    sample_id: int
    sample_name: str
    velocity_amount_cb: int
    attenuation_modulator_count: int
    other_attenuation_modulator_count: int
    loop_enabled: bool
    base_note: int
    fine_tune: int
    attenuation_cb: int


@dataclass(frozen=True)
class SaturnGmCalibrationInventory:
    source_path: Path
    rows: tuple[SaturnGmCalibrationRow, ...]
    velocity_amount_counts: tuple[tuple[int, int], ...]
    rows_with_other_attenuation_modulators: tuple[int, ...]

    @property
    def velocity_amounts(self) -> tuple[int, ...]:
        return tuple(amount for amount, _count in self.velocity_amount_counts)


def _raw_tables(payload: bytes):
    sections = _gm._sf2_sections(payload)
    required = (
        (b"pdta", b"phdr"), (b"pdta", b"pbag"), (b"pdta", b"pmod"),
        (b"pdta", b"pgen"), (b"pdta", b"inst"), (b"pdta", b"ibag"),
        (b"pdta", b"imod"), (b"pdta", b"igen"), (b"pdta", b"shdr"),
    )
    missing = [b"/".join(key).decode("ascii") for key in required if key not in sections]
    if missing:
        raise SaturnGmCalibrationInventoryError(
            "SoundFont missing calibration chunks: " + ", ".join(missing)
        )
    return dict(
        phdr=_gm._parse_preset_headers(sections[(b"pdta", b"phdr")]),
        inst=_gm._parse_inst_headers(sections[(b"pdta", b"inst")]),
        pbag=_scope._bag_records(sections[(b"pdta", b"pbag")]),
        ibag=_scope._bag_records(sections[(b"pdta", b"ibag")]),
        pgen=_gm._parse_generators(sections[(b"pdta", b"pgen")]),
        igen=_gm._parse_generators(sections[(b"pdta", b"igen")]),
        pmod=_scope.parse_sf2_modulators(sections[(b"pdta", b"pmod")], table="pmod"),
        imod=_scope.parse_sf2_modulators(sections[(b"pdta", b"imod")], table="imod"),
        samples=_gm._parse_samples(sections[(b"pdta", b"shdr")]),
    )


def _zone_matches_selected(mapping, selected) -> bool:
    """Match the exact high-level zone already selected by ``_choose_zone``.

    GeneralUser contains legitimate duplicate raw bag paths.  The normal
    SoundFont parser preserves bag order and ``_choose_zone`` uses that order as
    its final stable tie-break.  Reconstruct the complete selected zone here so
    the modulator audit follows that same path instead of treating identical raw
    generator paths as an error.
    """

    key_lo, key_hi = _gm._range(mapping.get(_gm._GEN_KEY_RANGE))
    vel_lo, vel_hi = _gm._range(mapping.get(_gm._GEN_VEL_RANGE))
    root_raw = mapping.get(_gm._GEN_ROOT_KEY)
    root_key = None if root_raw is None or root_raw > 127 else root_raw
    return (
        key_lo == selected.key_lo
        and key_hi == selected.key_hi
        and vel_lo == selected.vel_lo
        and vel_hi == selected.vel_hi
        and mapping.get(_gm._GEN_SAMPLE_ID, -1) == selected.sample_id
        and mapping.get(_gm._GEN_START, 0)
        + 32768 * mapping.get(_gm._GEN_START_COARSE, 0)
        == selected.start_offset
        and mapping.get(_gm._GEN_END, 0)
        + 32768 * mapping.get(_gm._GEN_END_COARSE, 0)
        == selected.end_offset
        and mapping.get(_gm._GEN_LOOP_START, 0)
        + 32768 * mapping.get(_gm._GEN_LOOP_START_COARSE, 0)
        == selected.loop_start_offset
        and mapping.get(_gm._GEN_LOOP_END, 0)
        + 32768 * mapping.get(_gm._GEN_LOOP_END_COARSE, 0)
        == selected.loop_end_offset
        and max(0, mapping.get(_gm._GEN_ATTENUATION, 0)) == selected.attenuation_cb
        and mapping.get(_gm._GEN_COARSE_TUNE, 0) == selected.coarse_tune
        and mapping.get(_gm._GEN_FINE_TUNE, 0) == selected.fine_tune
        and mapping.get(_gm._GEN_ATTACK, -12000) == selected.attack_tc
        and mapping.get(_gm._GEN_DECAY, -12000) == selected.decay_tc
        and max(0, mapping.get(_gm._GEN_SUSTAIN, 0)) == selected.sustain_cb
        and mapping.get(_gm._GEN_RELEASE, -12000) == selected.release_tc
        and (mapping.get(_gm._GEN_SAMPLE_MODES, 0) & 3) == selected.sample_modes
        and root_key == selected.root_key
        and mapping.get(_gm._GEN_SCALE_TUNING, 100) == selected.scale_tuning
    )


def _resolve_calibration_row(semantic, selected, **raw):
    """Recover modulators from the exact zone chosen by the semantic parser."""

    phdr = raw["phdr"]
    inst = raw["inst"]
    pbag = raw["pbag"]
    ibag = raw["ibag"]
    pgen = raw["pgen"]
    igen = raw["igen"]
    pmod = raw["pmod"]
    imod = raw["imod"]
    samples = raw["samples"]

    if selected.sample_id != semantic.sample_id:
        raise SaturnGmCalibrationInventoryError(
            f"selected zone/sample identity changed for {semantic.key!r}"
        )

    preset_indices = [
        index
        for index, (name, program, bank, _bag) in enumerate(phdr[:-1])
        if name == semantic.preset_name
        and program == semantic.program
        and bank == semantic.preset_bank
    ]
    if len(preset_indices) != 1:
        raise SaturnGmCalibrationInventoryError(
            f"GM preset {semantic.preset_bank}:{semantic.program} "
            f"{semantic.preset_name!r} is not unique"
        )
    preset_index = preset_indices[0]
    preset_bag_indices = tuple(range(phdr[preset_index][3], phdr[preset_index + 1][3]))
    preset_global_bag, preset_global_map = _scope._one_global_bag(
        preset_bag_indices,
        pbag,
        pgen,
        index_operator=_gm._GEN_INSTRUMENT,
        label=f"preset {semantic.preset_name!r}",
    )

    candidates = []
    for preset_local_bag in preset_bag_indices:
        preset_local_map = _scope._slice_generators(pbag, pgen, preset_local_bag)
        if _gm._GEN_INSTRUMENT not in preset_local_map:
            continue
        inst_index = preset_local_map[_gm._GEN_INSTRUMENT]
        if not 0 <= inst_index < len(inst) - 1:
            continue
        inst_bag_indices = tuple(range(inst[inst_index][1], inst[inst_index + 1][1]))
        inst_global_bag, inst_global_map = _scope._one_global_bag(
            inst_bag_indices,
            ibag,
            igen,
            index_operator=_gm._GEN_SAMPLE_ID,
            label=f"instrument {inst[inst_index][0]!r}",
        )
        for inst_local_bag in inst_bag_indices:
            inst_local_map = _scope._slice_generators(ibag, igen, inst_local_bag)
            if _gm._GEN_SAMPLE_ID not in inst_local_map:
                continue
            merged = _policy._space_spectre_merge_zone_maps(
                preset_global_map,
                preset_local_map,
                inst_global_map,
                inst_local_map,
            )
            if not _zone_matches_selected(merged, selected):
                continue
            candidates.append(
                (
                    preset_local_bag,
                    inst_local_bag,
                    inst_index,
                    inst_global_bag,
                )
            )

    if not candidates:
        raise SaturnGmCalibrationInventoryError(
            f"no raw SoundFont path reproduces selected GM zone {semantic.key!r}"
        )

    # ``parse_soundfont_bytes`` emits zones in preset-local then instrument-local
    # bag order. ``_choose_zone`` is stable when all semantic ranking fields tie,
    # so the first raw path is the exact path that supplied the selected zone.
    preset_local_bag, inst_local_bag, inst_index, inst_global_bag = min(
        candidates,
        key=lambda candidate: (candidate[0], candidate[1]),
    )

    preset_global_mods = (
        ()
        if preset_global_bag is None
        else _scope._slice_modulators(pbag, pmod, preset_global_bag)
    )
    preset_local_mods = _scope._slice_modulators(pbag, pmod, preset_local_bag)
    inst_global_mods = (
        ()
        if inst_global_bag is None
        else _scope._slice_modulators(ibag, imod, inst_global_bag)
    )
    inst_local_mods = _scope._slice_modulators(ibag, imod, inst_local_bag)
    effective = _scope.resolve_effective_modulators(
        inst_global_mods,
        inst_local_mods,
        preset_global_mods,
        preset_local_mods,
    )
    attenuation = tuple(
        mod
        for mod in effective
        if mod.identity.destination == _scope.SF2_INITIAL_ATTENUATION_DESTINATION
    )
    velocity = next(
        (
            mod
            for mod in attenuation
            if mod.identity == _scope.default_velocity_identity()
        ),
        None,
    )
    if velocity is None:
        raise SaturnGmCalibrationInventoryError(
            f"default velocity identity vanished for {semantic.key!r}"
        )
    if not 0 <= semantic.sample_id < len(samples):
        raise SaturnGmCalibrationInventoryError(
            f"sample id is out of range for {semantic.key!r}"
        )

    return _scope.SaturnModulatorScopeRow(
        kind=semantic.kind,
        program=semantic.program,
        note=semantic.note,
        velocity=semantic.velocity,
        preset_bank=semantic.preset_bank,
        preset_name=semantic.preset_name,
        preset_index=preset_index,
        preset_global_bag=preset_global_bag,
        preset_local_bag=preset_local_bag,
        instrument_index=inst_index,
        instrument_name=inst[inst_index][0],
        instrument_global_bag=inst_global_bag,
        instrument_local_bag=inst_local_bag,
        sample_id=semantic.sample_id,
        sample_name=samples[semantic.sample_id].name,
        velocity_attenuation_amount_cb=velocity.amount,
        attenuation_modulators=attenuation,
    )


def audit_gm_calibration_inventory(
    soundfont: Path | str | None = None,
) -> SaturnGmCalibrationInventory:
    source = _gm.ensure_generaluser_soundfont(soundfont)
    payload = source.read_bytes()
    raw = _raw_tables(payload)
    rows: list[SaturnGmCalibrationRow] = []
    other_programs: list[int] = []

    with _policy._channel10_selector():
        sf2 = _gm.parse_soundfont_bytes(payload)
        for program in range(GM_PROGRAM_COUNT):
            preset = _gm._select_melodic_preset(sf2, program)
            selected = _gm._choose_zone(
                preset,
                GM_CALIBRATION_NOTE,
                GM_CALIBRATION_VELOCITY,
            )
            semantic = _revision._row(
                sf2,
                preset,
                GM_CALIBRATION_NOTE,
                GM_CALIBRATION_VELOCITY,
                target_rate=11_025,
                pcm8=False,
                kind="melodic",
                program=program,
            )
            resolved = _resolve_calibration_row(semantic, selected, **raw)
            other = tuple(
                mod for mod in resolved.attenuation_modulators
                if mod.identity != _scope.default_velocity_identity()
            )
            if other:
                other_programs.append(program)
            rows.append(
                SaturnGmCalibrationRow(
                    program=program,
                    family=program // GM_FAMILY_SIZE,
                    preset_name=preset.name,
                    sample_id=semantic.sample_id,
                    sample_name=semantic.sample_name,
                    velocity_amount_cb=resolved.velocity_attenuation_amount_cb,
                    attenuation_modulator_count=len(resolved.attenuation_modulators),
                    other_attenuation_modulator_count=len(other),
                    loop_enabled=semantic.loop_enabled,
                    base_note=semantic.base_note,
                    fine_tune=semantic.fine_tune,
                    attenuation_cb=semantic.attenuation_cb,
                )
            )

    if len(rows) != GM_PROGRAM_COUNT or tuple(row.program for row in rows) != tuple(range(128)):
        raise SaturnGmCalibrationInventoryError("GM calibration inventory is incomplete")
    counts = Counter(row.velocity_amount_cb for row in rows)
    return SaturnGmCalibrationInventory(
        source_path=source,
        rows=tuple(rows),
        velocity_amount_counts=tuple(sorted(counts.items())),
        rows_with_other_attenuation_modulators=tuple(other_programs),
    )
