"""Fresh off-card full-build gate for the R25 RR calibration candidate.

The baseline is the exact R24 physical candidate that was accepted on Eridu and
subsequently deployed/observed on Saturn.  Its manifest, build report, runtime,
main/menu binding, proof renderer, R24 resident representation and deployable
BIN/CUE are hard pinned here.

A fresh output tree is reconstructed only from the baseline manifest's generated
input inventory.  R24 files remain byte-for-byte unchanged.  New R25 resident,
voice and calibration-proof files are layered beside them, main/menu are derived
from the accepted R24 candidate, and the new R25 C bodies are appended to the
existing generated runtime translation unit in the same proven integration
style as R23/R24.

Running this gate builds only on the host.  It never accesses Saturn hardware or
SAROO media and never selects a production RR.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_r25_resident_audio_service import render_srk_saturn_midi_68k_r25_voice_header
from .midi_68k_r25_rr_physical_calibration import (
    build_srk_saturn_midi_68k_r25_rr_calibration_service_image,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_source,
    build_saturn_midi_68k_r25_rr_physical_calibration_plan,
)
from .midi_68k_r25_rr_physical_candidate import (
    derive_r25_rr_calibration_candidate_main,
    derive_r25_rr_calibration_candidate_menu,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KR25RRCalibrationFullBuildGateError(RuntimeError):
    """Raised when the accepted R24 -> fresh R25 calibration chain is not exact."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationPrepared:
    baseline_root: Path
    output_root: Path
    release_rate: int
    eg1_word: int
    eg2_word: int
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    calibration_image_sha256: str
    resident_source_sha256: str
    resident_header_sha256: str
    voice_header_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationFullBuildResult:
    prepared: SaturnMidi68KR25RRCalibrationPrepared
    build: SaturnStandaloneBuildResult


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R24_PROOF_SOURCE = "src/srk_saturn_midi_68k_r24_physical_proof.c"
_R24_PROOF_HEADER = "src/srk_saturn_midi_68k_r24_physical_proof.h"
_R25_AUDIO_SOURCE = "src/srk_saturn_midi_68k_r25_resident_audio_service.c"
_R25_AUDIO_HEADER = "src/srk_saturn_midi_68k_r25_resident_audio_service.h"
_R25_VOICE_HEADER = "src/srk_saturn_midi_68k_r25_voice_state.h"
_R25_PROOF_SOURCE = "src/srk_saturn_midi_68k_r25_rr_calibration_proof.c"
_R25_PROOF_HEADER = "src/srk_saturn_midi_68k_r25_rr_calibration_proof.h"
_R24_GATE_KEY = "midi_68k_r24_physical_candidate_full_build_gate"
_R24_GATE_SCHEMA = "srk.saturn.midi-68k-r24-physical-candidate-full-build-gate.v1"
_GATE_KEY = "midi_68k_r25_rr_calibration_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-r25-rr-calibration-physical-candidate-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K R25 RR PHYSICAL CALIBRATION: generated sources follow. */"

# Exact accepted R24 physical candidate anchors (Eridu + guarded R24 deployment).
ACCEPTED_R24_MANIFEST_SHA256 = "669d85db980f5c7922c5198dcc1b597b1d85664e543423f2c8570eeafa01fca6"
ACCEPTED_R24_REPORT_SHA256 = "d63adcd5e69cf4d96b6daac32c2acb06b6ce0d51ff3514d8802b96d9b6f21741"
ACCEPTED_R24_BIN_SHA256 = "8931c836a72ad49c9d98350086a8ef949a00925812b52464e35b8e090a6fac25"
ACCEPTED_R24_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
ACCEPTED_R24_IMAGE_SHA256 = "e45bf515bc75d5b87ea862d309c91ed3fcc0e86dc2e2f75341b6e7e6d2545c4e"
ACCEPTED_R24_MAIN_SHA256 = "b4d6f25d3a39150061275a9ab701d3df32063cd0c73015eb9381c4fc7be5b45d"
ACCEPTED_R24_MENU_SHA256 = "7b36d84223c454999f3d2fecb7af2f17b368843f3dc24931dd1d958b92ad9e8e"
ACCEPTED_R24_RUNTIME_SHA256 = "ef8f0634ea018a247aac47b17a30fc043403849f0ea235e957db2708f7ebaed3"
ACCEPTED_R24_PROOF_HEADER_SHA256 = "80d9600baac43c0e19bb02c0de5010b904e2af27636eedff31bec124a7d9e918"
ACCEPTED_R24_PROOF_SOURCE_SHA256 = "fda9c0e3993fd1e10ad6780b679a8c8d519b682d3bb07171c75ca19bf0709851"
ACCEPTED_R24_SOURCE_MIDI_SHA256 = "9c4161da95e18da9d932c169785622549b653770d1d110433f6d9491568e1041"

