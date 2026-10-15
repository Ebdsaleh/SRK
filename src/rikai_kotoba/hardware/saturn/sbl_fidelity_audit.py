"""Offline fidelity audit for the native Space Spectre SDDRV candidate.

This module exists because transport/build success is not musical fidelity.
It independently checks two layers before another physical Saturn run is allowed:

* the locked M6 song must reproduce the authored MIDI channel-event stream
  event-by-event (tick, channel, pitch/data, velocity, note gate and step), with
  only Sega DEC2's documented seven-bit pitch-bend compression allowed;
* the generated SCSPBIN tone banks must be structurally parseable using the
  offsets consumed by Sega's sound driver, and the required melodic programs and
  percussion notes must resolve to real layers/sample addresses.

The audit is read-only.  It never writes to SAROO media and never modifies the
candidate, sequence bank or source MIDI.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct

from rikai_kotoba.formats.midi import parse_midi_bytes
from .midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
    load_srk_saturn_midi_68k_r26_space_spectre_bytes,
)
from .sbl_sequence import (
    _channel_sources,
    _tempo_events,
    decode_uncompressed_saturn_m6,
)
from .sbl_soundfont_gm import (
    SPACE_SPECTRE_DRUM_NOTES,
    SPACE_SPECTRE_MELODIC_PROGRAMS,
)
from .sbl_space_spectre_sequence import (
    BANK_NAME,
    EXPECTED_BANK_SHA256,
    _bind_saturn_tone_banks,
)


class SaturnSblFidelityAuditError(RuntimeError):
    """Raised when offline fidelity proof fails."""


@dataclass(frozen=True)
class SaturnM6FidelityReport:
    source_sha256: str
    sequence_sha256: str
    source_event_count: int
    decoded_event_count: int
    end_tick: int
    tempo_event_count: int
    exact: bool


@dataclass(frozen=True)
class SaturnScspLayerAudit:
    index: int
    start_note: int
    end_note: int
    raw_sa: int
    sample_address: int
    loop_start: int
    loop_end: int
    total_level: int
    direct_send_pan: int
    base_note: int
    fine_tune: int
    velocity_table: int


@dataclass(frozen=True)
class SaturnScspVoiceAudit:
    index: int
    offset: int
    bend_range: int
    layer_count: int
    volume_bias: int
    layers: tuple[SaturnScspLayerAudit, ...]


@dataclass(frozen=True)
class SaturnScspBankAudit:
    path: Path
    sha256: str
    size: int
    mixer_offset: int
    velocity_offset: int
    peg_offset: int
    plfo_offset: int
    voice_count: int
    velocity_table0: bytes
    voices: tuple[SaturnScspVoiceAudit, ...]


@dataclass(frozen=True)
class SaturnDrumNoteAudit:
    note: int
    layers: tuple[SaturnScspLayerAudit, ...]


@dataclass(frozen=True)
class SaturnSblSpaceSpectreFidelityReport:
    sequence: SaturnM6FidelityReport
    melodic: SaturnScspBankAudit
    drums: SaturnScspBankAudit
    melodic_programs: tuple[SaturnScspVoiceAudit, ...]
    drum_notes: tuple[SaturnDrumNoteAudit, ...]
    distinct_drum_sample_addresses: tuple[int, ...]


_SCSP_LAYER_BYTES = 0x20
_SCSP_SAMPLE_ADDRESS_MASK = 0x000FFFFF


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SaturnSblFidelityAuditError(f"{label} is missing: {path}")
    return path


def _expected_decoded_fields(source) -> tuple[str, int, int, int, int, int]:
    event = source.event
    if event.channel is None:
        raise SaturnSblFidelityAuditError("channel source unexpectedly has no channel")
    command = event.status & 0xF0
    if event.kind == "note_on":
        return "note_on", command, event.channel, event.data[0], event.data[1], source.gate_ticks
    if event.kind in {"poly_aftertouch", "control_change"}:
        return "midi", command, event.channel, event.data[0], event.data[1], 0
    if event.kind in {"program_change", "channel_pressure"}:
        return "midi", command, event.channel, event.data[0], 0, 0
    if event.kind == "pitch_bend":
        # Sega DEC2's M6 path stores the seven-bit pitch-bend MSB only.
        return "midi", command, event.channel, 0, event.data[1], 0
    raise SaturnSblFidelityAuditError(f"unsupported audited source event: {event.kind}")


def audit_space_spectre_m6(
    sequence_directory: Path,
    *,
    repository_root: Path | None = None,
) -> SaturnM6FidelityReport:
    """Prove the locked M6 payload preserves the authored channel-event timeline."""

    sequence_directory = Path(sequence_directory).expanduser().resolve(strict=False)
    bank_path = _require_file(sequence_directory / BANK_NAME, "native sequence bank")
    bank = bank_path.read_bytes()
    bank_sha = sha256(bank).hexdigest()
    if bank_sha != EXPECTED_BANK_SHA256:
        raise SaturnSblFidelityAuditError(
            f"native sequence SHA-256 changed: {bank_sha} != {EXPECTED_BANK_SHA256}"
        )
    if len(bank) < 7 or int.from_bytes(bank[0:2], "big") != 1:
        raise SaturnSblFidelityAuditError("native sequence bank is not a one-song bank")
    song_offset = int.from_bytes(bank[2:6], "big")
    if song_offset != 6 or song_offset >= len(bank):
        raise SaturnSblFidelityAuditError("native sequence bank song offset changed")
    song = bank[song_offset:]

    source_bytes = load_srk_saturn_midi_68k_r26_space_spectre_bytes(repository_root)
    source_sha = sha256(source_bytes).hexdigest()
    if source_sha != SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256:
        raise SaturnSblFidelityAuditError("locked Space Spectre MIDI SHA-256 changed")
    midi = parse_midi_bytes(source_bytes)
    authored, _ = _bind_saturn_tone_banks(midi)
    sources, end_tick = _channel_sources(authored)
    tempos = _tempo_events(authored, end_tick)

    if int.from_bytes(song[0:2], "big") != authored.header.ticks_per_quarter:
        raise SaturnSblFidelityAuditError("M6 resolution differs from authored MIDI")
    tempo_count = int.from_bytes(song[2:4], "big")
    track_start = int.from_bytes(song[4:6], "big")
    if tempo_count != len(tempos):
        raise SaturnSblFidelityAuditError(
            f"M6 tempo count mismatch: {tempo_count} != {len(tempos)}"
        )
    expected_track_start = 8 + 8 * len(tempos)
    if track_start != expected_track_start:
        raise SaturnSblFidelityAuditError(
            f"M6 track offset mismatch: {track_start} != {expected_track_start}"
        )
    for index, (step, tempo) in enumerate(tempos):
        offset = 8 + index * 8
        actual_step = int.from_bytes(song[offset : offset + 4], "big")
        actual_tempo = int.from_bytes(song[offset + 4 : offset + 8], "big")
        if (actual_step, actual_tempo) != (step, tempo):
            raise SaturnSblFidelityAuditError(
                f"tempo[{index}] mismatch: {(actual_step, actual_tempo)} != {(step, tempo)}"
            )

    decoded_all = decode_uncompressed_saturn_m6(song)
    if not decoded_all or decoded_all[-1].kind != "end_of_track":
        raise SaturnSblFidelityAuditError("decoded M6 has no final end-of-track")
    if any(event.kind == "end_of_track" for event in decoded_all[:-1]):
        raise SaturnSblFidelityAuditError("decoded M6 contains an early end-of-track")
    decoded = decoded_all[:-1]
    if len(decoded) != len(sources):
        raise SaturnSblFidelityAuditError(
            f"M6 event count mismatch: decoded={len(decoded)} source={len(sources)}"
        )
    if sources and sources[0].tick != 0:
        raise SaturnSblFidelityAuditError(
            "M6 encoding cannot prove a non-zero leading channel-event delay"
        )

    tick = 0
    for index, (source, actual) in enumerate(zip(sources, decoded)):
        expected_step = (
            sources[index + 1].tick - source.tick
            if index + 1 < len(sources)
            else end_tick - source.tick
        )
        if tick != source.tick:
            raise SaturnSblFidelityAuditError(
                f"event[{index}] reconstructed tick mismatch: {tick} != {source.tick}"
            )
        kind, command, channel, data0, data1, gate = _expected_decoded_fields(source)
        observed = (
            actual.kind,
            actual.command,
            actual.channel,
            actual.data0,
            actual.data1,
            actual.gate_ticks,
            actual.step_ticks,
        )
        expected = (kind, command, channel, data0, data1, gate, expected_step)
        if observed != expected:
            raise SaturnSblFidelityAuditError(
                f"event[{index}] mismatch at tick {source.tick}: {observed} != {expected}; "
                f"source_kind={source.event.kind}"
            )
        tick += actual.step_ticks
    if tick != end_tick:
        raise SaturnSblFidelityAuditError(
            f"M6 reconstructed end tick mismatch: {tick} != {end_tick}"
        )

    return SaturnM6FidelityReport(
        source_sha256=source_sha,
        sequence_sha256=bank_sha,
        source_event_count=len(sources),
        decoded_event_count=len(decoded),
        end_tick=end_tick,
        tempo_event_count=len(tempos),
        exact=True,
    )


def parse_scspbin_tone_bank(path: Path) -> SaturnScspBankAudit:
    """Parse a Sega SCSPBIN tone bank using the offsets consumed by SDDRV."""

    path = _require_file(Path(path).expanduser().resolve(strict=False), "SCSPBIN tone bank")
    payload = path.read_bytes()
    if len(payload) < 10:
        raise SaturnSblFidelityAuditError(f"tone bank is too small: {path}")
    mixer, velocity, peg, plfo = struct.unpack_from(">HHHH", payload, 0)
    if mixer < 10 or (mixer - 8) % 2:
        raise SaturnSblFidelityAuditError(
            f"invalid SCSPBIN voice-offset table boundary: 0x{mixer:X}"
        )
    voice_count = (mixer - 8) // 2
    if voice_count < 1:
        raise SaturnSblFidelityAuditError("SCSPBIN tone bank has no voices")
    if not (mixer <= velocity <= peg <= plfo <= len(payload)):
        raise SaturnSblFidelityAuditError(
            "SCSPBIN MIX/VL/PEG/PLFO offsets are not monotonic/in range"
        )
    if velocity + 10 > len(payload):
        raise SaturnSblFidelityAuditError("SCSPBIN velocity table 0 is truncated")

    voices: list[SaturnScspVoiceAudit] = []
    for index in range(voice_count):
        table_off = 8 + index * 2
        voice_off = int.from_bytes(payload[table_off : table_off + 2], "big")
        if voice_off + 4 > len(payload):
            raise SaturnSblFidelityAuditError(
                f"voice {index} offset is outside bank: 0x{voice_off:X}"
            )
        bend_range = payload[voice_off] & 0x0F
        layer_count = payload[voice_off + 2] + 1
        volume_bias = payload[voice_off + 3]
        if not 1 <= layer_count <= 128:
            raise SaturnSblFidelityAuditError(
                f"voice {index} has invalid layer count {layer_count}"
            )
        end = voice_off + 4 + layer_count * _SCSP_LAYER_BYTES
        if end > len(payload):
            raise SaturnSblFidelityAuditError(
                f"voice {index} layer data runs past bank end"
            )
        layers: list[SaturnScspLayerAudit] = []
        for layer_index in range(layer_count):
            off = voice_off + 4 + layer_index * _SCSP_LAYER_BYTES
            start_note = payload[off]
            end_note = payload[off + 1]
            raw_sa = int.from_bytes(payload[off + 2 : off + 6], "big")
            sample_address = raw_sa & _SCSP_SAMPLE_ADDRESS_MASK
            loop_start = int.from_bytes(payload[off + 6 : off + 8], "big")
            loop_end = int.from_bytes(payload[off + 8 : off + 10], "big")
            total_level = payload[off + 0x0F]
            direct_send_pan = payload[off + 0x18]
            base_note = payload[off + 0x19]
            fine_tune = struct.unpack_from("b", payload, off + 0x1A)[0]
            velocity_table = payload[off + 0x1D]
            if start_note > end_note:
                raise SaturnSblFidelityAuditError(
                    f"voice {index} layer {layer_index} has reversed key range "
                    f"{start_note}..{end_note}"
                )
            if sample_address >= len(payload):
                raise SaturnSblFidelityAuditError(
                    f"voice {index} layer {layer_index} sample address 0x{sample_address:X} "
                    f"is outside {len(payload)}-byte bank"
                )
            layers.append(
                SaturnScspLayerAudit(
                    index=layer_index,
                    start_note=start_note,
                    end_note=end_note,
                    raw_sa=raw_sa,
                    sample_address=sample_address,
                    loop_start=loop_start,
                    loop_end=loop_end,
                    total_level=total_level,
                    direct_send_pan=direct_send_pan,
                    base_note=base_note,
                    fine_tune=fine_tune,
                    velocity_table=velocity_table,
                )
            )
        voices.append(
            SaturnScspVoiceAudit(
                index=index,
                offset=voice_off,
                bend_range=bend_range,
                layer_count=layer_count,
                volume_bias=volume_bias,
                layers=tuple(layers),
            )
        )

    return SaturnScspBankAudit(
        path=path,
        sha256=_sha_file(path),
        size=len(payload),
        mixer_offset=mixer,
        velocity_offset=velocity,
        peg_offset=peg,
        plfo_offset=plfo,
        voice_count=voice_count,
        velocity_table0=payload[velocity : velocity + 10],
        voices=tuple(voices),
    )


def audit_space_spectre_tone_banks(project_directory: Path):
    project = Path(project_directory).expanduser().resolve(strict=False)
    melodic = parse_scspbin_tone_bank(project / "cd" / "SRKGM.BIN")
    drums = parse_scspbin_tone_bank(project / "cd" / "SRKDRUM.BIN")

    missing_programs = [p for p in SPACE_SPECTRE_MELODIC_PROGRAMS if p >= melodic.voice_count]
    if missing_programs:
        raise SaturnSblFidelityAuditError(
            f"melodic bank is missing required program voices: {missing_programs}"
        )
    melodic_programs = tuple(melodic.voices[p] for p in SPACE_SPECTRE_MELODIC_PROGRAMS)
    for voice in melodic_programs:
        if not voice.layers:
            raise SaturnSblFidelityAuditError(
                f"melodic program {voice.index} has no layers"
            )

    if not drums.voices:
        raise SaturnSblFidelityAuditError("drum bank has no voice 0")
    drum_voice = drums.voices[0]
    note_reports: list[SaturnDrumNoteAudit] = []
    all_addresses: set[int] = set()
    for note in SPACE_SPECTRE_DRUM_NOTES:
        matches = tuple(
            layer for layer in drum_voice.layers if layer.start_note <= note <= layer.end_note
        )
        if not matches:
            raise SaturnSblFidelityAuditError(
                f"drum note {note} resolves to no layer in drum voice 0"
            )
        note_reports.append(SaturnDrumNoteAudit(note=note, layers=matches))
        all_addresses.update(layer.sample_address for layer in matches)

    return melodic, drums, melodic_programs, tuple(note_reports), tuple(sorted(all_addresses))


def audit_space_spectre_fidelity(
    project_directory: Path,
    sequence_directory: Path,
    *,
    repository_root: Path | None = None,
) -> SaturnSblSpaceSpectreFidelityReport:
    """Run the complete read-only sequence + tone-bank fidelity audit."""

    sequence = audit_space_spectre_m6(
        sequence_directory,
        repository_root=repository_root,
    )
    melodic, drums, melodic_programs, drum_notes, distinct = audit_space_spectre_tone_banks(
        project_directory
    )
    return SaturnSblSpaceSpectreFidelityReport(
        sequence=sequence,
        melodic=melodic,
        drums=drums,
        melodic_programs=melodic_programs,
        drum_notes=drum_notes,
        distinct_drum_sample_addresses=distinct,
    )
