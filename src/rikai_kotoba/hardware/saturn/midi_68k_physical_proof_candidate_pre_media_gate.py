"""Independent read-only pre-media gate for SRK's R18 silent MIDI/68K candidate.

This gate re-opens a completed candidate as an external artifact, independently
revalidates its manifest/build-report/provenance contract and caller-supplied
accepted BIN/CUE hashes, then delegates only to the existing read-only SAROO
standalone deployment planner.

It contains no deployment/apply operation and performs no card writes.
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


class SaturnMidi68KPhysicalProofCandidatePreMediaGateError(RuntimeError):
    """Raised when the R18 candidate cannot pass the independent pre-media gate."""


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCandidatePreMediaResult:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    proof_source_sha256: str
    proof_header_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_GATE_KEY = "midi_68k_physical_proof_candidate_full_build_gate"
_EXPECTED_GATE_SCHEMA = "srk.saturn.midi-68k-physical-proof-candidate-full-build-gate.v1"
_EXPECTED_MAIN = "src/srk_saturn_main.c"
_EXPECTED_MENU = "src/srk_diag_menu.c"
_EXPECTED_PROOF_SOURCE = "src/srk_saturn_midi_68k_physical_proof.c"
_EXPECTED_PROOF_HEADER = "src/srk_saturn_midi_68k_physical_proof.h"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Silent Proof"


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
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"{label} must be exactly 64 hexadecimal SHA-256 characters"
        )
    return normalized


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"{label} path escapes the candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate manifest has no generated file inventory"
        )

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
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
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                "candidate generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        actual_size = path.stat().st_size
        actual_sha = _sha256_file(path)
        if actual_size != expected_size:
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate generated input size mismatch: {relative}; "
                f"expected {expected_size}, got {actual_size}"
            )
        if actual_sha.lower() != expected_sha.lower():
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate generated input hash mismatch: {relative}; "
                f"expected {expected_sha}, got {actual_sha}"
            )

    required = {
        _EXPECTED_MAIN,
        _EXPECTED_MENU,
        _EXPECTED_PROOF_SOURCE,
        _EXPECTED_PROOF_HEADER,
    }
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate generated-file inventory is missing required proof inputs: "
            + ", ".join(missing)
        )


def _verify_candidate_gate(root: Path, manifest: dict) -> tuple[str, str, str, str]:
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _EXPECTED_GATE_SCHEMA:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate manifest has no recognized physical-proof candidate gate"
        )

    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_main": _EXPECTED_MAIN,
        "candidate_menu": _EXPECTED_MENU,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "proof_linked": True,
        "proof_ui_compiled": True,
        "proof_call_path_compiled": True,
        "proof_called_during_build": False,
        "user_trigger_required": True,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "success_read_sequence": 1,
        "success_read_index": 1,
        "success_last_error": 0,
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
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate proof-gate contract mismatch: {key}"
            )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate manifest policy is missing"
        )
    required_policy = {
        "sd_writes": False,
        "midi_68k_physical_proof_linked": True,
        "midi_68k_physical_proof_called": False,
        "midi_68k_physical_proof_candidate_bound": True,
        "midi_68k_physical_proof_user_trigger_required": True,
        "midi_68k_candidate_build_time_hardware_actions": False,
        "midi_68k_runtime_called": False,
        "midi_68k_hardware_adapter_called": False,
        "midi_68k_program_installed": False,
        "midi_68k_reset_vectors_changed": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate policy mismatch: {key}"
            )

    main = _project_file(root, _EXPECTED_MAIN, "candidate main")
    menu = _project_file(root, _EXPECTED_MENU, "candidate menu")
    proof_source = _project_file(root, _EXPECTED_PROOF_SOURCE, "physical-proof source")
    proof_header = _project_file(root, _EXPECTED_PROOF_HEADER, "physical-proof header")

    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate main no longer begins with the physical-proof candidate define"
        )
    for marker in (
        "srk_saturn_midi_68k_physical_proof_begin(&srk_midi_68k_proof)",
        "srk_saturn_midi_68k_physical_proof_poll(&srk_midi_68k_proof)",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "Success: sequence=1 index=1 error=0",
    ):
        if marker not in main_text:
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate main is missing reviewed binding marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "Timing / Interrupt Test" in menu_text:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate menu no longer exposes only the isolated MIDI 68K proof label"
        )

    calculated = {
        "candidate_main_sha256": _sha256_file(main),
        "candidate_menu_sha256": _sha256_file(menu),
        "proof_source_sha256": _sha256_file(proof_source),
        "proof_header_sha256": _sha256_file(proof_header),
    }
    for key, actual in calculated.items():
        expected = gate.get(key)
        if not isinstance(expected, str) or actual.lower() != expected.lower():
            raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
                f"candidate proof-gate provenance hash mismatch: {key}"
            )

    return (
        calculated["candidate_main_sha256"],
        calculated["candidate_menu_sha256"],
        calculated["proof_source_sha256"],
        calculated["proof_header_sha256"],
    )


def _verify_build_report(root: Path, manifest_sha: str) -> tuple[dict, str]:
    report_path = root / _REPORT_NAME
    if not report_path.is_file():
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"candidate build report is missing: {report_path}"
        )
    report = _load_json(report_path, "candidate build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1":
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate build report schema is unsupported"
        )
    if report.get("successful") is not True:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate build report does not match the current candidate manifest"
        )
    return report, _sha256_file(report_path)


def inspect_midi_68k_physical_proof_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KPhysicalProofCandidatePreMediaResult:
    """Revalidate candidate evidence and return a read-only SAROO plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"candidate project is not a directory: {root}"
        )

    expected_bin = _require_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha256(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"candidate manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "candidate manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate manifest schema is unsupported"
        )
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "candidate project is not standalone-master mode"
        )

    manifest_sha = _sha256_file(manifest_path)
    _verify_generated_inventory(root, manifest)
    main_sha, menu_sha, proof_source_sha, proof_header_sha = _verify_candidate_gate(
        root, manifest
    )
    _report, report_sha = _verify_build_report(root, manifest_sha)

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected candidate: {exc}"
        ) from exc

    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "fresh deployable BIN SHA-256 does not match the externally accepted build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KPhysicalProofCandidatePreMediaGateError(
            "fresh deployable CUE SHA-256 does not match the externally accepted build output"
        )

    return SaturnMidi68KPhysicalProofCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        proof_source_sha256=proof_source_sha,
        proof_header_sha256=proof_header_sha,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
