"""SRK-owned deterministic Standard MIDI File used by Saturn diagnostics.

The asset is generated from code so its musical/control contract is reviewable,
reproducible and free of external MIDI-file dependencies.  It intentionally
exercises timing, multi-track merge, bank/program state, controller state,
pitch bend, sustain and note on/off handling before the sequence is handed to a
platform-specific playback backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


SRK_MIDI_DIAGNOSTIC_TICKS_PER_QUARTER = 96
SRK_MIDI_DIAGNOSTIC_END_TICK = 384


@dataclass(frozen=True)
class _AbsoluteEvent:
    tick: int
    payload: bytes


def _be16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _be32(value: int) -> bytes:
    return value.to_bytes(4, "big")


def _vlq(value: int) -> bytes:
    if value < 0 or value > 0x0FFFFFFF:
        raise ValueError(value)
    encoded = [value & 0x7F]
    value >>= 7
    while value:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.reverse()
    return bytes(encoded)


def _track(events: tuple[_AbsoluteEvent, ...]) -> bytes:
    previous_tick = 0
    body = bytearray()
    for event in events:
        if event.tick < previous_tick:
            raise ValueError("diagnostic MIDI events must be in nondecreasing tick order")
        body.extend(_vlq(event.tick - previous_tick))
        body.extend(event.payload)
        previous_tick = event.tick
    return b"MTrk" + _be32(len(body)) + bytes(body)


def _meta(meta_type: int, payload: bytes) -> bytes:
    return bytes((0xFF, meta_type)) + _vlq(len(payload)) + payload


def _tempo(us_per_quarter: int) -> bytes:
    if us_per_quarter <= 0 or us_per_quarter > 0xFFFFFF:
        raise ValueError(us_per_quarter)
    return _meta(0x51, us_per_quarter.to_bytes(3, "big"))


def build_srk_midi_diagnostic_bytes() -> bytes:
    """Return the canonical SRK deterministic diagnostic MIDI file.

    The file is SMF format 1 with one conductor track and two musical tracks.
    All content is authored by SRK and generated deterministically.
    """

    conductor = _track(
        (
            _AbsoluteEvent(0, _meta(0x03, b"SRK Conductor")),
            _AbsoluteEvent(0, _tempo(500000)),
            _AbsoluteEvent(192, _tempo(400000)),
            _AbsoluteEvent(SRK_MIDI_DIAGNOSTIC_END_TICK, _meta(0x2F, b"")),
        )
    )

    melody = _track(
        (
            _AbsoluteEvent(0, _meta(0x03, b"SRK Melody")),
            _AbsoluteEvent(0, bytes((0xB0, 0x00, 0x00))),  # bank MSB
            _AbsoluteEvent(0, bytes((0xB0, 0x20, 0x00))),  # bank LSB
            _AbsoluteEvent(0, bytes((0xC0, 0x00))),        # program 0
            _AbsoluteEvent(0, bytes((0xB0, 0x07, 100))),   # volume
            _AbsoluteEvent(0, bytes((0xB0, 0x0A, 32))),    # left-side pan
            _AbsoluteEvent(0, bytes((0x90, 60, 100))),     # C4 on
            _AbsoluteEvent(96, bytes((0x90, 60, 0))),      # running-style semantic off
            _AbsoluteEvent(96, bytes((0x90, 64, 96))),     # E4 on
            _AbsoluteEvent(192, bytes((0x80, 64, 48))),    # E4 off
            _AbsoluteEvent(192, bytes((0xB0, 0x0A, 96))),  # right-side pan
            _AbsoluteEvent(192, bytes((0xC0, 0x01))),      # program 1
            _AbsoluteEvent(192, bytes((0x90, 67, 92))),    # G4 on
            _AbsoluteEvent(288, bytes((0x80, 67, 48))),    # G4 off
            _AbsoluteEvent(SRK_MIDI_DIAGNOSTIC_END_TICK, _meta(0x2F, b"")),
        )
    )

    harmony = _track(
        (
            _AbsoluteEvent(0, _meta(0x03, b"SRK Harmony")),
            _AbsoluteEvent(0, bytes((0xB1, 0x00, 0x00))),  # bank MSB
            _AbsoluteEvent(0, bytes((0xB1, 0x20, 0x00))),  # bank LSB
            _AbsoluteEvent(0, bytes((0xC1, 0x02))),        # program 2
            _AbsoluteEvent(0, bytes((0xB1, 0x07, 90))),    # volume
            _AbsoluteEvent(0, bytes((0xB1, 0x0A, 96))),    # right-side pan
            _AbsoluteEvent(0, bytes((0xB1, 0x0B, 110))),   # expression
            _AbsoluteEvent(48, bytes((0x91, 48, 88))),     # C3 on
            _AbsoluteEvent(144, bytes((0xE1, 0x00, 0x50))),# bend upward
            _AbsoluteEvent(144, bytes((0xB1, 0x40, 127))), # sustain on
            _AbsoluteEvent(192, bytes((0x81, 48, 40))),    # C3 off
            _AbsoluteEvent(240, bytes((0x91, 55, 84))),    # G3 on
            _AbsoluteEvent(288, bytes((0xE1, 0x00, 0x40))),# bend center
            _AbsoluteEvent(336, bytes((0x81, 55, 40))),    # G3 off
            _AbsoluteEvent(336, bytes((0xB1, 0x40, 0))),   # sustain off
            _AbsoluteEvent(SRK_MIDI_DIAGNOSTIC_END_TICK, _meta(0x2F, b"")),
        )
    )

    header = (
        b"MThd"
        + _be32(6)
        + _be16(1)
        + _be16(3)
        + _be16(SRK_MIDI_DIAGNOSTIC_TICKS_PER_QUARTER)
    )
    return header + conductor + melody + harmony


def srk_midi_diagnostic_sha256() -> str:
    """Return the stable SHA-256 of the canonical generated SMF asset."""

    return sha256(build_srk_midi_diagnostic_bytes()).hexdigest()
