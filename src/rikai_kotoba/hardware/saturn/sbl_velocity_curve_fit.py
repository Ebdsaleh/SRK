"""Fit Sega SDDRV 10-byte velocity tables for arbitrary SoundFont amounts.

Space Spectre physically proved SRK's interpretation of Sega's K/V/L table
format, but its song scope needed only +500/+600/+800 cB curves.  The complete
128-program calibration inventory can legitimately resolve other GeneralUser
velocity->attenuation amounts.  This module keeps the three locked physical
curves unchanged and deterministically fits any additional non-negative amount
using only positive slope primitives implemented by the supplied NON.ASM.
"""

from __future__ import annotations

from functools import lru_cache
from math import log10

from .sbl_velocity_curve import (
    SPACE_SPECTRE_SEGA_VELOCITY_TABLES,
    SaturnVelocityCurveError,
    _segment_delta,
    sega_velocity_level,
    soundfont_velocity_linear_level,
)


_BREAKPOINT_CANDIDATES = (15, 31, 47, 63, 79, 95, 111)
# Canonical positive/constant NON.ASM slope forms used by the fitter.
_K_CODES = (
    0x00,  # constant
    0x33,  # +1/8
    0x23,  # +1/4
    0x13,  # +1/2
    0x02,  # +1
    0x09,  # +1.5
    0x11,  # +2
    0x19,  # +3
    0x21,  # +4
    0x29,  # +6
    0x31,  # +8
)


def _target(amount: int, velocity: int) -> float:
    return soundfont_velocity_linear_level(amount, velocity)


def _best_k(amount: int, start: int, end: int, base: int) -> int:
    if end < start:
        return 0x00
    best: tuple[float, int] | None = None
    for code in _K_CODES:
        error = 0.0
        for velocity in range(start, end + 1):
            delta = velocity if start == 1 else velocity - (start - 1)
            actual = max(1, min(127, base + _segment_delta(code, delta)))
            diff = actual - _target(amount, velocity)
            error += diff * diff
        candidate = (error, code)
        if best is None or candidate < best:
            best = candidate
    assert best is not None
    return best[1]


def _best_final(amount: int, breakpoint: int) -> tuple[int, int]:
    """Return L2/K3 with velocity 127 forced to full Sega level 127."""

    best: tuple[float, int, int] | None = None
    distance = 127 - breakpoint
    for code in _K_CODES:
        base = 127 - _segment_delta(code, distance)
        if not 0 <= base <= 127:
            continue
        error = 0.0
        for velocity in range(breakpoint + 1, 128):
            actual = max(
                1,
                min(127, base + _segment_delta(code, velocity - breakpoint)),
            )
            diff = actual - _target(amount, velocity)
            error += diff * diff
        candidate = (error, code, base)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise SaturnVelocityCurveError(
            f"no Sega final velocity segment can reach full scale for {amount} cB"
        )
    return best[2], best[1]


def _score(amount: int, table: bytes) -> tuple[float, float, bytes]:
    square = 0.0
    max_db = 0.0
    for velocity in range(1, 128):
        target = _target(amount, velocity)
        actual = sega_velocity_level(table, velocity)
        diff = actual - target
        square += diff * diff
        if target > 0.0 and actual > 0:
            max_db = max(max_db, abs(20.0 * log10(actual / target)))
    rms = (square / 127.0) ** 0.5
    return rms, max_db, table


@lru_cache(maxsize=None)
def fit_velocity_table(amount_cb: int) -> bytes:
    """Return a deterministic Sega velocity table for one SoundFont amount."""

    amount = int(amount_cb)
    if amount < 0:
        raise SaturnVelocityCurveError("velocity attenuation amount cannot be negative")
    locked = SPACE_SPECTRE_SEGA_VELOCITY_TABLES.get(amount)
    if locked is not None:
        return locked

    best: tuple[float, float, bytes] | None = None
    points = _BREAKPOINT_CANDIDATES
    for i, v0 in enumerate(points[:-2]):
        for j in range(i + 1, len(points) - 1):
            v1 = points[j]
            for v2 in points[j + 1 :]:
                l0 = max(1, min(127, int(round(_target(amount, v0)))))
                l1 = max(1, min(127, int(round(_target(amount, v1)))))
                k0 = _best_k(amount, 1, v0, 0)
                k1 = _best_k(amount, v0 + 1, v1, l0)
                k2 = _best_k(amount, v1 + 1, v2, l1)
                l2, k3 = _best_final(amount, v2)
                table = bytes((k0, v0, l0, k1, v1, l1, k2, v2, l2, k3))
                candidate = _score(amount, table)
                if best is None or candidate < best:
                    best = candidate

    if best is None:
        raise SaturnVelocityCurveError(
            f"could not fit Sega velocity table for SoundFont amount {amount} cB"
        )
    table = best[2]
    if sega_velocity_level(table, 127) != 127:
        raise SaturnVelocityCurveError(
            f"fitted Sega table does not reach full scale for {amount} cB"
        )
    return table
