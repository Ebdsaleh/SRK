"""Independent read-only pre-media review for the accepted R25 RR16 candidate.

The completed R25 calibration candidate is treated as external build evidence.
This gate pins the Eridu-accepted R25 manifest/report/artifact hashes, re-renders
the calibration resident and physical proof, re-derives main/menu from the
physically accepted R24 baseline, reconstructs the runtime injection, verifies
the standalone build and MODE1 geometry, and finally asks the existing SAROO
planner for a read-only fresh-destination plan.

There is intentionally no write/apply operation in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from . import midi_68k_r25_rr_calibration_full_build_gate as _build
from .midi_68k_r25_resident_audio_service import render_srk_saturn_midi_68k_r25_voice_header
from .midi_68k_r25_rr_physical_calibration import (
    build_saturn_midi_68k_r25_rr_physical_calibration_plan,
    build_srk_saturn_midi_68k_r25_rr_calibration_service_image,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_service_source,
)
from .midi_68k_r25_rr_physical_candidate import (
    derive_r25_rr_calibration_candidate_main,
    derive_r25_rr_calibration_candidate_menu,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_header,
    render_srk_saturn_midi_68k_r25_rr_calibration_proof_source,
)
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KR25RRCalibrationPreMediaGateError(RuntimeError):
    """Raised when the accepted R25 RR16 candidate fails independent review."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationPreMediaResult:
    project_root: Path
    baseline_root: Path
    manifest_sha256: str
    report_sha256: str
    calibration_image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    sector_count: int
    raw_bytes: int
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_RUNTIME = "src/srk_saturn_runtime.c"
_R25_AUDIO_SOURCE = "src/srk_saturn_midi_68k_r25_resident_audio_service.c"
_R25_AUDIO_HEADER = "src/srk_saturn_midi_68k_r25_resident_audio_service.h"
_R25_VOICE_HEADER = "src/srk_saturn_midi_68k_r25_voice_state.h"
_R25_PROOF_SOURCE = "src/srk_saturn_midi_68k_r25_rr_calibration_proof.c"
_R25_PROOF_HEADER = "src/srk_saturn_midi_68k_r25_rr_calibration_proof.h"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_GATE_KEY = "midi_68k_r25_rr_calibration_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-r25-rr-calibration-physical-candidate-full-build-gate.v1"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_R25_RR_CALIBRATION_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K R25 RR Cal"
_MARKER = "/* SRK MIDI 68K R25 RR PHYSICAL CALIBRATION: generated sources follow. */"

# Accepted Eridu build evidence returned after e573a5b.
ACCEPTED_R25_MANIFEST_SHA256 = "5a282c2ea1077b95ca34bc1fd11593f34cef015baa6da1eb5c5cfe69f830cba9"
ACCEPTED_R25_REPORT_SHA256 = "bcd65a3252e5b7980b2263b4134b8145405cbe043169bcbaacd196a1e708d991"
ACCEPTED_R25_IMAGE_SHA256 = "f11dd5559b5b1309922679f80fc8c36ed6cf8dc50a6b4073bdcdbaaeb3efe5e5"
ACCEPTED_R25_RESIDENT_SOURCE_SHA256 = "a1b813a3a0ef01f07bbb18c77ff7c4df273fc7cd1cd9621398f583148bb86b2b"
ACCEPTED_R25_RESIDENT_HEADER_SHA256 = "c5ddca1488c7df0f4f8319a93720f93946b13be023b20ac7fd5a7ba4c6c4cceb"
ACCEPTED_R25_VOICE_HEADER_SHA256 = "c7a4e15cb83e0fcd76352cbb4ee9fe16e14a31985d30fd8ccff9e5742ec0d0b0"
ACCEPTED_R25_MAIN_SHA256 = "4116d997b7732295b1a8315827a75d44665d10e7f248deb219ff9188168bb976"
ACCEPTED_R25_MENU_SHA256 = "493788a27273ff4e4bd73c1ca3d0849fe8cd50486e08fa6e75880e5b489a064d"
ACCEPTED_R25_RUNTIME_SHA256 = "d936d2a0b6b7763224b29e8db10cce4be33e5115f36df21a189417e7df4cccf4"
ACCEPTED_R25_PROOF_HEADER_SHA256 = "d422ce6b48f0fea1e7eb342a1c8f73d14fd25980037f56159fa93430a866651f"
ACCEPTED_R25_PROOF_SOURCE_SHA256 = "6b811165bcea3615da57144f0c3f81ac1d1c230c22ca5297820ec4bc275fe8be"
ACCEPTED_R25_BUILD_BIN_SHA256 = "d8882f9383e4f71c8b0a0f961f516fc0a47ccf471aee38849a605370bae7528a"
ACCEPTED_R25_BUILD_ISO_SHA256 = "e3261b3d03343d8de282f0e432866fbb9c93e0a2c51b88335e705b8d42484ed2"
ACCEPTED_R25_BUILD_MAP_SHA256 = "4d295cfb6bcd48bbbcf23e94dccd834cea0527a5ec9b029fa8322ce07e174921"
ACCEPTED_R25_BIN_SHA256 = "a9df54075e1ccbb8c2d0819ef499f09df6896ba1cc373909b883e6bdcba60a71"
ACCEPTED_R25_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
ACCEPTED_R25_SECTOR_COUNT = 144
ACCEPTED_R25_RAW_BYTES = 338688
ACCEPTED_R25_USER_BYTES = 294912


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
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(f"{label} root must be an object")
    return value


