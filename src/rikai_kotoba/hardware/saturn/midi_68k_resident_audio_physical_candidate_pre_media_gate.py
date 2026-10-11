"""Independent read-only pre-media gate for the R23 MIDI->SCSP candidate.

The gate re-opens a completed R23 physical candidate as an external artifact,
revalidates compiler provenance, the reviewed 32+2 scheduler/audio proof, the
complete MIDI and voice-state surfaces, the finished standalone build, and a
fresh MODE1/CUE deployment plan. It never writes to the mounted SAROO card.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from .midi_68k_resident_audio_physical_candidate import (
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_0_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
    SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
    SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_r23_expected_midi_words,
    build_srk_saturn_midi_68k_r23_physical_program,
    build_srk_saturn_midi_68k_r23_physical_snapshot,
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
    build_srk_saturn_midi_stream_batches,
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
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when R23 cannot pass independent read-only media review."""


@dataclass(frozen=True)
class SaturnMidi68KResidentAudioPhysicalCandidatePreMediaResult:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str
    proof_records: int
    batch1_records: int
    batch2_records: int
    clock_zero_us: int
    clock_partial_us: int
    clock_batch1_us: int
    note_on_clock_us: int
    note_off_clock_us: int
    audible_hold_polls: int
    summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int
    voice_words_verified: int
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_RUNTIME = "src/srk_saturn_runtime.c"
_PROOF_HEADER = "src/srk_saturn_midi_68k_r23_physical_proof.h"
_PROOF_SOURCE = "src/srk_saturn_midi_68k_r23_physical_proof.c"
_AUDIO_SOURCE = "src/srk_saturn_midi_68k_resident_audio_service.c"
_AUDIO_HEADER = "src/srk_saturn_midi_68k_resident_audio_service.h"
_VOICE_HEADER = "src/srk_saturn_midi_68k_voice_state.h"
_PRODUCER_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_PRODUCER_HEADER = "src/srk_saturn_midi_68k_stream_service.h"
_INERT_GATE_KEY = "midi_68k_resident_audio_full_build_gate"
_INERT_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-full-build-gate.v1"
_GATE_KEY = "midi_68k_resident_audio_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-physical-candidate-full-build-gate.v1"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_RESIDENT_AUDIO_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Audio Proof"


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha(value: str, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"{label} path escapes candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 candidate has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                "R23 generated-file inventory contains an invalid entry"
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
            or len(expected) != 64
        ):
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                "R23 generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 generated input changed: {relative}"
            )
    required = {
        _MAIN,
        _MENU,
        _RUNTIME,
        _PROOF_HEADER,
        _PROOF_SOURCE,
        _AUDIO_SOURCE,
        _AUDIO_HEADER,
        _VOICE_HEADER,
        _PRODUCER_SOURCE,
        _PRODUCER_HEADER,
    }
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 inventory is missing required inputs: " + ", ".join(missing)
        )


def _verify_compiler_provenance(
    root: Path,
    manifest: dict,
    *,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> str:
    gate = manifest.get(_GATE_KEY)
    inert = manifest.get(_INERT_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _GATE_SCHEMA:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 manifest has no recognized audio physical-candidate gate"
        )
    if not isinstance(inert, dict) or inert.get("schema") != _INERT_GATE_SCHEMA:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 candidate no longer carries accepted inert audio provenance"
        )

    expected = {
        "image_sha256": _require_sha(expected_image_sha256, "expected audio image SHA-256"),
        "resident_source_sha256": _require_sha(expected_resident_source_sha256, "resident source SHA-256"),
        "resident_header_sha256": _require_sha(expected_resident_header_sha256, "resident header SHA-256"),
        "voice_header_sha256": _require_sha(expected_voice_header_sha256, "voice header SHA-256"),
        "producer_source_sha256": _require_sha(expected_producer_source_sha256, "producer source SHA-256"),
        "producer_header_sha256": _require_sha(expected_producer_header_sha256, "producer header SHA-256"),
        "accepted_resident_object_sha256_evidence": _require_sha(
            expected_resident_object_sha256, "resident object SHA-256"
        ),
        "accepted_producer_object_sha256_evidence": _require_sha(
            expected_producer_object_sha256, "producer object SHA-256"
        ),
    }
    for key, value in expected.items():
        if str(gate.get(key, "")).lower() != value:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 candidate compiler provenance mismatch: {key}"
            )
        if str(inert.get(key, "")).lower() != value:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 inherited inert provenance mismatch: {key}"
            )

    image = build_srk_saturn_midi_68k_resident_audio_service_image()
    if image.sha256 != expected["image_sha256"]:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "current R23 resident generator no longer matches compiler evidence"
        )
    if image.word_count != 6278 or image.byte_size != 12556 or image.end_address != 0x0000710C:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "accepted R23 resident image geometry changed"
        )

    rendered = {
        _AUDIO_SOURCE: _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")
        ),
        _AUDIO_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")
        ),
        _VOICE_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")
        ),
        _PRODUCER_SOURCE: _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
        ),
        _PRODUCER_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
        ),
    }
    rendered_expected = {
        _AUDIO_SOURCE: expected["resident_source_sha256"],
        _AUDIO_HEADER: expected["resident_header_sha256"],
        _VOICE_HEADER: expected["voice_header_sha256"],
        _PRODUCER_SOURCE: expected["producer_source_sha256"],
        _PRODUCER_HEADER: expected["producer_header_sha256"],
    }
    for relative, actual in rendered.items():
        if actual != rendered_expected[relative]:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"current generated R23 representation changed: {relative}"
            )
        if _sha256_file(_project_file(root, relative, relative)) != actual:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"candidate generated representation changed: {relative}"
            )
    return image.sha256


