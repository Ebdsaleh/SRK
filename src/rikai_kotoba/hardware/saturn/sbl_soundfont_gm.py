"""Build compact Sega Saturn SBL tone banks from a General MIDI SoundFont.

The converter is deliberately song-scoped.  It reads only the SoundFont presets,
notes and PCM samples required by the supplied MIDI program, then emits native
Sega Sound Driver TON banks.  The generated banks are ordinary external build
artifacts; no SoundFont or derived PCM is committed to SRK.

TON layout and SCSP parameter choices are based on Sega's SBL 6.01 sound-driver
sources (SCSP.LIB/NON.ASM), ST-241, and the open-source mid2seq sf2ton work by
Joao F. Santos (BSD-3-Clause).  This implementation is independent Python code
specialized for deterministic SRK candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
import math
import os
import shutil
import struct
import tempfile
import urllib.request
from typing import Iterable, Mapping, Sequence


class SaturnSblSoundfontError(RuntimeError):
    """Raised when a SoundFont cannot produce a safe Saturn tone bank."""


GENERALUSER_COMMIT = "684543d5e5efaef08d02be50dcda8d552478fa60"
GENERALUSER_BLOB_SHA1 = "298b552d2e9d1307e03e5c5c99d2c046aaed9ec3"
GENERALUSER_BYTES = 32_319_396
GENERALUSER_URL = (
    "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/"
    f"{GENERALUSER_COMMIT}/GeneralUser-GS.sf2"
)

SATURN_SOUND_RAM_BANK_BUDGET = 0x80000 - 0x0B000
SATURN_TONE_MAX_BYTES = SATURN_SOUND_RAM_BANK_BUDGET
SATURN_LAYER_MAX_SAMPLES = 0xFFFF
SATURN_MAX_LAYERS_PER_VOICE = 128
SATURN_PCM_NATIVE_RATE = 44_100

# Space Spectre's exact GM requirements are intentionally small.  The builder
# derives these from the MIDI program at runtime; constants are regression
# guards and useful diagnostics, not a second source of truth.
SPACE_SPECTRE_MELODIC_PROGRAMS = (30, 39, 73, 120)
SPACE_SPECTRE_DRUM_NOTES = (35, 40, 42, 51)
SPACE_SPECTRE_PERCUSSION_CHANNEL = 9

# SoundFont generator operators used by the compact converter.
_GEN_START = 0
_GEN_END = 1
_GEN_LOOP_START = 2
_GEN_LOOP_END = 3
_GEN_START_COARSE = 4
_GEN_END_COARSE = 12
_GEN_PAN = 17
_GEN_ATTACK = 34
_GEN_DECAY = 36
_GEN_SUSTAIN = 37
_GEN_RELEASE = 38
_GEN_INSTRUMENT = 41
_GEN_KEY_RANGE = 43
_GEN_VEL_RANGE = 44
_GEN_LOOP_START_COARSE = 45
_GEN_ATTENUATION = 48
_GEN_LOOP_END_COARSE = 50
_GEN_COARSE_TUNE = 51
_GEN_FINE_TUNE = 52
_GEN_SAMPLE_ID = 53
_GEN_SAMPLE_MODES = 54
_GEN_SCALE_TUNING = 56
_GEN_ROOT_KEY = 58

_ADD_GENERATORS = {
    _GEN_START,
    _GEN_END,
    _GEN_LOOP_START,
    _GEN_LOOP_END,
    _GEN_START_COARSE,
    _GEN_END_COARSE,
    _GEN_LOOP_START_COARSE,
    _GEN_LOOP_END_COARSE,
    _GEN_PAN,
    _GEN_ATTACK,
    _GEN_DECAY,
    _GEN_SUSTAIN,
    _GEN_RELEASE,
    _GEN_ATTENUATION,
    _GEN_COARSE_TUNE,
    _GEN_FINE_TUNE,
}


@dataclass(frozen=True)
class Sf2Sample:
    name: str
    start: int
    end: int
    loop_start: int
    loop_end: int
    sample_rate: int
    original_key: int
    pitch_correction: int
    link: int
    sample_type: int


@dataclass(frozen=True)
class Sf2PresetZone:
    key_lo: int
    key_hi: int
    vel_lo: int
    vel_hi: int
    sample_id: int
    start_offset: int
    end_offset: int
    loop_start_offset: int
    loop_end_offset: int
    attenuation_cb: int
    coarse_tune: int
    fine_tune: int
    attack_tc: int
    decay_tc: int
    sustain_cb: int
    release_tc: int
    sample_modes: int
    root_key: int | None
    scale_tuning: int


@dataclass(frozen=True)
class Sf2Preset:
    name: str
    program: int
    bank: int
    zones: tuple[Sf2PresetZone, ...]


@dataclass(frozen=True)
class Sf2Data:
    smpl: bytes
    samples: tuple[Sf2Sample, ...]
    presets: tuple[Sf2Preset, ...]


@dataclass(frozen=True)
class MidiToneRequirements:
    melodic_notes: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    drum_notes: tuple[tuple[int, int], ...]

    @property
    def programs(self) -> tuple[int, ...]:
        return tuple(program for program, _ in self.melodic_notes)

    @property
    def percussion_notes(self) -> tuple[int, ...]:
        return tuple(note for note, _ in self.drum_notes)


@dataclass(frozen=True)
class SaturnToneLayer:
    start_note: int
    end_note: int
    base_note: int
    fine_tune: int
    pcm_key: tuple[int, int, int, int, int]
    loop_start: int
    loop_end: int
    loop_enabled: bool
    pcm8: bool
    attack_rate: int
    decay_rate: int
    decay_level: int
    release_rate: int
    total_level: int


@dataclass(frozen=True)
class SaturnToneVoice:
    layers: tuple[SaturnToneLayer, ...]
    bend_range: int = 2
    volume_bias: int = 0


@dataclass(frozen=True)
class _PcmBlock:
    key: tuple[int, int, int, int, int]
    data: bytes


@dataclass(frozen=True)
class SaturnSoundfontBanks:
    melodic_bytes: bytes
    drum_bytes: bytes
    source_sha256: str
    source_blob_sha1: str
    sample_rate: int
    pcm8: bool
    melodic_programs: tuple[int, ...]
    drum_notes: tuple[int, ...]

    @property
    def combined_bytes(self) -> int:
        return len(self.melodic_bytes) + len(self.drum_bytes)


@dataclass(frozen=True)
class SaturnSoundfontBankFiles:
    melodic_path: Path
    drum_path: Path
    report_path: Path
    source_path: Path
    melodic_sha256: str
    drum_sha256: str
    source_sha256: str
    sample_rate: int
    pcm8: bool
    combined_bytes: int


def _iter_riff_chunks(data: bytes, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        chunk_id = data[pos : pos + 4]
        size = struct.unpack_from("<I", data, pos + 4)[0]
        payload_start = pos + 8
        payload_end = payload_start + size
        if payload_end > end:
            raise SaturnSblSoundfontError("SoundFont RIFF chunk extends past file")
        yield chunk_id, payload_start, payload_end
        pos = payload_end + (size & 1)


def _sf2_sections(data: bytes) -> dict[tuple[bytes, bytes], bytes]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"sfbk":
        raise SaturnSblSoundfontError("input is not a RIFF SoundFont (sfbk)")
    riff_size = struct.unpack_from("<I", data, 4)[0]
    riff_end = min(len(data), 8 + riff_size)
    result: dict[tuple[bytes, bytes], bytes] = {}
    for chunk_id, p0, p1 in _iter_riff_chunks(data, 12, riff_end):
        if chunk_id != b"LIST" or p1 - p0 < 4:
            continue
        list_type = data[p0 : p0 + 4]
        for sub_id, s0, s1 in _iter_riff_chunks(data, p0 + 4, p1):
            result[(list_type, sub_id)] = data[s0:s1]
    return result


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _s16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def _parse_generators(data: bytes) -> list[tuple[int, int]]:
    if len(data) % 4:
        raise SaturnSblSoundfontError("SoundFont generator table is misaligned")
    result = []
    for off in range(0, len(data), 4):
        op = _u16(data, off)
        amount = _s16(data, off + 2)
        result.append((op, amount))
    return result


def _bag_gen_indices(data: bytes) -> list[int]:
    if len(data) % 4:
        raise SaturnSblSoundfontError("SoundFont bag table is misaligned")
    return [_u16(data, off) for off in range(0, len(data), 4)]


def _parse_samples(data: bytes) -> tuple[Sf2Sample, ...]:
    if len(data) % 46:
        raise SaturnSblSoundfontError("SoundFont sample-header table is misaligned")
    count = len(data) // 46
    if count < 1:
        raise SaturnSblSoundfontError("SoundFont has no sample headers")
    samples = []
    for index in range(count - 1):  # terminal EOS record
        off = index * 46
        name = data[off : off + 20].split(b"\0", 1)[0].decode("latin-1", "replace")
        start, end, loop_start, loop_end, rate = struct.unpack_from("<IIIII", data, off + 20)
        original_key = data[off + 40]
        pitch_correction = struct.unpack_from("<b", data, off + 41)[0]
        link = _u16(data, off + 42)
        sample_type = _u16(data, off + 44)
        samples.append(
            Sf2Sample(
                name=name,
                start=start,
                end=end,
                loop_start=loop_start,
                loop_end=loop_end,
                sample_rate=rate,
                original_key=original_key,
                pitch_correction=pitch_correction,
                link=link,
                sample_type=sample_type,
            )
        )
    return tuple(samples)


def _parse_inst_headers(data: bytes) -> list[tuple[str, int]]:
    if len(data) % 22:
        raise SaturnSblSoundfontError("SoundFont instrument table is misaligned")
    result = []
    for off in range(0, len(data), 22):
        name = data[off : off + 20].split(b"\0", 1)[0].decode("latin-1", "replace")
        result.append((name, _u16(data, off + 20)))
    return result


def _parse_preset_headers(data: bytes) -> list[tuple[str, int, int, int]]:
    if len(data) % 38:
        raise SaturnSblSoundfontError("SoundFont preset table is misaligned")
    result = []
    for off in range(0, len(data), 38):
        name = data[off : off + 20].split(b"\0", 1)[0].decode("latin-1", "replace")
        program = _u16(data, off + 20)
        bank = _u16(data, off + 22)
        bag = _u16(data, off + 24)
        result.append((name, program, bank, bag))
    return result


def _zone_map(gens: Sequence[tuple[int, int]]) -> dict[int, int]:
    result: dict[int, int] = {}
    for op, signed in gens:
        if op in (_GEN_KEY_RANGE, _GEN_VEL_RANGE, _GEN_INSTRUMENT, _GEN_SAMPLE_ID, _GEN_SAMPLE_MODES, _GEN_ROOT_KEY, _GEN_SCALE_TUNING):
            value = signed & 0xFFFF
        else:
            value = signed
        if op in _ADD_GENERATORS and op in result:
            result[op] += value
        else:
            result[op] = value
    return result


def _range(value: int | None) -> tuple[int, int]:
    if value is None:
        return 0, 127
    return value & 0xFF, (value >> 8) & 0xFF


def _merge_zone_maps(*maps: Mapping[int, int]) -> dict[int, int]:
    result: dict[int, int] = {}
    key_lo, key_hi = 0, 127
    vel_lo, vel_hi = 0, 127
    for mapping in maps:
        if _GEN_KEY_RANGE in mapping:
            lo, hi = _range(mapping[_GEN_KEY_RANGE])
            key_lo, key_hi = max(key_lo, lo), min(key_hi, hi)
        if _GEN_VEL_RANGE in mapping:
            lo, hi = _range(mapping[_GEN_VEL_RANGE])
            vel_lo, vel_hi = max(vel_lo, lo), min(vel_hi, hi)
        for op, value in mapping.items():
            if op in (_GEN_KEY_RANGE, _GEN_VEL_RANGE):
                continue
            if op in _ADD_GENERATORS:
                result[op] = result.get(op, 0) + value
            else:
                result[op] = value
    result[_GEN_KEY_RANGE] = key_lo | (key_hi << 8)
    result[_GEN_VEL_RANGE] = vel_lo | (vel_hi << 8)
    return result


def _slice_generators(
    bags: Sequence[int], generators: Sequence[tuple[int, int]], bag_index: int
) -> dict[int, int]:
    if bag_index < 0 or bag_index >= len(bags):
        raise SaturnSblSoundfontError("SoundFont bag index is out of range")
    start = bags[bag_index]
    end = bags[bag_index + 1] if bag_index + 1 < len(bags) else len(generators)
    if start > end or end > len(generators):
        raise SaturnSblSoundfontError("SoundFont generator index is out of range")
    return _zone_map(generators[start:end])


def parse_soundfont_bytes(data: bytes) -> Sf2Data:
    sections = _sf2_sections(data)
    required = (
        (b"sdta", b"smpl"),
        (b"pdta", b"phdr"),
        (b"pdta", b"pbag"),
        (b"pdta", b"pgen"),
        (b"pdta", b"inst"),
        (b"pdta", b"ibag"),
        (b"pdta", b"igen"),
        (b"pdta", b"shdr"),
    )
    missing = [b"/".join(key).decode("ascii") for key in required if key not in sections]
    if missing:
        raise SaturnSblSoundfontError("SoundFont missing chunks: " + ", ".join(missing))

    smpl = sections[(b"sdta", b"smpl")]
    samples = _parse_samples(sections[(b"pdta", b"shdr")])
    phdr = _parse_preset_headers(sections[(b"pdta", b"phdr")])
    inst = _parse_inst_headers(sections[(b"pdta", b"inst")])
    pbag = _bag_gen_indices(sections[(b"pdta", b"pbag")])
    ibag = _bag_gen_indices(sections[(b"pdta", b"ibag")])
    pgen = _parse_generators(sections[(b"pdta", b"pgen")])
    igen = _parse_generators(sections[(b"pdta", b"igen")])
    if len(phdr) < 2 or len(inst) < 2:
        raise SaturnSblSoundfontError("SoundFont has no usable presets/instruments")

    # Instrument global/local zones.  Each entry maps an instrument index to
    # (global generators, local sample zones).
    instruments: dict[int, tuple[dict[int, int], tuple[dict[int, int], ...]]] = {}
    for inst_index in range(len(inst) - 1):
        bag_start = inst[inst_index][1]
        bag_end = inst[inst_index + 1][1]
        if bag_start > bag_end or bag_end > len(ibag):
            raise SaturnSblSoundfontError("SoundFont instrument bag range is invalid")
        global_map: dict[int, int] = {}
        locals_: list[dict[int, int]] = []
        for bag_index in range(bag_start, bag_end):
            mapping = _slice_generators(ibag, igen, bag_index)
            if _GEN_SAMPLE_ID not in mapping:
                global_map = _merge_zone_maps(global_map, mapping)
            else:
                locals_.append(mapping)
        instruments[inst_index] = (global_map, tuple(locals_))

    presets: list[Sf2Preset] = []
    for preset_index in range(len(phdr) - 1):
        name, program, bank, bag_start = phdr[preset_index]
        bag_end = phdr[preset_index + 1][3]
        if bag_start > bag_end or bag_end > len(pbag):
            raise SaturnSblSoundfontError("SoundFont preset bag range is invalid")
        preset_global: dict[int, int] = {}
        preset_locals: list[dict[int, int]] = []
        for bag_index in range(bag_start, bag_end):
            mapping = _slice_generators(pbag, pgen, bag_index)
            if _GEN_INSTRUMENT not in mapping:
                preset_global = _merge_zone_maps(preset_global, mapping)
            else:
                preset_locals.append(mapping)

        zones: list[Sf2PresetZone] = []
        for preset_local in preset_locals:
            inst_index = preset_local.get(_GEN_INSTRUMENT, -1)
            if inst_index not in instruments:
                continue
            inst_global, inst_locals = instruments[inst_index]
            for inst_local in inst_locals:
                merged = _merge_zone_maps(preset_global, preset_local, inst_global, inst_local)
                key_lo, key_hi = _range(merged.get(_GEN_KEY_RANGE))
                vel_lo, vel_hi = _range(merged.get(_GEN_VEL_RANGE))
                if key_lo > key_hi or vel_lo > vel_hi:
                    continue
                sample_id = merged.get(_GEN_SAMPLE_ID, -1)
                if not (0 <= sample_id < len(samples)):
                    continue
                root_raw = merged.get(_GEN_ROOT_KEY)
                root_key = None if root_raw is None or root_raw > 127 else root_raw
                zones.append(
                    Sf2PresetZone(
                        key_lo=key_lo,
                        key_hi=key_hi,
                        vel_lo=vel_lo,
                        vel_hi=vel_hi,
                        sample_id=sample_id,
                        start_offset=merged.get(_GEN_START, 0) + 32768 * merged.get(_GEN_START_COARSE, 0),
                        end_offset=merged.get(_GEN_END, 0) + 32768 * merged.get(_GEN_END_COARSE, 0),
                        loop_start_offset=merged.get(_GEN_LOOP_START, 0) + 32768 * merged.get(_GEN_LOOP_START_COARSE, 0),
                        loop_end_offset=merged.get(_GEN_LOOP_END, 0) + 32768 * merged.get(_GEN_LOOP_END_COARSE, 0),
                        attenuation_cb=max(0, merged.get(_GEN_ATTENUATION, 0)),
                        coarse_tune=merged.get(_GEN_COARSE_TUNE, 0),
                        fine_tune=merged.get(_GEN_FINE_TUNE, 0),
                        attack_tc=merged.get(_GEN_ATTACK, -12000),
                        decay_tc=merged.get(_GEN_DECAY, -12000),
                        sustain_cb=max(0, merged.get(_GEN_SUSTAIN, 0)),
                        release_tc=merged.get(_GEN_RELEASE, -12000),
                        sample_modes=merged.get(_GEN_SAMPLE_MODES, 0) & 3,
                        root_key=root_key,
                        scale_tuning=merged.get(_GEN_SCALE_TUNING, 100),
                    )
                )
        presets.append(Sf2Preset(name=name, program=program, bank=bank, zones=tuple(zones)))

    return Sf2Data(smpl=smpl, samples=samples, presets=tuple(presets))


def parse_soundfont(path: Path | str) -> Sf2Data:
    source = Path(path).expanduser().resolve(strict=True)
    return parse_soundfont_bytes(source.read_bytes())


def derive_midi_tone_requirements(program) -> MidiToneRequirements:
    """Derive exact program/note/velocity requirements from an SRKM program."""
    # Imported lazily so this module remains independently testable.
    from .midi_program import SaturnMidiOpcode

    current_program = [0] * 16
    melodic: dict[int, dict[int, list[int]]] = {}
    drums: dict[int, list[int]] = {}
    for record in program.records:
        channel = int(record.channel)
        if record.opcode == SaturnMidiOpcode.PROGRAM_CHANGE:
            current_program[channel] = int(record.data0)
            continue
        if record.opcode != SaturnMidiOpcode.NOTE_ON or int(record.data1) == 0:
            continue
        note = int(record.data0)
        velocity = int(record.data1)
        if channel == SPACE_SPECTRE_PERCUSSION_CHANNEL:
            drums.setdefault(note, []).append(velocity)
        else:
            prog = current_program[channel]
            melodic.setdefault(prog, {}).setdefault(note, []).append(velocity)

    def representative(values: Sequence[int]) -> int:
        ordered = sorted(values)
        return ordered[(len(ordered) - 1) // 2]

    melodic_result = tuple(
        (
            prog,
            tuple((note, representative(vels)) for note, vels in sorted(notes.items())),
        )
        for prog, notes in sorted(melodic.items())
    )
    drum_result = tuple((note, representative(vels)) for note, vels in sorted(drums.items()))
    return MidiToneRequirements(melodic_result, drum_result)


def _select_melodic_preset(sf2: Sf2Data, program: int) -> Sf2Preset:
    matches = [p for p in sf2.presets if p.bank == 0 and p.program == program and p.zones]
    if len(matches) != 1:
        label = ", ".join(f"{p.bank}:{p.program} {p.name}" for p in matches) or "none"
        raise SaturnSblSoundfontError(
            f"SoundFont melodic preset bank 0 program {program} is not unique: {label}"
        )
    return matches[0]


def _select_drum_preset(sf2: Sf2Data) -> Sf2Preset:
    # GeneralUser GS documents Standard 1 Kit as percussion preset 0 and has
    # historically represented percussion through bank 120/128 conventions.
    named = [
        p for p in sf2.presets
        if p.program == 0 and p.zones and "standard 1" in p.name.casefold()
    ]
    if len(named) == 1:
        return named[0]
    conventional = [
        p for p in sf2.presets
        if p.program == 0 and p.zones and p.bank in (120, 128)
    ]
    if len(conventional) == 1:
        return conventional[0]
    candidates = named or conventional
    label = ", ".join(f"{p.bank}:{p.program} {p.name}" for p in candidates) or "none"
    raise SaturnSblSoundfontError(
        "SoundFont Standard 1 percussion preset could not be selected uniquely: " + label
    )


def _choose_zone(preset: Sf2Preset, note: int, velocity: int) -> Sf2PresetZone:
    exact = [
        z for z in preset.zones
        if z.key_lo <= note <= z.key_hi and z.vel_lo <= velocity <= z.vel_hi
    ]
    if not exact:
        # Some SoundFonts leave small gaps between velocity layers.  Prefer a
        # zone covering the key and nearest velocity range rather than silently
        # substituting another instrument.
        key_matches = [z for z in preset.zones if z.key_lo <= note <= z.key_hi]
        if not key_matches:
            raise SaturnSblSoundfontError(
                f"preset {preset.bank}:{preset.program} {preset.name!r} has no zone for note {note}"
            )
        exact = sorted(
            key_matches,
            key=lambda z: min(abs(velocity - z.vel_lo), abs(velocity - z.vel_hi)),
        )[:1]
    # Prefer the narrowest key/velocity zone: it is normally the most specific
    # multisample or velocity layer for the requested event.
    return min(
        exact,
        key=lambda z: ((z.key_hi - z.key_lo), (z.vel_hi - z.vel_lo), z.sample_id),
    )


def _timecents_to_ms(value: int) -> float:
    if value <= -12000:
        return 0.0
    return 1000.0 * (2.0 ** (value / 1200.0))


# Approximate SCSP envelope-time tables, matching the MAME/VGMTrans model used
# by existing Saturn tooling.  Indexing follows Sega's 5-bit AR/DR/RR fields.
_AR_MS = (
    100000.0, 100000.0, 6000.0, 4000.0, 3000.0, 2000.0, 1500.0, 1000.0,
    760.0, 500.0, 380.0, 250.0, 190.0, 130.0, 95.0, 63.0,
    47.0, 31.0, 24.0, 15.0, 12.0, 7.9, 6.0, 3.8,
    3.0, 2.0, 1.6, 1.1, 0.85, 0.53, 0.40, 0.0,
)
_DR_MS = (
    100000.0, 100000.0, 88600.0, 59100.0, 44300.0, 29600.0, 22200.0, 14800.0,
    11100.0, 7400.0, 5500.0, 3700.0, 2800.0, 1800.0, 1400.0, 920.0,
    690.0, 460.0, 340.0, 230.0, 170.0, 110.0, 85.0, 57.0,
    43.0, 28.0, 22.0, 14.0, 11.0, 7.1, 5.4, 3.6,
)


def _nearest_rate(ms: float, table: Sequence[float], *, instant: int = 31) -> int:
    if ms <= 0.0:
        return instant
    return min(range(len(table)), key=lambda i: abs(table[i] - ms))


def _attack_rate(tc: int) -> int:
    return _nearest_rate(_timecents_to_ms(tc) / 0.625, _AR_MS)


def _decay_rate(tc: int) -> int:
    return _nearest_rate(_timecents_to_ms(tc), _DR_MS)


def _decay_level(cb: int) -> int:
    if cb <= 0:
        return 0
    return min(31, max(0, int(round(cb / 32.0))))


def _total_level(cb: int) -> int:
    # 1 SCSP TL step is approximately 0.375 dB; SF2 attenuation is centibels.
    return min(255, max(0, int(round((cb * 0.1) / 0.375))))


def _resample_pcm16(
    smpl: bytes,
    start: int,
    end: int,
    source_rate: int,
    target_rate: int,
) -> list[int]:
    total_samples = len(smpl) // 2
    start = max(0, min(start, total_samples))
    end = max(start, min(end, total_samples))
    count = end - start
    if count <= 0 or source_rate <= 0 or target_rate <= 0:
        raise SaturnSblSoundfontError("SoundFont sample has invalid range/rate")
    out_count = max(1, int(round(count * target_rate / source_rate)))
    if out_count > SATURN_LAYER_MAX_SAMPLES:
        raise SaturnSblSoundfontError(
            f"resampled PCM exceeds Saturn 16-bit loop-address limit: {out_count} samples"
        )

    def sample_at(index: int) -> int:
        return struct.unpack_from("<h", smpl, (start + index) * 2)[0]

    if count == 1 or out_count == 1:
        return [sample_at(0)]
    values: list[int] = []
    scale = (count - 1) / (out_count - 1)
    for out_index in range(out_count):
        pos = out_index * scale
        left = int(pos)
        frac = pos - left
        if left + 1 < count:
            a = sample_at(left)
            b = sample_at(left + 1)
            value = int(round(a + (b - a) * frac))
        else:
            value = sample_at(left)
        values.append(max(-32768, min(32767, value)))
    return values


def _encode_pcm(values: Sequence[int], pcm8: bool) -> bytes:
    if pcm8:
        # SCSP 8-bit PCM is signed.  Round the 16-bit source instead of simply
        # truncating so small positive and negative samples remain symmetric.
        return bytes(((max(-128, min(127, int(round(v / 256.0)))) & 0xFF) for v in values))
    out = bytearray(len(values) * 2)
    for index, value in enumerate(values):
        struct.pack_into(">h", out, index * 2, value)
    return bytes(out)


def _normalize_tuning(root: int, cents: int, rate_octaves: int) -> tuple[int, int]:
    # Lower-rate PCM would play too high at SCSP native step 1.0.  Raising the
    # layer's base note makes Sega's note-base_note calculation request the
    # compensating lower playback step (12 semitones for each halving).
    base = int(root) + 12 * rate_octaves
    # Fold whole semitones of SF2 fine/coarse tuning into base-note polarity.
    semitones = int(math.trunc(cents / 100.0))
    fine = cents - semitones * 100
    base -= semitones
    while fine > 127:
        fine -= 100
        base -= 1
    while fine < -128:
        fine += 100
        base += 1
    if not (0 <= base <= 127):
        raise SaturnSblSoundfontError(
            f"tone base note {base} is outside Saturn byte range after sample-rate compensation"
        )
    return base, fine


def _materialize_layer(
    sf2: Sf2Data,
    zone: Sf2PresetZone,
    note: int,
    *,
    target_rate: int,
    pcm8: bool,
) -> tuple[SaturnToneLayer, _PcmBlock]:
    sample = sf2.samples[zone.sample_id]
    start = sample.start + zone.start_offset
    end = sample.end + zone.end_offset
    loop_start = sample.loop_start + zone.loop_start_offset
    loop_end = sample.loop_end + zone.loop_end_offset
    start = max(sample.start, min(start, sample.end - 1))
    end = max(start + 1, min(end, sample.end))
    loop_start = max(start, min(loop_start, end - 1))
    loop_end = max(loop_start + 1, min(loop_end, end))

    values = _resample_pcm16(sf2.smpl, start, end, sample.sample_rate, target_rate)
    source_count = end - start
    ratio = len(values) / source_count
    lsa = int(round((loop_start - start) * ratio))
    lea = int(round((loop_end - start) * ratio))
    lsa = max(0, min(lsa, len(values) - 1))
    lea = max(lsa + 1, min(lea, len(values)))
    loop_enabled = zone.sample_modes in (1, 3) and lea > lsa

    rate_ratio = SATURN_PCM_NATIVE_RATE // target_rate
    if target_rate * rate_ratio != SATURN_PCM_NATIVE_RATE or rate_ratio not in (1, 2, 4):
        raise SaturnSblSoundfontError("target PCM rate must be 44100, 22050 or 11025 Hz")
    rate_octaves = {1: 0, 2: 1, 4: 2}[rate_ratio]
    root = zone.root_key if zone.root_key is not None else sample.original_key
    if root > 127:
        root = 60
    cents = zone.coarse_tune * 100 + zone.fine_tune + sample.pitch_correction
    base_note, fine_tune = _normalize_tuning(root, cents, rate_octaves)

    key = (zone.sample_id, start, end, target_rate, 1 if pcm8 else 0)
    pcm = _PcmBlock(key=key, data=_encode_pcm(values, pcm8))
    layer = SaturnToneLayer(
        start_note=note,
        end_note=note,
        base_note=base_note,
        fine_tune=fine_tune,
        pcm_key=key,
        loop_start=lsa,
        loop_end=lea,
        loop_enabled=loop_enabled,
        pcm8=pcm8,
        attack_rate=_attack_rate(zone.attack_tc),
        decay_rate=_decay_rate(zone.decay_tc),
        decay_level=_decay_level(zone.sustain_cb),
        release_rate=_decay_rate(zone.release_tc),
        total_level=_total_level(zone.attenuation_cb),
    )
    return layer, pcm


def _silent_layer(*, pcm8: bool) -> SaturnToneLayer:
    return SaturnToneLayer(
        start_note=0,
        end_note=127,
        base_note=60,
        fine_tune=0,
        pcm_key=(-1, 0, 1, SATURN_PCM_NATIVE_RATE, 1 if pcm8 else 0),
        loop_start=0,
        loop_end=1,
        loop_enabled=True,
        pcm8=pcm8,
        attack_rate=31,
        decay_rate=0,
        decay_level=31,
        release_rate=31,
        total_level=255,
    )


def _pack_layer(layer: SaturnToneLayer, sa: int) -> bytes:
    if not (0 <= sa <= 0xFFFFF):
        raise SaturnSblSoundfontError(f"Saturn sample address out of 20-bit range: {sa:#x}")
    if not (0 <= layer.loop_start <= 0xFFFF and 1 <= layer.loop_end <= 0xFFFF):
        raise SaturnSblSoundfontError("Saturn loop addresses exceed 16-bit range")
    data = bytearray(32)
    data[0] = layer.start_note & 0x7F
    data[1] = layer.end_note & 0x7F
    data[2] = 0
    data[3] = ((1 if layer.loop_enabled else 0) << 5) | ((1 if layer.pcm8 else 0) << 4) | ((sa >> 16) & 0x0F)
    struct.pack_into(">H", data, 4, sa & 0xFFFF)
    struct.pack_into(">H", data, 6, layer.loop_start)
    struct.pack_into(">H", data, 8, layer.loop_end)
    data[0x0A] = (0 << 3) | ((layer.decay_rate >> 2) & 0x07)
    data[0x0B] = ((layer.decay_rate & 0x03) << 6) | (layer.attack_rate & 0x1F)
    data[0x0C] = (layer.decay_level >> 3) & 0x03
    data[0x0D] = ((layer.decay_level & 0x07) << 5) | (layer.release_rate & 0x1F)
    data[0x0E] = 0
    data[0x0F] = layer.total_level & 0xFF
    data[0x10] = 0
    data[0x11] = 0
    data[0x12] = 0
    data[0x13] = 0
    data[0x14] = 0
    data[0x15] = 0
    data[0x16] = 0
    data[0x17] = 0
    data[0x18] = 7 << 5  # maximum dry/direct send, center pan
    data[0x19] = layer.base_note & 0x7F
    data[0x1A] = layer.fine_tune & 0xFF
    data[0x1B] = 0
    data[0x1C] = 0
    data[0x1D] = 0  # velocity table 0
    data[0x1E] = 0
    data[0x1F] = 0
    return bytes(data)


def _pack_voice(voice: SaturnToneVoice, sample_offsets: Mapping[tuple[int, int, int, int, int], int]) -> bytes:
    if not voice.layers or len(voice.layers) > SATURN_MAX_LAYERS_PER_VOICE:
        raise SaturnSblSoundfontError("Saturn voice layer count must be 1..128")
    header = bytes((voice.bend_range & 0x0F, 0, (len(voice.layers) - 1) & 0x7F, voice.volume_bias & 0xFF))
    return header + b"".join(_pack_layer(layer, sample_offsets[layer.pcm_key]) for layer in voice.layers)


def _build_tone_bank(voices: Sequence[SaturnToneVoice], pcm_blocks: Sequence[_PcmBlock], *, pcm8: bool) -> bytes:
    if not voices or len(voices) > 128:
        raise SaturnSblSoundfontError("Saturn tone bank voice count must be 1..128")

    # Minimal valid tables: one mixer, one linear velocity table, one PEG and
    # one PLFO.  The generated layers disable PEG/PLFO and use MIDI CC pan.
    mixer = bytes(18)
    velocity = bytes((0x02, 0x7F, 0x00, 0x02, 0x7F, 0x00, 0x02, 0x7F, 0x00, 0x02))
    peg = bytes(10)
    plfo = bytes(4)

    header_size = 8 + len(voices) * 2
    mixer_offset = header_size
    velocity_offset = mixer_offset + len(mixer)
    peg_offset = velocity_offset + len(velocity)
    plfo_offset = peg_offset + len(peg)
    voice_start = plfo_offset + len(plfo)

    # First pass: metadata length is independent of PCM addresses.
    voice_offsets: list[int] = []
    cursor = voice_start
    for voice in voices:
        voice_offsets.append(cursor)
        cursor += 4 + 32 * len(voice.layers)
    if any(offset > 0xFFFF for offset in voice_offsets):
        raise SaturnSblSoundfontError("Saturn tone voice metadata exceeds 16-bit offset table")

    unique: dict[tuple[int, int, int, int, int], bytes] = {}
    silent_key = (-1, 0, 1, SATURN_PCM_NATIVE_RATE, 1 if pcm8 else 0)
    unique[silent_key] = b"\0" if pcm8 else b"\0\0"
    for block in pcm_blocks:
        previous = unique.get(block.key)
        if previous is not None and previous != block.data:
            raise SaturnSblSoundfontError("PCM deduplication key collision")
        unique[block.key] = block.data

    sample_offsets: dict[tuple[int, int, int, int, int], int] = {}
    pcm_data = bytearray()
    for key in sorted(unique):
        # Keep 16-bit samples even-aligned; 8-bit has no alignment requirement.
        if not pcm8 and (cursor + len(pcm_data)) & 1:
            pcm_data.append(0)
        sample_offsets[key] = cursor + len(pcm_data)
        pcm_data.extend(unique[key])

    packed_voices = [_pack_voice(voice, sample_offsets) for voice in voices]
    header = bytearray()
    for offset in (mixer_offset, velocity_offset, peg_offset, plfo_offset):
        header += struct.pack(">H", offset)
    for offset in voice_offsets:
        header += struct.pack(">H", offset)

    result = bytes(header) + mixer + velocity + peg + plfo + b"".join(packed_voices) + bytes(pcm_data)
    if len(result) > SATURN_TONE_MAX_BYTES:
        raise SaturnSblSoundfontError(
            f"single Saturn tone bank is too large: {len(result)} > {SATURN_TONE_MAX_BYTES}"
        )
    return result


def _build_strategy(
    sf2: Sf2Data,
    requirements: MidiToneRequirements,
    *,
    target_rate: int,
    pcm8: bool,
) -> SaturnSoundfontBanks:
    if requirements.programs != SPACE_SPECTRE_MELODIC_PROGRAMS:
        raise SaturnSblSoundfontError(
            f"Space Spectre melodic programs changed: {requirements.programs!r}"
        )
    if requirements.percussion_notes != SPACE_SPECTRE_DRUM_NOTES:
        raise SaturnSblSoundfontError(
            f"Space Spectre percussion notes changed: {requirements.percussion_notes!r}"
        )

    max_program = max(requirements.programs)
    silent = _silent_layer(pcm8=pcm8)
    melodic_voices = [SaturnToneVoice((silent,)) for _ in range(max_program + 1)]
    melodic_pcm: dict[tuple[int, int, int, int, int], _PcmBlock] = {}

    for program, notes in requirements.melodic_notes:
        preset = _select_melodic_preset(sf2, program)
        layers = []
        for note, velocity in notes:
            zone = _choose_zone(preset, note, velocity)
            layer, pcm = _materialize_layer(
                sf2, zone, note, target_rate=target_rate, pcm8=pcm8
            )
            layers.append(layer)
            melodic_pcm[pcm.key] = pcm
        melodic_voices[program] = SaturnToneVoice(tuple(layers))

    drum_preset = _select_drum_preset(sf2)
    drum_layers = []
    drum_pcm: dict[tuple[int, int, int, int, int], _PcmBlock] = {}
    for note, velocity in requirements.drum_notes:
        zone = _choose_zone(drum_preset, note, velocity)
        layer, pcm = _materialize_layer(
            sf2, zone, note, target_rate=target_rate, pcm8=pcm8
        )
        drum_layers.append(layer)
        drum_pcm[pcm.key] = pcm

    melodic_bytes = _build_tone_bank(
        melodic_voices, tuple(melodic_pcm.values()), pcm8=pcm8
    )
    drum_bytes = _build_tone_bank(
        (SaturnToneVoice(tuple(drum_layers)),), tuple(drum_pcm.values()), pcm8=pcm8
    )
    if len(melodic_bytes) + len(drum_bytes) > SATURN_SOUND_RAM_BANK_BUDGET:
        raise SaturnSblSoundfontError(
            "derived melodic + drum banks exceed Saturn sound-RAM budget: "
            f"{len(melodic_bytes) + len(drum_bytes)} > {SATURN_SOUND_RAM_BANK_BUDGET}"
        )
    return SaturnSoundfontBanks(
        melodic_bytes=melodic_bytes,
        drum_bytes=drum_bytes,
        source_sha256="",
        source_blob_sha1="",
        sample_rate=target_rate,
        pcm8=pcm8,
        melodic_programs=requirements.programs,
        drum_notes=requirements.percussion_notes,
    )


def build_compact_saturn_gm_banks(
    soundfont: Path | str,
    requirements: MidiToneRequirements,
) -> SaturnSoundfontBanks:
    path = Path(soundfont).expanduser().resolve(strict=True)
    payload = path.read_bytes()
    sf2 = parse_soundfont_bytes(payload)
    source_sha = sha256(payload).hexdigest()
    blob_sha = _git_blob_sha1_bytes(payload)

    failures: list[str] = []
    # Prefer bandwidth first, then bit depth.  The source instruments/notes do
    # not change between strategies; only PCM representation is compacted.
    for target_rate, pcm8 in ((22050, False), (22050, True), (11025, False), (11025, True)):
        try:
            result = _build_strategy(
                sf2, requirements, target_rate=target_rate, pcm8=pcm8
            )
            return SaturnSoundfontBanks(
                melodic_bytes=result.melodic_bytes,
                drum_bytes=result.drum_bytes,
                source_sha256=source_sha,
                source_blob_sha1=blob_sha,
                sample_rate=target_rate,
                pcm8=pcm8,
                melodic_programs=result.melodic_programs,
                drum_notes=result.drum_notes,
            )
        except SaturnSblSoundfontError as exc:
            failures.append(f"{target_rate}Hz/{8 if pcm8 else 16}bit: {exc}")
    raise SaturnSblSoundfontError(
        "Space Spectre SoundFont cannot fit Saturn sound RAM with safe compacting:\n  "
        + "\n  ".join(failures)
    )


def _git_blob_sha1_bytes(data: bytes) -> str:
    digest = sha1()
    digest.update(f"blob {len(data)}\0".encode("ascii"))
    digest.update(data)
    return digest.hexdigest()


def _git_blob_sha1_file(path: Path) -> str:
    size = path.stat().st_size
    digest = sha1()
    digest.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_soundfont_cache() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        root = Path(local) / "SRK" / "soundfonts"
    else:
        root = Path.home() / ".cache" / "srk" / "soundfonts"
    return root / f"GeneralUser-GS-{GENERALUSER_COMMIT[:12]}.sf2"


def ensure_generaluser_soundfont(path: Path | str | None = None) -> Path:
    destination = default_soundfont_cache() if path is None else Path(path).expanduser().resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if destination.stat().st_size != GENERALUSER_BYTES:
            raise SaturnSblSoundfontError(
                f"cached GeneralUser GS size mismatch: {destination}"
            )
        if _git_blob_sha1_file(destination) != GENERALUSER_BLOB_SHA1:
            raise SaturnSblSoundfontError(
                f"cached GeneralUser GS Git blob hash mismatch: {destination}"
            )
        return destination

    temp = destination.with_name(destination.name + ".part")
    if temp.exists():
        temp.unlink()
    request = urllib.request.Request(
        GENERALUSER_URL,
        headers={"User-Agent": "SRK-Saturn-SoundFont/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as handle:
            shutil.copyfileobj(response, handle, length=1024 * 1024)
    except Exception as exc:
        temp.unlink(missing_ok=True)
        raise SaturnSblSoundfontError(
            "could not download pinned GeneralUser GS SoundFont; pass --soundfont with a local .sf2 instead: "
            f"{exc}"
        ) from exc
    if temp.stat().st_size != GENERALUSER_BYTES or _git_blob_sha1_file(temp) != GENERALUSER_BLOB_SHA1:
        temp.unlink(missing_ok=True)
        raise SaturnSblSoundfontError("downloaded GeneralUser GS failed pinned size/blob verification")
    temp.replace(destination)
    return destination


def _derived_cache_root(soundfont: Path, source_sha: str) -> Path:
    return soundfont.parent / "derived" / source_sha[:16] / "space-spectre"


def ensure_space_spectre_tone_banks(
    soundfont: Path | str,
    requirements: MidiToneRequirements,
) -> SaturnSoundfontBankFiles:
    source = Path(soundfont).expanduser().resolve(strict=True)
    source_sha = _sha256_file(source)
    root = _derived_cache_root(source, source_sha)
    melodic = root / "SRKGM.BIN"
    drum = root / "SRKDRUM.BIN"
    report = root / "SRKGM_SOURCE.txt"

    # Rebuild is cheap compared with hardware iteration and protects against a
    # stale cache with incomplete older conversion logic.
    banks = build_compact_saturn_gm_banks(source, requirements)
    root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=".space-spectre-", dir=str(root.parent)))
    try:
        m = temp_root / melodic.name
        d = temp_root / drum.name
        r = temp_root / report.name
        m.write_bytes(banks.melodic_bytes)
        d.write_bytes(banks.drum_bytes)
        r.write_text(
            "SRK Space Spectre compact Saturn tone banks\n"
            f"source={source}\n"
            f"source_sha256={banks.source_sha256}\n"
            f"source_git_blob_sha1={banks.source_blob_sha1}\n"
            f"generaluser_commit={GENERALUSER_COMMIT}\n"
            f"sample_rate={banks.sample_rate}\n"
            f"pcm_bits={8 if banks.pcm8 else 16}\n"
            f"melodic_programs={','.join(map(str, banks.melodic_programs))}\n"
            f"drum_notes={','.join(map(str, banks.drum_notes))}\n"
            f"melodic_bytes={len(banks.melodic_bytes)}\n"
            f"drum_bytes={len(banks.drum_bytes)}\n",
            encoding="utf-8",
            newline="\n",
        )
        if root.exists():
            shutil.rmtree(root)
        temp_root.replace(root)
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    return SaturnSoundfontBankFiles(
        melodic_path=melodic,
        drum_path=drum,
        report_path=report,
        source_path=source,
        melodic_sha256=_sha256_file(melodic),
        drum_sha256=_sha256_file(drum),
        source_sha256=source_sha,
        sample_rate=banks.sample_rate,
        pcm8=banks.pcm8,
        combined_bytes=len(banks.melodic_bytes) + len(banks.drum_bytes),
    )
