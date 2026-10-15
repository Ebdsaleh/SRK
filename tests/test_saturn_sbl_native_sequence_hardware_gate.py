import pytest

from rikai_kotoba.hardware.saturn.sbl_native_sequence_hardware_gate import (
    CONFIRMATION_TOKEN,
    DEFAULT_DESTINATION_NAME,
    EXPECTED_AREA_MAP_BYTES,
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_DRUM_BANK_SHA256,
    EXPECTED_DRUM_START,
    EXPECTED_MELODIC_BANK_SHA256,
    EXPECTED_MELODIC_START,
    EXPECTED_NOTE_COUNT,
    EXPECTED_SEQUENCE_BYTES,
    EXPECTED_SEQUENCE_SHA256,
    EXPECTED_SEQUENCE_START,
    SaturnSblNativeSequenceHardwareGateError,
    run_saturn_sbl_native_sequence_hardware_gate,
)
from rikai_kotoba.tools.saturn_sbl_space_spectre_native_hardware import build_parser


def test_native_hardware_gate_locks_eridu_gate3d_contract():
    assert EXPECTED_NOTE_COUNT == 4381
    assert EXPECTED_SEQUENCE_BYTES == 23127
    assert EXPECTED_SEQUENCE_SHA256 == "56eef2dda77221e861b6e34724a493597d0e8e4b9523a2b48b2af18adac49967"
    assert EXPECTED_MELODIC_BANK_SHA256 == "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
    assert EXPECTED_DRUM_BANK_SHA256 == "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"
    assert EXPECTED_AREA_MAP_BYTES == 26
    assert EXPECTED_AREA_MAP_SHA256 == "b0c223db1907af25af5ffc237574ed11390ea4ee28a283810ae256077b479e3b"
    assert EXPECTED_MELODIC_START == 0x0B000
    assert EXPECTED_DRUM_START == 0x5966C
    assert EXPECTED_SEQUENCE_START == 0x74B0C
    assert DEFAULT_DESTINATION_NAME == "SRK-Space-Spectre-SBL-NATIVE-GATE3D"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-NATIVE-SPACE-SPECTRE"


def test_native_apply_requires_native_confirmation_before_any_io(tmp_path):
    with pytest.raises(SaturnSblNativeSequenceHardwareGateError, match="confirmation token"):
        run_saturn_sbl_native_sequence_hardware_gate(
            tmp_path / "candidate",
            tmp_path / "card",
            tmp_path / "guard.json",
            apply=True,
            confirmation="DEPLOY-SBL-GM-SPACE-SPECTRE",
        )


def test_native_hardware_cli_exposes_fresh_guarded_apply_contract():
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
