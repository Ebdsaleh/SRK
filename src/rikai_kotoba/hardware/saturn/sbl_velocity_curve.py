"""Sega SDDRV velocity-table model and SoundFont curve projection.

Sega's SDDRV consumes one 10-byte SCSPBIN velocity table per layer-selected
velocity-table index.  The exact layout, recovered from the supplied SBL/SGL
``NON.ASM`` and ``SCSP.LIB``, is::

    K0 V0 L0 K1 V1 L1 K2 V2 L2 K3

The driver selects one of four piecewise segments and applies the slope encoded
by K to the MIDI note-on velocity.  This module mirrors that integer arithmetic
for read-only fidelity work and carries deterministic four-segment fits for the
three effective GeneralUser velocity->attenuation amounts used by Space Spectre.

The target SoundFont law is the standard negative/unipolar/concave velocity
modulator.  For an attenuation amount A (centibels), its linear amplitude ratio
is ``(velocity / 127) ** (A / 480)``.  This follows directly from the 96 dB
(+960 cB) default curve, whose amplitude response is the familiar square law.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Mapping


class SaturnVelocityCurveError(RuntimeError):
    """Raised when a Sega velocity table or SoundFont amount is unsupported."""


SEGA_VELOCITY_TABLE_BYTES = 10
SPACE_SPECTRE_VELOCITY_AMOUNTS_CB = (500, 600, 800)
SOUNDFONT_VELOCITY_CHECKPOINTS = (15, 31, 47, 63, 79, 95, 111, 127)

# Fits are constrained to the exact slope primitives implemented by Sega's
# NON.ASM and to a full-scale output of 127 at MIDI velocity 127.
#
# Each table was optimized against the SoundFont amplitude target while keeping
# segment continuity.  Tests below audit the integer driver response rather than
# trusting these bytes as opaque constants.
SPACE_SPECTRE_SEGA_VELOCITY_TABLES: Mapping[int, bytes] = {
    500: bytes.fromhex("13 03 01 02 50 4E 09 54 54 02"),
    600: bytes.fromhex("13 11 08 02 61 58 09 73 73 02"),
    800: bytes.fromhex("23 0B 02 13 26 0F 02 51 3A 09"),
}


@dataclass(frozen=True)
class SaturnVelocityCheckpoint:
    velocity: int
    target_level: float
    sega_level: int
    error_db: float


@dataclass(frozen=True)
class SaturnVelocityTableAudit:
    amount_cb: int
    table: bytes
    checkpoints: tuple[SaturnVelocityCheckpoint, ...]
    max_linear_error: float
    rms_linear_error: float
    max_checkpoint_error_db: float
    mean_checkpoint_error_db: float


def _segment_delta(k: int, delta: int) -> int:
    """Mirror the positive Sega NON.ASM K slope forms used by SRK tables."""

    code = int(k) & 0xFF
    distance = max(0, int(delta))
    kind = code & 0x07
    exponent = (code >> 4) & 0x0F
    one_and_half = bool(code & 0x08)

    if kind in (0, 4):
        return 0
    if kind == 2:
        return distance
    if kind == 6:
        return -distance
    if kind == 3:
        return distance >> exponent
    if kind == 5:
        return -(distance >> exponent)
    if kind in (1, 7):
        if one_and_half:
            magnitude = (12 * distance * (1 << exponent)) >> 3
        else:
            magnitude = distance << exponent
        return magnitude if kind == 1 else -magnitude
    raise SaturnVelocityCurveError(f"unsupported Sega velocity K code: 0x{code:02X}")


def sega_velocity_level(table: bytes, velocity: int) -> int:
    """Evaluate one SCSPBIN velocity table exactly enough for authored curves.

    ``NON.ASM`` treats a zero converted result as 1 before multiplying by the
    inverted layer TL, because MIDI velocity zero is not a valid note-on level.
    The returned range is therefore 1..127 for input velocities 1..127.
    """

    payload = bytes(table)
    if len(payload) != SEGA_VELOCITY_TABLE_BYTES:
        raise SaturnVelocityCurveError(
            f"Sega velocity table must be {SEGA_VELOCITY_TABLE_BYTES} bytes"
        )
    value = int(velocity)
    if not 1 <= value <= 127:
        raise SaturnVelocityCurveError("MIDI note-on velocity must be 1..127")

    k0, v0, l0, k1, v1, l1, k2, v2, l2, k3 = payload
    if not (v0 <= v1 <= v2 <= 127):
        raise SaturnVelocityCurveError("Sega velocity breakpoints are not monotonic")

    if value <= v0:
        level = _segment_delta(k0, value)
    elif value <= v1:
        level = l0 + _segment_delta(k1, value - v0)
    elif value <= v2:
        level = l1 + _segment_delta(k2, value - v1)
    else:
        level = l2 + _segment_delta(k3, value - v2)

    return max(1, min(127, int(level)))


def soundfont_velocity_linear_level(amount_cb: int, velocity: int) -> float:
    """Return the ideal 0..127 linear level for the SF2 concave velocity law."""

    amount = int(amount_cb)
    value = int(velocity)
    if amount < 0:
        raise SaturnVelocityCurveError("velocity attenuation amount cannot be negative")
    if not 1 <= value <= 127:
        raise SaturnVelocityCurveError("MIDI note-on velocity must be 1..127")
    return 127.0 * ((value / 127.0) ** (amount / 480.0))


def soundfont_velocity_attenuation_db(amount_cb: int, velocity: int) -> float:
    """Return attenuation in dB for the ideal SF2 velocity modulator."""

    level = soundfont_velocity_linear_level(amount_cb, velocity)
    return -20.0 * log10(level / 127.0)


def table_for_velocity_amount(amount_cb: int) -> bytes:
    try:
        return SPACE_SPECTRE_SEGA_VELOCITY_TABLES[int(amount_cb)]
    except KeyError as exc:
        raise SaturnVelocityCurveError(
            f"no locked Sega velocity table for SoundFont amount {int(amount_cb)} cB"
        ) from exc


def audit_velocity_table(amount_cb: int) -> SaturnVelocityTableAudit:
    """Compare one locked Sega table against the ideal SF2 curve."""

    amount = int(amount_cb)
    table = table_for_velocity_amount(amount)
    linear_errors = []
    checkpoints = []
    checkpoint_errors = []

    for velocity in range(1, 128):
        target = soundfont_velocity_linear_level(amount, velocity)
        actual = sega_velocity_level(table, velocity)
        linear_errors.append(actual - target)
        if velocity in SOUNDFONT_VELOCITY_CHECKPOINTS:
            error_db = 20.0 * log10(actual / target)
            checkpoints.append(
                SaturnVelocityCheckpoint(
                    velocity=velocity,
                    target_level=target,
                    sega_level=actual,
                    error_db=error_db,
                )
            )
            checkpoint_errors.append(abs(error_db))

    mean_square = sum(error * error for error in linear_errors) / len(linear_errors)
    return SaturnVelocityTableAudit(
        amount_cb=amount,
        table=table,
        checkpoints=tuple(checkpoints),
        max_linear_error=max(abs(error) for error in linear_errors),
        rms_linear_error=mean_square ** 0.5,
        max_checkpoint_error_db=max(checkpoint_errors),
        mean_checkpoint_error_db=sum(checkpoint_errors) / len(checkpoint_errors),
    )
