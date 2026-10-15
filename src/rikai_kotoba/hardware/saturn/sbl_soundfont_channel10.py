"""Channel-10 SoundFont policy for Saturn Direct-MIDI candidates.

GeneralUser GS exposes its real percussion presets through the SoundFont
percussion bank and deliberately duplicates those kits into bank 120 so they
can also be selected on non-percussion MIDI channels.  Space Spectre uses MIDI
channel 10 for percussion, so SRK must prefer bank 128 rather than rejecting the
legitimate bank-120 duplicate as ambiguous.

The generated TON banks are also normalized to the first velocity curve from
Sega's SBL 6.01 ``BOOTTONE.BIN`` sample.  That keeps the compact SoundFont
conversion on a byte pattern directly proven by Sega's own tone-bank data rather
than the converter's earlier synthetic placeholder curve.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import struct
from typing import Callable, Iterator

from . import sbl_soundfont_gm as _gm


_DrumSelector = Callable[[_gm.Sf2Data], _gm.Sf2Preset]

# SBL 6.01 SEGASMP/SND/SMPSND1 BOOTTONE.BIN, velocity table 0.
# NON.ASM consumes this as K0,V0,L0,K1,V1,L1,K2,V2,L2,K3.
SEGA_BOOTTONE_VELOCITY_CURVE_0 = bytes(
    (0x08, 0x00, 0x7F, 0x0C, 0x7F, 0x7F, 0x08, 0x7F, 0x7F, 0x08)
)


def select_channel10_drum_preset(
    sf2: _gm.Sf2Data,
    *,
    fallback: _DrumSelector,
) -> _gm.Sf2Preset:
    """Select the canonical SF2 percussion preset for MIDI channel 10.

    Bank 128 is the SoundFont percussion-bank representation.  GeneralUser GS
    also contains bank-120 copies specifically for use away from channel 10;
    those copies must not make the channel-10 choice ambiguous.
    """

    canonical = [
        preset
        for preset in sf2.presets
        if preset.bank == 128 and preset.program == 0 and preset.zones
    ]
    named = [
        preset
        for preset in canonical
        if "standard 1" in preset.name.casefold()
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


@contextmanager
def _channel10_selector() -> Iterator[None]:
    """Scope the channel-10 policy to one deterministic bank derivation."""

    original = _gm._select_drum_preset

    def selector(sf2: _gm.Sf2Data) -> _gm.Sf2Preset:
        return select_channel10_drum_preset(sf2, fallback=original)

    _gm._select_drum_preset = selector
    try:
        yield
    finally:
        _gm._select_drum_preset = original


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
