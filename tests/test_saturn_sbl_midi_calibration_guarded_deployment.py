from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch

import pytest

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment import (
    CATEGORY,
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationGuardedDeploymentError,
    _allowed_paths,
    apply_sbl_midi_calibration_guarded_deployment,
    prepare_sbl_midi_calibration_guarded_deployment,
)


def _pre_media():
    return SimpleNamespace(
        manifest_sha256=EXPECTED_MANIFEST_SHA256,
        build_report_sha256=EXPECTED_BUILD_REPORT_SHA256,
        bin_sha256=EXPECTED_BIN_SHA256,
        cue_sha256=EXPECTED_CUE_SHA256,
        runtime_contract_exact=True,
        raw_scsp_callbacks_disabled=True,
        deployable_verified_against_iso=True,
    )


def _plan(card: Path):
    destination = card / "SAROO" / "ISO" / CATEGORY / DESTINATION_NAME
    return SimpleNamespace(
        destination_directory=destination,
        source_bin=Path("SRK-Diagnostics.bin"),
        source_cue=Path("SRK-Diagnostics.cue"),
        bin_sha256=EXPECTED_BIN_SHA256,
        cue_sha256=EXPECTED_CUE_SHA256,
    )


def _deployment(card: Path):
    destination = card / "SAROO" / "ISO" / CATEGORY / DESTINATION_NAME
    return SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=destination / "SRK-Diagnostics.bin",
        destination_cue=destination / "SRK-Diagnostics.cue",
        bin_sha256=EXPECTED_BIN_SHA256,
        cue_sha256=EXPECTED_CUE_SHA256,
    )


def test_calibration_guard_locks_exact_gate3_evidence_and_destination() -> None:
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-GATE3"
    assert CATEGORY == "TEST"
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-GATE3"
    assert EXPECTED_MANIFEST_SHA256 == (
        "cdbb9896eafd57ed4e00793be61a7f3b2331644e6a084b26dcb8ccbae139376e"
    )
    assert EXPECTED_BUILD_REPORT_SHA256 == (
        "68ed42a9aac1cae2944d549e9a4624e1a5e647eb76820190dc4ab0cde672b2dc"
    )
    assert EXPECTED_BIN_SHA256 == (
        "3c021003718cb1146c5d2b3ccef0fe98018e07ac54023ef66406c2dbf4d7e1fc"
    )
    assert EXPECTED_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )


def test_allowed_paths_are_only_new_directory_and_bin_cue() -> None:
    destination = Path(
        "C:/CARD/SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3"
    )
    deployment = SimpleNamespace(
        plan=SimpleNamespace(destination_directory=destination),
        destination_bin=destination / "SRK-Diagnostics.bin",
        destination_cue=destination / "SRK-Diagnostics.cue",
    )
    assert set(_allowed_paths(deployment)) == {
        "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3",
        "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3/SRK-Diagnostics.bin",
        "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3/SRK-Diagnostics.cue",
    }


def test_prepare_refuses_guard_manifest_on_card_before_audit() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        card = Path(temp_dir) / "CARD"
        card.mkdir()
        with pytest.raises(
            SaturnSblMidiCalibrationGuardedDeploymentError,
            match="outside",
        ):
            prepare_sbl_midi_calibration_guarded_deployment(
                Path(temp_dir) / "candidate",
                card,
                card / "guard.json",
            )


def test_prepare_revalidates_fixed_gate3_plan_and_writes_only_off_card_manifest() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        card = root / "CARD"
        card.mkdir()
        guard = root / "guard.json"
        inventory = SimpleNamespace(
            card_root=card,
            manifest_path=guard,
            manifest_sha256="a" * 64,
        )
        verification = SimpleNamespace(valid=True, differences=())
        with (
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment._audit",
                return_value=_pre_media(),
            ),
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.plan_saroo_standalone_image_deployment",
                return_value=_plan(card),
            ) as plan,
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.create_saroo_card_inventory",
                return_value=inventory,
            ) as create_inventory,
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.verify_saroo_card_inventory",
                return_value=verification,
            ),
        ):
            result = prepare_sbl_midi_calibration_guarded_deployment(
                root / "candidate", card, guard
            )
        assert result.exact_verification.valid
        plan.assert_called_once_with(
            card.resolve(),
            root / "candidate",
            destination_name=DESTINATION_NAME,
            category=CATEGORY,
        )
        create_inventory.assert_called_once_with(card.resolve(), guard.resolve())


def test_apply_requires_specific_confirmation_before_any_card_or_project_access() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        with patch(
            "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment._audit"
        ) as audit:
            with pytest.raises(
                SaturnSblMidiCalibrationGuardedDeploymentError,
                match=CONFIRMATION_TOKEN,
            ):
                apply_sbl_midi_calibration_guarded_deployment(
                    root / "candidate",
                    root / "CARD",
                    root / "guard.json",
                    expected_guard_manifest_sha256="0" * 64,
                    confirmation="WRONG",
                )
        audit.assert_not_called()


def test_apply_uses_fixed_destination_and_requires_only_authorised_differences() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        card = root / "CARD"
        card.mkdir()
        guard = root / "guard.json"
        guard.write_text('{"manifest_sha256":"' + "a" * 64 + '"}\n', encoding="utf-8")
        valid = SimpleNamespace(valid=True, differences=())
        deployment = _deployment(card)
        with (
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment._audit",
                return_value=_pre_media(),
            ),
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.plan_saroo_standalone_image_deployment",
                return_value=_plan(card),
            ),
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.verify_saroo_card_inventory",
                side_effect=(valid, valid),
            ) as verify,
            patch(
                "rikai_kotoba.hardware.saturn.sbl_midi_calibration_guarded_deployment.apply_saroo_standalone_image_deployment",
                return_value=deployment,
            ) as apply,
        ):
            result = apply_sbl_midi_calibration_guarded_deployment(
                root / "candidate",
                card,
                guard,
                expected_guard_manifest_sha256="a" * 64,
                confirmation=CONFIRMATION_TOKEN,
            )
        apply.assert_called_once()
        assert apply.call_args.kwargs["destination_name"] == DESTINATION_NAME
        assert apply.call_args.kwargs["category"] == CATEGORY
        assert result.post_guard.valid
        assert verify.call_count == 2
        assert set(result.allowed_changed_paths) == {
            "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3",
            "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3/SRK-Diagnostics.bin",
            "SAROO/ISO/TEST/SRK-Diagnostics-SBL-MIDI-CAL-GATE3/SRK-Diagnostics.cue",
        }


def test_guarded_module_has_no_format_or_whole_card_delete_surface() -> None:
    source = Path(
        "src/rikai_kotoba/hardware/saturn/sbl_midi_calibration_guarded_deployment.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "format(",
        "mkfs",
        "diskpart",
        "rmtree(card",
        "rmtree(card_root",
        "unlink(mount",
    ):
        assert forbidden not in source
