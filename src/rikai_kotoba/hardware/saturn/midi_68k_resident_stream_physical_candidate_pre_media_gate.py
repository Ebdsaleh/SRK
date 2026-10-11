"""Independent read-only pre-media gate for the R22 stream/scheduler proof.

The gate re-opens a completed callable R22 candidate as an external artifact,
revalidates the compiler-accepted resident stream image and SH-2 producer
representations, the reviewed 32+8 timestamp/refill proof, the full persistent
MIDI-state contract, and the completed standalone build before producing only a
read-only SAROO destination plan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from .midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
)
from .midi_68k_resident_stream_physical_candidate import (
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_0_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_stream_expected_words,
    build_srk_saturn_midi_68k_stream_physical_program,
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    render_srk_saturn_midi_68k_stream_physical_proof_header,
    render_srk_saturn_midi_68k_stream_physical_proof_source,
)
from .midi_68k_stream_service import (
    build_srk_saturn_midi_stream_batches,
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .midi_program import SaturnMidiOpcode
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when R22 cannot pass independent read-only media review."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamPhysicalCandidatePreMediaResult:
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
    clock_final_us: int
    summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_RUNTIME = "src/srk_saturn_runtime.c"
_PROOF_HEADER = "src/srk_saturn_midi_68k_stream_physical_proof.h"
_PROOF_SOURCE = "src/srk_saturn_midi_68k_stream_physical_proof.c"
_INERT_GATE_KEY = "midi_68k_resident_stream_full_build_gate"
_INERT_SCHEMA = "srk.saturn.midi-68k-resident-stream-full-build-gate.v1"
_CANDIDATE_GATE_KEY = "midi_68k_resident_stream_physical_candidate_full_build_gate"
_CANDIDATE_SCHEMA = "srk.saturn.midi-68k-resident-stream-physical-candidate-full-build-gate.v1"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Stream Proof"


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
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"{label} must be exactly 64 hexadecimal SHA-256 characters"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"{label} path escapes candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                "R22 generated-file inventory contains an invalid entry"
            )
        relative = entry.get("path")
        size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                "R22 generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 generated input changed: {relative}"
            )

    required = {_MAIN, _MENU, _RUNTIME, _PROOF_HEADER, _PROOF_SOURCE}
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 inventory is missing required inputs: " + ", ".join(missing)
        )


def _verify_stream_provenance(
    manifest: dict,
    *,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> str:
    inert = manifest.get(_INERT_GATE_KEY)
    if not isinstance(inert, dict) or inert.get("schema") != _INERT_SCHEMA:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 no longer carries accepted stream/scheduler inert provenance"
        )

    expected = {
        "image_sha256": _require_sha256(expected_image_sha256, "expected stream image SHA-256"),
        "resident_source_sha256": _require_sha256(expected_resident_source_sha256, "resident source SHA-256"),
        "resident_header_sha256": _require_sha256(expected_resident_header_sha256, "resident header SHA-256"),
        "producer_source_sha256": _require_sha256(expected_producer_source_sha256, "producer source SHA-256"),
        "producer_header_sha256": _require_sha256(expected_producer_header_sha256, "producer header SHA-256"),
        "accepted_resident_object_sha256_evidence": _require_sha256(
            expected_resident_object_sha256, "resident object SHA-256"
        ),
        "accepted_producer_object_sha256_evidence": _require_sha256(
            expected_producer_object_sha256, "producer object SHA-256"
        ),
    }
    for key, value in expected.items():
        if str(inert.get(key, "")).lower() != value:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 inherited stream provenance mismatch: {key}"
            )

    required = {
        "multi_batch_refill": True,
        "strict_sequence_service": True,
        "timestamp_scheduler": True,
        "published_clock_seqlock": True,
        "state_persistent_across_refills": True,
        "resident_stream_linked": True,
        "resident_stream_installed": False,
        "resident_stream_executed": False,
        "producer_linked": True,
        "producer_invoked": False,
        "midi_scsp_note_attempted": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
    }
    for key, value in required.items():
        if inert.get(key) != value:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 inherited stream contract mismatch: {key}"
            )

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    if image.sha256 != expected["image_sha256"]:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "current resident stream generator no longer matches compiler evidence"
        )
    if image.word_count != 5123 or image.byte_size != 10246 or image.end_address != 0x00006806:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "accepted resident stream image geometry changed"
        )

    rendered = {
        "resident_source_sha256": _sha256_bytes(
            render_srk_saturn_midi_68k_resident_stream_service_source().encode("utf-8")
        ),
        "resident_header_sha256": _sha256_bytes(
            render_srk_saturn_midi_68k_resident_stream_service_header().encode("utf-8")
        ),
        "producer_source_sha256": _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
        ),
        "producer_header_sha256": _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
        ),
    }
    for key, actual in rendered.items():
        if actual != expected[key]:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"current generated stream representation no longer matches compiler evidence: {key}"
            )
    return image.sha256


def _verify_proof_program() -> tuple[int, int, int]:
    program = build_srk_saturn_midi_68k_stream_physical_program()
    batches = build_srk_saturn_midi_stream_batches(program)
    if (
        SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS != 40
        or len(program.records) != 40
        or tuple(len(batch.records) for batch in batches) != (32, 8)
        or tuple(batch.sequence for batch in batches) != (1, 2)
        or SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_0_US != 0
        or SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US != 15000
        or SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US != 32000
        or SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US != 40000
    ):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "reviewed R22 32+8 timing/refill proof contract changed"
        )
    if set(record.opcode for record in program.records) != set(SaturnMidiOpcode):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 proof no longer exercises every SRKM v1 opcode"
        )
    summaries, controllers, active = build_srk_saturn_midi_68k_stream_expected_words()
    if (len(summaries), len(controllers), len(active)) != (256, 1024, 128):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 full-state verification surface changed"
        )
    return len(summaries), len(controllers), len(active)


def _verify_candidate_gate(
    root: Path,
    manifest: dict,
) -> tuple[str, str, str, str, str]:
    gate = manifest.get(_CANDIDATE_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _CANDIDATE_SCHEMA:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 manifest has no recognized stream physical-candidate gate"
        )

    snapshot = asdict(build_srk_saturn_midi_68k_stream_physical_snapshot())
    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
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
        "resident_stream_linked": True,
        "resident_stream_installed_during_build": False,
        "resident_stream_executed_during_build": False,
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
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 candidate contract mismatch: {key}"
            )
    if gate.get("expected_state_snapshot") != snapshot:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 expected-state snapshot no longer matches the reviewed host model"
        )

    policy = manifest.get("policy")
    required_policy = {
        "sd_writes": False,
        "midi_68k_resident_stream_present": True,
        "midi_68k_resident_stream_linked": True,
        "midi_68k_resident_stream_installed": False,
        "midi_68k_resident_stream_executed": False,
        "midi_68k_resident_stream_candidate_bound": True,
        "midi_68k_stream_producer_linked": True,
        "midi_68k_stream_producer_invoked": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    if not isinstance(policy, dict):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 policy is missing"
        )
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 policy mismatch: {key}"
            )

    main = _project_file(root, _MAIN, "R22 main")
    menu = _project_file(root, _MENU, "R22 menu")
    runtime = _project_file(root, _RUNTIME, "R22 runtime")
    proof_header = _project_file(root, _PROOF_HEADER, "R22 proof header")
    proof_source = _project_file(root, _PROOF_SOURCE, "R22 proof source")
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")

    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 main no longer begins with the stream candidate define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 8u",
        "srk_saturn_midi_68k_stream_physical_proof_begin",
        "srk_saturn_midi_68k_stream_physical_proof_poll",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "Stream PASS: refill + timing + state",
        "wait_zero_pass",
        "partial_15ms_pass",
        "batch1_ack_pass",
        "refill_wait_pass",
        "batch2_ack_pass",
        "final_cc74",
        'srk_midi_68k_draw_field(2, 26, 36, "Release A to arm proof action");',
        'srk_midi_68k_draw_field(2, 27, 36, "START Return to diagnostics menu");',
    ):
        if marker not in main_text:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 main is missing reviewed marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "MIDI 68K State Proof" in menu_text:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 menu no longer isolates the stream/scheduler proof"
        )
    for marker in (
        "srk_saturn_midi_stream_clock_publish(0UL)",
        "srk_saturn_midi_stream_clock_publish(15000UL)",
        "srk_saturn_midi_stream_clock_publish(32000UL)",
        "srk_saturn_midi_stream_clock_publish(40000UL)",
        "srk_saturn_midi_stream_batch_publish",
        "expected_summary_words",
        "expected_controller_words",
        "expected_active_words",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 runtime is missing reviewed proof seam: {marker}"
            )

    main_sha = _sha256_file(main)
    menu_sha = _sha256_file(menu)
    runtime_sha = _sha256_file(runtime)
    proof_header_sha = _sha256_file(proof_header)
    proof_source_sha = _sha256_file(proof_source)
    expected_proof_header_sha = _sha256_bytes(
        render_srk_saturn_midi_68k_stream_physical_proof_header().encode("utf-8")
    )
    expected_proof_source_sha = _sha256_bytes(
        render_srk_saturn_midi_68k_stream_physical_proof_source().encode("utf-8")
    )
    for key, actual in (
        ("candidate_main_sha256", main_sha),
        ("candidate_menu_sha256", menu_sha),
        ("runtime_after_sha256", runtime_sha),
        ("proof_header_sha256", proof_header_sha),
        ("proof_source_sha256", proof_source_sha),
    ):
        if str(gate.get(key, "")).lower() != actual.lower():
            raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
                f"R22 candidate provenance hash mismatch: {key}"
            )
    if proof_header_sha != expected_proof_header_sha or proof_source_sha != expected_proof_source_sha:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 physical proof no longer matches its reviewed renderer"
        )
    return main_sha, menu_sha, runtime_sha, proof_header_sha, proof_source_sha


def _verify_build_report(root: Path, manifest_sha: str) -> str:
    report_path = root / _REPORT
    if not report_path.is_file():
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"R22 build report is missing: {report_path}"
        )
    report = _load_json(report_path, "R22 build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 build report is not a successful standalone build"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 build report does not match the current manifest"
        )
    return _sha256_file(report_path)


def inspect_midi_68k_resident_stream_physical_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KResidentStreamPhysicalCandidatePreMediaResult:
    """Revalidate R22 independently and return only a read-only SAROO plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"R22 candidate project is not a directory: {root}"
        )
    expected_bin = _require_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha256(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"R22 manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "R22 manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "R22 manifest identity is unsupported"
        )

    manifest_sha = _sha256_file(manifest_path)
    _verify_generated_inventory(root, manifest)
    image_sha = _verify_stream_provenance(
        manifest,
        expected_image_sha256=expected_image_sha256,
        expected_resident_source_sha256=expected_resident_source_sha256,
        expected_resident_header_sha256=expected_resident_header_sha256,
        expected_producer_source_sha256=expected_producer_source_sha256,
        expected_producer_header_sha256=expected_producer_header_sha256,
        expected_resident_object_sha256=expected_resident_object_sha256,
        expected_producer_object_sha256=expected_producer_object_sha256,
    )
    summary_count, controller_count, active_count = _verify_proof_program()
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
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected R22 candidate: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "fresh R22 BIN SHA-256 does not match externally accepted build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KResidentStreamPhysicalCandidatePreMediaGateError(
            "fresh R22 CUE SHA-256 does not match externally accepted build output"
        )

    return SaturnMidi68KResidentStreamPhysicalCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        runtime_after_sha256=runtime_sha,
        proof_header_sha256=proof_header_sha,
        proof_source_sha256=proof_source_sha,
        proof_records=40,
        batch1_records=32,
        batch2_records=8,
        clock_zero_us=0,
        clock_partial_us=15000,
        clock_batch1_us=32000,
        clock_final_us=40000,
        summary_words_verified=summary_count,
        controller_words_verified=controller_count,
        active_note_words_verified=active_count,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
