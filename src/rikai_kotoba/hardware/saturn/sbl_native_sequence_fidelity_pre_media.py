"""Read-only pre-media gate for the corrected native SDDRV GATE3F project.

This module audits an already-built local candidate and deliberately knows
nothing about SAROO/card paths.  It binds the final project manifest to the
standalone build report, re-hashes every locked audio asset, reconstructs the
Sega external area map, verifies the native SDDRV runtime contract, and hashes
the deployable BIN/CUE.  It never writes files or executes hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from .midi_68k_r26_double_impact import SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
from .sbl_native_sequence_fidelity_candidate import (
    GATE3F_DRUM_BYTES,
    GATE3F_DRUM_SHA256,
    GATE3F_MELODIC_BYTES,
    GATE3F_MELODIC_SHA256,
)
from .sbl_native_sequence_hardware_gate import (
    EXPECTED_SEGA_SND_SHA256,
    EXPECTED_SOUND_DRIVER_SHA256,
)
from .sbl_sequence import (
    SBL_AREA_SEQUENCE,
    SBL_AREA_TONE,
    SaturnSblArea,
    encode_sbl_external_area_map,
)
from .sbl_space_spectre_sequence import EXPECTED_BANK_BYTES, EXPECTED_BANK_SHA256


class SaturnSblNativeSequenceFidelityPreMediaError(RuntimeError):
    """Raised when GATE3F cannot safely become eligible for media deployment."""


_MELODIC_START = 0x0000B000
_SOUND_RAM_END = 0x00080000
_AREA_MAP_BYTES = 26

_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MELODIC = "cd/SRKGM.BIN"
_DRUM = "cd/SRKDRUM.BIN"
_SEQUENCE = "cd/SPACESEQ.BNK"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"


def _align4(value: int) -> int:
    return (value + 3) & ~3


EXPECTED_DRUM_START = _align4(_MELODIC_START + GATE3F_MELODIC_BYTES)
EXPECTED_SEQUENCE_START = _align4(EXPECTED_DRUM_START + GATE3F_DRUM_BYTES)


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise SaturnSblNativeSequenceFidelityPreMediaError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError(f"{label} root is not an object")
    return value


def _expect(actual, expected, label: str) -> None:
    if actual != expected:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            f"GATE3F pre-media mismatch for {label}: expected {expected!r}, got {actual!r}"
        )


def _file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            f"{label} escapes project root: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnSblNativeSequenceFidelityPreMediaError(f"{label} is missing: {path}")
    return path


def _expected_area_map() -> bytes:
    payload = encode_sbl_external_area_map(
        (
            SaturnSblArea(SBL_AREA_TONE, 0, _MELODIC_START, GATE3F_MELODIC_BYTES),
            SaturnSblArea(SBL_AREA_TONE, 1, EXPECTED_DRUM_START, GATE3F_DRUM_BYTES),
            SaturnSblArea(
                SBL_AREA_SEQUENCE,
                0,
                EXPECTED_SEQUENCE_START,
                EXPECTED_BANK_BYTES,
            ),
        )
    )
    if len(payload) != _AREA_MAP_BYTES:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            f"internal expected area map is {len(payload)} bytes"
        )
    if EXPECTED_SEQUENCE_START + EXPECTED_BANK_BYTES > _SOUND_RAM_END:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            "locked GATE3F sound assets exceed Saturn sound RAM"
        )
    return payload


EXPECTED_AREA_MAP_SHA256 = _sha_bytes(_expected_area_map())


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            "project manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblNativeSequenceFidelityPreMediaError(
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
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                "generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _file(root, relative, "generated project input")
        if path.stat().st_size != size or _sha_file(path) != expected_sha.lower():
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                f"generated project input changed after manifest creation: {relative}"
            )
    required = {_MELODIC, _DRUM, _SEQUENCE, _AREA_MAP, _DRIVER, _RUNTIME}
    missing = required - seen
    if missing:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            "generated inventory lacks required GATE3F files: " + ", ".join(sorted(missing))
        )


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnSblNativeSequenceFidelityPreMediaError("build report artifact list is missing")
    result: dict[str, dict] = {}
    for record in artifacts:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise SaturnSblNativeSequenceFidelityPreMediaError("invalid build artifact record")
        relative = record["path"]
        if relative in result:
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                f"duplicate build artifact record: {relative}"
            )
        result[relative] = record
    return result


def _verify_report_manifest_binding(manifest_path: Path, report: dict) -> str:
    actual = _sha_file(manifest_path)
    _expect(report.get("project_manifest_sha256"), actual, "build-report manifest SHA-256")
    return actual


@dataclass(frozen=True)
class SaturnSblNativeSequenceFidelityPreMediaReport:
    project_root: Path
    manifest_sha256: str
    build_report_sha256: str
    melodic_sha256: str
    drum_sha256: str
    sequence_sha256: str
    area_map_sha256: str
    driver_sha256: str
    sega_snd_sha256: str
    bin_sha256: str
    cue_sha256: str
    bin_bytes: int
    cue_bytes: int
    runtime_contract_exact: bool
    deployable_verified_against_iso: bool


def audit_gate3f_pre_media(project_directory: Path | str) -> SaturnSblNativeSequenceFidelityPreMediaReport:
    root = Path(project_directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            f"GATE3F project is not a directory: {root}"
        )

    manifest_path = _file(root, _MANIFEST, "GATE3F project manifest")
    report_path = _file(root, _REPORT, "GATE3F build report")
    manifest = _load_json(manifest_path, "GATE3F project manifest")
    build = _load_json(report_path, "GATE3F build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    _verify_generated_inventory(root, manifest)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("GATE3F manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "saroo_writes": False,
        "sbl_direct_midi_gm_candidate": False,
        "sbl_native_sequence_gm_candidate": True,
        "sbl_native_sequence_fidelity_gate3f": True,
        "sbl_fidelity_tone_policy": True,
        "soundfont_static_attenuation_compatibility_scale": 0.40,
        "multi_velocity_tables": True,
        "direct_midi_streaming": False,
        "sh2_midi_priming": False,
        "hardware_executed_during_build": False,
        "gate3f_off_card_only": True,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")

    lock = manifest.get("sbl_fidelity_tone_lock")
    if not isinstance(lock, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("GATE3F fidelity tone lock is missing")
    for key, expected in {
        "schema": "srk.saturn.sbl-fidelity-tone-lock.v1",
        "melodic_sha256": GATE3F_MELODIC_SHA256,
        "melodic_bytes": GATE3F_MELODIC_BYTES,
        "drum_sha256": GATE3F_DRUM_SHA256,
        "drum_bytes": GATE3F_DRUM_BYTES,
    }.items():
        _expect(lock.get(key), expected, f"fidelity lock {key}")

    native = manifest.get("sbl_native_sequence_gm")
    if not isinstance(native, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("native SDDRV manifest record is missing")
    _expect(native.get("schema"), "srk.saturn.sbl-native-sequence-gm-candidate.v1", "native schema")
    _expect(native.get("source_midi_sha256"), SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256, "source MIDI")
    _expect(native.get("note_count"), 4381, "native note count")
    _expect(native.get("off_card_only"), True, "native off-card policy")

    playback = native.get("playback")
    if not isinstance(playback, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("native playback record is missing")
    for key, expected in {
        "api": "SND_StartSeq",
        "sequence_number": 1,
        "bank": 0,
        "song": 0,
        "priority": 1,
        "direct_midi_streaming": False,
        "sh2_event_scheduler": False,
    }.items():
        _expect(playback.get(key), expected, f"native playback {key}")

    melodic = _file(root, _MELODIC, "corrected melodic TON")
    drums = _file(root, _DRUM, "corrected drum TON")
    sequence = _file(root, _SEQUENCE, "native sequence bank")
    area_map = _file(root, _AREA_MAP, "Sega area map")
    driver = _file(root, _DRIVER, "Sega sound driver")

    _expect(melodic.stat().st_size, GATE3F_MELODIC_BYTES, "melodic byte count")
    _expect(_sha_file(melodic), GATE3F_MELODIC_SHA256, "melodic SHA-256")
    _expect(drums.stat().st_size, GATE3F_DRUM_BYTES, "drum byte count")
    _expect(_sha_file(drums), GATE3F_DRUM_SHA256, "drum SHA-256")
    _expect(sequence.stat().st_size, EXPECTED_BANK_BYTES, "sequence byte count")
    _expect(_sha_file(sequence), EXPECTED_BANK_SHA256, "sequence SHA-256")
    _expect(driver.stat().st_size > 0, True, "sound-driver non-empty state")
    _expect(_sha_file(driver), EXPECTED_SOUND_DRIVER_SHA256, "sound-driver SHA-256")

    expected_map = _expected_area_map()
    _expect(area_map.read_bytes(), expected_map, "Sega external area-map bytes")
    _expect(_sha_file(area_map), EXPECTED_AREA_MAP_SHA256, "area-map SHA-256")

    area_record = native.get("area_map")
    if not isinstance(area_record, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("native area-map record is missing")
    for key, expected in {
        "format": "sega-external-mp",
        "bytes": _AREA_MAP_BYTES,
        "sha256": EXPECTED_AREA_MAP_SHA256,
        "melodic_start": _MELODIC_START,
        "drum_start": EXPECTED_DRUM_START,
        "sequence_start": EXPECTED_SEQUENCE_START,
    }.items():
        _expect(area_record.get(key), expected, f"area-map manifest {key}")

    sega_snd = native.get("sega_snd")
    if not isinstance(sega_snd, dict) or not isinstance(sega_snd.get("path"), str):
        raise SaturnSblNativeSequenceFidelityPreMediaError("native sega_snd record is missing")
    _expect(sega_snd.get("sha256"), EXPECTED_SEGA_SND_SHA256, "sega_snd manifest SHA-256")
    sega_snd_path = Path(sega_snd["path"]).expanduser().resolve(strict=True)
    _expect(_sha_file(sega_snd_path), EXPECTED_SEGA_SND_SHA256, "sega_snd disk SHA-256")

    _expect(build.get("schema"), "srk.saturn.standalone-build.v1", "build-report schema")
    _expect(build.get("successful"), True, "build success")
    manifest_sha = _verify_report_manifest_binding(manifest_path, build)
    build_policy = build.get("policy")
    if not isinstance(build_policy, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("build-report policy is missing")
    for key, expected in {
        "source_inputs_verified_after_build": True,
        "private_sdk_dependencies_verified_after_build": True,
        "private_sdk_dependencies_copied": False,
        "sd_writes": False,
        "commercial_image_changes": False,
    }.items():
        _expect(build_policy.get(key), expected, f"build policy {key}")

    runtime = _file(root, _RUNTIME, "native runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    required_runtime = (
        "SND_StartSeq(1,0,0,1)",
        "SND_KD_SEQ",
        "SND_SetTlVl(15)",
        "GFS_Load(id,0,dst,(Sint32)bytes)",
        "SND_GetSeqStat",
    )
    for anchor in required_runtime:
        if anchor not in runtime:
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                f"native runtime lost required anchor: {anchor}"
            )
    for forbidden in (
        "SND_CtrlDirMidi",
        "SND_GetSeqPlayPos",
        "GFS_Load(id,0,dst,(Sint32)((bytes+3UL)/4UL))",
    ):
        if forbidden in runtime:
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                f"native runtime contains forbidden legacy path: {forbidden}"
            )

    deployable = build.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnSblNativeSequenceFidelityPreMediaError("build report has no deployable BIN/CUE")
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
            raise SaturnSblNativeSequenceFidelityPreMediaError(
                f"build report lacks artifact record for {relative}"
            )
        _expect(record.get("size"), path.stat().st_size, f"artifact size {relative}")
        _expect(record.get("sha256"), actual_sha, f"artifact SHA-256 {relative}")

    cue_text = cue_path.read_text(encoding="ascii", errors="strict")
    if 'FILE "SRK-Diagnostics.bin" BINARY' not in cue_text or "TRACK 01 MODE1/2352" not in cue_text:
        raise SaturnSblNativeSequenceFidelityPreMediaError(
            "deployable CUE no longer describes the expected single MODE1/2352 BIN"
        )

    return SaturnSblNativeSequenceFidelityPreMediaReport(
        project_root=root,
        manifest_sha256=manifest_sha,
        build_report_sha256=_sha_file(report_path),
        melodic_sha256=GATE3F_MELODIC_SHA256,
        drum_sha256=GATE3F_DRUM_SHA256,
        sequence_sha256=EXPECTED_BANK_SHA256,
        area_map_sha256=EXPECTED_AREA_MAP_SHA256,
        driver_sha256=EXPECTED_SOUND_DRIVER_SHA256,
        sega_snd_sha256=EXPECTED_SEGA_SND_SHA256,
        bin_sha256=bin_sha,
        cue_sha256=cue_sha,
        bin_bytes=bin_path.stat().st_size,
        cue_bytes=cue_path.stat().st_size,
        runtime_contract_exact=True,
        deployable_verified_against_iso=True,
    )
