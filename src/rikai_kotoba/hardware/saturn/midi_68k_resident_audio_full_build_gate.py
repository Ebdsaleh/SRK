"""Fresh inert standalone integration for R23 MIDI-driven SCSP audio.

R22A is the immutable physical stream/scheduler baseline.  This gate derives a
new standalone tree from the exact accepted R22A candidate, preserves its
callable physical proof byte-for-byte, and links the compiler-accepted R23
resident audio image only as inert data.  It never installs or executes the new
MC68EC000 image and performs no hardware I/O or SAROO writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_audio_service import (
    SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_audio_service_image,
    render_srk_saturn_midi_68k_resident_audio_service_header,
    render_srk_saturn_midi_68k_resident_audio_service_source,
    render_srk_saturn_midi_68k_resident_audio_voice_header,
)
from .midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .midi_68k_voice_allocator import (
    SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
    SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_HOLD_US,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_OWNED_SLOTS,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentAudioFullBuildGateError(RuntimeError):
    """Raised when R23 inert standalone integration cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioFullBuildGatePrepared:
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
    voice_header_sha256: str
    producer_source_sha256: str
    producer_header_sha256: str
    resident_object_sha256: str
    producer_object_sha256: str
    r22a_main_sha256: str
    r22a_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioFullBuildGateResult:
    prepared: SaturnMidi68KResidentAudioFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R22A_PROOF_SOURCE = "src/srk_saturn_midi_68k_stream_physical_proof.c"
_R22A_PROOF_HEADER = "src/srk_saturn_midi_68k_stream_physical_proof.h"
_PRODUCER_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_PRODUCER_HEADER = "src/srk_saturn_midi_68k_stream_service.h"
_AUDIO_SOURCE = "src/srk_saturn_midi_68k_resident_audio_service.c"
_AUDIO_HEADER = "src/srk_saturn_midi_68k_resident_audio_service.h"
_VOICE_HEADER = "src/srk_saturn_midi_68k_voice_state.h"
_R22A_GATE_KEY = "midi_68k_resident_stream_physical_candidate_full_build_gate"
_R22A_GATE_SCHEMA = "srk.saturn.midi-68k-resident-stream-physical-candidate-full-build-gate.v1"
_GATE_KEY = "midi_68k_resident_audio_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K R23 AUDIO INERT FULL-BUILD GATE: generated service follows. */"


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
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            f"{label} root must be an object"
        )
    return value


