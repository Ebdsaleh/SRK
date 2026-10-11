"""Prepare a fresh callable R23 MIDI->SCSP physical candidate.

The input is the successful, inert R23 full-build integration.  This preparation
step verifies its complete generated-file inventory, build-report pairing,
compiler anchors and deploy artifacts, then derives a fresh standalone tree with
the R23 physical proof bound to the existing explicit-A diagnostic screen.

No build-time or preparation-time Saturn/SAROO I/O occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_audio_physical_candidate import (
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
    SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_r23_expected_midi_words,
    build_srk_saturn_midi_68k_r23_physical_snapshot,
    derive_resident_audio_candidate_main,
    derive_resident_audio_candidate_menu,
    render_srk_saturn_midi_68k_r23_physical_proof_header,
    render_srk_saturn_midi_68k_r23_physical_proof_source,
)
from .midi_68k_resident_audio_service import (
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
    SATURN_MIDI_68K_R23_CHANNEL,
    SATURN_MIDI_68K_R23_NOTE,
    SATURN_MIDI_68K_R23_OWNED_SLOTS,
    SATURN_MIDI_68K_R23_VELOCITY,
    SATURN_MIDI_68K_SCSP_REGISTER_BASE,
    SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
    SATURN_MIDI_68K_VOICE_STATE_WORDS,
)


class SaturnMidi68KResidentAudioCandidatePrepareError(RuntimeError):
    """Raised when the R23 physical candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioCandidatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str
    proof_records: int
    batch1_records: int
    batch2_records: int
    note_on_clock_us: int
    note_off_clock_us: int
    audible_hold_polls: int
    state_summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int
    voice_words_verified: int


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_AUDIO_SOURCE = "src/srk_saturn_midi_68k_resident_audio_service.c"
_AUDIO_HEADER = "src/srk_saturn_midi_68k_resident_audio_service.h"
_VOICE_HEADER = "src/srk_saturn_midi_68k_voice_state.h"
_PRODUCER_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_PRODUCER_HEADER = "src/srk_saturn_midi_68k_stream_service.h"
_PROOF_SOURCE = "src/srk_saturn_midi_68k_r23_physical_proof.c"
_PROOF_HEADER = "src/srk_saturn_midi_68k_r23_physical_proof.h"
_INERT_GATE_KEY = "midi_68k_resident_audio_full_build_gate"
_INERT_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-full-build-gate.v1"
_GATE_KEY = "midi_68k_resident_audio_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-physical-candidate-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K R23 AUDIO PHYSICAL CANDIDATE: generated proof follows. */"


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
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
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
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert baseline has no generated-file inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                "invalid R23 inert generated-file entry"
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
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                "invalid or duplicate R23 inert generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"R23 inert generated input size/path mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"R23 inert generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert build report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_inert_baseline(
    root: Path,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert baseline must contain manifest and successful build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "R23 inert manifest")
    report = _load_json(report_path, "R23 inert build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert manifest identity changed"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert report no longer matches manifest"
        )

    gate = manifest.get(_INERT_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _INERT_GATE_SCHEMA:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "baseline is not the reviewed R23 inert audio integration"
        )

    exact = {
        "image_sha256": _require_sha(expected_image_sha256, "expected R23 audio image"),
        "resident_source_sha256": _require_sha(expected_resident_source_sha256, "resident source"),
        "resident_header_sha256": _require_sha(expected_resident_header_sha256, "resident header"),
        "voice_header_sha256": _require_sha(expected_voice_header_sha256, "voice header"),
        "producer_source_sha256": _require_sha(expected_producer_source_sha256, "producer source"),
        "producer_header_sha256": _require_sha(expected_producer_header_sha256, "producer header"),
        "accepted_resident_object_sha256_evidence": _require_sha(
            expected_resident_object_sha256, "resident object"
        ),
        "accepted_producer_object_sha256_evidence": _require_sha(
            expected_producer_object_sha256, "producer object"
        ),
    }
    for key, expected in exact.items():
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"R23 inert gate changed: {key}"
            )

    required = {
        "existing_r22a_candidate_binding_preserved": True,
        "voice_allocator": "slot-0-monophonic-no-steal",
        "owned_slots": SATURN_MIDI_68K_R23_OWNED_SLOTS,
        "voice_state_address": SATURN_MIDI_68K_VOICE_STATE_ADDRESS,
        "scsp_register_base": SATURN_MIDI_68K_SCSP_REGISTER_BASE,
        "first_note_channel": SATURN_MIDI_68K_R23_CHANNEL,
        "first_note_note": SATURN_MIDI_68K_R23_NOTE,
        "first_note_velocity": SATURN_MIDI_68K_R23_VELOCITY,
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
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active": False,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"R23 inert gate changed: {key}"
            )

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted_bin = _require_sha(expected_bin_sha256, "expected R23 inert BIN")
    accepted_cue = _require_sha(expected_cue_sha256, "expected R23 inert CUE")
    for relative, expected, label in (
        (_DEPLOY_BIN, accepted_bin, "R23 inert BIN"),
        (_DEPLOY_CUE, accepted_cue, "R23 inert CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"{label} report hash changed"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"{label} disk hash changed"
            )

    runtime_sha = _sha256_file(root / _RUNTIME)
    accepted_runtime = _require_sha(expected_runtime_sha256, "expected R23 inert runtime")
    if runtime_sha != accepted_runtime:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert runtime hash mismatch"
        )
    if runtime_sha.lower() != str(gate.get("runtime_after_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert gate/runtime hash mismatch"
        )

    main_sha = _sha256_file(root / _MAIN)
    menu_sha = _sha256_file(root / _MENU)
    if main_sha.lower() != str(gate.get("r22a_main_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert baseline no longer preserves R22A main"
        )
    if menu_sha.lower() != str(gate.get("r22a_menu_sha256", "")).lower():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 inert baseline no longer preserves R22A menu"
        )

    for relative, expected, label in (
        (_AUDIO_SOURCE, exact["resident_source_sha256"], "resident source"),
        (_AUDIO_HEADER, exact["resident_header_sha256"], "resident header"),
        (_VOICE_HEADER, exact["voice_header_sha256"], "voice header"),
        (_PRODUCER_SOURCE, exact["producer_source_sha256"], "producer source"),
        (_PRODUCER_HEADER, exact["producer_header_sha256"], "producer header"),
    ):
        if not (root / relative).is_file() or _sha256_file(root / relative) != expected:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                f"R23 inert {label} hash mismatch"
            )

    return manifest, generated, manifest_sha, report_sha, accepted_bin, accepted_cue