_ACCEPTED_R24_REPRESENTATION = {
    "src/srk_saturn_midi_68k_r24_resident_audio_service.c": "11ac3007edc80f599950fb4acc341c99e4fa7daa4ae1a6065ff91d755e240739",
    "src/srk_saturn_midi_68k_r24_resident_audio_service.h": "0c636c5cdce47434fc94c3c2eb057d392204b8ed42845f725929b7a27fb18930",
    "src/srk_saturn_midi_68k_r24_voice_state.h": "4d9670de85e14e5eddd4c1904157040f507c5167b917e9226681c415f0ca34cd",
    "src/srk_saturn_midi_68k_r24_player.c": "2d4ee8fe65bef1d604bf7abe4578647037d4e2d537f15a0b0411993554d778ea",
    "src/srk_saturn_midi_68k_r24_player.h": "7e87a9b9229c7b1ff95dbc0d4dad9a4814833572b119be5862b61fbb6f06dff4",
    "src/srk_saturn_midi_68k_r24_frt_backend.c": "6feda5d7a2daaf7ed6fe2185eeaab3cb9b552baaca280f204655fa10b6cd9201",
    "src/srk_saturn_midi_68k_r24_frt_backend.h": "559cbc879100380de53d31f613f31ef1efccf35b8c2b4972bb04f68d32f3e6e1",
    "src/srk_saturn_midi_68k_stream_service.c": "ce7e48b49381836828f1f40f9205c530a7aa368c407463049416030d8b5d974d",
    "src/srk_saturn_midi_68k_stream_service.h": "59c12246a82d0b6341746092cc8facfb374fd8da39db003919ca6c976cdb5e61",
}


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(f"{label} root must be an object")
    return value


def _inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if path.is_file() and path.name != _MANIFEST:
            relative = path.relative_to(root).as_posix()
            if relative == _REPORT or relative.startswith("build/"):
                continue
            values.append(
                {"path": relative, "size": path.stat().st_size, "sha256": _sha256_file(path)}
            )
    return values


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "accepted R24 build report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_r24_baseline(root: Path) -> tuple[dict, list[dict[str, object]]]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "accepted R24 physical baseline must contain manifest and build report"
        )
    if _sha256_file(manifest_path) != ACCEPTED_R24_MANIFEST_SHA256:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "R24 physical baseline manifest does not match accepted Eridu evidence"
        )
    if _sha256_file(report_path) != ACCEPTED_R24_REPORT_SHA256:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "R24 physical baseline build report does not match accepted Eridu evidence"
        )

    manifest = _load_json(manifest_path, "R24 physical manifest")
    report = _load_json(report_path, "R24 physical build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError("R24 baseline manifest schema changed")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError("R24 baseline build is not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != ACCEPTED_R24_MANIFEST_SHA256:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "R24 build report no longer points at the accepted candidate manifest"
        )

    gate = manifest.get(_R24_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R24_GATE_SCHEMA:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "baseline is not the accepted R24 physical-candidate gate"
        )
    exact = {
        "source_midi_sha256": ACCEPTED_R24_SOURCE_MIDI_SHA256,
        "r24_image_sha256": ACCEPTED_R24_IMAGE_SHA256,
        "candidate_main_sha256": ACCEPTED_R24_MAIN_SHA256,
        "candidate_menu_sha256": ACCEPTED_R24_MENU_SHA256,
        "runtime_after_sha256": ACCEPTED_R24_RUNTIME_SHA256,
        "proof_header_sha256": ACCEPTED_R24_PROOF_HEADER_SHA256,
        "proof_source_sha256": ACCEPTED_R24_PROOF_SOURCE_SHA256,
    }
    for key, expected in exact.items():
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(f"accepted R24 gate changed: {key}")
    for key, expected in (
        ("resident_installed_during_build", False),
        ("resident_executed_during_build", False),
        ("player_invoked_during_build", False),
        ("frt_invoked_during_build", False),
        ("scsp_mmio_during_build", False),
        ("sound_ram_writes_during_build", False),
        ("build_time_hardware_io", False),
        ("saroo_write", False),
        ("off_card_only", True),
        ("behaviorally_active_when_deployed_and_explicitly_triggered", True),
    ):
        if gate.get(key) is not expected:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                f"accepted R24 build policy changed: {key}"
            )

    exact_files = {
        _MAIN: ACCEPTED_R24_MAIN_SHA256,
        _MENU: ACCEPTED_R24_MENU_SHA256,
        _RUNTIME: ACCEPTED_R24_RUNTIME_SHA256,
        _R24_PROOF_HEADER: ACCEPTED_R24_PROOF_HEADER_SHA256,
        _R24_PROOF_SOURCE: ACCEPTED_R24_PROOF_SOURCE_SHA256,
        **_ACCEPTED_R24_REPRESENTATION,
    }
    for relative, expected in exact_files.items():
        path = root / relative
        if not path.is_file() or _sha256_file(path) != expected:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                f"accepted R24 physical file changed: {relative}"
            )

    artifacts = _artifact_map(report)
    for relative, expected, label in (
        (_DEPLOY_BIN, ACCEPTED_R24_BIN_SHA256, "R24 deploy BIN"),
        (_DEPLOY_CUE, ACCEPTED_R24_CUE_SHA256, "R24 deploy CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(f"{label} report hash changed")
        if not path.is_file() or _sha256_file(path) != expected:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(f"{label} disk hash changed")

    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "accepted R24 manifest has no generated input inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError("invalid R24 generated input entry")
        relative = entry.get("path")
        size = entry.get("size")
        expected = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected, str)
        ):
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                "invalid or duplicate R24 generated input metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size or _sha256_file(path) != expected.lower():
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                f"accepted R24 generated input changed: {relative}"
            )
        verified.append(entry)
    return manifest, verified


