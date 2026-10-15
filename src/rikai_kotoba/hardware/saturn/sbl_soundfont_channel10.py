"""Channel-10 SoundFont policy for Saturn Direct-MIDI candidates.

GeneralUser GS exposes its real percussion presets through the SoundFont
percussion bank and deliberately duplicates those kits into bank 120 so they
can also be selected on non-percussion MIDI channels. Space Spectre uses MIDI
channel 10 for percussion, so SRK must prefer bank 128 rather than rejecting the
legitimate bank-120 duplicate as ambiguous.

The generated TON banks are also normalized to the first velocity curve from
Sega's SBL 6.01 ``BOOTTONE.BIN`` sample. That keeps the compact SoundFont
conversion on a byte pattern directly proven by Sega's own tone-bank data rather
than the converter's earlier synthetic placeholder curve.

SoundFont global/local generator inheritance is also corrected here as a scoped
policy around the Space Spectre bank build. At a given SoundFont hierarchy
level, a local-zone generator supersedes the corresponding global-zone value;
only after those per-level values are resolved are preset and instrument
contributions combined. The base compact parser historically added all four
maps in one pass, which can double-count attenuation, tuning, and envelope
values and produce badly unbalanced Saturn TL values.

Sega's Tone Editor layer format documents Fine Tune as a signed value restricted
to -63..+63.  The base converter historically allowed the full signed-byte
range after SoundFont coarse/fine/sample-correction accumulation.  The scoped
policy below folds excess cents into BASE NOTE in whole semitones, preserving
the intended pitch while ensuring every emitted layer stays inside Sega's
published range.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import struct
from typing import Callable, Iterator, Mapping

from . import sbl_soundfont_gm as _gm


_DrumSelector = Callable[[_gm.Sf2Data], _gm.Sf2Preset]
_ORIGINAL_MERGE_ZONE_MAPS = _gm._merge_zone_maps
_ORIGINAL_NORMALIZE_TUNING = _gm._normalize_tuning

# SBL 6.01 SEGASMP/SND/SMPSND1 BOOTTONE.BIN, velocity table 0.
# NON.ASM consumes this as K0,V0,L0,K1,V1,L1,K2,V2,L2,K3.
SEGA_BOOTTONE_VELOCITY_CURVE_0 = bytes(
    (0x08, 0x00, 0x7F, 0x0C, 0x7F, 0x7F, 0x08, 0x7F, 0x7F, 0x08)
)
SEGA_FINE_TUNE_MIN = -63
SEGA_FINE_TUNE_MAX = 63


def select_channel10_drum_preset(
    sf2: _gm.Sf2Data,
    *,
    fallback: _DrumSelector,
) -> _gm.Sf2Preset:
    """Select the canonical SF2 percussion preset for MIDI channel 10."""

    canonical = [
        preset
        for preset in sf2.presets
        if preset.bank == 128 and preset.program == 0 and preset.zones
    ]
    named = [
        preset for preset in canonical if "standard 1" in preset.name.casefold()
    ]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        label = ", ".join(
            f"{preset.bank}:{preset.program} {preset.name}" for preset in named
        )
        raise _gm.SaturnSblSoundfontError(
            "SoundFont channel-10 Standard 1 percussion preset is not unique: "
            + label
        )
    if len(canonical) == 1:
        return canonical[0]
    if len(canonical) > 1:
        label = ", ".join(
            f"{preset.bank}:{preset.program} {preset.name}" for preset in canonical
        )
        raise _gm.SaturnSblSoundfontError(
            "SoundFont channel-10 percussion bank 128 program 0 is not unique: "
            + label
        )
    return fallback(sf2)


def _resolve_global_local_zone(
    global_map: Mapping[int, int],
    local_map: Mapping[int, int],
) -> dict[int, int]:
    """Resolve one SoundFont hierarchy level before cross-level addition."""

    result = dict(global_map)
    for range_op in (_gm._GEN_KEY_RANGE, _gm._GEN_VEL_RANGE):
        global_value = global_map.get(range_op)
        local_value = local_map.get(range_op)
        if global_value is None and local_value is None:
            continue
        global_lo, global_hi = _gm._range(global_value)
        local_lo, local_hi = _gm._range(local_value)
        lo = max(global_lo, local_lo)
        hi = min(global_hi, local_hi)
        result[range_op] = lo | (hi << 8)

    for op, value in local_map.items():
        if op in (_gm._GEN_KEY_RANGE, _gm._GEN_VEL_RANGE):
            continue
        result[op] = value
    return result


def _space_spectre_merge_zone_maps(
    *maps: Mapping[int, int],
) -> dict[int, int]:
    """Correct the parser's four-map SoundFont hierarchy merge."""

    if len(maps) != 4:
        return _ORIGINAL_MERGE_ZONE_MAPS(*maps)
    preset_effective = _resolve_global_local_zone(maps[0], maps[1])
    instrument_effective = _resolve_global_local_zone(maps[2], maps[3])
    return _ORIGINAL_MERGE_ZONE_MAPS(preset_effective, instrument_effective)


