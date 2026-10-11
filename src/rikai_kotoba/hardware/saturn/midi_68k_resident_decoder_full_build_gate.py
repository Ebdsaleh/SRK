"""Fresh off-card inert full-build gate for the post-R19 resident decoder.

The input must be the exact physically accepted R19 callable candidate tree.
This gate preserves that candidate unchanged, adds the exact compiler-accepted
content-independent resident decoder as linked constant data, and runs the
normal standalone builder.  The new decoder is not installed, selected by
reset vectors, executed, or bound to the diagnostic UI.  No SAROO/card path
exists here.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_decoder import (
    SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS,
    SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_decoder_image,
    render_srk_saturn_midi_68k_resident_decoder_header,
    render_srk_saturn_midi_68k_resident_decoder_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentDecoderFullBuildGateError(RuntimeError):
    """Raised when the inert resident-decoder integration cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    image_sha256: str
    image_word_count: int
    image_byte_size: int
    program_address: int
    program_end_address: int
    max_records: int
    source_sha256: str
    header_sha256: str
    compiler_object_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderFullBuildGateResult:
    prepared: SaturnMidi68KResidentDecoderFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_DECODER_SOURCE_NAME = "srk_saturn_midi_68k_resident_decoder.c"
_DECODER_HEADER_NAME = "srk_saturn_midi_68k_resident_decoder.h"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R19_GATE_KEY = "midi_68k_silent_batch_physical_candidate_full_build_gate"
_R19_GATE_SCHEMA = "srk.saturn.midi-68k-silent-batch-physical-candidate-full-build-gate.v1"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K RESIDENT DECODER INERT FULL-BUILD GATE: constant image follows. */"
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
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"cannot read {description}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"{description} root must be an object"
        )
    return value


def _artifact_map(report: dict) -> dict[str, dict]:
    values = report.get("artifacts")
    if not isinstance(values, list):
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 build report has no artifact inventory"
        )
    result: dict[str, dict] = {}
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            result[str(value["path"])] = value
    return result


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 manifest has no generated file inventory"
        )

    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                "accepted R19 generated-file inventory contains an invalid entry"
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
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                "accepted R19 generated-file metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 generated input is missing: {relative}"
            )
        if path.stat().st_size != expected_size:
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 generated input size mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _verify_accepted_r19_candidate(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 candidate must contain its manifest and successful build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    expected_manifest = _require_sha256(
        expected_manifest_sha256, "expected R19 manifest SHA-256"
    )
    expected_report = _require_sha256(
        expected_report_sha256, "expected R19 build-report SHA-256"
    )
    if manifest_sha.lower() != expected_manifest:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"R19 manifest hash mismatch: expected {expected_manifest}, got {manifest_sha}"
        )
    if report_sha.lower() != expected_report:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"R19 build-report hash mismatch: expected {expected_report}, got {report_sha}"
        )

    manifest = _load_json(manifest_path, "accepted R19 manifest")
    report = _load_json(report_path, "accepted R19 build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 manifest schema is unsupported"
        )
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 project is not standalone-master mode"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 build report does not match the current manifest"
        )

    gate = manifest.get(_R19_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R19_GATE_SCHEMA:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "baseline is not the accepted R19 silent-batch physical candidate"
        )
    required_gate = {
        "candidate_define": "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1",
        "candidate_menu_label": "MIDI 68K Batch Proof",
        "expected_read_sequence": 1,
        "expected_read_index": 27,
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
    for key, expected in required_gate.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 candidate gate changed: {key}"
            )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "accepted R19 policy is missing"
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
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 policy changed: {key}"
            )

    generated = _verify_generated_inputs(root, manifest)
    artifacts = _artifact_map(report)
    actual_hashes: list[str] = []
    for relative, expected_value, label in (
        (_DEPLOY_BIN, expected_bin_sha256, "accepted R19 deployable BIN"),
        (_DEPLOY_CUE, expected_cue_sha256, "accepted R19 deployable CUE"),
    ):
        expected = _require_sha256(expected_value, f"expected {label} SHA-256")
        entry = artifacts.get(relative)
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"{label} hash does not match the accepted build report"
            )
        path = root / relative
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"{label} file no longer matches accepted console evidence"
            )
        actual_hashes.append(expected)

    return manifest, generated, manifest_sha, report_sha, actual_hashes[0], actual_hashes[1]


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