def prepare_saturn_midi_68k_r25_rr_calibration_candidate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    release_rate: int,
) -> SaturnMidi68KR25RRCalibrationPrepared:
    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            f"accepted R24 physical baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    manifest, generated = _verify_r24_baseline(baseline)
    plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=release_rate)
    if plan.production_rr_selected or plan.envelope_readback_available:
        raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
            "R25 calibration plan crossed the production-selection/readback boundary"
        )
    image = build_srk_saturn_midi_68k_r25_rr_calibration_service_image(
        release_rate=release_rate
    )
    resident_source = render_srk_saturn_midi_68k_r25_rr_calibration_service_source(
        release_rate=release_rate
    )
    resident_header = render_srk_saturn_midi_68k_r25_rr_calibration_service_header(
        release_rate=release_rate
    )
    voice_header = render_srk_saturn_midi_68k_r25_voice_header()
    proof_header = render_srk_saturn_midi_68k_r25_rr_calibration_proof_header(
        release_rate=release_rate
    )
    proof_source = render_srk_saturn_midi_68k_r25_rr_calibration_proof_source(
        release_rate=release_rate
    )

    blobs = {
        _R25_AUDIO_SOURCE: resident_source.encode("utf-8"),
        _R25_AUDIO_HEADER: resident_header.encode("utf-8"),
        _R25_VOICE_HEADER: voice_header.encode("utf-8"),
        _R25_PROOF_SOURCE: proof_source.encode("utf-8"),
        _R25_PROOF_HEADER: proof_header.encode("utf-8"),
    }
    hashes = {name: _sha256_bytes(data) for name, data in blobs.items()}

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    staging = temporary / "stage"
    staging.mkdir()
    try:
        for entry in generated:
            relative = str(entry["path"])
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(baseline / relative, destination)

        main_path = staging / _MAIN
        menu_path = staging / _MENU
        runtime_path = staging / _RUNTIME
        runtime_before = runtime_path.read_bytes()
        if _sha256_bytes(runtime_before) != ACCEPTED_R24_RUNTIME_SHA256:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                "R24 runtime changed during fresh staging"
            )
        candidate_main = derive_r25_rr_calibration_candidate_main(
            main_path.read_text(encoding="utf-8"), release_rate=release_rate
        ).encode("utf-8")
        candidate_menu = derive_r25_rr_calibration_candidate_menu(
            menu_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        main_path.write_bytes(candidate_main)
        menu_path.write_bytes(candidate_menu)
        for relative, data in blobs.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        marker = _MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KR25RRCalibrationFullBuildGateError(
                "accepted R24 runtime already contains R25 calibration injection"
            )
        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n"
        for relative in (_R25_AUDIO_SOURCE, _R25_PROOF_SOURCE):
            runtime_after += blobs[relative]
            if not runtime_after.endswith(b"\n"):
                runtime_after += b"\n"
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate = dict(manifest)
        policy = dict(candidate.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_r24_physical_baseline_preserved": True,
                "midi_68k_r25_rr_calibration_present": True,
                "midi_68k_r25_rr_calibration_bound": True,
                "midi_68k_r25_rr_calibration_resident_installed": False,
                "midi_68k_r25_rr_calibration_resident_executed": False,
                "midi_68k_r25_rr_calibration_frt_invoked": False,
                "midi_68k_r25_rr_calibration_build_time_hardware_io": False,
                "midi_68k_r25_production_rr_selected": False,
            }
        )
        candidate["policy"] = policy
        candidate[_GATE_KEY] = {
            "schema": _GATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": ACCEPTED_R24_MANIFEST_SHA256,
            "baseline_report_sha256": ACCEPTED_R24_REPORT_SHA256,
            "baseline_deploy_bin_sha256": ACCEPTED_R24_BIN_SHA256,
            "baseline_deploy_cue_sha256": ACCEPTED_R24_CUE_SHA256,
            "accepted_r24_image_sha256": ACCEPTED_R24_IMAGE_SHA256,
            "accepted_r24_candidate_main_sha256": ACCEPTED_R24_MAIN_SHA256,
            "accepted_r24_candidate_menu_sha256": ACCEPTED_R24_MENU_SHA256,
            "accepted_r24_runtime_sha256": ACCEPTED_R24_RUNTIME_SHA256,
            "accepted_r24_proof_header_sha256": ACCEPTED_R24_PROOF_HEADER_SHA256,
            "accepted_r24_proof_source_sha256": ACCEPTED_R24_PROOF_SOURCE_SHA256,
            "release_rate": plan.release_rate,
            "eg1_word": plan.eg1_word,
            "eg2_word": plan.eg2_word,
            "calibration_image_sha256": image.sha256,
            "calibration_resident_source_sha256": hashes[_R25_AUDIO_SOURCE],
            "calibration_resident_header_sha256": hashes[_R25_AUDIO_HEADER],
            "calibration_voice_header_sha256": hashes[_R25_VOICE_HEADER],
            "calibration_proof_source_sha256": hashes[_R25_PROOF_SOURCE],
            "calibration_proof_header_sha256": hashes[_R25_PROOF_HEADER],
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "channel": plan.channel,
            "note": plan.note,
            "velocity": plan.velocity,
            "note_on_us": plan.note_on_us,
            "note_off_us": plan.note_off_us,
            "observation_window_us": plan.observation_window_us,
            "observation_end_us": plan.observation_end_us,
            "record_count": plan.record_count,
            "batch_count": plan.batch_count,
            "measurement_mode": plan.measurement_mode,
            "envelope_readback_available": plan.envelope_readback_available,
            "production_rr_selected": plan.production_rr_selected,
            "candidate_define": "#define SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE 1",
            "candidate_menu_label": "MIDI 68K R25 RR Cal",
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "clock_backend": "accepted-r24-sh2-frt-div128-runtime-vdp2-selection",
            "frt_original_tcr_restored_on_terminal_path": True,
            "resident_installed_during_build": False,
            "resident_executed_during_build": False,
            "frt_invoked_during_build": False,
            "scsp_mmio_during_build": False,
            "sound_ram_writes_during_build": False,
            "build_time_hardware_io": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active_when_deployed_and_explicitly_triggered": True,
        }
        candidate["generated_files"] = _inventory(staging)
        (staging / _MANIFEST).write_text(
            json.dumps(candidate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        staging.replace(output)
        temporary.rmdir()
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return SaturnMidi68KR25RRCalibrationPrepared(
        baseline_root=baseline,
        output_root=output,
        release_rate=plan.release_rate,
        eg1_word=plan.eg1_word,
        eg2_word=plan.eg2_word,
        baseline_manifest_sha256=ACCEPTED_R24_MANIFEST_SHA256,
        baseline_report_sha256=ACCEPTED_R24_REPORT_SHA256,
        baseline_bin_sha256=ACCEPTED_R24_BIN_SHA256,
        baseline_cue_sha256=ACCEPTED_R24_CUE_SHA256,
        calibration_image_sha256=image.sha256,
        resident_source_sha256=hashes[_R25_AUDIO_SOURCE],
        resident_header_sha256=hashes[_R25_AUDIO_HEADER],
        voice_header_sha256=hashes[_R25_VOICE_HEADER],
        candidate_main_sha256=_sha256_bytes(candidate_main),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
        proof_header_sha256=hashes[_R25_PROOF_HEADER],
        proof_source_sha256=hashes[_R25_PROOF_SOURCE],
    )


def run_saturn_midi_68k_r25_rr_calibration_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    release_rate: int,
) -> SaturnMidi68KR25RRCalibrationFullBuildResult:
    prepared = prepare_saturn_midi_68k_r25_rr_calibration_candidate(
        baseline_project,
        output_directory,
        release_rate=release_rate,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KR25RRCalibrationFullBuildResult(prepared=prepared, build=build)
