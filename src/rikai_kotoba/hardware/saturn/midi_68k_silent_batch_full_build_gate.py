"""Fresh off-card full-build gate for SRK's silent full-batch MC68EC000 image.

The gate derives from the exact accepted R18 callable candidate tree, preserves
that candidate's existing UI/runtime binding unchanged, and only adds the new
silent 27-record MC68EC000 image as linked constant data.  The batch image is
not installed, selected by reset vectors, executed, or allowed to touch SCSP.
No SAROO/card deployment path exists here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_silent_batch_consumer import (
    SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_silent_batch_consumer_image,
    render_srk_saturn_midi_68k_silent_batch_header,
    render_srk_saturn_midi_68k_silent_batch_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KSilentBatchFullBuildGateError(RuntimeError):
    """Raised when the silent full-batch standalone integration gate is unsafe."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    image_sha256: str
    image_word_count: int
    image_byte_size: int
    program_address: int
    program_end_address: int
    expected_records: int
    source_sha256: str
    header_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchFullBuildGateResult:
    prepared: SaturnMidi68KSilentBatchFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_BATCH_SOURCE_NAME = "srk_saturn_midi_68k_silent_batch_program.c"
_BATCH_HEADER_NAME = "srk_saturn_midi_68k_silent_batch_program.h"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K SILENT FULL-BATCH INERT FULL-BUILD GATE: constant image follows. */"
)


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


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"cannot read {description}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"{description} root must be an object"
        )
    return value


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            "accepted R18 manifest has no generated file inventory"
        )

    verified: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                "accepted R18 inventory contains an invalid entry"
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
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                "accepted R18 generated-file metadata is invalid"
            )
        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 generated input is missing: {relative}"
            )
        if path.stat().st_size != expected_size:
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 generated input size mismatch: {relative}"
            )
        actual_sha = _sha256_file(path)
        if actual_sha.lower() != expected_sha.lower():
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _verify_accepted_r18_candidate(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            "accepted R18 candidate must contain both manifest and successful build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    if manifest_sha.lower() != _require_sha256(expected_manifest_sha256, "expected R18 manifest SHA-256"):
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"R18 manifest hash mismatch: expected {expected_manifest_sha256}, got {manifest_sha}"
        )
    if report_sha.lower() != _require_sha256(expected_report_sha256, "expected R18 build-report SHA-256"):
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"R18 build-report hash mismatch: expected {expected_report_sha256}, got {report_sha}"
        )

    manifest = _load_json(manifest_path, "accepted R18 manifest")
    report = _load_json(report_path, "accepted R18 build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KSilentBatchFullBuildGateError("R18 manifest schema is unsupported")
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KSilentBatchFullBuildGateError("R18 project is not standalone-master mode")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KSilentBatchFullBuildGateError("R18 baseline build was not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            "R18 build report does not match the accepted manifest"
        )

    gate = manifest.get("midi_68k_physical_proof_candidate_full_build_gate")
    if not isinstance(gate, dict):
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            "baseline is not the callable R18 MIDI/68K physical-proof candidate"
        )
    required_gate = {
        "proof_linked": True,
        "proof_ui_compiled": True,
        "proof_call_path_compiled": True,
        "proof_called_during_build": False,
        "user_trigger_required": True,
        "trigger_requires_release_after_screen_entry": True,
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
    for key, expected in required_gate.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 candidate gate state changed: {key}"
            )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KSilentBatchFullBuildGateError("R18 manifest policy is missing")
    required_policy = {
        "sd_writes": False,
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
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 policy changed at build-time boundary: {key}"
            )

    return manifest, _verify_generated_inputs(root, manifest), manifest_sha, report_sha


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