def prepare_midi_68k_resident_decoder_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
) -> SaturnMidi68KResidentDecoderFullBuildGatePrepared:
    """Derive a fresh R19-based tree with the general decoder linked but inert."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if not baseline_root.is_dir():
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"accepted R19 baseline is not a directory: {baseline_root}"
        )
    if output_root.exists():
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if baseline_root == output_root or baseline_root in output_root.parents:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "output directory must not be the accepted R19 baseline or its child"
        )

    (
        manifest,
        generated_entries,
        manifest_sha,
        report_sha,
        baseline_bin_sha,
        baseline_cue_sha,
    ) = _verify_accepted_r19_candidate(
        baseline_root,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    expected_image = _require_sha256(expected_image_sha256, "expected resident-decoder image SHA-256")
    if image.sha256.lower() != expected_image:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            f"resident-decoder image hash mismatch: expected {expected_image}, got {image.sha256}"
        )

    source_bytes = render_srk_saturn_midi_68k_resident_decoder_source().encode("utf-8")
    header_bytes = render_srk_saturn_midi_68k_resident_decoder_header().encode("utf-8")
    source_sha = _sha256_bytes(source_bytes)
    header_sha = _sha256_bytes(header_bytes)
    accepted_source_sha = _require_sha256(
        expected_compiler_source_sha256, "expected compiler-accepted source SHA-256"
    )
    accepted_header_sha = _require_sha256(
        expected_compiler_header_sha256, "expected compiler-accepted header SHA-256"
    )
    accepted_object_sha = _require_sha256(
        expected_compiler_object_sha256, "expected compiler-produced object SHA-256"
    )
    if source_sha != accepted_source_sha:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "resident-decoder source no longer matches the compiler-accepted representation"
        )
    if header_sha != accepted_header_sha:
        raise SaturnMidi68KResidentDecoderFullBuildGateError(
            "resident-decoder header no longer matches the compiler-accepted representation"
        )

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
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                f"accepted R19 runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_before = runtime_path.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentDecoderFullBuildGateError(
                "accepted R19 runtime already contains resident-decoder full-build injection"
            )

        (source_dir / _DECODER_SOURCE_NAME).write_bytes(source_bytes)
        (source_dir / _DECODER_HEADER_NAME).write_bytes(header_bytes)

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
        policy["midi_68k_resident_decoder_present"] = True
        policy["midi_68k_resident_decoder_linked"] = True
        policy["midi_68k_resident_decoder_installed"] = False
        policy["midi_68k_resident_decoder_executed"] = False
        policy["midi_68k_resident_decoder_candidate_bound"] = False
        policy["midi_68k_resident_decoder_build_time_hardware_actions"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        candidate_manifest["policy"] = policy
        candidate_manifest["midi_68k_resident_decoder_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-resident-decoder-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "baseline_deploy_bin_sha256": baseline_bin_sha,
            "baseline_deploy_cue_sha256": baseline_cue_sha,
            "existing_r19_candidate_binding_preserved": True,
            "decoder_source_copy": f"src/{_DECODER_SOURCE_NAME}",
            "decoder_header_copy": f"src/{_DECODER_HEADER_NAME}",
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "image_sha256": image.sha256,
            "image_word_count": image.word_count,
            "image_byte_size": image.byte_size,
            "program_address": SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
            "program_end_address": image.end_address,
            "runtime_record_minimum": 1,
            "runtime_record_maximum": SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS,
            "embedded_records": 0,
            "source_sha256": source_sha,
            "header_sha256": header_sha,
            "accepted_compile_object_sha256_evidence": accepted_object_sha,
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "decoder_linked": True,
            "decoder_installed": False,
            "decoder_executed": False,
            "decoder_candidate_bound": False,
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

    return SaturnMidi68KResidentDecoderFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin_sha,
        baseline_cue_sha256=baseline_cue_sha,
        image_sha256=image.sha256,
        image_word_count=image.word_count,
        image_byte_size=image.byte_size,
        program_address=SATURN_MIDI_68K_RESIDENT_DECODER_PROGRAM_ADDRESS,
        program_end_address=image.end_address,
        max_records=SATURN_MIDI_68K_RESIDENT_DECODER_MAX_RECORDS,
        source_sha256=source_sha,
        header_sha256=header_sha,
        compiler_object_sha256=accepted_object_sha,
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_resident_decoder_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
) -> SaturnMidi68KResidentDecoderFullBuildGateResult:
    """Prepare and build the standalone image with the decoder linked but inert."""

    prepared = prepare_midi_68k_resident_decoder_full_build_gate(
        baseline_project,
        output_directory,
        expected_baseline_manifest_sha256=expected_baseline_manifest_sha256,
        expected_baseline_report_sha256=expected_baseline_report_sha256,
        expected_baseline_bin_sha256=expected_baseline_bin_sha256,
        expected_baseline_cue_sha256=expected_baseline_cue_sha256,
        expected_image_sha256=expected_image_sha256,
        expected_compiler_source_sha256=expected_compiler_source_sha256,
        expected_compiler_header_sha256=expected_compiler_header_sha256,
        expected_compiler_object_sha256=expected_compiler_object_sha256,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentDecoderFullBuildGateResult(prepared=prepared, build=build)
