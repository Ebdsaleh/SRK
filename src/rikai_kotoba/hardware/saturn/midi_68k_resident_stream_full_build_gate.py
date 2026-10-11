"""Fresh inert standalone integration for the continuous MIDI 68K stream service.

The baseline is the physically accepted R21 full-state candidate.  Its callable
proof remains byte-for-byte preserved while the new resident stream image and
SH-2 refill/timebase producer are linked only as inert code/data.  Nothing in
this gate installs or executes the new MC68EC000 image.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_stream_service import (
    SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
)
from .midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentStreamFullBuildGateError(RuntimeError):
    """Raised when the continuous-service inert integration cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    image_sha256: str
    image_word_count: int
    image_byte_size: int
    program_end_address: int
    resident_source_sha256: str
    resident_header_sha256: str
    producer_source_sha256: str
    producer_header_sha256: str
    resident_object_sha256: str
    producer_object_sha256: str
    r21_main_sha256: str
    r21_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamFullBuildGateResult:
    prepared: SaturnMidi68KResidentStreamFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_RESIDENT_SOURCE = "src/srk_saturn_midi_68k_resident_stream_service.c"
_RESIDENT_HEADER = "src/srk_saturn_midi_68k_resident_stream_service.h"
_PRODUCER_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_PRODUCER_HEADER = "src/srk_saturn_midi_68k_stream_service.h"
_R21_GATE_KEY = "midi_68k_resident_state_decoder_physical_candidate_full_build_gate"
_R21_GATE_SCHEMA = "srk.saturn.midi-68k-resident-state-decoder-physical-candidate-full-build-gate.v1"
_GATE_KEY = "midi_68k_resident_stream_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-stream-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K RESIDENT STREAM INERT FULL-BUILD GATE: generated service follows. */"


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