def prepare_midi_68k_silent_batch_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_image_sha256: str,
) -> SaturnMidi68KSilentBatchFullBuildGatePrepared:
    """Derive a fresh full-build tree with the new batch image linked but inert."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if not baseline_root.is_dir():
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"accepted R18 baseline is not a directory: {baseline_root}"
        )
    if output_root.exists():
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if baseline_root == output_root or baseline_root in output_root.parents:
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            "output directory must not be the accepted R18 baseline or its child"
        )

    manifest, generated_entries, manifest_sha, report_sha = _verify_accepted_r18_candidate(
        baseline_root,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
    )

    image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
    expected_image = _require_sha256(expected_image_sha256, "expected silent-batch image SHA-256")
    if image.sha256.lower() != expected_image:
        raise SaturnMidi68KSilentBatchFullBuildGateError(
            f"silent-batch image hash mismatch: expected {expected_image}, got {image.sha256}"
        )
    header_text = render_srk_saturn_midi_68k_silent_batch_header()
    source_text = render_srk_saturn_midi_68k_silent_batch_source()
    header_bytes = header_text.encode("utf-8")
    source_bytes = source_text.encode("utf-8")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    staging.mkdir()
    try:
        _copy_generated_inputs(baseline_root, staging, generated_entries)
        source_dir = staging / "src"
        runtime_path = source_dir / _RUNTIME_NAME
        if not runtime_path.is_file():
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                f"accepted R18 runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_before = runtime_path.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KSilentBatchFullBuildGateError(
                "accepted R18 runtime already contains silent-batch full-build injection"
            )

        (source_dir / _BATCH_HEADER_NAME).write_bytes(header_bytes)
        (source_dir / _BATCH_SOURCE_NAME).write_bytes(source_bytes)

        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n" + source_bytes
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy["sd_writes"] = False
        policy["midi_68k_silent_batch_program_present"] = True
        policy["midi_68k_silent_batch_program_linked"] = True
        policy["midi_68k_silent_batch_program_installed"] = False
        policy["midi_68k_silent_batch_program_executed"] = False
        policy["midi_68k_silent_batch_candidate_bound"] = False
        policy["midi_68k_silent_batch_build_time_hardware_actions"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        candidate_manifest["policy"] = policy
        candidate_manifest["midi_68k_silent_batch_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-silent-batch-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "existing_r18_candidate_binding_preserved": True,
            "batch_program_source_copy": f"src/{_BATCH_SOURCE_NAME}",
            "batch_program_header_copy": f"src/{_BATCH_HEADER_NAME}",
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "image_sha256": image.sha256,
            "image_word_count": len(image.words),
            "image_byte_size": image.byte_size,
            "program_address": SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS,
            "program_end_address": image.end_address,
            "expected_records": image.expected_records,
            "queue_word_count": image.queue_word_count,
            "source_sha256": _sha256_bytes(source_bytes),
            "header_sha256": _sha256_bytes(header_bytes),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "batch_program_linked": True,
            "batch_program_installed": False,
            "batch_program_executed": False,
            "batch_candidate_bound": False,
            "midi_scsp_note_attempted": False,
            "build_time_smpc_commands": False,
            "build_time_sound_ram_writes": False,
            "build_time_mc68ec000_execution": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
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

    return SaturnMidi68KSilentBatchFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        image_sha256=image.sha256,
        image_word_count=len(image.words),
        image_byte_size=image.byte_size,
        program_address=SATURN_MIDI_68K_SILENT_BATCH_PROGRAM_ADDRESS,
        program_end_address=image.end_address,
        expected_records=image.expected_records,
        source_sha256=_sha256_bytes(source_bytes),
        header_sha256=_sha256_bytes(header_bytes),
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_silent_batch_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_image_sha256: str,
) -> SaturnMidi68KSilentBatchFullBuildGateResult:
    """Prepare and build the standalone image with the new batch program inert."""

    prepared = prepare_midi_68k_silent_batch_full_build_gate(
        baseline_project,
        output_directory,
        expected_baseline_manifest_sha256=expected_baseline_manifest_sha256,
        expected_baseline_report_sha256=expected_baseline_report_sha256,
        expected_image_sha256=expected_image_sha256,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KSilentBatchFullBuildGateResult(prepared=prepared, build=build)