def normalize_sega_fine_tuning(
    root: int,
    cents: int,
    rate_octaves: int,
) -> tuple[int, int]:
    """Preserve pitch while constraining TON Fine Tune to Sega's -63..+63."""

    base, fine = _ORIGINAL_NORMALIZE_TUNING(root, cents, rate_octaves)
    while fine > SEGA_FINE_TUNE_MAX:
        fine -= 100
        base -= 1
    while fine < SEGA_FINE_TUNE_MIN:
        fine += 100
        base += 1
    if not 0 <= base <= 127:
        raise _gm.SaturnSblSoundfontError(
            f"tone base note {base} is outside Saturn byte range after Sega fine-tune folding"
        )
    if not SEGA_FINE_TUNE_MIN <= fine <= SEGA_FINE_TUNE_MAX:
        raise _gm.SaturnSblSoundfontError(
            f"tone fine tune {fine} is outside Sega range after folding"
        )
    return base, fine


@contextmanager
def _channel10_selector() -> Iterator[None]:
    """Scope channel-10, hierarchy and Sega tuning policy to one derivation."""

    original_selector = _gm._select_drum_preset
    original_merge = _gm._merge_zone_maps
    original_tuning = _gm._normalize_tuning

    def selector(sf2: _gm.Sf2Data) -> _gm.Sf2Preset:
        return select_channel10_drum_preset(sf2, fallback=original_selector)

    _gm._select_drum_preset = selector
    _gm._merge_zone_maps = _space_spectre_merge_zone_maps
    _gm._normalize_tuning = normalize_sega_fine_tuning
    try:
        yield
    finally:
        _gm._normalize_tuning = original_tuning
        _gm._merge_zone_maps = original_merge
        _gm._select_drum_preset = original_selector


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_sega_velocity_curve(path: Path | str) -> None:
    """Replace TON velocity table 0 with Sega's proven BOOTTONE curve."""

    tone = Path(path).expanduser().resolve(strict=True)
    payload = bytearray(tone.read_bytes())
    if len(payload) < 4:
        raise _gm.SaturnSblSoundfontError(f"Saturn TON bank header is truncated: {tone}")
    velocity_offset = struct.unpack_from(">H", payload, 2)[0]
    end = velocity_offset + len(SEGA_BOOTTONE_VELOCITY_CURVE_0)
    if velocity_offset < 8 or end > len(payload):
        raise _gm.SaturnSblSoundfontError(
            f"Saturn TON velocity-table offset is invalid: {velocity_offset:#x} in {tone}"
        )
    payload[velocity_offset:end] = SEGA_BOOTTONE_VELOCITY_CURVE_0
    tone.write_bytes(payload)


def ensure_channel10_space_spectre_tone_banks(
    soundfont: Path | str,
    requirements: _gm.MidiToneRequirements,
) -> _gm.SaturnSoundfontBankFiles:
    """Derive Space Spectre banks with canonical channel-10/Sega TON policy."""

    with _channel10_selector():
        banks = _gm.ensure_space_spectre_tone_banks(soundfont, requirements)

    normalize_sega_velocity_curve(banks.melodic_path)
    normalize_sega_velocity_curve(banks.drum_path)
    with banks.report_path.open("a", encoding="utf-8", newline="\n") as report:
        report.write("velocity_curve=sbl601_boottone_table0\n")
        report.write("soundfont_hierarchy=local_over_global_then_cross_level_add\n")
        report.write("fine_tune_range=sega_-63_63_folded_into_base_note\n")

    return _gm.SaturnSoundfontBankFiles(
        melodic_path=banks.melodic_path,
        drum_path=banks.drum_path,
        report_path=banks.report_path,
        source_path=banks.source_path,
        melodic_sha256=_sha256_file(banks.melodic_path),
        drum_sha256=_sha256_file(banks.drum_path),
        source_sha256=banks.source_sha256,
        sample_rate=banks.sample_rate,
        pcm8=banks.pcm8,
        combined_bytes=banks.combined_bytes,
    )
