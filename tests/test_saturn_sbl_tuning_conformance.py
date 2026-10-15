from __future__ import annotations

from pathlib import Path
import struct

from rikai_kotoba.hardware.saturn.sbl_tuning_conformance import (
    audit_fine_tune_bank,
    audit_space_spectre_fine_tuning,
)
from rikai_kotoba.tools.saturn_sbl_tuning_conformance import build_parser


def _tone_bank(*fine_values: int) -> bytes:
    assert fine_values
    mixer = 10
    velocity = mixer + 18
    peg = velocity + 10
    plfo = peg + 10
    voice_start = plfo + 4
    pcm_start = voice_start + 4 + 0x20 * len(fine_values)
    payload = bytearray(pcm_start + 2)
    struct.pack_into(">HHHHH", payload, 0, mixer, velocity, peg, plfo, voice_start)
    payload[voice_start] = 2
    payload[voice_start + 2] = len(fine_values) - 1
    for index, fine in enumerate(fine_values):
        off = voice_start + 4 + index * 0x20
        payload[off] = 60 + index
        payload[off + 1] = 60 + index
        payload[off + 2 : off + 6] = pcm_start.to_bytes(4, "big")
        payload[off + 8 : off + 10] = (1).to_bytes(2, "big")
        payload[off + 0x18] = 7 << 5
        payload[off + 0x19] = 60
        struct.pack_into("b", payload, off + 0x1A, fine)
        payload[off + 0x1D] = 0
    return bytes(payload)


def test_fine_tune_audit_accepts_sega_boundaries(tmp_path):
    tone = tmp_path / "tone.bin"
    tone.write_bytes(_tone_bank(-63, 0, 63))

    report = audit_fine_tune_bank(tone)

    assert report.conforming
    assert report.minimum == -63
    assert report.maximum == 63
    assert report.layer_count == 3
    assert report.violations == ()


def test_fine_tune_audit_reports_values_outside_sega_range(tmp_path):
    tone = tmp_path / "tone.bin"
    tone.write_bytes(_tone_bank(-64, 64))

    report = audit_fine_tune_bank(tone)

    assert not report.conforming
    assert [item.fine_tune for item in report.violations] == [-64, 64]


def test_project_audit_can_compare_generated_banks_with_reference(tmp_path):
    project = tmp_path / "project"
    cd = project / "cd"
    cd.mkdir(parents=True)
    (cd / "SRKGM.BIN").write_bytes(_tone_bank(64))
    (cd / "SRKDRUM.BIN").write_bytes(_tone_bank(-63))
    reference = tmp_path / "BOOTTONE.BIN"
    reference.write_bytes(_tone_bank(0))

    report = audit_space_spectre_fine_tuning(
        project,
        reference_tone_bank=reference,
    )

    assert not report.conforming
    assert not report.melodic.conforming
    assert report.drums.conforming
    assert report.reference is not None
    assert report.reference.conforming


def test_tuning_conformance_cli_has_only_read_only_inputs():
    args = build_parser().parse_args(
        ["--project", "candidate", "--reference", "BOOTTONE.BIN"]
    )
    assert args.project == Path("candidate")
    assert args.reference == Path("BOOTTONE.BIN")
