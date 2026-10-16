from __future__ import annotations

from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn import sbl_native_sequence_fidelity_hardware_gate as gate
from rikai_kotoba.tools import saturn_sbl_space_spectre_gate3f_hardware as cli


def test_gate3f_media_locks_match_eridu_pre_media_result() -> None:
    assert gate.EXPECTED_MANIFEST_SHA256 == "e26309b105082e6cec23a7faa445113b4d2aa034931190fde8ba8be9d5f92303"
    assert gate.EXPECTED_BUILD_REPORT_SHA256 == "6e795aeba5ea5e0a148669f5671d3ae35b6fe02a98717db70370ab1a602e6174"
    assert gate.EXPECTED_BIN_BYTES == 752640
    assert gate.EXPECTED_BIN_SHA256 == "006c037998696d584a3053aa60f6d3fb602b4aad1b36e2552f44aefb008d5130"
    assert gate.EXPECTED_CUE_BYTES == 81
    assert gate.EXPECTED_CUE_SHA256 == "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"


def test_gate3f_uses_fresh_distinct_destination_and_token() -> None:
    assert gate.DEFAULT_DESTINATION_NAME == "SRK-Space-Spectre-SBL-NATIVE-GATE3F"
    assert gate.CONFIRMATION_TOKEN == "DEPLOY-SBL-NATIVE-SPACE-SPECTRE-GATE3F"
    assert "GATE3D" not in gate.DEFAULT_DESTINATION_NAME
    assert "GATE3E" not in gate.DEFAULT_DESTINATION_NAME


def test_apply_requires_exact_gate3f_confirmation_before_card_work(tmp_path: Path) -> None:
    with pytest.raises(gate.SaturnSblNativeSequenceFidelityHardwareGateError, match="confirmation token"):
        gate.run_gate3f_hardware_gate(
            tmp_path / "project",
            tmp_path / "card",
            tmp_path / "guard.json",
            apply=True,
            confirmation="WRONG",
        )


def test_allowed_paths_are_limited_to_new_directory_and_two_media_files(tmp_path: Path) -> None:
    class Plan:
        card_root = tmp_path / "card"
        destination_directory = card_root / "SAROO" / "ISO" / "TEST" / "fresh"
        source_bin = tmp_path / "SRK-Diagnostics.bin"
        source_cue = tmp_path / "SRK-Diagnostics.cue"

    assert gate._allowed_paths(Plan()) == (
        "SAROO/ISO/TEST/fresh",
        "SAROO/ISO/TEST/fresh/SRK-Diagnostics.bin",
        "SAROO/ISO/TEST/fresh/SRK-Diagnostics.cue",
    )


def test_cli_defaults_to_read_only_and_fresh_gate3f_name() -> None:
    args = cli.build_parser().parse_args(
        [
            "--project", "candidate",
            "--workspace", "workspace",
            "--card-root", "D:/",
        ]
    )
    assert args.apply is False
    assert args.confirm == ""
    assert args.category == "TEST"
    assert args.name == gate.DEFAULT_DESTINATION_NAME


def test_cli_apply_surface_requires_explicit_confirmation_fields() -> None:
    parser = cli.build_parser()
    actions = {action.dest for action in parser._actions}
    assert {"project", "workspace", "card_root", "category", "name", "guard_manifest", "apply", "confirm"} <= actions
    assert "destination" not in actions
    assert "output" not in actions
