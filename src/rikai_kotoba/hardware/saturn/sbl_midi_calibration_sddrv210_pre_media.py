"""Read-only pre-media audit for the telemetry-correct SDDRV Ver 2.10 one-shot.

The Ver 2.10 driver and telemetry layout are hard locked here. Final executable
hashes are intentionally reported from the fresh telemetry-correct build rather
than accepted as deployment evidence until the guarded-deployment lock is filled
from physical-build provenance in a subsequent reviewed commit.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import sbl_midi_calibration_consolidated_pre_media as _base
from .sbl_midi_calibration_sddrv210 import SDDRV210_SHA256


SaturnSblMidiCalibrationSddrv210PreMediaError = _base.SaturnSblMidiCalibrationConsolidatedPreMediaError

# Exact successful off-card transition build supplied on 2026-10-17. This is
# provenance for the driver-only swap, not the final telemetry-correct image.
TRANSITION_MANIFEST_SHA256 = "648ee095706c0b81b6e9da4e17351e408391c3878890b6f2ac4b12d8f8cdb2b8"
TRANSITION_BUILD_REPORT_SHA256 = "473239f6fd8d65c8d7438121a2e2822d03f9e03891ebade6114f30741c9ee28c"
TRANSITION_DEPLOYABLE_BIN_SHA256 = "f083a04d0eabd249083539db74f6a55482537e279210ab0a081da84aaf97d0ec"
TRANSITION_DEPLOYABLE_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"

# Exact telemetry-correct off-card build audited on Eridu on 2026-10-18.
FINAL_MANIFEST_SHA256 = "799197d9babc8ce2a3e14cae5a32f84dd89369fc50b12a5ad8e9d23e284f1d82"
FINAL_BUILD_REPORT_SHA256 = "cb91a8a35b2c5744c042b4b6abe4284e27fca31fda3aa7bbdd9991e2d4e14417"
FINAL_DEPLOYABLE_BIN_SHA256 = "b43ac550f5560d1a99e686833e826e38167b28bdbc8e4dd49b7c270754c3189c"
FINAL_DEPLOYABLE_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"

_EXPECTED_TELEMETRY = {
    "driver_version": "2.10",
    "driver_sha256": SDDRV210_SHA256,
    "sound_ram_base": "0x25A00000",
    "system_information_pointer_address": "0x25A00400",
    "system_information_pointer_expected": "0x00000440",
    "host_interface_pointer_address": "0x25A00404",
    "host_interface_pointer_expected": "0x00000700",
    "area_map_current_pointer_address": "0x25A00408",
    "area_map_current_pointer_expected": "0x00000500",
    "system_interface_work_pointer_address": "0x25A00412",
    "system_interface_work_pointer_expected": "0x00000480",
    "driver_error_address": "0x25A00416",
    "command_history_offset_address": "0x25A0041A",
    "command_history_ring_start": "0x0800",
    "command_history_ring_end": "0x0FFF",
    "command_history_entry_bytes": 16,
    "command_history_offset_mask": "0x07F0",
    "command_history_offset_max": "0x0800",
    "cpu_error_address": "0x25A00420",
    "command_history_proves_driver_execution": True,
    "interface_table_must_match_before_execution_proof": True,
}


@dataclass(frozen=True)
class SaturnSblMidiCalibrationSddrv210PreMediaReport:
    project_root: Path
    manifest_sha256: str
    build_report_sha256: str
    sound_driver_sha256: str
    soundfont_sha256: str
    sega_snd_sha256: str
    area_map_sha256: str
    family_sha256: tuple[str, ...]
    bin_sha256: str
    cue_sha256: str
    bin_bytes: int
    cue_bytes: int
    program_count: int
    family_count: int
    largest_family_bytes: int
    screen_owned_sbl_lifecycle: bool
    raw_scsp_audio_test_retained: bool
    driver_execution_telemetry: bool
    sega_oneshot_order: bool
    deployable_verified_against_iso: bool
    sddrv210_telemetry_contract: bool
    final_deployment_hash_lock_ready: bool


def _actual_artifacts(root: Path, build: dict) -> dict[str, tuple[int, str]]:
    artifacts = _base._artifact_map(build)
    locked: dict[str, tuple[int, str]] = {}
    for relative in _base.EXPECTED_ARTIFACTS:
        record = artifacts.get(relative)
        if not isinstance(record, dict):
            raise SaturnSblMidiCalibrationSddrv210PreMediaError(
                f"SDDRV210 build report lacks artifact record for {relative}"
            )
        size = record.get("size")
        digest = record.get("sha256")
        if not isinstance(size, int) or size <= 0 or not isinstance(digest, str) or len(digest) != 64:
            raise SaturnSblMidiCalibrationSddrv210PreMediaError(
                f"SDDRV210 build report has invalid artifact metadata for {relative}"
            )
        path = _base._file(root, relative, f"SDDRV210 artifact {relative}")
        _base._expect(path.stat().st_size, size, f"SDDRV210 artifact size {relative}")
        _base._expect(_base._sha_file(path), digest.lower(), f"SDDRV210 artifact SHA-256 {relative}")
        locked[relative] = (size, digest.lower())
    return locked


@contextmanager
def _base_expectations(artifacts: dict[str, tuple[int, str]]):
    old_driver = _base.EXPECTED_SOUND_DRIVER_SHA256
    old_artifacts = _base.EXPECTED_ARTIFACTS
    _base.EXPECTED_SOUND_DRIVER_SHA256 = SDDRV210_SHA256
    _base.EXPECTED_ARTIFACTS = artifacts
    try:
        yield
    finally:
        _base.EXPECTED_SOUND_DRIVER_SHA256 = old_driver
        _base.EXPECTED_ARTIFACTS = old_artifacts


def audit_sddrv210_midi_calibration_pre_media(
    project_directory: Path | str,
) -> SaturnSblMidiCalibrationSddrv210PreMediaReport:
    try:
        root = Path(project_directory).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationSddrv210PreMediaError(
            f"SDDRV210 calibration project is unavailable: {project_directory}"
        ) from exc
    if not root.is_dir():
        raise SaturnSblMidiCalibrationSddrv210PreMediaError(
            f"SDDRV210 calibration project is not a directory: {root}"
        )

    manifest_path = _base._file(root, _base._MANIFEST, "SDDRV210 project manifest")
    report_path = _base._file(root, _base._REPORT, "SDDRV210 build report")
    manifest = _base._load_json(manifest_path, "SDDRV210 project manifest")
    build = _base._load_json(report_path, "SDDRV210 build report")
    artifacts = _actual_artifacts(root, build)

    with _base_expectations(artifacts):
        report = _base.audit_consolidated_midi_calibration_pre_media(root)

    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("sddrv210_telemetry_contract") is not True:
        raise SaturnSblMidiCalibrationSddrv210PreMediaError(
            "manifest does not declare the SDDRV210 telemetry contract"
        )
    calibration = manifest.get("sbl_midi_calibration")
    telemetry = calibration.get("telemetry") if isinstance(calibration, dict) else None
    if not isinstance(telemetry, dict):
        raise SaturnSblMidiCalibrationSddrv210PreMediaError(
            "SDDRV210 telemetry manifest record is missing"
        )
    for key, expected in _EXPECTED_TELEMETRY.items():
        _base._expect(telemetry.get(key), expected, f"SDDRV210 telemetry {key}")

    runtime = _base._file(root, _base._RUNTIME, "SDDRV210 runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    _base._require_source_anchors(
        runtime,
        (
            "SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_ADDRESS 0x25A00400UL",
            "SRK_SBL_CAL_HOST_INTERFACE_POINTER_ADDRESS 0x25A00404UL",
            "SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_ADDRESS 0x25A00408UL",
            "SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS 0x25A00412UL",
            "SRK_SBL_CAL_HISTORY_RING_START 0x0800u",
            "SRK_SBL_CAL_HISTORY_RING_END 0x0FFFu",
            "SRK_SBL_CAL_HISTORY_OFFSET_MASK 0x07F0u",
            "SRK_SBL_CAL_HISTORY_OFFSET_MAX 0x0800u",
            "raw>SRK_SBL_CAL_HISTORY_OFFSET_MAX",
            "s->interface_valid=(s->system_information_pointer==SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_EXPECTED",
            "s->history_valid=(s->interface_valid&&history_valid&&history>=SRK_SBL_CAL_HISTORY_RING_START&&history<=SRK_SBL_CAL_HISTORY_RING_END)",
            "s->commands_queued>0UL&&s->history_valid",
            "history!=s->history_baseline",
        ),
        "SDDRV210 runtime telemetry",
    )

    main = _base._file(root, _base._MAIN, "SDDRV210 main").read_text(
        encoding="utf-8", errors="strict"
    )
    _base._require_source_anchors(
        main,
        (
            '"IF:"',
            '"Hist:"',
            '"H:"',
            '"400:"',
            '"404:"',
            '"408:"',
            '"412:"',
        ),
        "SDDRV210 main telemetry presentation",
    )

    return SaturnSblMidiCalibrationSddrv210PreMediaReport(
        project_root=report.project_root,
        manifest_sha256=report.manifest_sha256,
        build_report_sha256=report.build_report_sha256,
        sound_driver_sha256=report.sound_driver_sha256,
        soundfont_sha256=report.soundfont_sha256,
        sega_snd_sha256=report.sega_snd_sha256,
        area_map_sha256=report.area_map_sha256,
        family_sha256=report.family_sha256,
        bin_sha256=report.bin_sha256,
        cue_sha256=report.cue_sha256,
        bin_bytes=report.bin_bytes,
        cue_bytes=report.cue_bytes,
        program_count=report.program_count,
        family_count=report.family_count,
        largest_family_bytes=report.largest_family_bytes,
        screen_owned_sbl_lifecycle=report.screen_owned_sbl_lifecycle,
        raw_scsp_audio_test_retained=report.raw_scsp_audio_test_retained,
        driver_execution_telemetry=report.driver_execution_telemetry,
        sega_oneshot_order=report.sega_oneshot_order,
        deployable_verified_against_iso=report.deployable_verified_against_iso,
        sddrv210_telemetry_contract=True,
        final_deployment_hash_lock_ready=(
            report.manifest_sha256.lower() == FINAL_MANIFEST_SHA256
            and report.build_report_sha256.lower() == FINAL_BUILD_REPORT_SHA256
            and report.bin_sha256.lower() == FINAL_DEPLOYABLE_BIN_SHA256
            and report.cue_sha256.lower() == FINAL_DEPLOYABLE_CUE_SHA256
        ),
    )
