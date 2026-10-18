"""Read-only audit for the SDDRV210 master-volume-control candidate."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from . import sbl_midi_calibration_sddrv210_pre_media as _sddrv
from .sbl_midi_calibration_sddrv210_volume import (
    MASTER_VOLUME_DEFAULT,
    MASTER_VOLUME_MAX,
    MASTER_VOLUME_MIN,
)


SaturnSblMidiCalibrationSddrv210VolumePreMediaError = (
    _sddrv.SaturnSblMidiCalibrationSddrv210PreMediaError
)

_VOLUME_ORDER_ANCHOR = "SND_SetTlVl((SndTlVl)srk_cal_state->master_volume)"

FINAL_MANIFEST_SHA256 = "6f7d29e898c9f527fe87e9135beeb0f8e47853fd617504e9bc90f3ae763df268"
FINAL_BUILD_REPORT_SHA256 = "483c39cb3207d92a38911059fc91343ed2af159df50f9a919b115ab687ec84fd"
FINAL_DEPLOYABLE_BIN_SHA256 = "d57668eb08171e6862af7e492868a6608a55d73f8d404ef6e6b45ee40a7d135a"
FINAL_DEPLOYABLE_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"


def final_hash_lock_matches(report) -> bool:
    return (
        report.manifest_sha256.lower() == FINAL_MANIFEST_SHA256
        and report.build_report_sha256.lower() == FINAL_BUILD_REPORT_SHA256
        and report.bin_sha256.lower() == FINAL_DEPLOYABLE_BIN_SHA256
        and report.cue_sha256.lower() == FINAL_DEPLOYABLE_CUE_SHA256
    )


@contextmanager
def _volume_base_contract():
    old = _sddrv._base.EXPECTED_VOLUME_ANCHOR
    _sddrv._base.EXPECTED_VOLUME_ANCHOR = _VOLUME_ORDER_ANCHOR
    try:
        yield
    finally:
        _sddrv._base.EXPECTED_VOLUME_ANCHOR = old


def audit_sddrv210_volume_pre_media(project_directory):
    with _volume_base_contract():
        report = _sddrv.audit_sddrv210_midi_calibration_pre_media(project_directory)
    root = Path(project_directory).expanduser().resolve(strict=True)

    manifest_path = _sddrv._base._file(
        root, _sddrv._base._MANIFEST, "SDDRV210 volume project manifest"
    )
    manifest = _sddrv._base._load_json(
        manifest_path, "SDDRV210 volume project manifest"
    )
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_master_volume_control") is not True:
        raise SaturnSblMidiCalibrationSddrv210VolumePreMediaError(
            "manifest does not declare SDDRV210 master-volume control"
        )

    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210VolumePreMediaError(
            "SDDRV210 volume telemetry manifest record is missing"
        )
    expected = {
        "master_volume_min": MASTER_VOLUME_MIN,
        "master_volume_max": MASTER_VOLUME_MAX,
        "master_volume_default": MASTER_VOLUME_DEFAULT,
        "master_volume_control": "DPAD_UP_DOWN",
        "master_volume_command": "SND_SetTlVl",
    }
    for key, wanted in expected.items():
        _sddrv._base._expect(
            telemetry.get(key),
            wanted,
            f"SDDRV210 volume telemetry {key}",
        )

    runtime = _sddrv._base._file(
        root, _sddrv._base._RUNTIME, "SDDRV210 volume runtime"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        runtime,
        (
            "SRK_SBL_CAL_MASTER_VOLUME_MIN 0u",
            "SRK_SBL_CAL_MASTER_VOLUME_MAX 15u",
            "SRK_SBL_CAL_MASTER_VOLUME_DEFAULT 15u",
            "s->master_volume=SRK_SBL_CAL_MASTER_VOLUME_DEFAULT",
            "SND_SetTlVl((SndTlVl)srk_cal_state->master_volume)",
            "srk_saturn_sbl_midi_calibration_runtime_adjust_volume",
            "SND_SetTlVl((SndTlVl)state->master_volume)",
        ),
        "SDDRV210 master-volume runtime",
    )

    main = _sddrv._base._file(
        root, _sddrv._base._MAIN, "SDDRV210 volume main"
    ).read_text(encoding="utf-8", errors="strict")
    _sddrv._base._require_source_anchors(
        main,
        (
            '"Master volume:"',
            '"UP/DOWN Master volume"',
            "SRK_DIAG_BUTTON_UP",
            "SRK_DIAG_BUTTON_DOWN",
            "&srk_midi_calibration_runtime,1",
            "&srk_midi_calibration_runtime,-1",
        ),
        "SDDRV210 master-volume controls",
    )
    return report