def prepare_midi_68k_resident_audio_physical_candidate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_baseline_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> SaturnMidi68KResidentAudioCandidatePrepared:
    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            f"R23 inert baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        baseline_bin,
        baseline_cue,
    ) = _verify_inert_baseline(
        baseline,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_runtime_sha256=expected_baseline_runtime_sha256,
        expected_image_sha256=expected_image_sha256,
        expected_resident_source_sha256=expected_resident_source_sha256,
        expected_resident_header_sha256=expected_resident_header_sha256,
        expected_voice_header_sha256=expected_voice_header_sha256,
        expected_producer_source_sha256=expected_producer_source_sha256,
        expected_producer_header_sha256=expected_producer_header_sha256,
        expected_resident_object_sha256=expected_resident_object_sha256,
        expected_producer_object_sha256=expected_producer_object_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    if image.sha256 != _require_sha(expected_image_sha256, "expected R23 audio image"):
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "current R23 resident generator no longer matches compiler evidence"
        )

    generated_hashes = {
        "resident_source": _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")
        ),
        "resident_header": _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")
        ),
        "voice_header": _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")
        ),
        "producer_source": _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
        ),
        "producer_header": _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
        ),
    }
    expected_hashes = {
        "resident_source": _require_sha(expected_resident_source_sha256, "resident source"),
        "resident_header": _require_sha(expected_resident_header_sha256, "resident header"),
        "voice_header": _require_sha(expected_voice_header_sha256, "voice header"),
        "producer_source": _require_sha(expected_producer_source_sha256, "producer source"),
        "producer_header": _require_sha(expected_producer_header_sha256, "producer header"),
    }
    if generated_hashes != expected_hashes:
        raise SaturnMidi68KResidentAudioCandidatePrepareError(
            "R23 generated representation no longer matches compiler evidence"
        )

    proof_header = render_srk_saturn_midi_68k_r23_physical_proof_header()
    proof_source = render_srk_saturn_midi_68k_r23_physical_proof_source()
    summaries, controllers, active = build_srk_saturn_midi_68k_r23_expected_midi_words()
    snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()

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
        main_path = staging / _MAIN
        menu_path = staging / _MENU
        if not runtime_path.is_file() or not main_path.is_file() or not menu_path.is_file():
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                "R23 inert baseline is missing runtime/main/menu source"
            )

        runtime_before = runtime_path.read_bytes()
        candidate_main = derive_resident_audio_candidate_main(
            main_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        candidate_menu = derive_resident_audio_candidate_menu(
            menu_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        main_path.write_bytes(candidate_main)
        menu_path.write_bytes(candidate_menu)

        (staging / _PROOF_HEADER).write_text(
            proof_header, encoding="utf-8", newline="\n"
        )
        (staging / _PROOF_SOURCE).write_text(
            proof_source, encoding="utf-8", newline="\n"
        )

        marker = _MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentAudioCandidatePrepareError(
                "R23 inert runtime already contains physical candidate injection"
            )
        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n" + proof_source.encode("utf-8")
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
                "midi_68k_resident_audio_candidate_bound": True,
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
            "accepted_inert_deploy_bin_sha256": baseline_bin,
            "accepted_inert_deploy_cue_sha256": baseline_cue,
            "candidate_define": "#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1",
            "candidate_menu_label": "MIDI 68K Audio Proof",
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "proof_records": SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
            "batch1_records": SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
            "batch2_records": SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
            "partial_clock_us": SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
            "batch1_clock_us": SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
            "note_on_clock_us": SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
            "note_off_clock_us": SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
            "audible_hold_polls": SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
            "expected_final_read_sequence": 2,
            "expected_final_read_index": 2,
            "expected_final_batch_count": 2,
            "expected_total_records": SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
            "wait_zero_required": True,
            "partial_15ms_exactly_15_required": True,
            "batch1_ack_required": True,
            "refill_wait_at_old_clock_required": True,
            "scsp_key_on_readback_required": True,
            "audible_midi_note_required": True,
            "scheduled_note_off_required": True,
            "scsp_key_off_readback_required": True,
            "persistent_midi_state_required": True,
            "state_summary_words_verified": len(summaries),
            "controller_words_verified": len(controllers),
            "active_note_words_verified": len(active),
            "voice_words_verified": SATURN_MIDI_68K_VOICE_STATE_WORDS,
            "expected_final_cc74": snapshot.cc74,
            "expected_voice_key_on_count": snapshot.voice_key_on_count,
            "expected_voice_key_off_count": snapshot.voice_key_off_count,
            "image_sha256": image.sha256,
            "resident_source_sha256": generated_hashes["resident_source"],
            "resident_header_sha256": generated_hashes["resident_header"],
            "voice_header_sha256": generated_hashes["voice_header"],
            "producer_source_sha256": generated_hashes["producer_source"],
            "producer_header_sha256": generated_hashes["producer_header"],
            "accepted_resident_object_sha256_evidence": _require_sha(
                expected_resident_object_sha256, "resident object"
            ),
            "accepted_producer_object_sha256_evidence": _require_sha(
                expected_producer_object_sha256, "producer object"
            ),
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "proof_header_sha256": _sha256_bytes(proof_header.encode("utf-8")),
            "proof_source_sha256": _sha256_bytes(proof_source.encode("utf-8")),
            "resident_audio_linked": True,
            "resident_audio_installed_during_build": False,
            "resident_audio_executed_during_build": False,
            "resident_audio_candidate_bound": True,
            "producer_linked": True,
            "producer_invoked_during_build": False,
            "midi_scsp_note_attempted_during_build": False,
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

    return SaturnMidi68KResidentAudioCandidatePrepared(
        baseline_root=baseline,
        output_root=output,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin,
        baseline_cue_sha256=baseline_cue,
        image_sha256=image.sha256,
        candidate_main_sha256=_sha256_bytes(candidate_main),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        runtime_after_sha256=_sha256_bytes(runtime_after),
        proof_header_sha256=_sha256_bytes(proof_header.encode("utf-8")),
        proof_source_sha256=_sha256_bytes(proof_source.encode("utf-8")),
        proof_records=SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
        batch1_records=SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
        batch2_records=SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
        note_on_clock_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
        note_off_clock_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
        audible_hold_polls=SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
        state_summary_words_verified=len(summaries),
        controller_words_verified=len(controllers),
        active_note_words_verified=len(active),
        voice_words_verified=SATURN_MIDI_68K_VOICE_STATE_WORDS,
    )
