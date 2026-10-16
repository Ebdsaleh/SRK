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
            resolved = _scope._resolve_row(semantic, **raw)
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
