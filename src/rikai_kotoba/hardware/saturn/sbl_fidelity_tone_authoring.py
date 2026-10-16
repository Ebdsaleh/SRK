"""In-memory high-fidelity Saturn TON authoring for Space Spectre.

This module keeps the historical compact converter untouched while applying the
two fidelity corrections proven by the GATE3E offline audits:

* SoundFont static ``initialAttenuation`` uses the 40% compatibility mapping;
* each used layer selects a Sega-native 10-byte velocity table matching its
  resolved SoundFont velocity -> attenuation modulator.

The policy is scoped around one build and restores every monkey-patched helper
afterward.  Nothing is written to disk.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import struct
from typing import Iterator, Mapping, Sequence

from . import sbl_soundfont_gm as _gm
from . import sbl_soundfont_channel10 as _policy
from .sbl_level_model_audit import (
    nearest_scsp_total_level,
    soundfont_static_attenuation_db,
)
from .sbl_velocity_curve import table_for_velocity_amount


class SaturnFidelityToneAuthoringError(RuntimeError):
    """Raised when the corrected in-memory TON build cannot be proven safe."""


ToneKey = tuple[str, int, int]


@dataclass(frozen=True)
class SaturnFidelityToneRow:
    kind: str
    program: int
    note: int
    velocity_amount_cb: int
    velocity_table: int
    total_level: int
    base_note: int
    fine_tune: int
    pcm_sha256: str

    @property
    def key(self) -> ToneKey:
        return self.kind, self.program, self.note


@dataclass(frozen=True)
class SaturnFidelityToneBuild:
    banks: _gm.SaturnSoundfontBanks
    rows: tuple[SaturnFidelityToneRow, ...]
    melodic_table_amounts: tuple[int, ...]
    drum_table_amounts: tuple[int, ...]
    melodic_velocity_tables: tuple[bytes, ...]
    drum_velocity_tables: tuple[bytes, ...]


@dataclass
class _BuildState:
    velocity_amount_by_key: dict[ToneKey, int]
    melodic_table_amounts: tuple[int, ...]
    drum_table_amounts: tuple[int, ...]
    melodic_velocity_tables: tuple[bytes, ...]
    drum_velocity_tables: tuple[bytes, ...]
    current_kind: str | None = None
    current_program: int = 0
    bank_call: int = 0
    layer_table_index: dict[int, int] | None = None
    rows: list[SaturnFidelityToneRow] | None = None

    def __post_init__(self) -> None:
        self.layer_table_index = {}
        self.rows = []


def _static_total_level(centibels: int) -> int:
    target_db = soundfont_static_attenuation_db(centibels)
    level, _actual_db = nearest_scsp_total_level(target_db)
    return level


def _validate_velocity_table_catalog(tables: Sequence[bytes]) -> tuple[bytes, ...]:
    result = tuple(bytes(table) for table in tables)
    if not result:
        raise SaturnFidelityToneAuthoringError("Saturn TON requires at least one velocity table")
    if len(result) > 256:
        raise SaturnFidelityToneAuthoringError("Saturn TON velocity-table count exceeds byte index range")
    for index, table in enumerate(result):
        if len(table) != 10:
            raise SaturnFidelityToneAuthoringError(
                f"velocity table {index} is {len(table)} bytes instead of 10"
            )
    return result


def _pack_tone_bank(
    voices: Sequence[_gm.SaturnToneVoice],
    pcm_blocks: Sequence[_gm._PcmBlock],
    *,
    pcm8: bool,
    velocity_tables: Sequence[bytes],
) -> bytes:
    """Pack a TON bank exactly like the base converter, with N velocity tables."""

    if not voices or len(voices) > 128:
        raise SaturnFidelityToneAuthoringError("Saturn tone bank voice count must be 1..128")
    velocity_tables = _validate_velocity_table_catalog(velocity_tables)

    mixer = bytes(18)
    velocity = b"".join(velocity_tables)
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
    for voice in voices:
        voice_offsets.append(cursor)
        cursor += 4 + 32 * len(voice.layers)
    if any(offset > 0xFFFF for offset in voice_offsets):
        raise SaturnFidelityToneAuthoringError(
            "Saturn tone voice metadata exceeds 16-bit offset table"
        )

    unique: dict[tuple[int, int, int, int, int], bytes] = {}
    silent_key = (-1, 0, 1, _gm.SATURN_PCM_NATIVE_RATE, 1 if pcm8 else 0)
    unique[silent_key] = b"\0" if pcm8 else b"\0\0"
    for block in pcm_blocks:
        previous = unique.get(block.key)
        if previous is not None and previous != block.data:
            raise SaturnFidelityToneAuthoringError("PCM deduplication key collision")
        unique[block.key] = block.data

    sample_offsets: dict[tuple[int, int, int, int, int], int] = {}
    pcm_data = bytearray()
    for key in sorted(unique):
        if not pcm8 and (cursor + len(pcm_data)) & 1:
            pcm_data.append(0)
        sample_offsets[key] = cursor + len(pcm_data)
        pcm_data.extend(unique[key])

    packed_voices = [_gm._pack_voice(voice, sample_offsets) for voice in voices]
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
        raise SaturnFidelityToneAuthoringError(
            f"single Saturn tone bank is too large: {len(result)} > {_gm.SATURN_TONE_MAX_BYTES}"
        )
    return result


def _catalog(
    mapping: Mapping[ToneKey, int],
    kind: str,
) -> tuple[int, ...]:
    values = tuple(sorted({int(amount) for key, amount in mapping.items() if key[0] == kind}))
    if not values:
        raise SaturnFidelityToneAuthoringError(f"no {kind} velocity amounts were supplied")
    for amount in values:
        table_for_velocity_amount(amount)
    return values


@contextmanager
def _fidelity_policy(state: _BuildState) -> Iterator[None]:
    original_melodic_selector = _gm._select_melodic_preset
    original_drum_selector = _gm._select_drum_preset
    original_materialize = _gm._materialize_layer
    original_total_level = _gm._total_level
    original_pack_layer = _gm._pack_layer
    original_build_tone_bank = _gm._build_tone_bank
    original_build_strategy = _gm._build_strategy

    def melodic_selector(sf2: _gm.Sf2Data, program: int) -> _gm.Sf2Preset:
        state.current_kind = "melodic"
        state.current_program = int(program)
        return original_melodic_selector(sf2, program)

    def drum_selector(sf2: _gm.Sf2Data) -> _gm.Sf2Preset:
        state.current_kind = "drum"
        state.current_program = 0
        return original_drum_selector(sf2)

    def materialize(
        sf2: _gm.Sf2Data,
        zone: _gm.Sf2PresetZone,
        note: int,
        *,
        target_rate: int,
        pcm8: bool,
    ):
        layer, pcm = original_materialize(
            sf2,
            zone,
            note,
            target_rate=target_rate,
            pcm8=pcm8,
        )
        if state.current_kind is None:
            raise SaturnFidelityToneAuthoringError("tone layer materialized outside a selected preset")
        key = (state.current_kind, state.current_program, int(note))
        if key not in state.velocity_amount_by_key:
            raise SaturnFidelityToneAuthoringError(
                f"no resolved SoundFont velocity amount for tone row {key!r}"
            )
        amount = state.velocity_amount_by_key[key]
        catalog = (
            state.melodic_table_amounts
            if state.current_kind == "melodic"
            else state.drum_table_amounts
        )
        table_index = catalog.index(amount)
        assert state.layer_table_index is not None
        assert state.rows is not None
        state.layer_table_index[id(layer)] = table_index
        state.rows.append(
            SaturnFidelityToneRow(
                kind=state.current_kind,
                program=state.current_program,
                note=int(note),
                velocity_amount_cb=amount,
                velocity_table=table_index,
                total_level=layer.total_level,
                base_note=layer.base_note,
                fine_tune=layer.fine_tune,
                pcm_sha256=sha256(pcm.data).hexdigest(),
            )
        )
        return layer, pcm

    def pack_layer(layer: _gm.SaturnToneLayer, sa: int) -> bytes:
        data = bytearray(original_pack_layer(layer, sa))
        assert state.layer_table_index is not None
        data[0x1D] = state.layer_table_index.get(id(layer), 0) & 0xFF
        return bytes(data)

    def build_tone_bank(
        voices: Sequence[_gm.SaturnToneVoice],
        pcm_blocks: Sequence[_gm._PcmBlock],
        *,
        pcm8: bool,
    ) -> bytes:
        if state.bank_call == 0:
            tables = state.melodic_velocity_tables
        elif state.bank_call == 1:
            tables = state.drum_velocity_tables
        else:
            raise SaturnFidelityToneAuthoringError(
                f"unexpected TON bank call {state.bank_call}; expected melodic then drums"
            )
        state.bank_call += 1
        return _pack_tone_bank(voices, pcm_blocks, pcm8=pcm8, velocity_tables=tables)

    def build_strategy(*args, **kwargs):
        state.bank_call = 0
        assert state.layer_table_index is not None
        assert state.rows is not None
        state.layer_table_index.clear()
        state.rows.clear()
        return original_build_strategy(*args, **kwargs)

    _gm._select_melodic_preset = melodic_selector
    _gm._select_drum_preset = drum_selector
    _gm._materialize_layer = materialize
    _gm._total_level = _static_total_level
    _gm._pack_layer = pack_layer
    _gm._build_tone_bank = build_tone_bank
    _gm._build_strategy = build_strategy
    try:
        yield
    finally:
        _gm._build_strategy = original_build_strategy
        _gm._build_tone_bank = original_build_tone_bank
        _gm._pack_layer = original_pack_layer
        _gm._total_level = original_total_level
        _gm._materialize_layer = original_materialize
        _gm._select_drum_preset = original_drum_selector
        _gm._select_melodic_preset = original_melodic_selector


def build_space_spectre_fidelity_tone_banks(
    soundfont,
    requirements: _gm.MidiToneRequirements,
    velocity_amount_by_key: Mapping[ToneKey, int],
) -> SaturnFidelityToneBuild:
    """Build corrected Space Spectre tone banks entirely in memory."""

    mapping = {tuple(key): int(value) for key, value in velocity_amount_by_key.items()}
    melodic_amounts = _catalog(mapping, "melodic")
    drum_amounts = _catalog(mapping, "drum")
    state = _BuildState(
        velocity_amount_by_key=mapping,
        melodic_table_amounts=melodic_amounts,
        drum_table_amounts=drum_amounts,
        melodic_velocity_tables=tuple(table_for_velocity_amount(v) for v in melodic_amounts),
        drum_velocity_tables=tuple(table_for_velocity_amount(v) for v in drum_amounts),
    )

    with _policy._channel10_selector():
        with _fidelity_policy(state):
            banks = _gm.build_compact_saturn_gm_banks(soundfont, requirements)

    assert state.rows is not None
    rows = tuple(state.rows)
    observed = {row.key for row in rows}
    expected = set(mapping)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise SaturnFidelityToneAuthoringError(
            f"fidelity tone rows differ from resolved modulator scope; missing={missing!r} extra={extra!r}"
        )
    if len(observed) != len(rows):
        raise SaturnFidelityToneAuthoringError("fidelity tone rows are not unique")

    return SaturnFidelityToneBuild(
        banks=banks,
        rows=rows,
        melodic_table_amounts=melodic_amounts,
        drum_table_amounts=drum_amounts,
        melodic_velocity_tables=state.melodic_velocity_tables,
        drum_velocity_tables=state.drum_velocity_tables,
    )
