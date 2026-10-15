from __future__ import annotations

from pathlib import Path
import struct

import pytest

from rikai_kotoba.hardware.saturn.midi_68k_r26_double_impact import (
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from rikai_kotoba.hardware.saturn.sbl_soundfont_gm import (
    GENERALUSER_BLOB_SHA1,
    GENERALUSER_BYTES,
    GENERALUSER_COMMIT,
    SATURN_SOUND_RAM_BANK_BUDGET,
    MidiToneRequirements,
    SaturnSblSoundfontError,
    SPACE_SPECTRE_DRUM_NOTES,
    SPACE_SPECTRE_MELODIC_PROGRAMS,
    build_compact_saturn_gm_banks,
    derive_midi_tone_requirements,
    parse_soundfont_bytes,
)


_ROOT = Path(__file__).resolve().parents[1]


def _chunk(chunk_id: bytes, payload: bytes) -> bytes:
    value = chunk_id + struct.pack("<I", len(payload)) + payload
    return value + (b"\0" if len(payload) & 1 else b"")


def _list_chunk(kind: bytes, chunks: list[bytes]) -> bytes:
    return _chunk(b"LIST", kind + b"".join(chunks))


def _name20(value: str) -> bytes:
    return value.encode("ascii")[:20].ljust(20, b"\0")


def _tiny_soundfont() -> bytes:
    # One looped 22.05-kHz source sample is intentionally shared by every
    # preset.  This fixture tests the SF2 graph/TON layout without embedding a
    # third-party SoundFont in the repository.
    values = [max(-32768, min(32767, (index - 128) * 200)) for index in range(256)]
    smpl = b"".join(struct.pack("<h", value) for value in values)
    shdr = (
        _name20("tone")
        + struct.pack("<IIIII", 0, 256, 32, 224, 22050)
        + bytes((60,))
        + struct.pack("<bHH", 0, 0, 1)
    )
    shdr += (
        _name20("EOS")
        + struct.pack("<IIIII", 256, 256, 256, 256, 22050)
        + bytes((60,))
        + struct.pack("<bHH", 0, 0, 1)
    )

    programs = SPACE_SPECTRE_MELODIC_PROGRAMS
    inst = bytearray()
    ibag = bytearray()
    igen = bytearray()
    for index in range(5):
        inst += _name20(f"inst{index}") + struct.pack("<H", index)
        ibag += struct.pack("<HH", index, 0)
        igen += struct.pack("<HH", 53, 0)  # sampleID=0
    inst += _name20("EOI") + struct.pack("<H", 5)
    ibag += struct.pack("<HH", 5, 0)

    phdr = bytearray()
    pbag = bytearray()
    pgen = bytearray()
    for index, program in enumerate(programs):
        phdr += _name20(f"gm{program}") + struct.pack(
            "<HHHIII", program, 0, index, 0, 0, 0
        )
        pbag += struct.pack("<HH", index, 0)
        pgen += struct.pack("<HH", 41, index)  # instrument
    phdr += _name20("Standard 1 Kit") + struct.pack(
        "<HHHIII", 0, 120, 4, 0, 0, 0
    )
    pbag += struct.pack("<HH", 4, 0)
    pgen += struct.pack("<HH", 41, 4)
    phdr += _name20("EOP") + struct.pack("<HHHIII", 0, 0, 5, 0, 0, 0)
    pbag += struct.pack("<HH", 5, 0)

    sdta = _list_chunk(b"sdta", [_chunk(b"smpl", smpl)])
    pdta = _list_chunk(
        b"pdta",
        [
            _chunk(b"phdr", bytes(phdr)),
            _chunk(b"pbag", bytes(pbag)),
            _chunk(b"pmod", b""),
            _chunk(b"pgen", bytes(pgen)),
            _chunk(b"inst", bytes(inst)),
            _chunk(b"ibag", bytes(ibag)),
            _chunk(b"imod", b""),
            _chunk(b"igen", bytes(igen)),
            _chunk(b"shdr", shdr),
        ],
    )
    body = b"sfbk" + _list_chunk(b"INFO", []) + sdta + pdta
    return b"RIFF" + struct.pack("<I", len(body)) + body


def _voice_count(tone: bytes) -> int:
    return (struct.unpack_from(">H", tone, 0)[0] - 8) // 2


def test_space_spectre_requirements_lock_real_gm_programs_and_drum_notes():
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(_ROOT)
    requirements = derive_midi_tone_requirements(profile.program)

    assert requirements.programs == (30, 39, 73, 120)
    assert requirements.percussion_notes == (35, 40, 42, 51)
    assert all(notes for _, notes in requirements.melodic_notes)


def test_tiny_sf2_resolves_sparse_gm_presets_and_standard_drum_kit():
    sf2 = parse_soundfont_bytes(_tiny_soundfont())
    assert [(p.bank, p.program) for p in sf2.presets] == [
        (0, 30),
        (0, 39),
        (0, 73),
        (0, 120),
        (120, 0),
    ]
    assert all(len(p.zones) == 1 for p in sf2.presets)


def test_compact_tone_bank_preserves_program_120_without_embedding_121_samples(tmp_path):
    soundfont = tmp_path / "tiny.sf2"
    soundfont.write_bytes(_tiny_soundfont())
    requirements = MidiToneRequirements(
        melodic_notes=(
            (30, ((60, 100),)),
            (39, ((48, 100),)),
            (73, ((72, 100),)),
            (120, ((63, 100),)),
        ),
        drum_notes=((35, 100), (40, 100), (42, 100), (51, 100)),
    )

    result = build_compact_saturn_gm_banks(soundfont, requirements)

    assert _voice_count(result.melodic_bytes) == 121
    assert _voice_count(result.drum_bytes) == 1
    assert result.melodic_programs == SPACE_SPECTRE_MELODIC_PROGRAMS
    assert result.drum_notes == SPACE_SPECTRE_DRUM_NOTES
    assert result.combined_bytes <= SATURN_SOUND_RAM_BANK_BUDGET

    voice_120 = struct.unpack_from(">H", result.melodic_bytes, 8 + 120 * 2)[0]
    assert result.melodic_bytes[voice_120 + 2] == 0  # exactly one layer
    assert result.melodic_bytes[voice_120 + 4] == 63
    assert result.melodic_bytes[voice_120 + 5] == 63


def test_converter_refuses_changed_space_spectre_program_contract(tmp_path):
    soundfont = tmp_path / "tiny.sf2"
    soundfont.write_bytes(_tiny_soundfont())
    requirements = MidiToneRequirements(
        melodic_notes=((30, ((60, 100),)),),
        drum_notes=((35, 100), (40, 100), (42, 100), (51, 100)),
    )
    with pytest.raises(SaturnSblSoundfontError, match="melodic programs changed"):
        build_compact_saturn_gm_banks(soundfont, requirements)


def test_pinned_generaluser_identity_is_explicit_and_not_a_floating_download():
    assert len(GENERALUSER_COMMIT) == 40
    assert len(GENERALUSER_BLOB_SHA1) == 40
    assert GENERALUSER_BYTES == 32_319_396
