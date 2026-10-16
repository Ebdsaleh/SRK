"""Author complete eight-program GM calibration tone families for Saturn SDDRV.

The historical Space Spectre TON banks are deliberately song-scoped.  They are
excellent physical evidence for Sega's SDDRV path and for the corrected static
attenuation / velocity-table policy, but they are not a 128-program General MIDI
instrument bank.

This module applies those physically proven GATE3F fidelity rules to the existing
128-program calibration inventory.  It emits sixteen independent TON banks, one
for each GM family, with eight real C4/velocity-100 voices per bank.  No silent
placeholder voices are synthesized and nothing is written to SAROO.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
import struct
from typing import Mapping, Sequence

from . import sbl_soundfont_gm as _gm
from . import sbl_soundfont_channel10 as _policy
from .sbl_fidelity_tone_authoring import _static_total_level
from .sbl_gm_calibration_inventory import (
    GM_CALIBRATION_NOTE,
    GM_CALIBRATION_VELOCITY,
    GM_FAMILY_SIZE,
    GM_PROGRAM_COUNT,
    SaturnGmCalibrationInventory,
    audit_gm_calibration_inventory,
)
from .sbl_velocity_curve_fit import fit_velocity_table


class SaturnGmCalibrationFamilyBankError(RuntimeError):
    """Raised when a complete real-voice GM calibration family cannot be built."""


GM_FAMILY_COUNT = GM_PROGRAM_COUNT // GM_FAMILY_SIZE
GM_FAMILY_FILENAME_TEMPLATE = "GMC{family:02d}.BIN"
GM_CALIBRATION_TARGET_RATE = 11_025
GM_CALIBRATION_PCM8 = False


@dataclass(frozen=True)
class SaturnGmCalibrationVoice:
    program: int
    family: int
    local_voice: int
    preset_name: str
    sample_id: int
    sample_name: str
    velocity_amount_cb: int
    velocity_table: int
    total_level: int
    base_note: int
    fine_tune: int
    pcm_sha256: str


@dataclass(frozen=True)
class SaturnGmCalibrationFamilyBank:
    family: int
    filename: str
    programs: tuple[int, ...]
    payload: bytes
    sha256: str
    voices: tuple[SaturnGmCalibrationVoice, ...]
    velocity_amounts: tuple[int, ...]

    @property
    def size(self) -> int:
        return len(self.payload)


@dataclass(frozen=True)
class SaturnGmCalibrationFamilyBanks:
    source_path: Path
    source_sha256: str
    banks: tuple[SaturnGmCalibrationFamilyBank, ...]

    @property
    def max_bank_bytes(self) -> int:
        return max(bank.size for bank in self.banks)

    @property
    def program_count(self) -> int:
        return sum(len(bank.programs) for bank in self.banks)


def _pack_layer_with_velocity_table(
    layer: _gm.SaturnToneLayer,
    sample_address: int,
    velocity_table: int,
) -> bytes:
    data = bytearray(_gm._pack_layer(layer, sample_address))
    if not 0 <= velocity_table <= 0xFF:
        raise SaturnGmCalibrationFamilyBankError(
            f"velocity table index is outside byte range: {velocity_table}"
        )
    data[0x1D] = velocity_table
    return bytes(data)


def _pack_family(
    voices: Sequence[tuple[_gm.SaturnToneLayer, _gm._PcmBlock, int]],
    velocity_tables: Sequence[bytes],
) -> bytes:
    if len(voices) != GM_FAMILY_SIZE:
        raise SaturnGmCalibrationFamilyBankError(
            f"calibration family must contain exactly {GM_FAMILY_SIZE} real voices"
        )
    tables = tuple(bytes(table) for table in velocity_tables)
    if not tables or len(tables) > 256 or any(len(table) != 10 for table in tables):
        raise SaturnGmCalibrationFamilyBankError("invalid Sega velocity-table catalog")

    mixer = bytes(18)
    velocity = b"".join(tables)
    peg = bytes(10)
    plfo = bytes(4)

    header_size = 8 + len(voices) * 2
    mixer_offset = header_size
    velocity_offset = mixer_offset + len(mixer)
    peg_offset = velocity_offset + len(velocity)
    plfo_offset = peg_offset + len(peg)
    voice_start = plfo_offset + len(plfo)

    voice_offsets: list[int] = []
    cursor = voice_start
    for _layer, _pcm, _table in voices:
        voice_offsets.append(cursor)
        cursor += 4 + 32
    if any(offset > 0xFFFF for offset in voice_offsets):
        raise SaturnGmCalibrationFamilyBankError("family voice metadata exceeds TON offset range")

    unique_pcm: dict[tuple[int, int, int, int, int], bytes] = {}
    for _layer, pcm, _table in voices:
        previous = unique_pcm.get(pcm.key)
        if previous is not None and previous != pcm.data:
            raise SaturnGmCalibrationFamilyBankError("PCM deduplication key collision")
        unique_pcm[pcm.key] = pcm.data
    if any(key[0] < 0 for key in unique_pcm):
        raise SaturnGmCalibrationFamilyBankError("silent placeholder PCM entered calibration family")

    sample_offsets: dict[tuple[int, int, int, int, int], int] = {}
    pcm_data = bytearray()
    for key in sorted(unique_pcm):
        if not GM_CALIBRATION_PCM8 and (cursor + len(pcm_data)) & 1:
            pcm_data.append(0)
        sample_offsets[key] = cursor + len(pcm_data)
        pcm_data.extend(unique_pcm[key])

    packed_voices: list[bytes] = []
    for layer, pcm, table_index in voices:
        body = _pack_layer_with_velocity_table(
            layer,
            sample_offsets[pcm.key],
            table_index,
        )
        packed_voices.append(bytes((2, 0, 0, 0)) + body)

    header = bytearray()
    for offset in (mixer_offset, velocity_offset, peg_offset, plfo_offset):
        header += struct.pack(">H", offset)
    for offset in voice_offsets:
        header += struct.pack(">H", offset)

    result = (
        bytes(header)
        + mixer
        + velocity
        + peg
        + plfo
        + b"".join(packed_voices)
        + bytes(pcm_data)
    )
    if len(result) > _gm.SATURN_TONE_MAX_BYTES:
        raise SaturnGmCalibrationFamilyBankError(
            f"calibration family exceeds Saturn TON budget: {len(result)}"
        )
    return result


def _row_map(inventory: SaturnGmCalibrationInventory) -> Mapping[int, object]:
    rows = {row.program: row for row in inventory.rows}
    if set(rows) != set(range(GM_PROGRAM_COUNT)):
        raise SaturnGmCalibrationFamilyBankError("128-program calibration inventory is incomplete")
    if inventory.rows_with_other_attenuation_modulators:
        raise SaturnGmCalibrationFamilyBankError(
            "GM calibration inventory contains unresolved non-velocity attenuation modulators: "
            + ",".join(str(value) for value in inventory.rows_with_other_attenuation_modulators)
        )
    return rows


def build_gm_calibration_family_banks(
    soundfont: Path | str | None = None,
) -> SaturnGmCalibrationFamilyBanks:
    """Build sixteen real eight-voice TON banks covering GM programs 0..127."""

    inventory = audit_gm_calibration_inventory(soundfont)
    row_by_program = _row_map(inventory)
    payload = inventory.source_path.read_bytes()
    source_sha = sha256(payload).hexdigest()

    with _policy._channel10_selector():
        sf2 = _gm.parse_soundfont_bytes(payload)
        families: list[SaturnGmCalibrationFamilyBank] = []
        for family in range(GM_FAMILY_COUNT):
            programs = tuple(
                range(family * GM_FAMILY_SIZE, (family + 1) * GM_FAMILY_SIZE)
            )
            amounts = tuple(sorted({row_by_program[p].velocity_amount_cb for p in programs}))
            tables = tuple(fit_velocity_table(amount) for amount in amounts)
            packed: list[tuple[_gm.SaturnToneLayer, _gm._PcmBlock, int]] = []
            voice_info: list[SaturnGmCalibrationVoice] = []

            for local_voice, program in enumerate(programs):
                row = row_by_program[program]
                preset = _gm._select_melodic_preset(sf2, program)
                zone = _gm._choose_zone(
                    preset,
                    GM_CALIBRATION_NOTE,
                    GM_CALIBRATION_VELOCITY,
                )
                layer, pcm = _gm._materialize_layer(
                    sf2,
                    zone,
                    GM_CALIBRATION_NOTE,
                    target_rate=GM_CALIBRATION_TARGET_RATE,
                    pcm8=GM_CALIBRATION_PCM8,
                )
                layer = replace(
                    layer,
                    total_level=_static_total_level(zone.attenuation_cb),
                )
                table_index = amounts.index(row.velocity_amount_cb)
                packed.append((layer, pcm, table_index))
                voice_info.append(
                    SaturnGmCalibrationVoice(
                        program=program,
                        family=family,
                        local_voice=local_voice,
                        preset_name=preset.name,
                        sample_id=row.sample_id,
                        sample_name=row.sample_name,
                        velocity_amount_cb=row.velocity_amount_cb,
                        velocity_table=table_index,
                        total_level=layer.total_level,
                        base_note=layer.base_note,
                        fine_tune=layer.fine_tune,
                        pcm_sha256=sha256(pcm.data).hexdigest(),
                    )
                )

            bank_payload = _pack_family(packed, tables)
            families.append(
                SaturnGmCalibrationFamilyBank(
                    family=family,
                    filename=GM_FAMILY_FILENAME_TEMPLATE.format(family=family),
                    programs=programs,
                    payload=bank_payload,
                    sha256=sha256(bank_payload).hexdigest(),
                    voices=tuple(voice_info),
                    velocity_amounts=amounts,
                )
            )

    result = SaturnGmCalibrationFamilyBanks(
        source_path=inventory.source_path,
        source_sha256=source_sha,
        banks=tuple(families),
    )
    if len(result.banks) != GM_FAMILY_COUNT:
        raise SaturnGmCalibrationFamilyBankError("GM family count changed")
    covered = tuple(program for bank in result.banks for program in bank.programs)
    if covered != tuple(range(GM_PROGRAM_COUNT)):
        raise SaturnGmCalibrationFamilyBankError("GM family coverage is not exactly 0..127")
    if result.program_count != GM_PROGRAM_COUNT:
        raise SaturnGmCalibrationFamilyBankError("GM program count changed")
    return result