def _require_sha(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStreamFullBuildGateError(f"{label} root must be an object")
    return value


def _inventory(root: Path) -> list[dict[str, object]]:
    values = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if path.is_file() and path.name != _MANIFEST:
            values.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return values


def _verify_generated(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            "R21 manifest has no generated-file inventory"
        )
    verified = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentStreamFullBuildGateError("invalid R21 generated entry")
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
        ):
            raise SaturnMidi68KResidentStreamFullBuildGateError(
                "invalid or duplicate R21 generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != expected_size:
            raise SaturnMidi68KResidentStreamFullBuildGateError(
                f"R21 generated input size/path mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentStreamFullBuildGateError(
                f"R21 generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            "R21 report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_r21(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_runtime_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            "R21 baseline must contain manifest and successful build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    if manifest_sha != _require_sha(expected_manifest_sha256, "expected R21 manifest"):
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 manifest hash mismatch")
    if report_sha != _require_sha(expected_report_sha256, "expected R21 report"):
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 report hash mismatch")

    manifest = _load_json(manifest_path, "R21 manifest")
    report = _load_json(report_path, "R21 report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 manifest identity changed")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 build report is not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 report no longer matches manifest")

    gate = manifest.get(_R21_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R21_GATE_SCHEMA:
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            "baseline is not the reviewed R21 full-state candidate"
        )
    required = {
        "candidate_menu_label": "MIDI 68K State Proof",
        "expected_read_sequence": 1,
        "expected_read_index": 20,
        "expected_last_error": 0,
        "proof_records": 20,
        "proof_final_time_us": 20000,
        "proof_covers_every_srkm_v1_opcode": True,
        "state_verification_required": True,
        "state_summary_words_verified": 256,
        "controller_words_verified": 1024,
        "active_note_words_verified": 128,
        "state_decoder_candidate_bound": True,
        "midi_scsp_note_attempted": False,
        "build_time_smpc_commands": False,
        "build_time_sound_ram_writes": False,
        "build_time_mc68ec000_execution": False,
        "saroo_write": False,
        "off_card_only": True,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentStreamFullBuildGateError(f"R21 gate changed: {key}")

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted = []
    for relative, provided, label in (
        (_DEPLOY_BIN, expected_bin_sha256, "R21 BIN"),
        (_DEPLOY_CUE, expected_cue_sha256, "R21 CUE"),
    ):
        expected = _require_sha(provided, f"expected {label}")
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentStreamFullBuildGateError(f"{label} report hash changed")
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentStreamFullBuildGateError(f"{label} disk hash changed")
        accepted.append(expected)

    main_sha = _sha256_file(root / _MAIN)
    menu_sha = _sha256_file(root / _MENU)
    if main_sha.lower() != str(gate.get("candidate_main_sha256", "")).lower():
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 main hash changed")
    if menu_sha.lower() != str(gate.get("candidate_menu_sha256", "")).lower():
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 menu hash changed")
    runtime_sha = _sha256_file(root / _RUNTIME)
    if runtime_sha != _require_sha(expected_runtime_sha256, "expected R21 runtime"):
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 runtime hash mismatch")
    if runtime_sha.lower() != str(gate.get("runtime_after_sha256", "")).lower():
        raise SaturnMidi68KResidentStreamFullBuildGateError("R21 gate/runtime hash mismatch")

    return (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        accepted[0],
        accepted[1],
        main_sha,
        menu_sha,
        runtime_sha,
    )


def prepare_midi_68k_resident_stream_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_baseline_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> SaturnMidi68KResidentStreamFullBuildGatePrepared:
    """Create a fresh inert stream-service tree from exact physical R21 evidence."""

    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            f"R21 baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        baseline_bin,
        baseline_cue,
        main_sha,
        menu_sha,
        runtime_sha,
    ) = _verify_r21(
        baseline,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_runtime_sha256=expected_baseline_runtime_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    if image.sha256 != _require_sha(expected_image_sha256, "expected stream image"):
        raise SaturnMidi68KResidentStreamFullBuildGateError("stream image hash mismatch")

    resident_source = render_srk_saturn_midi_68k_resident_stream_service_source().encode("utf-8")
    resident_header = render_srk_saturn_midi_68k_resident_stream_service_header().encode("utf-8")
    producer_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    producer_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
    generated_hashes = {
        "resident_source": _sha256_bytes(resident_source),
        "resident_header": _sha256_bytes(resident_header),
        "producer_source": _sha256_bytes(producer_source),
        "producer_header": _sha256_bytes(producer_header),
    }
    expected_hashes = {
        "resident_source": _require_sha(expected_resident_source_sha256, "resident source"),
        "resident_header": _require_sha(expected_resident_header_sha256, "resident header"),
        "producer_source": _require_sha(expected_producer_source_sha256, "producer source"),
        "producer_header": _require_sha(expected_producer_header_sha256, "producer header"),
    }
    if generated_hashes != expected_hashes:
        raise SaturnMidi68KResidentStreamFullBuildGateError(
            "stream generated representation no longer matches compiler evidence"
        )
    resident_object = _require_sha(expected_resident_object_sha256, "resident object")
    producer_object = _require_sha(expected_producer_object_sha256, "producer object")

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

        runtime_path = staging / _RUNTIME
        runtime_before = runtime_path.read_bytes()
        if _sha256_bytes(runtime_before) != runtime_sha:
            raise SaturnMidi68KResidentStreamFullBuildGateError(
                "R21 runtime changed during staging"
            )
        marker = _MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentStreamFullBuildGateError(
                "R21 runtime already contains stream-service inert injection"
            )

        (staging / _RESIDENT_SOURCE).write_bytes(resident_source)
        (staging / _RESIDENT_HEADER).write_bytes(resident_header)
        (staging / _PRODUCER_SOURCE).write_bytes(producer_source)
        (staging / _PRODUCER_HEADER).write_bytes(producer_header)

        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n" + resident_source + b"\n" + producer_source
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate = dict(manifest)
        policy = dict(candidate.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_resident_stream_present": True,
                "midi_68k_resident_stream_linked": True,
                "midi_68k_resident_stream_installed": False,
                "midi_68k_resident_stream_executed": False,
                "midi_68k_resident_stream_candidate_bound": False,
                "midi_68k_stream_producer_linked": True,
                "midi_68k_stream_producer_invoked": False,
                "midi_sound_ram_writes": False,
                "midi_scsp_mmio": False,
                "midi_smpc_commands": False,
                "midi_mc68ec000_execution": False,
            }
        )
        candidate["policy"] = policy
        candidate[_GATE_KEY] = {
            "schema": _GATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "baseline_deploy_bin_sha256": baseline_bin,
            "baseline_deploy_cue_sha256": baseline_cue,
            "existing_r21_candidate_binding_preserved": True,
            "r21_main_sha256": main_sha,
            "r21_menu_sha256": menu_sha,
            "r21_runtime_sha256": runtime_sha,
            "resident_source_copy": _RESIDENT_SOURCE,
            "resident_header_copy": _RESIDENT_HEADER,
            "producer_source_copy": _PRODUCER_SOURCE,
            "producer_header_copy": _PRODUCER_HEADER,
            "compile_injection": _RUNTIME,
            "image_sha256": image.sha256,
            "image_word_count": image.word_count,
            "image_byte_size": image.byte_size,
            "program_address": SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
            "program_end_address": image.end_address,
            "queue_capacity": 32,
            "multi_batch_refill": True,
            "strict_sequence_service": True,
            "timestamp_scheduler": True,
            "published_clock_seqlock": True,
            "state_persistent_across_refills": True,
            "resident_source_sha256": generated_hashes["resident_source"],
            "resident_header_sha256": generated_hashes["resident_header"],
            "producer_source_sha256": generated_hashes["producer_source"],
            "producer_header_sha256": generated_hashes["producer_header"],
            "accepted_resident_object_sha256_evidence": resident_object,
            "accepted_producer_object_sha256_evidence": producer_object,
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "resident_stream_linked": True,
            "resident_stream_installed": False,
            "resident_stream_executed": False,
            "resident_stream_candidate_bound": False,
            "producer_linked": True,
            "producer_invoked": False,
            "midi_scsp_note_attempted": False,
            "build_time_hardware_io": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
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

    return SaturnMidi68KResidentStreamFullBuildGatePrepared(
        baseline_root=baseline,
        output_root=output,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin,
        baseline_cue_sha256=baseline_cue,
        image_sha256=image.sha256,
        image_word_count=image.word_count,
        image_byte_size=image.byte_size,
        program_end_address=image.end_address,
        resident_source_sha256=generated_hashes["resident_source"],
        resident_header_sha256=generated_hashes["resident_header"],
        producer_source_sha256=generated_hashes["producer_source"],
        producer_header_sha256=generated_hashes["producer_header"],
        resident_object_sha256=resident_object,
        producer_object_sha256=producer_object,
        r21_main_sha256=main_sha,
        r21_menu_sha256=menu_sha,
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_resident_stream_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs,
) -> SaturnMidi68KResidentStreamFullBuildGateResult:
    prepared = prepare_midi_68k_resident_stream_full_build_gate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentStreamFullBuildGateResult(prepared=prepared, build=build)
