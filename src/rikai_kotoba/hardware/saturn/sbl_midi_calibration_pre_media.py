"""Read-only pre-media audit for the Sega SBL MIDI calibration candidate.

This gate deliberately has no knowledge of SAROO/card destinations.  It binds
an already-built calibration project to its manifest, generated-file inventory,
external Sega sound assets, standalone build report, generated SBL/Direct-MIDI
runtime contract, and deployable BIN/CUE.  It never writes project or media
files and never executes Saturn hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .sbl_gm_candidate_contract import build_sega_sbl_area_map


class SaturnSblMidiCalibrationPreMediaError(RuntimeError):
    """Raised when a calibration candidate is not safe to cross the media boundary."""


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MELODIC = "cd/SRKGM.BIN"
_DRUM = "cd/SRKDRUM.BIN"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_TONE_START = 0x0000B000

# Eridu-validated real Sega/SBL inputs used by the successful calibration GATE3.
EXPECTED_SOUND_DRIVER_SHA256 = (
    "76754e5bae4217e48d6a3c53c181033ddaab050deabda638bc41bf2f7f4906e3"
)
EXPECTED_MELODIC_SHA256 = (
    "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
)
EXPECTED_DRUM_SHA256 = (
    "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"
)
EXPECTED_SEGA_SND_SHA256 = (
    "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
)


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblMidiCalibrationPreMediaError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} root is not an object")
    return value


def _expect(actual, expected, label: str) -> None:
    if actual != expected:
        raise SaturnSblMidiCalibrationPreMediaError(
            f"calibration pre-media mismatch for {label}: "
            f"expected {expected!r}, got {actual!r}"
        )


def _file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnSblMidiCalibrationPreMediaError(
            f"{label} escapes project root: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} is missing: {path}")
    return path


def _external_file(record: object, label: str, expected_sha: str) -> Path:
    if not isinstance(record, dict):
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} manifest record is missing")
    path_text = record.get("path")
    manifest_sha = record.get("sha256")
    if not isinstance(path_text, str) or not path_text:
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} external path is invalid")
    _expect(manifest_sha, expected_sha, f"{label} manifest SHA-256")
    try:
        path = Path(path_text).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationPreMediaError(
            f"{label} external file is unavailable: {path_text}"
        ) from exc
    if not path.is_file():
        raise SaturnSblMidiCalibrationPreMediaError(f"{label} is not a file: {path}")
    _expect(_sha_file(path), expected_sha, f"{label} disk SHA-256")
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblMidiCalibrationPreMediaError(
            "project manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblMidiCalibrationPreMediaError(
                "generated-file inventory contains a non-object"
            )
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
            raise SaturnSblMidiCalibrationPreMediaError(
                "generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _file(root, relative, "generated project input")
        if path.stat().st_size != size or _sha_file(path) != expected_sha.lower():
            raise SaturnSblMidiCalibrationPreMediaError(
                f"generated project input changed after manifest creation: {relative}"
            )

    required = {_MELODIC, _DRUM, _AREA_MAP, _DRIVER, _RUNTIME, _MAIN}
    missing = required - seen
    if missing:
        raise SaturnSblMidiCalibrationPreMediaError(
            "generated inventory lacks calibration files: " + ", ".join(sorted(missing))
        )


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnSblMidiCalibrationPreMediaError("build report artifact list is missing")
    result: dict[str, dict] = {}
    for record in artifacts:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise SaturnSblMidiCalibrationPreMediaError("invalid build artifact record")
        relative = record["path"]
        if relative in result:
            raise SaturnSblMidiCalibrationPreMediaError(
                f"duplicate build artifact record: {relative}"
            )
        result[relative] = record
    return result


def _verify_report_manifest_binding(manifest_path: Path, report: dict) -> str:
    actual = _sha_file(manifest_path)
    _expect(report.get("project_manifest_sha256"), actual, "build-report manifest SHA-256")
    return actual


def _require_source_anchors(source: str, anchors: tuple[str, ...], label: str) -> None:
    for anchor in anchors:
        if anchor not in source:
            raise SaturnSblMidiCalibrationPreMediaError(
                f"{label} lost required anchor: {anchor}"
            )


@dataclass(frozen=True)
class SaturnSblMidiCalibrationPreMediaReport:
    project_root: Path
    manifest_sha256: str
    build_report_sha256: str
    sound_driver_sha256: str
    melodic_sha256: str
    drum_sha256: str
    area_map_sha256: str
    sega_snd_sha256: str
    bin_sha256: str
    cue_sha256: str
    bin_bytes: int
    cue_bytes: int
    drum_start: int
    runtime_contract_exact: bool
    raw_scsp_callbacks_disabled: bool
    deployable_verified_against_iso: bool


def audit_midi_calibration_pre_media(
    project_directory: Path | str,
) -> SaturnSblMidiCalibrationPreMediaReport:
    """Audit one finished SBL MIDI calibration candidate without modifying it."""

    try:
        root = Path(project_directory).expanduser().resolve(strict=True)
    except OSError as exc:
        raise SaturnSblMidiCalibrationPreMediaError(
            f"calibration project is unavailable: {project_directory}"
        ) from exc
    if not root.is_dir():
        raise SaturnSblMidiCalibrationPreMediaError(
            f"calibration project is not a directory: {root}"
        )

    manifest_path = _file(root, _MANIFEST, "calibration project manifest")
    report_path = _file(root, _REPORT, "calibration build report")
    manifest = _load_json(manifest_path, "calibration project manifest")
    build = _load_json(report_path, "calibration build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    _verify_generated_inventory(root, manifest)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblMidiCalibrationPreMediaError("calibration manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "sbl_midi_calibration_candidate": True,
        "synthetic_r26_r28_timbres_used": False,
        "hardware_executed_during_build": False,
        "raw_scsp_audio_callbacks_disabled": True,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")
    if policy.get("saroo_writes") not in (None, False):
        raise SaturnSblMidiCalibrationPreMediaError(
            "calibration manifest permits SAROO writes"
        )

    calibration = manifest.get("sbl_midi_calibration")
    if not isinstance(calibration, dict):
        raise SaturnSblMidiCalibrationPreMediaError(
            "calibration manifest record is missing"
        )
    _expect(
        calibration.get("schema"),
        "srk.saturn.sbl-midi-calibration-candidate.v1",
        "calibration schema",
    )
    _expect(calibration.get("review_persistence_bound"), False, "review persistence")
    _expect(
        calibration.get("raw_scsp_audio_callbacks_disabled"),
        True,
        "calibration raw-SCSP callback policy",
    )
    _expect(calibration.get("off_card_only"), True, "calibration off-card policy")

    direct = calibration.get("direct_midi")
    if not isinstance(direct, dict):
        raise SaturnSblMidiCalibrationPreMediaError("Direct-MIDI contract is missing")
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

    melodic = _file(root, _MELODIC, "calibration melodic bank")
    drums = _file(root, _DRUM, "calibration drum bank")
    area_map = _file(root, _AREA_MAP, "calibration Sega area map")
    driver = _file(root, _DRIVER, "calibration Sega sound driver")

    _expect(_sha_file(driver), EXPECTED_SOUND_DRIVER_SHA256, "copied sound-driver SHA-256")
    _expect(_sha_file(melodic), EXPECTED_MELODIC_SHA256, "copied melodic SHA-256")
    _expect(_sha_file(drums), EXPECTED_DRUM_SHA256, "copied drum SHA-256")

    driver_external = _external_file(
        calibration.get("sound_driver"), "sound driver", EXPECTED_SOUND_DRIVER_SHA256
    )
    melodic_record = calibration.get("melodic_bank")
    drum_record = calibration.get("drum_bank")
    melodic_external = _external_file(
        melodic_record, "melodic bank", EXPECTED_MELODIC_SHA256
    )
    drum_external = _external_file(drum_record, "drum bank", EXPECTED_DRUM_SHA256)
    sega_snd_path = _external_file(
        calibration.get("sega_snd"), "sega_snd.a", EXPECTED_SEGA_SND_SHA256
    )

    _expect(driver.read_bytes(), driver_external.read_bytes(), "copied/external sound driver")
    _expect(melodic.read_bytes(), melodic_external.read_bytes(), "copied/external melodic bank")
    _expect(drums.read_bytes(), drum_external.read_bytes(), "copied/external drum bank")
    _expect(melodic_record.get("bank") if isinstance(melodic_record, dict) else None, 0, "melodic bank id")
    _expect(drum_record.get("bank") if isinstance(drum_record, dict) else None, 1, "drum bank id")

    expected_map, drum_start = build_sega_sbl_area_map(
        melodic.stat().st_size, drums.stat().st_size
    )
    _expect(area_map.read_bytes(), expected_map, "Sega two-bank area-map bytes")
    map_sha = _sha_file(area_map)
    area_record = calibration.get("area_map")
    if not isinstance(area_record, dict):
        raise SaturnSblMidiCalibrationPreMediaError("area-map manifest record is missing")
    _expect(area_record.get("sha256"), map_sha, "area-map manifest SHA-256")
    _expect(area_record.get("bank0_start"), _TONE_START, "area-map bank0 start")
    _expect(area_record.get("bank1_start"), drum_start, "area-map bank1 start")

    _expect(build.get("schema"), "srk.saturn.standalone-build.v1", "build-report schema")
    _expect(build.get("successful"), True, "standalone build success")
    manifest_sha = _verify_report_manifest_binding(manifest_path, build)
    build_policy = build.get("policy")
    if not isinstance(build_policy, dict):
        raise SaturnSblMidiCalibrationPreMediaError("build-report policy is missing")
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

    runtime = _file(root, _RUNTIME, "calibration runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    _require_source_anchors(
        runtime,
        (
            'GFS_Load(id,0,dst,(Sint32)bytes)',
            'SND_Init(&ini);',
            'SND_ChgMap(0)',
            'SND_KD_TONE,0)',
            'SND_KD_TONE,1)',
            'SND_ChgMix(0,0)',
            'SND_SetTlVl(15)',
            'return SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2);',
            '#define SRK_SBL_CAL_SEQ_NO 2u',
            '#define SRK_SBL_CAL_SEQ_PRI 0u',
            '#define SRK_SBL_CAL_NOTE_OFF 0u',
            '#define SRK_SBL_CAL_NOTE_ON 1u',
            '#define SRK_SBL_CAL_CONTROL_CHANGE 3u',
            '#define SRK_SBL_CAL_PROGRAM_CHANGE 4u',
            '#define SRK_SBL_CAL_BANK_CONTROLLER 32u',
            '#define SRK_SBL_CAL_MELODIC_BANK 0u',
            '#define SRK_SBL_CAL_PAN_CONTROLLER 10u',
            'host->midi_persist_review = 0;',
        ),
        "calibration runtime",
    )
    for forbidden in (
        "0x25A00000",
        "0x25B00000",
        "SRK_AUDIO_SOUND_RAM",
        "SRK_AUDIO_SCSP_SLOT0",
    ):
        if forbidden in runtime:
            raise SaturnSblMidiCalibrationPreMediaError(
                f"calibration runtime contains raw-SCSP marker: {forbidden}"
            )

    main = _file(root, _MAIN, "calibration main").read_text(
        encoding="utf-8", errors="strict"
    )
    _require_source_anchors(
        main,
        (
            'srk_saturn_audio_bind(&srk_host, &srk_host_state);',
            'srk_host.present_audio_tone = 0;',
            'srk_host.stop_audio = 0;',
            'srk_host.read_audio_status = 0;',
            'srk_saturn_sbl_midi_calibration_runtime_reset(&srk_midi_calibration_runtime);',
            'srk_saturn_sbl_midi_calibration_runtime_begin(&srk_midi_calibration_runtime)',
            'srk_saturn_sbl_midi_calibration_bind(&srk_host);',
        ),
        "calibration main",
    )
    if main.count("srk_diag_app_frame(") != 1:
        raise SaturnSblMidiCalibrationPreMediaError(
            "calibration main no longer has exactly one reusable diagnostic app frame loop"
        )

    deployable = build.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnSblMidiCalibrationPreMediaError("build report has no deployable BIN/CUE")
    for key, expected in {
        "format": "cue-bin-mode1-2352",
        "bin": _DEPLOY_BIN,
        "cue": _DEPLOY_CUE,
        "verified_against_iso": True,
    }.items():
        _expect(deployable.get(key), expected, f"deployable {key}")

    artifacts = _artifact_map(build)
    bin_path = _file(root, _DEPLOY_BIN, "deployable BIN")
    cue_path = _file(root, _DEPLOY_CUE, "deployable CUE")
    bin_sha = _sha_file(bin_path)
    cue_sha = _sha_file(cue_path)
    for relative, path, actual_sha in (
        (_DEPLOY_BIN, bin_path, bin_sha),
        (_DEPLOY_CUE, cue_path, cue_sha),
    ):
        record = artifacts.get(relative)
        if not isinstance(record, dict):
            raise SaturnSblMidiCalibrationPreMediaError(
                f"build report lacks artifact record for {relative}"
            )
        _expect(record.get("size"), path.stat().st_size, f"artifact size {relative}")
        _expect(record.get("sha256"), actual_sha, f"artifact SHA-256 {relative}")

    cue_text = cue_path.read_text(encoding="ascii", errors="strict")
    if (
        'FILE "SRK-Diagnostics.bin" BINARY' not in cue_text
        or "TRACK 01 MODE1/2352" not in cue_text
    ):
        raise SaturnSblMidiCalibrationPreMediaError(
            "deployable CUE no longer describes the expected single MODE1/2352 BIN"
        )

    return SaturnSblMidiCalibrationPreMediaReport(
        project_root=root,
        manifest_sha256=manifest_sha,
        build_report_sha256=_sha_file(report_path),
        sound_driver_sha256=EXPECTED_SOUND_DRIVER_SHA256,
        melodic_sha256=EXPECTED_MELODIC_SHA256,
        drum_sha256=EXPECTED_DRUM_SHA256,
        area_map_sha256=map_sha,
        sega_snd_sha256=_sha_file(sega_snd_path),
        bin_sha256=bin_sha,
        cue_sha256=cue_sha,
        bin_bytes=bin_path.stat().st_size,
        cue_bytes=cue_path.stat().st_size,
        drum_start=drum_start,
        runtime_contract_exact=True,
        raw_scsp_callbacks_disabled=True,
        deployable_verified_against_iso=True,
    )
