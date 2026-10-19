"""Attribute silent SDDRV210 keyed TL to authored TON versus runtime scaling.

R4 physical evidence proved Direct MIDI reaches KYONB with a valid sample address
and non-zero direct mixer, but the keyed SCSP TL is 0xFF.  This read-only audit
parses the exact GMC00..GMC15 SCSPBIN family files already built for calibration
and reports the authored layer TL, direct-send/pan byte, velocity-table index,
and velocity conversion level at the calibration velocity.

It performs no build, no media write, and no hardware action.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from .sbl_gm_calibration_family_banks import (
    GM_CALIBRATION_NOTE,
    GM_CALIBRATION_VELOCITY,
    GM_FAMILY_COUNT,
    GM_FAMILY_FILENAME_TEMPLATE,
    GM_FAMILY_SIZE,
)
from .sbl_pcm_balance_audit import scsp_tl_attenuation_db
from .sbl_velocity_curve import sega_velocity_level


class SaturnSddrv210TlAttributionError(RuntimeError):
    """Raised when a calibration TON bank cannot be attributed safely."""


@dataclass(frozen=True)
class SaturnSddrv210TlRow:
    program: int
    family: int
    local_voice: int
    authored_tl: int
    authored_tl_db: float
    direct_send_pan: int
    velocity_table_index: int
    velocity_level: int
    sample_address: int
    loop_enabled: bool
    pcm8: bool


@dataclass(frozen=True)
class SaturnSddrv210TlAttribution:
    project_root: Path
    rows: tuple[SaturnSddrv210TlRow, ...]

    @property
    def authored_ff_programs(self) -> tuple[int, ...]:
        return tuple(row.program for row in self.rows if row.authored_tl == 0xFF)

    @property
    def authored_tl_min(self) -> int:
        return min(row.authored_tl for row in self.rows)

    @property
    def authored_tl_max(self) -> int:
        return max(row.authored_tl for row in self.rows)


def _u16be(payload: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(payload):
        raise SaturnSddrv210TlAttributionError(
            f"SCSPBIN 16-bit read exceeds payload at 0x{offset:X}"
        )
    return struct.unpack_from(">H", payload, offset)[0]


def _parse_family(payload: bytes, family: int) -> tuple[SaturnSddrv210TlRow, ...]:
    if len(payload) < 8 + 2 * GM_FAMILY_SIZE:
        raise SaturnSddrv210TlAttributionError(
            f"family {family} SCSPBIN is too small: {len(payload)} bytes"
        )

    mixer_offset = _u16be(payload, 0)
    velocity_offset = _u16be(payload, 2)
    peg_offset = _u16be(payload, 4)
    plfo_offset = _u16be(payload, 6)
    if not (
        8 + 2 * GM_FAMILY_SIZE <= mixer_offset
        < velocity_offset
        <= peg_offset
        <= plfo_offset
        < len(payload)
    ):
        raise SaturnSddrv210TlAttributionError(
            f"family {family} SCSPBIN table offsets are invalid"
        )
    velocity_bytes = peg_offset - velocity_offset
    if velocity_bytes <= 0 or velocity_bytes % 10:
        raise SaturnSddrv210TlAttributionError(
            f"family {family} velocity table bytes are invalid: {velocity_bytes}"
        )
    velocity_tables = tuple(
        payload[offset : offset + 10]
        for offset in range(velocity_offset, peg_offset, 10)
    )

    rows = []
    for local_voice in range(GM_FAMILY_SIZE):
        program = family * GM_FAMILY_SIZE + local_voice
        voice_offset = _u16be(payload, 8 + local_voice * 2)
        if voice_offset + 4 + 32 > len(payload):
            raise SaturnSddrv210TlAttributionError(
                f"program {program} voice/layer exceeds SCSPBIN payload"
            )
        layer_count = (payload[voice_offset + 2] & 0x7F) + 1
        if layer_count != 1:
            raise SaturnSddrv210TlAttributionError(
                f"program {program} calibration voice has {layer_count} layers; expected 1"
            )
        layer = payload[voice_offset + 4 : voice_offset + 36]
        authored_tl = layer[0x0F]
        velocity_index = layer[0x1D]
        if velocity_index >= len(velocity_tables):
            raise SaturnSddrv210TlAttributionError(
                f"program {program} velocity table {velocity_index} is out of range"
            )
        table = velocity_tables[velocity_index]
        velocity_level = sega_velocity_level(table, GM_CALIBRATION_VELOCITY)
        sample_address = ((layer[3] & 0x0F) << 16) | _u16be(layer, 4)
        rows.append(
            SaturnSddrv210TlRow(
                program=program,
                family=family,
                local_voice=local_voice,
                authored_tl=authored_tl,
                authored_tl_db=scsp_tl_attenuation_db(authored_tl),
                direct_send_pan=layer[0x18],
                velocity_table_index=velocity_index,
                velocity_level=velocity_level,
                sample_address=sample_address,
                loop_enabled=bool(layer[3] & 0x20),
                pcm8=bool(layer[3] & 0x10),
            )
        )
    return tuple(rows)


def audit_sddrv210_tl_attribution(project_directory: Path | str) -> SaturnSddrv210TlAttribution:
    root = Path(project_directory).expanduser().resolve(strict=True)
    cd = root / "cd"
    if not cd.is_dir():
        raise SaturnSddrv210TlAttributionError(
            f"calibration project has no cd directory: {cd}"
        )

    rows = []
    for family in range(GM_FAMILY_COUNT):
        path = cd / GM_FAMILY_FILENAME_TEMPLATE.format(family=family)
        if not path.is_file():
            raise SaturnSddrv210TlAttributionError(
                f"missing calibration family bank: {path}"
            )
        rows.extend(_parse_family(path.read_bytes(), family))

    result = SaturnSddrv210TlAttribution(root, tuple(rows))
    if len(result.rows) != 128 or tuple(row.program for row in result.rows) != tuple(range(128)):
        raise SaturnSddrv210TlAttributionError(
            "TL attribution did not cover exactly GM programs 0..127"
        )
    return result
