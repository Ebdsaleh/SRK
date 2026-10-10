"""Fresh off-card build gate for SRK's first callable silent MIDI/68K proof image.

The input must be the previously successful inert physical-proof full-build tree.
Only manifest-pinned generated inputs are copied into a new tree.  The candidate
then replaces the standalone main/menu sources with the reviewed guarded binding,
enables that binding only in the derived copy, relabels the isolated placeholder
screen, refreshes the generated-file inventory, and runs the normal standalone
builder.

Preparing or building this candidate performs no Saturn hardware action and has
no SAROO/card deployment path.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidi68KPhysicalProofCandidateFullBuildGateError(RuntimeError):
    """Raised when a physical-proof candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCandidatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    reviewed_main_source_sha256: str
    candidate_main_sha256: str
    reviewed_menu_source_sha256: str
    candidate_menu_sha256: str
    proof_source_sha256: str
    proof_header_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCandidateResult:
    prepared: SaturnMidi68KPhysicalProofCandidatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_MAIN_NAME = "srk_saturn_main.c"
_MENU_NAME = "srk_diag_menu.c"
_PROOF_SOURCE_NAME = "srk_saturn_midi_68k_physical_proof.c"
_PROOF_HEADER_NAME = "srk_saturn_midi_68k_physical_proof.h"
_CANDIDATE_DEFINE = "#define SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE 1"
_OLD_MENU_LABEL = '"Timing / Interrupt Test"'
_NEW_MENU_LABEL = '"MIDI 68K Silent Proof"'


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"cannot read {description}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"{description} root must be an object"
        )
    return value


def _repo_binding_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        standalone = parent / "integrations" / "saturn" / "standalone"
        diagnostics = parent / "integrations" / "saturn" / "diagnostics"
        main = standalone / _MAIN_NAME
        menu = diagnostics / _MENU_NAME
        if main.is_file() and menu.is_file():
            return main, menu
    raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
        "cannot locate reviewed SRK diagnostic-binding main/menu sources"
    )


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline manifest has no generated file inventory"
        )

    verified: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                "baseline generated file inventory contains an invalid entry"
            )
        relative = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or not isinstance(expected_size, int)
            or expected_size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                "baseline generated file inventory metadata is invalid"
            )

        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"baseline generated input is missing: {relative}"
            )
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"baseline generated input size mismatch: {relative}; "
                f"expected {expected_size}, got {actual_size}"
            )
        actual_sha = _sha256_file(path)
        if actual_sha.lower() != expected_sha.lower():
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"baseline generated input hash mismatch: {relative}; "
                f"expected {expected_sha}, got {actual_sha}"
            )
        verified.append(entry)
    return verified


def _verify_inert_physical_proof_baseline(
    root: Path,
) -> tuple[dict, list[dict[str, object]], str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file():
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"baseline manifest is missing: {manifest_path}"
        )
    if not report_path.is_file():
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"baseline build report is missing: {report_path}"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "baseline manifest")
    report = _load_json(report_path, "baseline build report")

    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline manifest schema is unsupported"
        )
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline project is not standalone-master mode"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1":
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline build report schema is unsupported"
        )
    if report.get("successful") is not True:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline full build was not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline build report does not match the current manifest"
        )

    proof_gate = manifest.get("midi_68k_physical_proof_full_build_gate")
    if not isinstance(proof_gate, dict):
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline is not an inert MIDI 68K physical-proof full-build gate"
        )
    required_gate_state = {
        "proof_linked": True,
        "proof_called": False,
        "adapter_linked": True,
        "adapter_called": False,
        "runtime_called": False,
        "installer_called": False,
        "program_installed": False,
        "reset_vectors_changed": False,
        "producer_called": False,
        "smpc_commands_executed": False,
        "sound_ram_runtime_writes": False,
        "mc68ec000_execution": False,
        "behaviorally_active": False,
    }
    for key, expected in required_gate_state.items():
        if proof_gate.get(key) is not expected:
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"baseline physical-proof gate state is not inert: {key}"
            )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "baseline manifest policy is missing"
        )
    required_policy_state = {
        "midi_68k_physical_proof_linked": True,
        "midi_68k_physical_proof_called": False,
        "midi_68k_runtime_called": False,
        "midi_68k_hardware_adapter_called": False,
        "midi_68k_program_installed": False,
        "midi_68k_reset_vectors_changed": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    for key, expected in required_policy_state.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"baseline policy is not at the accepted inert boundary: {key}"
            )

    entries = _verify_generated_inputs(root, manifest)
    return manifest, entries, manifest_sha, report_sha