def _file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            f"{label} path escapes project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(f"{label} is missing: {path}")
    return path


def _expect(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(f"R25 contract mismatch: {label}")


def _verify_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 candidate has no generated inventory")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR25RRCalibrationPreMediaGateError("invalid generated inventory entry")
        relative, size, expected = entry.get("path"), entry.get("size"), entry.get("sha256")
        if (
            not isinstance(relative, str) or not relative or relative in seen
            or not isinstance(size, int) or size < 0
            or not isinstance(expected, str) or len(expected) != 64
        ):
            raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
                "invalid or duplicate generated inventory metadata"
            )
        seen.add(relative)
        path = _file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path) != expected.lower():
            raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
                f"R25 generated input changed: {relative}"
            )
    required = {
        _MAIN, _MENU, _RUNTIME, _R25_AUDIO_SOURCE, _R25_AUDIO_HEADER,
        _R25_VOICE_HEADER, _R25_PROOF_SOURCE, _R25_PROOF_HEADER,
    }
    if not required.issubset(seen):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            "R25 inventory is missing required calibration inputs"
        )


def _verify_r24_baseline(root: Path) -> None:
    exact = {
        _MANIFEST: _build.ACCEPTED_R24_MANIFEST_SHA256,
        _REPORT: _build.ACCEPTED_R24_REPORT_SHA256,
        _MAIN: _build.ACCEPTED_R24_MAIN_SHA256,
        _MENU: _build.ACCEPTED_R24_MENU_SHA256,
        _RUNTIME: _build.ACCEPTED_R24_RUNTIME_SHA256,
        "src/srk_saturn_midi_68k_r24_physical_proof.h": _build.ACCEPTED_R24_PROOF_HEADER_SHA256,
        "src/srk_saturn_midi_68k_r24_physical_proof.c": _build.ACCEPTED_R24_PROOF_SOURCE_SHA256,
        _DEPLOY_BIN: _build.ACCEPTED_R24_BIN_SHA256,
        _DEPLOY_CUE: _build.ACCEPTED_R24_CUE_SHA256,
    }
    for relative, expected in exact.items():
        if _sha256_file(_file(root, relative, f"accepted R24 {relative}")) != expected:
            raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
                f"accepted R24 baseline changed: {relative}"
            )


def _render_current_r25() -> tuple[dict[str, bytes], str]:
    plan = build_saturn_midi_68k_r25_rr_physical_calibration_plan(release_rate=16)
    for actual, expected, label in (
        (plan.release_rate, 16, "RR"), (plan.eg1_word, 0x001F, "EG1"),
        (plan.eg2_word, 0x3C10, "EG2"), (plan.channel, 0, "channel"),
        (plan.note, 69, "note"), (plan.velocity, 100, "velocity"),
        (plan.note_on_us, 250000, "note on"), (plan.note_off_us, 1250000, "note off"),
        (plan.observation_window_us, 2000000, "observation window"),
        (plan.observation_end_us, 3250000, "observation end"),
        (plan.record_count, 2, "record count"), (plan.batch_count, 1, "batch count"),
        (plan.production_rr_selected, False, "production RR"),
        (plan.envelope_readback_available, False, "envelope readback"),
        (plan.measurement_mode, "operator-observed-audio", "measurement mode"),
    ):
        _expect(actual, expected, label)
    image = build_srk_saturn_midi_68k_r25_rr_calibration_service_image(release_rate=16)
    blobs = {
        _R25_AUDIO_SOURCE: render_srk_saturn_midi_68k_r25_rr_calibration_service_source(release_rate=16).encode("utf-8"),
        _R25_AUDIO_HEADER: render_srk_saturn_midi_68k_r25_rr_calibration_service_header(release_rate=16).encode("utf-8"),
        _R25_VOICE_HEADER: render_srk_saturn_midi_68k_r25_voice_header().encode("utf-8"),
        _R25_PROOF_SOURCE: render_srk_saturn_midi_68k_r25_rr_calibration_proof_source(release_rate=16).encode("utf-8"),
        _R25_PROOF_HEADER: render_srk_saturn_midi_68k_r25_rr_calibration_proof_header(release_rate=16).encode("utf-8"),
    }
    return blobs, image.sha256


def inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR25RRCalibrationPreMediaResult:
    """Revalidate the accepted RR16 candidate and return a read-only SAROO plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            f"R25 RR16 candidate project is not a directory: {root}"
        )
    manifest_path = _file(root, _MANIFEST, "R25 manifest")
    report_path = _file(root, _REPORT, "R25 build report")
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    _expect(manifest_sha, ACCEPTED_R25_MANIFEST_SHA256, "accepted manifest SHA-256")
    _expect(report_sha, ACCEPTED_R25_REPORT_SHA256, "accepted report SHA-256")

    manifest = _load_json(manifest_path, "R25 manifest")
    report = _load_json(report_path, "R25 build report")
    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 calibration gate is missing")
    _expect(gate.get("schema"), _GATE_SCHEMA, "gate schema")
    _verify_inventory(root, manifest)

    required_gate = {
        "baseline_manifest_sha256": _build.ACCEPTED_R24_MANIFEST_SHA256,
        "baseline_report_sha256": _build.ACCEPTED_R24_REPORT_SHA256,
        "baseline_deploy_bin_sha256": _build.ACCEPTED_R24_BIN_SHA256,
        "baseline_deploy_cue_sha256": _build.ACCEPTED_R24_CUE_SHA256,
        "accepted_r24_image_sha256": _build.ACCEPTED_R24_IMAGE_SHA256,
        "accepted_r24_candidate_main_sha256": _build.ACCEPTED_R24_MAIN_SHA256,
        "accepted_r24_candidate_menu_sha256": _build.ACCEPTED_R24_MENU_SHA256,
        "accepted_r24_runtime_sha256": _build.ACCEPTED_R24_RUNTIME_SHA256,
        "accepted_r24_proof_header_sha256": _build.ACCEPTED_R24_PROOF_HEADER_SHA256,
        "accepted_r24_proof_source_sha256": _build.ACCEPTED_R24_PROOF_SOURCE_SHA256,
        "release_rate": 16, "eg1_word": 0x001F, "eg2_word": 0x3C10,
        "channel": 0, "note": 69, "velocity": 100,
        "note_on_us": 250000, "note_off_us": 1250000,
        "observation_window_us": 2000000, "observation_end_us": 3250000,
        "record_count": 2, "batch_count": 1,
        "measurement_mode": "operator-observed-audio",
        "envelope_readback_available": False, "production_rr_selected": False,
        "candidate_define": _EXPECTED_DEFINE, "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A", "trigger_requires_release_after_screen_entry": True,
        "clock_backend": "accepted-r24-sh2-frt-div128-runtime-vdp2-selection",
        "frt_original_tcr_restored_on_terminal_path": True,
        "resident_installed_during_build": False, "resident_executed_during_build": False,
        "frt_invoked_during_build": False, "scsp_mmio_during_build": False,
        "sound_ram_writes_during_build": False, "build_time_hardware_io": False,
        "saroo_write": False, "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
    }
    for key, expected in required_gate.items():
        _expect(gate.get(key), expected, key)

    baseline_text = gate.get("baseline_project")
    if not isinstance(baseline_text, str) or not baseline_text:
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 gate has no R24 baseline path")
    baseline = _canonical(baseline_text)
    if not baseline.is_dir():
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            f"accepted R24 baseline is unavailable: {baseline}"
        )
    _verify_r24_baseline(baseline)

    blobs, image_sha = _render_current_r25()
    _expect(image_sha, ACCEPTED_R25_IMAGE_SHA256, "calibration image SHA-256")
    _expect(str(gate.get("calibration_image_sha256", "")).lower(), image_sha, "manifest image SHA-256")
    render_contract = {
        _R25_AUDIO_SOURCE: (ACCEPTED_R25_RESIDENT_SOURCE_SHA256, "calibration_resident_source_sha256"),
        _R25_AUDIO_HEADER: (ACCEPTED_R25_RESIDENT_HEADER_SHA256, "calibration_resident_header_sha256"),
        _R25_VOICE_HEADER: (ACCEPTED_R25_VOICE_HEADER_SHA256, "calibration_voice_header_sha256"),
        _R25_PROOF_SOURCE: (ACCEPTED_R25_PROOF_SOURCE_SHA256, "calibration_proof_source_sha256"),
        _R25_PROOF_HEADER: (ACCEPTED_R25_PROOF_HEADER_SHA256, "calibration_proof_header_sha256"),
    }
    for relative, (expected, gate_key) in render_contract.items():
        _expect(_sha256_bytes(blobs[relative]), expected, f"current renderer {relative}")
        _expect(_sha256_file(_file(root, relative, relative)), expected, f"disk {relative}")
        _expect(str(gate.get(gate_key, "")).lower(), expected, gate_key)

    baseline_main = _file(baseline, _MAIN, "accepted R24 main").read_text(encoding="utf-8")
    baseline_menu = _file(baseline, _MENU, "accepted R24 menu").read_text(encoding="utf-8")
    expected_main = derive_r25_rr_calibration_candidate_main(baseline_main, release_rate=16).encode("utf-8")
    expected_menu = derive_r25_rr_calibration_candidate_menu(baseline_menu).encode("utf-8")
    _expect(_sha256_bytes(expected_main), ACCEPTED_R25_MAIN_SHA256, "derived R25 main SHA-256")
    _expect(_file(root, _MAIN, "R25 main").read_bytes(), expected_main, "derived R25 main bytes")
    _expect(_sha256_bytes(expected_menu), ACCEPTED_R25_MENU_SHA256, "derived R25 menu SHA-256")
    _expect(_file(root, _MENU, "R25 menu").read_bytes(), expected_menu, "derived R25 menu bytes")

    expected_runtime = _file(baseline, _RUNTIME, "accepted R24 runtime").read_bytes()
    if not expected_runtime.endswith(b"\n"):
        expected_runtime += b"\n"
    expected_runtime += b"\n" + _MARKER.encode("ascii") + b"\n"
    for relative in (_R25_AUDIO_SOURCE, _R25_PROOF_SOURCE):
        expected_runtime += blobs[relative]
        if not expected_runtime.endswith(b"\n"):
            expected_runtime += b"\n"
        expected_runtime += b"\n"
    _expect(_sha256_bytes(expected_runtime), ACCEPTED_R25_RUNTIME_SHA256, "reconstructed runtime SHA-256")
    _expect(_file(root, _RUNTIME, "R25 runtime").read_bytes(), expected_runtime, "reconstructed runtime bytes")
    for key, expected in {
        "candidate_main_sha256": ACCEPTED_R25_MAIN_SHA256,
        "candidate_menu_sha256": ACCEPTED_R25_MENU_SHA256,
        "runtime_before_sha256": _build.ACCEPTED_R24_RUNTIME_SHA256,
        "runtime_after_sha256": ACCEPTED_R25_RUNTIME_SHA256,
    }.items():
        _expect(str(gate.get(key, "")).lower(), expected, key)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 manifest policy is missing")
    for key, expected in {
        "sd_writes": False, "midi_68k_r24_physical_baseline_preserved": True,
        "midi_68k_r25_rr_calibration_present": True, "midi_68k_r25_rr_calibration_bound": True,
        "midi_68k_r25_rr_calibration_resident_installed": False,
        "midi_68k_r25_rr_calibration_resident_executed": False,
        "midi_68k_r25_rr_calibration_frt_invoked": False,
        "midi_68k_r25_rr_calibration_build_time_hardware_io": False,
        "midi_68k_r25_production_rr_selected": False,
    }.items():
        _expect(policy.get(key), expected, f"policy {key}")

    _expect(report.get("schema"), "srk.saturn.standalone-build.v1", "report schema")
    _expect(report.get("successful"), True, "successful build")
    _expect(str(report.get("project_manifest_sha256", "")).lower(), manifest_sha, "report/manifest pairing")
    report_policy = report.get("policy")
    if not isinstance(report_policy, dict):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 build policy is missing")
    for key, expected in {
        "commercial_image_changes": False, "path_mutated": False,
        "private_sdk_dependencies_copied": False,
        "private_sdk_dependencies_verified_after_build": True,
        "private_sdk_dependencies_verified_before_build": True,
        "sd_writes": False, "shell_used": False,
        "source_inputs_verified_after_build": True, "source_inputs_verified_before_build": True,
    }.items():
        _expect(report_policy.get(key), expected, f"build policy {key}")

    deployable = report.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 deployable record is missing")
    for actual, expected, label in (
        (deployable.get("format"), "cue-bin-mode1-2352", "deployable format"),
        (deployable.get("verified_against_iso"), True, "MODE1/ISO verification"),
        (deployable.get("sector_count"), ACCEPTED_R25_SECTOR_COUNT, "sector count"),
        (deployable.get("raw_bytes"), ACCEPTED_R25_RAW_BYTES, "raw bytes"),
        (deployable.get("user_bytes"), ACCEPTED_R25_USER_BYTES, "user bytes"),
        (deployable.get("bin"), _DEPLOY_BIN, "deployable BIN path"),
        (deployable.get("cue"), _DEPLOY_CUE, "deployable CUE path"),
    ):
        _expect(actual, expected, label)

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError("R25 report has no artifact inventory")
    by_path = {str(entry.get("path")): entry for entry in artifacts if isinstance(entry, dict)}
    exact_artifacts = {
        "build/srk_diag.bin": (192592, ACCEPTED_R25_BUILD_BIN_SHA256),
        "build/srk_diag.iso": (294912, ACCEPTED_R25_BUILD_ISO_SHA256),
        "build/srk_diag.map": (72516, ACCEPTED_R25_BUILD_MAP_SHA256),
        _DEPLOY_BIN: (338688, ACCEPTED_R25_BIN_SHA256),
        _DEPLOY_CUE: (81, ACCEPTED_R25_CUE_SHA256),
    }
    for relative, (size, expected) in exact_artifacts.items():
        entry = by_path.get(relative)
        if not isinstance(entry, dict):
            raise SaturnMidi68KR25RRCalibrationPreMediaGateError(f"missing accepted artifact: {relative}")
        _expect(entry.get("size"), size, f"reported size {relative}")
        _expect(str(entry.get("sha256", "")).lower(), expected, f"reported hash {relative}")
        path = _file(root, relative, relative)
        _expect(path.stat().st_size, size, f"disk size {relative}")
        _expect(_sha256_file(path), expected, f"disk hash {relative}")

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root, root, destination_name=destination_name, category=category
        )
    except Exception as exc:
        raise SaturnMidi68KR25RRCalibrationPreMediaGateError(
            f"read-only SAROO plan rejected R25 RR16 candidate: {exc}"
        ) from exc
    _expect(plan.bin_sha256.lower(), ACCEPTED_R25_BIN_SHA256, "planned BIN hash")
    _expect(plan.cue_sha256.lower(), ACCEPTED_R25_CUE_SHA256, "planned CUE hash")
    _expect(plan.sector_count, ACCEPTED_R25_SECTOR_COUNT, "planned sectors")
    _expect(plan.raw_bytes, ACCEPTED_R25_RAW_BYTES, "planned raw bytes")

    return SaturnMidi68KR25RRCalibrationPreMediaResult(
        project_root=root,
        baseline_root=baseline,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        calibration_image_sha256=image_sha,
        candidate_main_sha256=ACCEPTED_R25_MAIN_SHA256,
        candidate_menu_sha256=ACCEPTED_R25_MENU_SHA256,
        runtime_after_sha256=ACCEPTED_R25_RUNTIME_SHA256,
        proof_header_sha256=ACCEPTED_R25_PROOF_HEADER_SHA256,
        proof_source_sha256=ACCEPTED_R25_PROOF_SOURCE_SHA256,
        deployable_bin_sha256=ACCEPTED_R25_BIN_SHA256,
        deployable_cue_sha256=ACCEPTED_R25_CUE_SHA256,
        sector_count=ACCEPTED_R25_SECTOR_COUNT,
        raw_bytes=ACCEPTED_R25_RAW_BYTES,
        plan=plan,
    )