def _verify_proof_contract() -> tuple[int, int, int, int]:
    program = build_srk_saturn_midi_68k_r23_physical_program()
    batches = build_srk_saturn_midi_stream_batches(program)
    if (
        SATURN_MIDI_68K_R23_PHYSICAL_RECORDS != 34
        or len(program.records) != 34
        or tuple(len(batch.records) for batch in batches) != (32, 2)
        or tuple(batch.sequence for batch in batches) != (1, 2)
        or SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_0_US != 0
        or SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US != 15000
        or SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US != 32000
        or SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US != 33000
        or SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US != 1033000
        or SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS != 60
    ):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "reviewed R23 32+2 scheduler/audio proof contract changed"
        )
    if program.records[32].opcode.name != "NOTE_ON" or program.records[33].opcode.name != "NOTE_OFF":
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 second batch no longer contains NOTE_ON then NOTE_OFF"
        )
    if (
        program.records[32].channel != SATURN_MIDI_68K_R23_CHANNEL
        or program.records[32].data0 != SATURN_MIDI_68K_R23_NOTE
        or program.records[32].data1 != SATURN_MIDI_68K_R23_VELOCITY
    ):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 first audible note contract changed"
        )
    summaries, controllers, active = build_srk_saturn_midi_68k_r23_expected_midi_words()
    if (len(summaries), len(controllers), len(active), SATURN_MIDI_68K_VOICE_STATE_WORDS) != (
        256,
        1024,
        128,
        15,
    ):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 verification surface changed"
        )
    snapshot = build_srk_saturn_midi_68k_r23_physical_snapshot()
    if (
        snapshot.cc74,
        snapshot.final_active_note_count,
        snapshot.total_records,
        snapshot.batches,
        snapshot.voice_key_on_count,
        snapshot.voice_key_off_count,
    ) != (31, 0, 34, 2, 1, 1):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 final state snapshot changed"
        )
    return len(summaries), len(controllers), len(active), SATURN_MIDI_68K_VOICE_STATE_WORDS


def _verify_candidate_gate(root: Path, manifest: dict) -> tuple[str, str, str, str, str]:
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _GATE_SCHEMA:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 candidate gate is missing"
        )
    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "proof_records": 34,
        "batch1_records": 32,
        "batch2_records": 2,
        "partial_clock_us": 15000,
        "batch1_clock_us": 32000,
        "note_on_clock_us": 33000,
        "note_off_clock_us": 1033000,
        "audible_hold_polls": 60,
        "expected_final_read_sequence": 2,
        "expected_final_read_index": 2,
        "expected_final_batch_count": 2,
        "expected_total_records": 34,
        "wait_zero_required": True,
        "partial_15ms_exactly_15_required": True,
        "batch1_ack_required": True,
        "refill_wait_at_old_clock_required": True,
        "scsp_key_on_readback_required": True,
        "audible_midi_note_required": True,
        "scheduled_note_off_required": True,
        "scsp_key_off_readback_required": True,
        "persistent_midi_state_required": True,
        "state_summary_words_verified": 256,
        "controller_words_verified": 1024,
        "active_note_words_verified": 128,
        "voice_words_verified": 15,
        "expected_final_cc74": 31,
        "expected_voice_key_on_count": 1,
        "expected_voice_key_off_count": 1,
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
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 candidate contract mismatch: {key}"
            )

    policy = manifest.get("policy")
    required_policy = {
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
    if not isinstance(policy, dict):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 policy is missing"
        )
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 policy mismatch: {key}"
            )

    main = _project_file(root, _MAIN, "R23 main")
    menu = _project_file(root, _MENU, "R23 menu")
    runtime = _project_file(root, _RUNTIME, "R23 runtime")
    proof_header = _project_file(root, _PROOF_HEADER, "R23 proof header")
    proof_source = _project_file(root, _PROOF_SOURCE, "R23 proof source")
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")

    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 main no longer begins with the audio candidate define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 2u",
        "srk_saturn_midi_68k_r23_physical_proof_begin",
        "srk_saturn_midi_68k_r23_physical_proof_poll",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "Audio PASS: heard MIDI note + key off",
        "telemetry.key_on_pass",
        "telemetry.audible_hold_polls",
        "telemetry.key_off_pass",
        "telemetry.scsp_control",
    ):
        if marker not in main_text:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 main is missing reviewed marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "MIDI 68K Stream Proof" in menu_text:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 menu no longer isolates the audio proof"
        )
    for marker in (
        "srk_saturn_midi_stream_clock_publish(0UL)",
        "srk_saturn_midi_stream_clock_publish(15000UL)",
        "srk_saturn_midi_stream_clock_publish(32000UL)",
        "srk_saturn_midi_stream_clock_publish(33000UL)",
        "srk_saturn_midi_stream_clock_publish(1033000UL)",
        "SRK_R23_PROOF_SCSP",
        "srk_r23_expected_voice_on",
        "srk_r23_expected_voice_off",
        "srk_r23_verify_final_midi_state",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 runtime is missing reviewed proof seam: {marker}"
            )

    main_sha = _sha256_file(main)
    menu_sha = _sha256_file(menu)
    runtime_sha = _sha256_file(runtime)
    proof_header_sha = _sha256_file(proof_header)
    proof_source_sha = _sha256_file(proof_source)
    expected_header_sha = _sha256_bytes(
        render_srk_saturn_midi_68k_r23_physical_proof_header().encode("utf-8")
    )
    expected_source_sha = _sha256_bytes(
        render_srk_saturn_midi_68k_r23_physical_proof_source().encode("utf-8")
    )
    for key, actual in (
        ("candidate_main_sha256", main_sha),
        ("candidate_menu_sha256", menu_sha),
        ("runtime_after_sha256", runtime_sha),
        ("proof_header_sha256", proof_header_sha),
        ("proof_source_sha256", proof_source_sha),
    ):
        if str(gate.get(key, "")).lower() != actual.lower():
            raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
                f"R23 candidate provenance hash mismatch: {key}"
            )
    if proof_header_sha != expected_header_sha or proof_source_sha != expected_source_sha:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 physical proof no longer matches its reviewed renderer"
        )
    return main_sha, menu_sha, runtime_sha, proof_header_sha, proof_source_sha


