"""Read-only pre-media audit for SBL MIDI calibration GATE4.

GATE4 is the hardware root-cause probe that keeps GATE3's proven SDDRV,
Direct-MIDI callbacks and tone assets but replaces the old 20-byte area map
with Sega's external Sound Simulator ``.MP`` representation.  This audit has no
SAROO/card write surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .sbl_midi_calibration_gate4_candidate import build_gate4_external_area_map
from .sbl_midi_calibration_pre_media import (
    EXPECTED_DRUM_SHA256,
    EXPECTED_MELODIC_SHA256,
    EXPECTED_SEGA_SND_SHA256,
    EXPECTED_SOUND_DRIVER_SHA256,
)


class SaturnSblMidiCalibrationGate4PreMediaError(RuntimeError):
    """Raised when GATE4 no longer matches its reviewed off-card contract."""


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_RUNTIME_HEADER = "src/srk_saturn_sbl_midi_calibration_runtime.h"
_MAIN = "src/srk_saturn_main.c"
_MELODIC = "cd/SRKGM.BIN"
_DRUM = "cd/SRKDRUM.BIN"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_EXPECTED_MAP_SHA256 = "b4a249b0d9df4985ad6f3357cd978e017b41bbf82d0d6603f378d968c6b67001"


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expect(actual, expected, label: str) -> None:
    if actual != expected:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"GATE4 pre-media mismatch for {label}: expected {expected!r}, got {actual!r}"
        )


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"{label} escapes project root: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnSblMidiCalibrationGate4PreMediaError(f"{label} is missing: {path}")
    return path


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError(f"{label} root is not an object")
    return value


def _external(record: object, label: str, expected_sha: str) -> Path:
    if not isinstance(record, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError(f"{label} record is missing")
    path_text = record.get("path")
    _expect(record.get("sha256"), expected_sha, f"{label} manifest SHA-256")
    if not isinstance(path_text, str) or not path_text:
        raise SaturnSblMidiCalibrationGate4PreMediaError(f"{label} path is invalid")
    try:
        path = Path(path_text).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"{label} external file is unavailable: {path_text}"
        ) from exc
    if not path.is_file():
        raise SaturnSblMidiCalibrationGate4PreMediaError(f"{label} is not a file: {path}")
    _expect(_sha_file(path), expected_sha, f"{label} disk SHA-256")
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblMidiCalibrationGate4PreMediaError("generated-file inventory is missing")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblMidiCalibrationGate4PreMediaError("invalid generated-file record")
        relative = entry.get("path")
        size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnSblMidiCalibrationGate4PreMediaError(
                "generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated project input")
        if path.stat().st_size != size or _sha_file(path) != expected_sha.lower():
            raise SaturnSblMidiCalibrationGate4PreMediaError(
                f"generated project input changed after manifest creation: {relative}"
            )

    required = {_MELODIC, _DRUM, _AREA_MAP, _DRIVER, _RUNTIME, _RUNTIME_HEADER, _MAIN}
    missing = required - seen
    if missing:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            "generated inventory lacks GATE4 files: " + ", ".join(sorted(missing))
        )


def _artifact(report: dict, relative: str) -> dict:
    entries = report.get("artifacts")
    if not isinstance(entries, list):
        raise SaturnSblMidiCalibrationGate4PreMediaError("build artifact inventory is missing")
    matches = [
        item for item in entries
        if isinstance(item, dict) and item.get("path") == relative
    ]
    if len(matches) != 1:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"build report does not uniquely contain artifact {relative}"
        )
    return matches[0]


def _anchors(source: str, values: tuple[str, ...], label: str) -> None:
    for value in values:
        if value not in source:
            raise SaturnSblMidiCalibrationGate4PreMediaError(
                f"{label} lost required anchor: {value}"
            )


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGate4PreMediaReport:
    project_root: Path
    manifest_sha256: str
    build_report_sha256: str
    area_map_sha256: str
    area_map_bytes: int
    sound_driver_sha256: str
    melodic_sha256: str
    drum_sha256: str
    sega_snd_sha256: str
    bin_sha256: str
    cue_sha256: str
    bin_bytes: int
    cue_bytes: int
    drum_start: int


def audit_sbl_midi_calibration_gate4_pre_media(
    project_directory: Path | str,
) -> SaturnSblMidiCalibrationGate4PreMediaReport:
    try:
        root = Path(project_directory).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"GATE4 project is unavailable: {project_directory}"
        ) from exc
    if not root.is_dir():
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            f"GATE4 project is not a directory: {root}"
        )

    manifest_path = _project_file(root, _MANIFEST, "GATE4 manifest")
    report_path = _project_file(root, _REPORT, "GATE4 build report")
    manifest = _load_json(manifest_path, "GATE4 manifest")
    report = _load_json(report_path, "GATE4 build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    _verify_generated_inventory(root, manifest)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "sbl_midi_calibration_candidate": True,
        "synthetic_r26_r28_timbres_used": False,
        "hardware_executed_during_build": False,
        "raw_scsp_audio_callbacks_disabled": True,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")

    calibration = manifest.get("sbl_midi_calibration")
    if not isinstance(calibration, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("calibration manifest record is missing")
    _expect(
        calibration.get("schema"),
        "srk.saturn.sbl-midi-calibration-candidate.v1",
        "calibration schema",
    )
    _expect(calibration.get("review_persistence_bound"), False, "review persistence")
    _expect(calibration.get("raw_scsp_audio_callbacks_disabled"), True, "raw-SCSP callbacks")
    _expect(calibration.get("off_card_only"), True, "off-card build policy")

    direct = calibration.get("direct_midi")
    if not isinstance(direct, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("Direct-MIDI contract is missing")
    for key, expected in {
        "sequence": 2,
        "priority": 0,
        "melodic_channel": 0,
        "bank_select_controller": 32,
        "melodic_bank": 0,
        "pan_controller": 10,
        "reference_note": 60,
        "reference_velocity": 100,
        "reference_pan": 64,
    }.items():
        _expect(direct.get(key), expected, f"Direct-MIDI {key}")

    driver = _project_file(root, _DRIVER, "GATE4 sound driver")
    melodic = _project_file(root, _MELODIC, "GATE4 melodic bank")
    drum = _project_file(root, _DRUM, "GATE4 drum bank")
    area_map = _project_file(root, _AREA_MAP, "GATE4 external area map")

    _expect(_sha_file(driver), EXPECTED_SOUND_DRIVER_SHA256, "copied sound driver")
    _expect(_sha_file(melodic), EXPECTED_MELODIC_SHA256, "copied melodic bank")
    _expect(_sha_file(drum), EXPECTED_DRUM_SHA256, "copied drum bank")

    driver_external = _external(
        calibration.get("sound_driver"), "sound driver", EXPECTED_SOUND_DRIVER_SHA256
    )
    melodic_external = _external(
        calibration.get("melodic_bank"), "melodic bank", EXPECTED_MELODIC_SHA256
    )
    drum_external = _external(
        calibration.get("drum_bank"), "drum bank", EXPECTED_DRUM_SHA256
    )
    sega_snd = _external(
        calibration.get("sega_snd"), "sega_snd.a", EXPECTED_SEGA_SND_SHA256
    )
    _expect(driver.read_bytes(), driver_external.read_bytes(), "driver copy")
    _expect(melodic.read_bytes(), melodic_external.read_bytes(), "melodic copy")
    _expect(drum.read_bytes(), drum_external.read_bytes(), "drum copy")

    expected_map, drum_start = build_gate4_external_area_map(
        melodic.stat().st_size, drum.stat().st_size
    )
    _expect(area_map.read_bytes(), expected_map, "external .MP map bytes")
    _expect(area_map.stat().st_size, 18, "external .MP map byte count")
    map_sha = _sha_file(area_map)
    _expect(map_sha, _EXPECTED_MAP_SHA256, "external .MP map SHA-256")
    map_record = calibration.get("area_map")
    if not isinstance(map_record, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("area-map record is missing")
    _expect(map_record.get("sha256"), map_sha, "manifest area-map SHA-256")
    _expect(map_record.get("bank0_start"), 0xB000, "bank 0 start")
    _expect(map_record.get("bank1_start"), drum_start, "bank 1 start")

    _expect(report.get("schema"), "srk.saturn.standalone-build.v1", "build schema")
    _expect(report.get("successful"), True, "build success")
    manifest_sha = _sha_file(manifest_path)
    _expect(report.get("project_manifest_sha256"), manifest_sha, "report/manifest binding")
    build_policy = report.get("policy")
    if not isinstance(build_policy, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("build policy is missing")
    for key, expected in {
        "shell_used": False,
        "path_mutated": False,
        "source_inputs_verified_after_build": True,
        "private_sdk_dependencies_verified_after_build": True,
        "private_sdk_dependencies_copied": False,
        "sd_writes": False,
        "commercial_image_changes": False,
    }.items():
        _expect(build_policy.get(key), expected, f"build policy {key}")

    runtime_header = _project_file(root, _RUNTIME_HEADER, "GATE4 runtime header").read_text(
        encoding="utf-8", errors="strict"
    )
    _anchors(
        runtime_header,
        (
            "#define SRK_SBL_CAL_MAP_BYTES 18UL",
            "#define SRK_SBL_CAL_GATE4_EXTERNAL_MP 1u",
        ),
        "GATE4 runtime header",
    )

    runtime = _project_file(root, _RUNTIME, "GATE4 runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    _anchors(
        runtime,
        (
            "SND_Init(&ini);",
            "SND_ChgMap(0)",
            "SND_MoveData((Uint16 *)srk_cal_tone",
            "SND_MoveData((Uint16 *)srk_cal_drum",
            "SND_ChgMix(0,0)",
            "SND_SetTlVl(15)",
            "return SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2);",
            "host->midi_select_program = srk_saturn_sbl_midi_select_program;",
            "host->midi_set_pan = srk_saturn_sbl_midi_set_pan;",
            "host->midi_note_on = srk_saturn_sbl_midi_note_on;",
            "host->midi_note_off = srk_saturn_sbl_midi_note_off;",
            "host->midi_persist_review = 0;",
        ),
        "GATE4 runtime",
    )
    for forbidden in (
        "0x25A00000",
        "0x25B00000",
        "SRK_AUDIO_SOUND_RAM",
        "SRK_AUDIO_SCSP_SLOT0",
    ):
        if forbidden in runtime:
            raise SaturnSblMidiCalibrationGate4PreMediaError(
                f"GATE4 runtime contains raw-SCSP marker: {forbidden}"
            )

    main = _project_file(root, _MAIN, "GATE4 main").read_text(
        encoding="utf-8", errors="strict"
    )
    _anchors(
        main,
        (
            "srk_saturn_audio_bind(&srk_host, &srk_host_state);",
            "srk_host.present_audio_tone = 0;",
            "srk_host.stop_audio = 0;",
            "srk_host.read_audio_status = 0;",
            "srk_saturn_sbl_midi_calibration_runtime_reset(&srk_midi_calibration_runtime);",
            "if(srk_saturn_sbl_midi_calibration_runtime_begin(&srk_midi_calibration_runtime))",
            "srk_saturn_sbl_midi_calibration_bind(&srk_host);",
        ),
        "GATE4 main",
    )
    if main.count("srk_diag_app_frame(") != 1:
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            "GATE4 main lost the single reusable diagnostic frame loop"
        )

    deployable = report.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnSblMidiCalibrationGate4PreMediaError("deployable record is missing")
    for key, expected in {
        "format": "cue-bin-mode1-2352",
        "bin": _DEPLOY_BIN,
        "cue": _DEPLOY_CUE,
        "verified_against_iso": True,
    }.items():
        _expect(deployable.get(key), expected, f"deployable {key}")

    bin_path = _project_file(root, _DEPLOY_BIN, "GATE4 deployable BIN")
    cue_path = _project_file(root, _DEPLOY_CUE, "GATE4 deployable CUE")
    bin_sha = _sha_file(bin_path)
    cue_sha = _sha_file(cue_path)
    for relative, path, digest in (
        (_DEPLOY_BIN, bin_path, bin_sha),
        (_DEPLOY_CUE, cue_path, cue_sha),
    ):
        record = _artifact(report, relative)
        _expect(record.get("size"), path.stat().st_size, f"artifact size {relative}")
        _expect(record.get("sha256"), digest, f"artifact SHA-256 {relative}")

    cue_text = cue_path.read_text(encoding="ascii", errors="strict")
    if (
        'FILE "SRK-Diagnostics.bin" BINARY' not in cue_text
        or "TRACK 01 MODE1/2352" not in cue_text
    ):
        raise SaturnSblMidiCalibrationGate4PreMediaError(
            "GATE4 CUE does not describe the expected MODE1/2352 BIN"
        )

    return SaturnSblMidiCalibrationGate4PreMediaReport(
        project_root=root,
        manifest_sha256=manifest_sha,
        build_report_sha256=_sha_file(report_path),
        area_map_sha256=map_sha,
        area_map_bytes=area_map.stat().st_size,
        sound_driver_sha256=EXPECTED_SOUND_DRIVER_SHA256,
        melodic_sha256=EXPECTED_MELODIC_SHA256,
        drum_sha256=EXPECTED_DRUM_SHA256,
        sega_snd_sha256=_sha_file(sega_snd),
        bin_sha256=bin_sha,
        cue_sha256=cue_sha,
        bin_bytes=bin_path.stat().st_size,
        cue_bytes=cue_path.stat().st_size,
        drum_start=drum_start,
    )
