from pathlib import Path
import struct

from rikai_kotoba.hardware.saturn.sbl_fidelity_audit import (
    SaturnDrumNoteAudit,
    audit_space_spectre_m6,
    parse_scspbin_tone_bank,
)
from rikai_kotoba.hardware.saturn.sbl_space_spectre_sequence import (
    EXPECTED_BANK_SHA256,
    build_space_spectre_native_sequence,
)
from rikai_kotoba.tools.saturn_sbl_space_spectre_fidelity_audit import (
    _drum_note_text,
    build_parser,
)


def _synthetic_drum_bank() -> bytes:
    # SCSPBIN header: MIX points immediately after the one-entry voice table.
    payload = bytearray(512)
    mixer = 10
    velocity = 20
    peg = 30
    plfo = 40
    struct.pack_into(">HHHH", payload, 0, mixer, velocity, peg, plfo)
    voice_offset = 64
    struct.pack_into(">H", payload, 8, voice_offset)
    # bend, portamento, layer_count-1, volume bias
    payload[voice_offset : voice_offset + 4] = bytes((2, 0, 3, 0))
    payload[velocity : velocity + 10] = bytes.fromhex("08 00 7f 0c 7f 7f 08 7f 7f 08")

    for index, (note, sample_address) in enumerate(((35, 300), (40, 340), (42, 380), (51, 420))):
        off = voice_offset + 4 + index * 0x20
        payload[off] = note
        payload[off + 1] = note
        payload[off + 2 : off + 6] = sample_address.to_bytes(4, "big")
        payload[off + 6 : off + 8] = (0).to_bytes(2, "big")
        payload[off + 8 : off + 10] = (16).to_bytes(2, "big")
        payload[off + 0x0F] = 0
        payload[off + 0x18] = 7
        payload[off + 0x19] = note
        payload[off + 0x1A] = 0
        payload[off + 0x1D] = 0
    return bytes(payload)


def test_scspbin_audit_parses_sega_driver_offsets(tmp_path):
    bank_path = tmp_path / "drums.bin"
    bank_path.write_bytes(_synthetic_drum_bank())

    bank = parse_scspbin_tone_bank(bank_path)

    assert bank.voice_count == 1
    assert bank.mixer_offset == 10
    assert bank.velocity_offset == 20
    assert bank.velocity_table0 == bytes.fromhex("08 00 7f 0c 7f 7f 08 7f 7f 08")
    voice = bank.voices[0]
    assert voice.layer_count == 4
    assert [layer.start_note for layer in voice.layers] == [35, 40, 42, 51]
    assert [layer.sample_address for layer in voice.layers] == [300, 340, 380, 420]
    assert [layer.base_note for layer in voice.layers] == [35, 40, 42, 51]


def test_locked_space_spectre_m6_is_audited_event_by_event(tmp_path):
    sequence_dir = tmp_path / "sequence"
    built = build_space_spectre_native_sequence(sequence_dir)
    assert built.bank_sha256 == EXPECTED_BANK_SHA256

    report = audit_space_spectre_m6(sequence_dir)

    assert report.exact is True
    assert report.sequence_sha256 == EXPECTED_BANK_SHA256
    assert report.source_event_count == report.decoded_event_count == 4779
    assert report.end_tick == 9478
    assert report.tempo_event_count == 1


def test_fidelity_audit_cli_is_read_only_input_only():
    args = build_parser().parse_args(
        [
            "--project",
            "GATE3E",
            "--sequence",
            "GATE3B",
        ]
    )
    assert args.project == Path("GATE3E")
    assert args.sequence == Path("GATE3B")


def test_fidelity_audit_renders_drum_note_objects_by_note_number():
    drum_note = SaturnDrumNoteAudit(note=35, layers=())
    assert _drum_note_text(drum_note) == "Note  35: 0 matching layer(s)"
