from __future__ import annotations

import struct

import pytest

from rikai_kotoba.hardware.saturn.sbl_gm_hardware_gate import (
    CONFIRMATION_TOKEN,
    DEFAULT_DESTINATION_NAME,
    EXPECTED_DRUM_BANK_SHA256,
    EXPECTED_MELODIC_BANK_SHA256,
    EXPECTED_PERCUSSION_NOTES,
    EXPECTED_RECORD_COUNT,
    SEGA_BOOTTONE_VELOCITY_TABLE0,
    SaturnSblGmHardwareGateError,
    _validate_tone_bank,
    run_saturn_sbl_gm_hardware_gate,
)
from rikai_kotoba.tools.saturn_sbl_space_spectre_hardware import build_parser


def _tiny_tone(voices: int) -> bytes:
    mix = 8 + voices * 2
    velocity = max(20, mix + 2)
    peg = velocity + 12
    plfo = peg + 10
    payload = bytearray(plfo + 8)
    struct.pack_into(">HHHH", payload, 0, mix, velocity, peg, plfo)
    payload[velocity : velocity + len(SEGA_BOOTTONE_VELOCITY_TABLE0)] = (
        SEGA_BOOTTONE_VELOCITY_TABLE0
    )
    return bytes(payload)


def test_hardware_gate_locks_successful_space_spectre_contract():
    assert EXPECTED_RECORD_COUNT == 9154
    assert EXPECTED_PERCUSSION_NOTES == (35, 40, 42, 51)
    assert len(EXPECTED_MELODIC_BANK_SHA256) == 64
    assert len(EXPECTED_DRUM_BANK_SHA256) == 64
    assert DEFAULT_DESTINATION_NAME == "SRK-Space-Spectre-SBL-GM-GATE2"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-GM-SPACE-SPECTRE"


def test_hardware_gate_accepts_sega_velocity_curve_and_voice_count():
    _validate_tone_bank(_tiny_tone(1), expected_voices=1, label="drum")
    _validate_tone_bank(_tiny_tone(121), expected_voices=121, label="melodic")


def test_hardware_gate_refuses_wrong_voice_count():
    with pytest.raises(SaturnSblGmHardwareGateError, match="voice count"):
        _validate_tone_bank(_tiny_tone(1), expected_voices=121, label="melodic")


def test_hardware_gate_refuses_changed_velocity_curve():
    payload = bytearray(_tiny_tone(1))
    velocity = struct.unpack_from(">H", payload, 2)[0]
    payload[velocity] ^= 0x01
    with pytest.raises(SaturnSblGmHardwareGateError, match="velocity curve"):
        _validate_tone_bank(bytes(payload), expected_voices=1, label="drum")


def test_apply_requires_space_spectre_specific_confirmation_before_any_io(tmp_path):
    with pytest.raises(SaturnSblGmHardwareGateError, match="confirmation token"):
        run_saturn_sbl_gm_hardware_gate(
            tmp_path / "candidate",
            tmp_path / "card",
            tmp_path / "guard.json",
            apply=True,
            confirmation="DEPLOY-SATURN-IMAGE",
        )


def test_hardware_cli_exposes_guarded_apply_contract():
    args = build_parser().parse_args(
        [
            "--project",
            "candidate",
            "--workspace",
            "workspace",
            "--card-root",
            "D:/",
            "--apply",
            "--confirm",
            CONFIRMATION_TOKEN,
        ]
    )
    assert args.apply is True
    assert args.confirm == CONFIRMATION_TOKEN
    assert args.category == "TEST"
    assert args.name == DEFAULT_DESTINATION_NAME
