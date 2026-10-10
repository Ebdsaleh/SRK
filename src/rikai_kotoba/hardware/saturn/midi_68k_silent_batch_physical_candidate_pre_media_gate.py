"""Independent read-only pre-media gate for SRK's R19 silent 27-record MIDI/68K candidate.

The gate re-opens a completed callable candidate as an external artifact,
revalidates its manifest/build report, the compiler-accepted batch image
provenance, candidate binding/runtime seams and externally accepted BIN/CUE
hashes, then delegates only to the existing read-only SAROO deployment planner.

It contains no apply operation and performs no card writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when the R19 candidate cannot pass the independent pre-media gate."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    installer_source_sha256: str
    installer_header_sha256: str
    batch_runtime_source_sha256: str
    batch_runtime_header_sha256: str
    proof_header_sha256: str
    runtime_after_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_INERT_GATE_KEY = "midi_68k_silent_batch_full_build_gate"
_CANDIDATE_GATE_KEY = "midi_68k_silent_batch_physical_candidate_full_build_gate"
_EXPECTED_INERT_SCHEMA = "srk.saturn.midi-68k-silent-batch-full-build-gate.v1"
_EXPECTED_CANDIDATE_SCHEMA = (
    "srk.saturn.midi-68k-silent-batch-physical-candidate-full-build-gate.v1"
)
_EXPECTED_MAIN = "src/srk_saturn_main.c"
_EXPECTED_MENU = "src/srk_diag_menu.c"
_EXPECTED_RUNTIME = "src/srk_saturn_runtime.c"
_EXPECTED_INSTALLER_SOURCE = "src/srk_saturn_midi_68k_silent_batch_installer.c"
_EXPECTED_INSTALLER_HEADER = "src/srk_saturn_midi_68k_silent_batch_installer.h"
_EXPECTED_BATCH_RUNTIME_SOURCE = "src/srk_saturn_midi_68k_silent_batch_runtime.c"
_EXPECTED_BATCH_RUNTIME_HEADER = "src/srk_saturn_midi_68k_silent_batch_runtime.h"
_EXPECTED_PROOF_HEADER = "src/srk_saturn_midi_68k_physical_proof.h"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Batch Proof"
_EXPECTED_RECORDS = 27


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


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
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"{label} must be exactly 64 hexadecimal SHA-256 characters"
        )
    return normalized


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"{label} path escapes the candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate manifest has no generated file inventory"
        )

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                "candidate generated-file inventory contains an invalid entry"
            )
        relative = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(expected_size, int)
            or expected_size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                "candidate generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        actual_size = path.stat().st_size
        actual_sha = _sha256_file(path)
        if actual_size != expected_size:
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate generated input size mismatch: {relative}; "
                f"expected {expected_size}, got {actual_size}"
            )
        if actual_sha.lower() != expected_sha.lower():
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate generated input hash mismatch: {relative}; "
                f"expected {expected_sha}, got {actual_sha}"
            )

    required = {
        _EXPECTED_MAIN,
        _EXPECTED_MENU,
        _EXPECTED_RUNTIME,
        _EXPECTED_INSTALLER_SOURCE,
        _EXPECTED_INSTALLER_HEADER,
        _EXPECTED_BATCH_RUNTIME_SOURCE,
        _EXPECTED_BATCH_RUNTIME_HEADER,
        _EXPECTED_PROOF_HEADER,
    }
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate generated-file inventory is missing required R19 inputs: "
            + ", ".join(missing)
        )


def _verify_image_provenance(manifest: dict, expected_image_sha256: str) -> str:
    gate = manifest.get(_INERT_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _EXPECTED_INERT_SCHEMA:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate no longer carries the inert silent-batch provenance gate"
        )
    expected = _require_sha256(expected_image_sha256, "expected silent-batch image SHA-256")
    actual = str(gate.get("image_sha256", "")).lower()
    if actual != expected:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate silent-batch image hash no longer matches the externally accepted image"
        )
    if gate.get("expected_records") != _EXPECTED_RECORDS:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate inert provenance no longer describes the accepted 27-record image"
        )
    return actual


def _verify_candidate_gate(root: Path, manifest: dict) -> tuple[str, ...]:
    gate = manifest.get(_CANDIDATE_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _EXPECTED_CANDIDATE_SCHEMA:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate manifest has no recognized R19 physical-candidate gate"
        )

    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "expected_read_sequence": 1,
        "expected_read_index": _EXPECTED_RECORDS,
        "expected_last_error": 0,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "batch_program_linked": True,
        "batch_program_installed_during_build": False,
        "batch_program_executed_during_build": False,
        "batch_candidate_bound": True,
        "midi_scsp_note_attempted": False,
        "build_time_smpc_commands": False,
        "build_time_sound_ram_writes": False,
        "build_time_mc68ec000_execution": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate R19 gate contract mismatch: {key}"
            )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate manifest policy is missing"
        )
    required_policy = {
        "sd_writes": False,
        "midi_68k_silent_batch_program_present": True,
        "midi_68k_silent_batch_program_linked": True,
        "midi_68k_silent_batch_program_installed": False,
        "midi_68k_silent_batch_program_executed": False,
        "midi_68k_silent_batch_candidate_bound": True,
        "midi_68k_silent_batch_user_trigger_required": True,
        "midi_68k_silent_batch_build_time_hardware_actions": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate policy mismatch: {key}"
            )

    files = {
        "candidate_main_sha256": _project_file(root, _EXPECTED_MAIN, "candidate main"),
        "candidate_menu_sha256": _project_file(root, _EXPECTED_MENU, "candidate menu"),
        "installer_source_sha256": _project_file(root, _EXPECTED_INSTALLER_SOURCE, "batch installer source"),
        "installer_header_sha256": _project_file(root, _EXPECTED_INSTALLER_HEADER, "batch installer header"),
        "batch_runtime_source_sha256": _project_file(root, _EXPECTED_BATCH_RUNTIME_SOURCE, "batch runtime source"),
        "batch_runtime_header_sha256": _project_file(root, _EXPECTED_BATCH_RUNTIME_HEADER, "batch runtime header"),
        "proof_header_sha256": _project_file(root, _EXPECTED_PROOF_HEADER, "physical-proof header"),
        "runtime_after_sha256": _project_file(root, _EXPECTED_RUNTIME, "candidate runtime"),
    }

    main_text = files["candidate_main_sha256"].read_text(encoding="utf-8")
    menu_text = files["candidate_menu_sha256"].read_text(encoding="utf-8")
    runtime_text = files["runtime_after_sha256"].read_text(encoding="utf-8")
    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate main no longer begins with the R19 candidate define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u",
        "srk_saturn_midi_68k_silent_batch_physical_proof_begin",
        "srk_saturn_midi_68k_silent_batch_physical_proof_poll",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "Success: sequence=1 index=27 error=0",
    ):
        if marker not in main_text:
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate main is missing reviewed R19 binding marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "Timing / Interrupt Test" in menu_text:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate menu no longer exposes only the isolated R19 proof label"
        )
    for marker in (
        "srk_saturn_midi_68k_silent_batch_install_while_stopped",
        "srk_saturn_midi_68k_silent_batch_protocol_begin",
        "srk_saturn_midi_68k_silent_batch_protocol_poll",
        "srk_saturn_midi_68k_silent_batch_physical_proof_reset",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate runtime is missing reviewed R19 seam: {marker}"
            )

    calculated: list[str] = []
    for key, path in files.items():
        actual = _sha256_file(path)
        expected = gate.get(key)
        if not isinstance(expected, str) or actual.lower() != expected.lower():
            raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
                f"candidate R19 provenance hash mismatch: {key}"
            )
        calculated.append(actual)
    return tuple(calculated)


def _verify_build_report(root: Path, manifest_sha: str) -> tuple[dict, str]:
    report_path = root / _REPORT_NAME
    if not report_path.is_file():
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"candidate build report is missing: {report_path}"
        )
    report = _load_json(report_path, "candidate build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1":
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate build report schema is unsupported"
        )
    if report.get("successful") is not True:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate build report does not match the current candidate manifest"
        )
    return report, _sha256_file(report_path)


def inspect_midi_68k_silent_batch_physical_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult:
    """Revalidate the completed R19 candidate and return a read-only SAROO plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"candidate project is not a directory: {root}"
        )

    expected_bin = _require_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha256(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"candidate manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "candidate manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate manifest schema is unsupported"
        )
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "candidate project is not standalone-master mode"
        )

    manifest_sha = _sha256_file(manifest_path)
    _verify_generated_inventory(root, manifest)
    image_sha = _verify_image_provenance(manifest, expected_image_sha256)
    (
        main_sha,
        menu_sha,
        installer_source_sha,
        installer_header_sha,
        batch_runtime_source_sha,
        batch_runtime_header_sha,
        proof_header_sha,
        runtime_after_sha,
    ) = _verify_candidate_gate(root, manifest)
    _report, report_sha = _verify_build_report(root, manifest_sha)

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected candidate: {exc}"
        ) from exc

    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "fresh deployable BIN SHA-256 does not match the externally accepted R19 build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KSilentBatchPhysicalCandidatePreMediaGateError(
            "fresh deployable CUE SHA-256 does not match the externally accepted R19 build output"
        )

    return SaturnMidi68KSilentBatchPhysicalCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        installer_source_sha256=installer_source_sha,
        installer_header_sha256=installer_header_sha,
        batch_runtime_source_sha256=batch_runtime_source_sha,
        batch_runtime_header_sha256=batch_runtime_header_sha,
        proof_header_sha256=proof_header_sha,
        runtime_after_sha256=runtime_after_sha,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