def _verify_build_report(root: Path, manifest_sha: str) -> str:
    report_path = root / _REPORT
    if not report_path.is_file():
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"R23 build report is missing: {report_path}"
        )
    report = _load_json(report_path, "R23 build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 build report is not a successful standalone build"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 build report does not match the current manifest"
        )
    return _sha256_file(report_path)


def inspect_midi_68k_resident_audio_physical_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KResidentAudioPhysicalCandidatePreMediaResult:
    """Revalidate R23 independently and return only a read-only SAROO plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"R23 candidate project is not a directory: {root}"
        )
    expected_bin = _require_sha(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"R23 manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "R23 manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "R23 manifest identity is unsupported"
        )
    manifest_sha = _sha256_file(manifest_path)

    _verify_generated_inventory(root, manifest)
    image_sha = _verify_compiler_provenance(
        root,
        manifest,
        expected_image_sha256=expected_image_sha256,
        expected_resident_source_sha256=expected_resident_source_sha256,
        expected_resident_header_sha256=expected_resident_header_sha256,
        expected_voice_header_sha256=expected_voice_header_sha256,
        expected_producer_source_sha256=expected_producer_source_sha256,
        expected_producer_header_sha256=expected_producer_header_sha256,
        expected_resident_object_sha256=expected_resident_object_sha256,
        expected_producer_object_sha256=expected_producer_object_sha256,
    )
    summary_count, controller_count, active_count, voice_count = _verify_proof_contract()
    main_sha, menu_sha, runtime_sha, proof_header_sha, proof_source_sha = _verify_candidate_gate(
        root, manifest
    )
    report_sha = _verify_build_report(root, manifest_sha)

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected R23 candidate: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "fresh R23 BIN SHA-256 does not match externally accepted build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KResidentAudioPhysicalCandidatePreMediaGateError(
            "fresh R23 CUE SHA-256 does not match externally accepted build output"
        )

    return SaturnMidi68KResidentAudioPhysicalCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        runtime_after_sha256=runtime_sha,
        proof_header_sha256=proof_header_sha,
        proof_source_sha256=proof_source_sha,
        proof_records=SATURN_MIDI_68K_R23_PHYSICAL_RECORDS,
        batch1_records=SATURN_MIDI_68K_R23_PHYSICAL_BATCH1_RECORDS,
        batch2_records=SATURN_MIDI_68K_R23_PHYSICAL_BATCH2_RECORDS,
        clock_zero_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_0_US,
        clock_partial_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_PARTIAL_US,
        clock_batch1_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_BATCH1_US,
        note_on_clock_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_ON_US,
        note_off_clock_us=SATURN_MIDI_68K_R23_PHYSICAL_CLOCK_NOTE_OFF_US,
        audible_hold_polls=SATURN_MIDI_68K_R23_PHYSICAL_HOLD_POLLS,
        summary_words_verified=summary_count,
        controller_words_verified=controller_count,
        active_note_words_verified=active_count,
        voice_words_verified=voice_count,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
