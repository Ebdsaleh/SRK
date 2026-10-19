from __future__ import annotations

from pathlib import Path
import struct

import pytest

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_tl_attribution import (
    _parse_family,
    audit_sddrv210_tl_attribution,
)
from rikai_kotoba.tools.saturn_sddrv210_tl_attribution import build_parser


FULL_LEVEL_TABLE = bytes.fromhex("08 00 7F 0C 7F 7F 08 7F 7F 08")


def _family_payload(tls: tuple[int, ...]) -> bytes:
    assert len(tls) == 8
    header_size = 8 + 16
    mixer = bytes(18)
    velocity = FULL_LEVEL_TABLE
    peg = bytes(10)
    plfo = bytes(4)
    mixer_offset = header_size
    velocity_offset = mixer_offset + len(mixer)
    peg_offset = velocity_offset + len(velocity)
    plfo_offset = peg_offset + len(peg)
    voice_start = plfo_offset + len(plfo)

    offsets = tuple(voice_start + index * 36 for index in range(8))
    header = bytearray(struct.pack(">HHHH", mixer_offset, velocity_offset, peg_offset, plfo_offset))
    for offset in offsets:
        header += struct.pack(">H", offset)

    voices = bytearray()
    for local, tl in enumerate(tls):
        voices += bytes((2, 0, 0, 0))
        layer = bytearray(32)
        layer[0] = 60
        layer[1] = 60
        layer[3] = 0x20
        struct.pack_into(">H", layer, 4, 0x2000 + local * 0x20)
        struct.pack_into(">H", layer, 6, 0)
        struct.pack_into(">H", layer, 8, 100)
        layer[0x0F] = tl
        layer[0x18] = 0xE0
        layer[0x1D] = 0
        voices += layer
    return bytes(header) + mixer + velocity + peg + plfo + bytes(voices)


def test_tl_attribution_decodes_authored_layer_and_velocity_state():
    rows = _parse_family(_family_payload((0xFF, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26)), 0)

    assert len(rows) == 8
    first = rows[0]
    assert first.program == 0
    assert first.family == 0
    assert first.local_voice == 0
    assert first.authored_tl == 0xFF
    assert first.authored_tl_db == pytest.approx(95.7)
    assert first.direct_send_pan == 0xE0
    assert first.velocity_table_index == 0
    assert first.velocity_level == 127
    assert first.sample_address == 0x2000
    assert first.loop_enabled is True
    assert first.pcm8 is False


def test_tl_attribution_covers_all_128_programs_and_finds_authored_ff(tmp_path: Path):
    project = tmp_path / "R4"
    cd = project / "cd"
    cd.mkdir(parents=True)
    for family in range(16):
        tls = [0x20] * 8
        if family == 0:
            tls[0] = 0xFF
        if family == 2:
            tls[0] = 0xFF  # program 16
        (cd / f"GMC{family:02d}.BIN").write_bytes(_family_payload(tuple(tls)))

    report = audit_sddrv210_tl_attribution(project)

    assert len(report.rows) == 128
    assert report.rows[16].program == 16
    assert report.authored_ff_programs == (0, 16)
    assert report.authored_tl_min == 0x20
    assert report.authored_tl_max == 0xFF


def test_tl_attribution_cli_is_strictly_off_card():
    parser = build_parser()
    args = parser.parse_args(["--project", "R4"])
    assert str(args.project) == "R4"
    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--project" in options
    for forbidden in (
        "--card-root",
        "--apply",
        "--confirm",
        "--output",
        "--saturn-root",
        "--deploy",
    ):
        assert forbidden not in options


def test_tl_attribution_source_preserves_r4_hardware_boundary():
    root = Path(__file__).resolve().parents[1]
    source = (
        root
        / "src"
        / "rikai_kotoba"
        / "tools"
        / "saturn_sddrv210_tl_attribution.py"
    ).read_text(encoding="utf-8")
    assert "R4 hardware fact   : KEYED TL=0xFF / MX=0xE000 observed" in source
    assert "TL=FF IS PRESENT IN AUTHORED SCSPBIN" in source
    assert "SDDRV VELOCITY/VOLUME -> LIVE SCSP TL" in source
    assert "SAROO writes       : NONE" in source
