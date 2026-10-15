"""Channel-10 SoundFont selection policy for Saturn Direct-MIDI candidates.

GeneralUser GS exposes its real percussion presets through the SoundFont
percussion bank and deliberately duplicates those kits into bank 120 so they
can also be selected on non-percussion MIDI channels.  Space Spectre uses MIDI
channel 10 for percussion, so SRK must prefer bank 128 rather than rejecting the
legitimate bank-120 duplicate as ambiguous.

This module keeps that source-specific/channel-semantic policy separate from the
generic compact TON converter.  The generic selector remains the fallback for
SoundFonts that do not expose a bank-128 percussion preset.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from . import sbl_soundfont_gm as _gm


_DrumSelector = Callable[[_gm.Sf2Data], _gm.Sf2Preset]


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


def ensure_channel10_space_spectre_tone_banks(
    soundfont: Path | str,
    requirements: _gm.MidiToneRequirements,
) -> _gm.SaturnSoundfontBankFiles:
    """Derive Space Spectre banks with canonical channel-10 drum selection."""

    with _channel10_selector():
        return _gm.ensure_space_spectre_tone_banks(soundfont, requirements)