def _inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
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
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A baseline has no generated-file inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                "invalid R22A generated-file entry"
            )
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
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                "invalid or duplicate R22A generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size:
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                f"R22A generated input size/path mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                f"R22A generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A build report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_r22a(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_runtime_sha256: str,
    expected_main_sha256: str,
    expected_menu_sha256: str,
    expected_proof_source_sha256: str,
    expected_proof_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A baseline must contain manifest and successful build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    if manifest_sha != _require_sha(expected_manifest_sha256, "expected R22A manifest"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A manifest hash mismatch")
    if report_sha != _require_sha(expected_report_sha256, "expected R22A report"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A report hash mismatch")

    manifest = _load_json(manifest_path, "R22A manifest")
    report = _load_json(report_path, "R22A report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A manifest identity changed"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R22A report no longer matches manifest"
        )

    gate = manifest.get(_R22A_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R22A_GATE_SCHEMA:
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "baseline is not the reviewed R22A stream physical candidate"
        )
    required = {
        "candidate_menu_label": "MIDI 68K Stream Proof",
        "proof_records": 40,
        "batch1_records": 32,
        "batch2_records": 8,
        "partial_clock_us": 15000,
        "batch1_clock_us": 32000,
        "final_clock_us": 40000,
        "expected_final_read_sequence": 2,
        "expected_final_read_index": 8,
        "expected_final_batch_count": 2,
        "expected_total_records": 40,
        "wait_zero_required": True,
        "partial_15ms_exactly_15_required": True,
        "batch1_ack_required": True,
        "refill_wait_at_old_clock_required": True,
        "batch2_ack_required": True,
        "persistent_state_required": True,
        "state_summary_words_verified": 256,
        "controller_words_verified": 1024,
        "active_note_words_verified": 128,
        "resident_stream_candidate_bound": True,
        "producer_linked": True,
        "producer_invoked_during_build": False,
        "midi_scsp_note_attempted": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                f"R22A gate changed: {key}"
            )

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted_bin = _require_sha(expected_bin_sha256, "expected R22A BIN")
    accepted_cue = _require_sha(expected_cue_sha256, "expected R22A CUE")
    for relative, expected, label in (
        (_DEPLOY_BIN, accepted_bin, "R22A BIN"),
        (_DEPLOY_CUE, accepted_cue, "R22A CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                f"{label} report hash changed"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                f"{label} disk hash changed"
            )

    main_sha = _sha256_file(root / _MAIN)
    menu_sha = _sha256_file(root / _MENU)
    runtime_sha = _sha256_file(root / _RUNTIME)
    if main_sha != _require_sha(expected_main_sha256, "expected R22A main"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A main hash mismatch")
    if menu_sha != _require_sha(expected_menu_sha256, "expected R22A menu"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A menu hash mismatch")
    if runtime_sha != _require_sha(expected_runtime_sha256, "expected R22A runtime"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A runtime hash mismatch")
    if main_sha.lower() != str(gate.get("candidate_main_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A gate/main hash mismatch")
    if menu_sha.lower() != str(gate.get("candidate_menu_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A gate/menu hash mismatch")
    if runtime_sha.lower() != str(gate.get("runtime_after_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A gate/runtime hash mismatch")

    proof_source = _require_sha(expected_proof_source_sha256, "expected R22A proof source")
    proof_header = _require_sha(expected_proof_header_sha256, "expected R22A proof header")
    if _sha256_file(root / _R22A_PROOF_SOURCE) != proof_source:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A proof source hash mismatch")
    if _sha256_file(root / _R22A_PROOF_HEADER) != proof_header:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A proof header hash mismatch")
    if str(gate.get("proof_source_sha256", "")).lower() != proof_source:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A gate/proof-source mismatch")
    if str(gate.get("proof_header_sha256", "")).lower() != proof_header:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A gate/proof-header mismatch")

    producer_source = _require_sha(expected_producer_source_sha256, "expected producer source")
    producer_header = _require_sha(expected_producer_header_sha256, "expected producer header")
    if _sha256_file(root / _PRODUCER_SOURCE) != producer_source:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A producer source hash mismatch")
    if _sha256_file(root / _PRODUCER_HEADER) != producer_header:
        raise SaturnMidi68KResidentAudioFullBuildGateError("R22A producer header hash mismatch")

    return (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        accepted_bin,
        accepted_cue,
        main_sha,
        menu_sha,
        runtime_sha,
    )


def prepare_midi_68k_resident_audio_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_baseline_runtime_sha256: str,
    expected_baseline_main_sha256: str,
    expected_baseline_menu_sha256: str,
    expected_baseline_proof_source_sha256: str,
    expected_baseline_proof_header_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> SaturnMidi68KResidentAudioFullBuildGatePrepared:
    """Create a fresh inert R23 tree from exact accepted R22A evidence."""

    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            f"R22A baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentAudioFullBuildGateError(
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
    ) = _verify_r22a(
        baseline,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_runtime_sha256=expected_baseline_runtime_sha256,
        expected_main_sha256=expected_baseline_main_sha256,
        expected_menu_sha256=expected_baseline_menu_sha256,
        expected_proof_source_sha256=expected_baseline_proof_source_sha256,
        expected_proof_header_sha256=expected_baseline_proof_header_sha256,
        expected_producer_source_sha256=expected_producer_source_sha256,
        expected_producer_header_sha256=expected_producer_header_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    if image.sha256 != _require_sha(expected_image_sha256, "expected R23 audio image"):
        raise SaturnMidi68KResidentAudioFullBuildGateError("R23 audio image hash mismatch")

    resident_source = render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")
    resident_header = render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")
    voice_header = render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")
    producer_source = render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
    producer_header = render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
    generated_hashes = {
        "resident_source": _sha256_bytes(resident_source),
        "resident_header": _sha256_bytes(resident_header),
        "voice_header": _sha256_bytes(voice_header),
        "producer_source": _sha256_bytes(producer_source),
        "producer_header": _sha256_bytes(producer_header),
    }
    expected_hashes = {
        "resident_source": _require_sha(expected_resident_source_sha256, "resident source"),
        "resident_header": _require_sha(expected_resident_header_sha256, "resident header"),
        "voice_header": _require_sha(expected_voice_header_sha256, "voice header"),
        "producer_source": _require_sha(expected_producer_source_sha256, "producer source"),
        "producer_header": _require_sha(expected_producer_header_sha256, "producer header"),
    }
    if generated_hashes != expected_hashes:
        raise SaturnMidi68KResidentAudioFullBuildGateError(
            "R23 generated representation no longer matches compiler evidence"
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
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                "R22A runtime changed during staging"
            )
        marker = _MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentAudioFullBuildGateError(
                "R22A runtime already contains R23 inert audio injection"
            )

        (staging / _AUDIO_SOURCE).write_bytes(resident_source)
        (staging / _AUDIO_HEADER).write_bytes(resident_header)
        (staging / _VOICE_HEADER).write_bytes(voice_header)

        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n" + resident_source
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate = dict(manifest)
        policy = dict(candidate.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_resident_audio_present": True,
                "midi_68k_resident_audio_linked": True,
                "midi_68k_resident_audio_installed": False,
                "midi_68k_resident_audio_executed": False,
                "midi_68k_resident_audio_candidate_bound": False,
                "midi_scsp_capable_image_linked": True,
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
            "existing_r22a_candidate_binding_preserved": True,
            "r22a_main_sha256": main_sha,
            "r22a_menu_sha256": menu_sha,
            "r22a_runtime_sha256": runtime_sha,
            "resident_source_copy": _AUDIO_SOURCE,
            "resident_header_copy": _AUDIO_HEADER,
            "voice_header_copy": _VOICE_HEADER,
            "producer_source_copy": _PRODUCER_SOURCE,
            "producer_header_copy": _PRODUCER_HEADER,
            "compile_injection": _RUNTIME,
            "image_sha256": image.sha256,
            "image_word_count": image.word_count,
            "image_byte_size": image.byte_size,
            "program_address": SATURN_MIDI_68K_RESIDENT_AUDIO_PROGRAM_ADDRESS,
            "program_end_address": image.end_address,
            "resident_source_sha256": generated_hashes["resident_source"],
            "resident_header_sha256": generated_hashes["resident_header"],
            "voice_header_sha256": generated_hashes["voice_header"],
            "producer_source_sha256": generated_hashes["producer_source"],
            "producer_header_sha256": generated_hashes["producer_header"],
            "accepted_resident_object_sha256_evidence": resident_object,
            "accepted_producer_object_sha256_evidence": producer_object,
            "voice_allocator": "slot-0-monophonic-no-steal",
            "owned_slots": SATURN_MIDI_68K_R23_OWNED_SLOTS,
            "voice_state_address": SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
            "pcm_waveform_address": SATURN_MIDI_68K_AUDIO_SAMPLE_ADDRESS,
            "pitch_table_address": SATURN_MIDI_68K_PITCH_TABLE_ADDRESS,
            "scsp_register_base": SATURN_MIDI_68K_SCSP_REGISTER_BASE,
            "first_note_channel": SATURN_MIDI_68K_R23_CHANNEL,
            "first_note_note": SATURN_MIDI_68K_R23_NOTE,
            "first_note_velocity": SATURN_MIDI_68K_R23_VELOCITY,
            "first_note_hold_us": SATURN_MIDI_68K_R23_HOLD_US,
            "r22a_queue_refill_semantics_preserved": True,
            "r22a_timestamp_scheduler_preserved": True,
            "r22a_midi_state_semantics_preserved": True,
            "resident_audio_linked": True,
            "resident_audio_installed": False,
            "resident_audio_executed": False,
            "resident_audio_candidate_bound": False,
            "producer_already_linked_from_r22a": True,
            "producer_invoked_during_build": False,
            "midi_scsp_image_capable": True,
            "midi_scsp_note_attempted_during_build": False,
            "build_time_hardware_io": False,
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
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

    return SaturnMidi68KResidentAudioFullBuildGatePrepared(
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
        voice_header_sha256=generated_hashes["voice_header"],
        producer_source_sha256=generated_hashes["producer_source"],
        producer_header_sha256=generated_hashes["producer_header"],
        resident_object_sha256=resident_object,
        producer_object_sha256=producer_object,
        r22a_main_sha256=main_sha,
        r22a_menu_sha256=menu_sha,
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_resident_audio_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentAudioFullBuildGateResult:
    prepared = prepare_midi_68k_resident_audio_full_build_gate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentAudioFullBuildGateResult(prepared=prepared, build=build)