def _copy_generated_inputs(
    baseline_root: Path,
    staging: Path,
    entries: list[dict[str, object]],
) -> None:
    for entry in entries:
        relative = str(entry["path"])
        source = baseline_root / relative
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _inventory_generated_files(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.name == _MANIFEST_NAME:
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def prepare_midi_68k_physical_proof_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KPhysicalProofCandidatePrepared:
    """Derive one fresh callable-but-off-card silent physical-proof candidate."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if not baseline_root.is_dir():
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"baseline project is not a directory: {baseline_root}"
        )
    if output_root.exists():
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if baseline_root == output_root or baseline_root in output_root.parents:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "output directory must not be the baseline or a child of the accepted baseline"
        )

    manifest, generated_entries, manifest_sha, report_sha = (
        _verify_inert_physical_proof_baseline(baseline_root)
    )
    reviewed_main_path, reviewed_menu_path = _repo_binding_paths()
    reviewed_main = reviewed_main_path.read_text(encoding="utf-8")
    reviewed_menu = reviewed_menu_path.read_text(encoding="utf-8")

    required_main_markers = (
        "SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE",
        '#include "srk_saturn_midi_68k_physical_proof.h"',
        "SRK_DIAG_SCREEN_TIMING_INTERRUPT_TEST",
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 1u",
        "SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_physical_proof_reset",
        "SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_physical_proof_begin",
        "SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_physical_proof_poll",
        "Success: sequence=1 index=1 error=0",
    )
    for marker in required_main_markers:
        if marker not in reviewed_main:
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                f"reviewed diagnostic binding is missing required marker: {marker}"
            )
    if _CANDIDATE_DEFINE in reviewed_main:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "reviewed repository main unexpectedly enables the physical-proof candidate"
        )
    if reviewed_menu.count(_OLD_MENU_LABEL) != 1:
        raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
            "reviewed diagnostics menu no longer has exactly one isolated placeholder label"
        )

    candidate_main = _CANDIDATE_DEFINE + "\n" + reviewed_main
    candidate_menu = reviewed_menu.replace(_OLD_MENU_LABEL, _NEW_MENU_LABEL, 1)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    staging.mkdir()
    try:
        _copy_generated_inputs(baseline_root, staging, generated_entries)

        source_dir = staging / "src"
        source_dir.mkdir(parents=True, exist_ok=True)
        main_path = source_dir / _MAIN_NAME
        menu_path = source_dir / _MENU_NAME
        main_path.write_text(candidate_main, encoding="utf-8", newline="\n")
        menu_path.write_text(candidate_menu, encoding="utf-8", newline="\n")

        proof_source = source_dir / _PROOF_SOURCE_NAME
        proof_header = source_dir / _PROOF_HEADER_NAME
        if not proof_source.is_file() or not proof_header.is_file():
            raise SaturnMidi68KPhysicalProofCandidateFullBuildGateError(
                "accepted inert baseline is missing the pinned physical-proof source/header"
            )

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy["sd_writes"] = False
        policy["midi_68k_physical_proof_linked"] = True
        policy["midi_68k_physical_proof_called"] = False
        policy["midi_68k_physical_proof_candidate_bound"] = True
        policy["midi_68k_physical_proof_user_trigger_required"] = True
        policy["midi_68k_candidate_build_time_hardware_actions"] = False
        policy["midi_68k_runtime_called"] = False
        policy["midi_68k_hardware_adapter_called"] = False
        policy["midi_68k_program_installed"] = False
        policy["midi_68k_reset_vectors_changed"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        candidate_manifest["policy"] = policy

        candidate_manifest["midi_68k_physical_proof_candidate_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-physical-proof-candidate-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "candidate_define": _CANDIDATE_DEFINE,
            "candidate_main": f"src/{_MAIN_NAME}",
            "candidate_menu": f"src/{_MENU_NAME}",
            "candidate_menu_label": _NEW_MENU_LABEL.strip('"'),
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
            "reviewed_main_source_sha256": _sha256_bytes(reviewed_main.encode("utf-8")),
            "candidate_main_sha256": _sha256_bytes(candidate_main.encode("utf-8")),
            "reviewed_menu_source_sha256": _sha256_bytes(reviewed_menu.encode("utf-8")),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu.encode("utf-8")),
            "proof_source_sha256": _sha256_file(proof_source),
            "proof_header_sha256": _sha256_file(proof_header),
        }
        candidate_manifest["generated_files"] = _inventory_generated_files(staging)
        (staging / _MANIFEST_NAME).write_text(
            json.dumps(candidate_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        staging.replace(output_root)
        temporary_parent.rmdir()
    except BaseException:
        shutil.rmtree(temporary_parent, ignore_errors=True)
        raise

    return SaturnMidi68KPhysicalProofCandidatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        reviewed_main_source_sha256=_sha256_bytes(reviewed_main.encode("utf-8")),
        candidate_main_sha256=_sha256_bytes(candidate_main.encode("utf-8")),
        reviewed_menu_source_sha256=_sha256_bytes(reviewed_menu.encode("utf-8")),
        candidate_menu_sha256=_sha256_bytes(candidate_menu.encode("utf-8")),
        proof_source_sha256=_sha256_file(output_root / "src" / _PROOF_SOURCE_NAME),
        proof_header_sha256=_sha256_file(output_root / "src" / _PROOF_HEADER_NAME),
    )


def run_midi_68k_physical_proof_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KPhysicalProofCandidateResult:
    """Build the explicit callable silent proof in a fresh off-card tree."""

    prepared = prepare_midi_68k_physical_proof_candidate_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KPhysicalProofCandidateResult(prepared=prepared, build=build)
