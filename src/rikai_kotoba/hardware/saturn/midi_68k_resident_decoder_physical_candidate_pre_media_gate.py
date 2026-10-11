"""Independent read-only pre-media gate for the R20 resident-decoder candidate.

The gate re-opens a completed seven-record callable candidate as an external
artifact, verifies its standalone manifest/report, inherited compiler-accepted
resident-decoder provenance, exact generated seven-record all-opcode proof,
candidate binding seams and externally accepted BIN/CUE hashes, then delegates
only to the existing read-only SAROO deployment planner.

It has no apply operation and performs no card writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from .midi_68k_resident_decoder import build_srk_saturn_midi_68k_resident_decoder_image
from .midi_68k_resident_decoder_physical_binding import (
    render_resident_decoder_installer_header,
    render_resident_decoder_installer_source,
    render_resident_decoder_proof_header,
    render_resident_decoder_proof_source,
    render_resident_decoder_runtime_header,
    render_resident_decoder_runtime_source,
)
from .midi_68k_resident_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
    build_srk_saturn_midi_68k_resident_decoder_proof_program,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
)
from .midi_program import SaturnMidiOpcode
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when the R20 decoder candidate cannot pass pre-media review."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaResult:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    seam_sha256: dict[str, str]
    proof_records: int
    proof_final_time_us: int
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_INERT_GATE_KEY = "midi_68k_resident_decoder_full_build_gate"
_CANDIDATE_GATE_KEY = "midi_68k_resident_decoder_physical_candidate_full_build_gate"
_INERT_SCHEMA = "srk.saturn.midi-68k-resident-decoder-full-build-gate.v1"
_CANDIDATE_SCHEMA = "srk.saturn.midi-68k-resident-decoder-physical-candidate-full-build-gate.v1"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Decoder Proof"
_EXPECTED_MAIN = "src/srk_saturn_main.c"
_EXPECTED_MENU = "src/srk_diag_menu.c"
_EXPECTED_RUNTIME = "src/srk_saturn_runtime.c"
_SEAM_RENDERERS = {
    "srk_saturn_midi_68k_resident_decoder_installer.c": render_resident_decoder_installer_source,
    "srk_saturn_midi_68k_resident_decoder_installer.h": render_resident_decoder_installer_header,
    "srk_saturn_midi_68k_resident_decoder_proof_preload.c": render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
    "srk_saturn_midi_68k_resident_decoder_proof_preload.h": render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    "srk_saturn_midi_68k_resident_decoder_runtime.c": render_resident_decoder_runtime_source,
    "srk_saturn_midi_68k_resident_decoder_runtime.h": render_resident_decoder_runtime_header,
    "srk_saturn_midi_68k_resident_decoder_physical_proof.c": render_resident_decoder_proof_source,
    "srk_saturn_midi_68k_resident_decoder_physical_proof.h": render_resident_decoder_proof_header,
}


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
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"{label} must be exactly 64 hexadecimal SHA-256 characters"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"{label} path escapes the candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                "candidate generated-file inventory contains an invalid entry"
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
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                "candidate generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate generated input changed: {relative}"
            )

    required = {_EXPECTED_MAIN, _EXPECTED_MENU, _EXPECTED_RUNTIME}
    required.update(f"src/{name}" for name in _SEAM_RENDERERS)
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate inventory is missing required R20 inputs: " + ", ".join(missing)
        )


def _verify_decoder_provenance(
    manifest: dict,
    *,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
) -> str:
    inert = manifest.get(_INERT_GATE_KEY)
    if not isinstance(inert, dict) or inert.get("schema") != _INERT_SCHEMA:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate no longer carries the accepted inert decoder provenance"
        )
    expected = {
        "image_sha256": _require_sha256(expected_image_sha256, "expected decoder image SHA-256"),
        "source_sha256": _require_sha256(expected_compiler_source_sha256, "expected compiler source SHA-256"),
        "header_sha256": _require_sha256(expected_compiler_header_sha256, "expected compiler header SHA-256"),
        "accepted_compile_object_sha256_evidence": _require_sha256(
            expected_compiler_object_sha256, "expected compiler object SHA-256"
        ),
    }
    for key, value in expected.items():
        if str(inert.get(key, "")).lower() != value:
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate inherited decoder provenance mismatch: {key}"
            )
    image = build_srk_saturn_midi_68k_resident_decoder_image()
    if image.sha256.lower() != expected["image_sha256"]:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "current resident decoder generator no longer matches accepted image evidence"
        )
    if image.word_count != 239 or image.byte_size != 478 or image.end_address != 0x000041DE:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "accepted resident decoder geometry changed"
        )
    return image.sha256


def _verify_proof_program() -> None:
    program = build_srk_saturn_midi_68k_resident_decoder_proof_program()
    if SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS != 7 or len(program.records) != 7:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "reviewed physical proof no longer contains exactly seven records"
        )
    if SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US != 7000 or program.duration_us != 7000:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "reviewed physical proof final timestamp changed"
        )
    if tuple(record.opcode for record in program.records) != tuple(SaturnMidiOpcode):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "reviewed physical proof no longer covers every SRKM v1 opcode exactly once"
        )
    if tuple(record.channel for record in program.records) != tuple(range(7)):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "reviewed physical proof channel sequence changed"
        )


def _verify_candidate_gate(root: Path, manifest: dict) -> tuple[str, str, str, dict[str, str]]:
    gate = manifest.get(_CANDIDATE_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _CANDIDATE_SCHEMA:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate manifest has no recognized R20 physical-candidate gate"
        )
    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "expected_read_sequence": 1,
        "expected_read_index": 7,
        "expected_last_error": 0,
        "proof_records": 7,
        "proof_final_time_us": 7000,
        "proof_covers_every_srkm_v1_opcode_once": True,
        "decoder_linked": True,
        "decoder_installed_during_build": False,
        "decoder_executed_during_build": False,
        "decoder_candidate_bound": True,
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
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate R20 gate contract mismatch: {key}"
            )

    policy = manifest.get("policy")
    required_policy = {
        "sd_writes": False,
        "midi_68k_resident_decoder_present": True,
        "midi_68k_resident_decoder_linked": True,
        "midi_68k_resident_decoder_installed": False,
        "midi_68k_resident_decoder_executed": False,
        "midi_68k_resident_decoder_candidate_bound": True,
        "midi_68k_resident_decoder_user_trigger_required": True,
        "midi_68k_resident_decoder_build_time_hardware_actions": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    if not isinstance(policy, dict):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate policy is missing"
        )
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate policy mismatch: {key}"
            )

    main = _project_file(root, _EXPECTED_MAIN, "candidate main")
    menu = _project_file(root, _EXPECTED_MENU, "candidate menu")
    runtime = _project_file(root, _EXPECTED_RUNTIME, "candidate runtime")
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")
    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate main no longer begins with the R20 decoder define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u",
        "srk_saturn_midi_68k_resident_decoder_physical_proof_begin",
        "srk_saturn_midi_68k_resident_decoder_physical_proof_poll",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "Success: sequence=1 index=7 error=0",
        "telemetry.processed",
        "telemetry.current_record",
        "telemetry.decoder_ready",
    ):
        if marker not in main_text:
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate main is missing reviewed R20 marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "MIDI 68K Batch Proof" in menu_text:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate menu no longer isolates the R20 decoder proof"
        )
    for marker in (
        "resident_decoder_install_while_stopped",
        "proof_preload_publish",
        "resident_decoder_protocol_poll",
        "resident_decoder_physical_proof_begin",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate runtime is missing reviewed R20 seam: {marker}"
            )

    main_sha = _sha256_file(main)
    menu_sha = _sha256_file(menu)
    runtime_sha = _sha256_file(runtime)
    for key, actual in (
        ("candidate_main_sha256", main_sha),
        ("candidate_menu_sha256", menu_sha),
        ("runtime_after_sha256", runtime_sha),
    ):
        if str(gate.get(key, "")).lower() != actual.lower():
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate provenance hash mismatch: {key}"
            )

    seam_manifest = gate.get("seam_sha256")
    if not isinstance(seam_manifest, dict) or set(seam_manifest) != set(_SEAM_RENDERERS):
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate seam hash inventory is incomplete or unexpected"
        )
    seam_hashes: dict[str, str] = {}
    for name, renderer in _SEAM_RENDERERS.items():
        path = _project_file(root, f"src/{name}", f"candidate seam {name}")
        disk_sha = _sha256_file(path)
        rendered = renderer().encode("utf-8")
        rendered_sha = _sha256_bytes(rendered)
        if disk_sha != rendered_sha or str(seam_manifest.get(name, "")).lower() != disk_sha.lower():
            raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
                f"candidate generated seam no longer matches reviewed renderer: {name}"
            )
        seam_hashes[name] = disk_sha
    return main_sha, menu_sha, runtime_sha, seam_hashes


def _verify_build_report(root: Path, manifest_sha: str) -> str:
    report_path = root / _REPORT_NAME
    if not report_path.is_file():
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"candidate build report is missing: {report_path}"
        )
    report = _load_json(report_path, "candidate build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate build report is not a successful standalone build"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate build report does not match the current candidate manifest"
        )
    return _sha256_file(report_path)


def inspect_midi_68k_resident_decoder_physical_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaResult:
    """Revalidate R20 independently and return a read-only SAROO media plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"candidate project is not a directory: {root}"
        )
    expected_bin = _require_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha256(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"candidate manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "candidate manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "candidate manifest identity is unsupported"
        )

    manifest_sha = _sha256_file(manifest_path)
    _verify_generated_inventory(root, manifest)
    image_sha = _verify_decoder_provenance(
        manifest,
        expected_image_sha256=expected_image_sha256,
        expected_compiler_source_sha256=expected_compiler_source_sha256,
        expected_compiler_header_sha256=expected_compiler_header_sha256,
        expected_compiler_object_sha256=expected_compiler_object_sha256,
    )
    _verify_proof_program()
    main_sha, menu_sha, runtime_sha, seam_hashes = _verify_candidate_gate(root, manifest)
    report_sha = _verify_build_report(root, manifest_sha)

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected R20 candidate: {exc}"
        ) from exc

    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "fresh deployable BIN SHA-256 does not match the externally accepted R20 build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaGateError(
            "fresh deployable CUE SHA-256 does not match the externally accepted R20 build output"
        )

    return SaturnMidi68KResidentDecoderPhysicalCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        runtime_after_sha256=runtime_sha,
        seam_sha256=seam_hashes,
        proof_records=7,
        proof_final_time_us=7000,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
