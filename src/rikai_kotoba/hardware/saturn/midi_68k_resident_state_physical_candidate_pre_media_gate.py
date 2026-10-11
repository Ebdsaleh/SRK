"""Independent read-only pre-media gate for the Phase-B full-state candidate.

The gate re-opens a completed callable candidate as an external artifact,
revalidates the compiler-accepted Phase-B image, richer 20-record proof, all ten
generated binding seams and the complete expected-state contract, then delegates
only to the existing read-only SAROO deployment planner.  It has no apply path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from .midi_68k_resident_state_decoder import (
    build_srk_saturn_midi_68k_resident_state_decoder_image,
)
from .midi_68k_resident_state_decoder_physical_binding import (
    render_resident_state_decoder_installer_header,
    render_resident_state_decoder_installer_source,
    render_resident_state_decoder_proof_header,
    render_resident_state_decoder_proof_source,
    render_resident_state_decoder_runtime_header,
    render_resident_state_decoder_runtime_source,
)
from .midi_68k_resident_state_decoder_physical_candidate import (
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US,
    SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS,
    build_srk_saturn_midi_68k_resident_state_expected_words,
    build_srk_saturn_midi_68k_resident_state_proof_program,
    build_srk_saturn_midi_68k_resident_state_proof_snapshot,
    render_srk_saturn_midi_68k_resident_state_proof_preload_header,
    render_srk_saturn_midi_68k_resident_state_proof_preload_source,
    render_srk_saturn_midi_68k_resident_state_verifier_header,
    render_srk_saturn_midi_68k_resident_state_verifier_source,
)
from .midi_program import SaturnMidiOpcode
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when the Phase-B state candidate cannot pass pre-media review."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStatePhysicalCandidatePreMediaResult:
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
    summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_INERT_GATE_KEY = "midi_68k_resident_state_decoder_full_build_gate"
_CANDIDATE_GATE_KEY = "midi_68k_resident_state_decoder_physical_candidate_full_build_gate"
_INERT_SCHEMA = "srk.saturn.midi-68k-resident-state-decoder-full-build-gate.v1"
_CANDIDATE_SCHEMA = "srk.saturn.midi-68k-resident-state-decoder-physical-candidate-full-build-gate.v1"
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_RESIDENT_STATE_DECODER_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K State Proof"
_EXPECTED_MAIN = "src/srk_saturn_main.c"
_EXPECTED_MENU = "src/srk_diag_menu.c"
_EXPECTED_RUNTIME = "src/srk_saturn_runtime.c"
_SEAM_RENDERERS = {
    "srk_saturn_midi_68k_resident_state_decoder_installer.c": render_resident_state_decoder_installer_source,
    "srk_saturn_midi_68k_resident_state_decoder_installer.h": render_resident_state_decoder_installer_header,
    "srk_saturn_midi_68k_resident_state_proof_preload.c": render_srk_saturn_midi_68k_resident_state_proof_preload_source,
    "srk_saturn_midi_68k_resident_state_proof_preload.h": render_srk_saturn_midi_68k_resident_state_proof_preload_header,
    "srk_saturn_midi_68k_resident_state_verifier.c": render_srk_saturn_midi_68k_resident_state_verifier_source,
    "srk_saturn_midi_68k_resident_state_verifier.h": render_srk_saturn_midi_68k_resident_state_verifier_header,
    "srk_saturn_midi_68k_resident_state_decoder_runtime.c": render_resident_state_decoder_runtime_source,
    "srk_saturn_midi_68k_resident_state_decoder_runtime.h": render_resident_state_decoder_runtime_header,
    "srk_saturn_midi_68k_resident_state_physical_proof.c": render_resident_state_decoder_proof_source,
    "srk_saturn_midi_68k_resident_state_physical_proof.h": render_resident_state_decoder_proof_header,
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
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"{label} must be exactly 64 hexadecimal SHA-256 characters"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"{label} path escapes the candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate manifest has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
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
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                "candidate generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate generated input changed: {relative}"
            )

    required = {_EXPECTED_MAIN, _EXPECTED_MENU, _EXPECTED_RUNTIME}
    required.update(f"src/{name}" for name in _SEAM_RENDERERS)
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate inventory is missing required Phase-B inputs: " + ", ".join(missing)
        )


def _verify_state_decoder_provenance(
    manifest: dict,
    *,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
) -> str:
    inert = manifest.get(_INERT_GATE_KEY)
    if not isinstance(inert, dict) or inert.get("schema") != _INERT_SCHEMA:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate no longer carries accepted Phase-B inert provenance"
        )
    expected = {
        "image_sha256": _require_sha256(expected_image_sha256, "expected Phase-B image SHA-256"),
        "source_sha256": _require_sha256(expected_compiler_source_sha256, "expected compiler source SHA-256"),
        "header_sha256": _require_sha256(expected_compiler_header_sha256, "expected compiler header SHA-256"),
        "accepted_compile_object_sha256_evidence": _require_sha256(
            expected_compiler_object_sha256, "expected compiler object SHA-256"
        ),
    }
    for key, value in expected.items():
        if str(inert.get(key, "")).lower() != value:
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate inherited Phase-B provenance mismatch: {key}"
            )

    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    if image.sha256.lower() != expected["image_sha256"]:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "current Phase-B generator no longer matches accepted image evidence"
        )
    if image.word_count != 4898 or image.byte_size != 9796 or image.end_address != 0x00006644:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "accepted Phase-B image geometry changed"
        )
    return image.sha256


def _verify_proof_program() -> tuple[int, int, int]:
    program = build_srk_saturn_midi_68k_resident_state_proof_program()
    if (
        SATURN_MIDI_68K_RESIDENT_STATE_PROOF_RECORDS != 20
        or len(program.records) != 20
        or SATURN_MIDI_68K_RESIDENT_STATE_PROOF_FINAL_TIME_US != 20000
        or program.duration_us != 20000
    ):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "reviewed Phase-B physical proof count/time contract changed"
        )
    if set(record.opcode for record in program.records) != set(SaturnMidiOpcode):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "reviewed Phase-B proof no longer exercises every SRKM v1 opcode"
        )
    summaries, controllers, active = build_srk_saturn_midi_68k_resident_state_expected_words()
    if (len(summaries), len(controllers), len(active)) != (256, 1024, 128):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "reviewed full-state verification surface changed"
        )
    return len(summaries), len(controllers), len(active)


def _verify_candidate_gate(
    root: Path,
    manifest: dict,
) -> tuple[str, str, str, dict[str, str]]:
    gate = manifest.get(_CANDIDATE_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _CANDIDATE_SCHEMA:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate manifest has no recognized Phase-B physical-candidate gate"
        )

    snapshot = asdict(build_srk_saturn_midi_68k_resident_state_proof_snapshot())
    required = {
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
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
        "state_decoder_linked": True,
        "state_decoder_installed_during_build": False,
        "state_decoder_executed_during_build": False,
        "state_decoder_candidate_bound": True,
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
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate Phase-B gate contract mismatch: {key}"
            )
    if gate.get("expected_state_snapshot") != snapshot:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate expected-state snapshot no longer matches the reviewed model"
        )

    policy = manifest.get("policy")
    required_policy = {
        "sd_writes": False,
        "midi_68k_resident_state_decoder_present": True,
        "midi_68k_resident_state_decoder_linked": True,
        "midi_68k_resident_state_decoder_installed": False,
        "midi_68k_resident_state_decoder_executed": False,
        "midi_68k_resident_state_decoder_candidate_bound": True,
        "midi_68k_resident_state_decoder_user_trigger_required": True,
        "midi_68k_resident_state_decoder_build_time_hardware_actions": False,
        "midi_sound_ram_writes": False,
        "midi_scsp_mmio": False,
        "midi_smpc_commands": False,
        "midi_mc68ec000_execution": False,
    }
    if not isinstance(policy, dict):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate policy is missing"
        )
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate policy mismatch: {key}"
            )

    main = _project_file(root, _EXPECTED_MAIN, "candidate main")
    menu = _project_file(root, _EXPECTED_MENU, "candidate menu")
    runtime = _project_file(root, _EXPECTED_RUNTIME, "candidate runtime")
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")
    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate main no longer begins with the Phase-B state define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 20u",
        "srk_saturn_midi_68k_resident_state_physical_proof_begin",
        "srk_saturn_midi_68k_resident_state_physical_proof_poll",
        "(srk_app.input.current & SRK_DIAG_BUTTON_A) == 0u",
        "(srk_app.input.pressed & SRK_DIAG_BUTTON_A) != 0u",
        "State PASS: full MIDI state matched",
        "state_verify.status",
        "state_verify.ch3_program",
        "state_verify.ch3_cc74",
        "state_verify.ch9_program",
        'srk_midi_68k_draw_field(2, 26, 36, "Release A to arm proof action");',
        'srk_midi_68k_draw_field(2, 27, 36, "START Return to diagnostics menu");',
    ):
        if marker not in main_text:
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate main is missing reviewed Phase-B marker: {marker}"
            )
    for forbidden in (
        'srk_midi_68k_draw_field(2, 17, 36, "Release A to arm proof action");',
        'srk_midi_68k_draw_field(2, 19, 36, "START Return to diagnostics menu");',
    ):
        if forbidden in main_text:
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                "candidate main still contains an overlapping R20 prompt row"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "MIDI 68K Decoder Proof" in menu_text:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate menu no longer isolates the Phase-B state proof"
        )
    for marker in (
        "resident_state_decoder_install_while_stopped",
        "resident_state_proof_preload_publish",
        "resident_state_verify(&current.state_verify)",
        "resident_state_protocol_poll",
        "resident_state_physical_proof_begin",
        "expected_summary_words",
        "expected_controller_words",
        "expected_active_words",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate runtime is missing reviewed Phase-B seam: {marker}"
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
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate provenance hash mismatch: {key}"
            )

    seam_manifest = gate.get("seam_sha256")
    if not isinstance(seam_manifest, dict) or set(seam_manifest) != set(_SEAM_RENDERERS):
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate seam hash inventory is incomplete or unexpected"
        )
    seam_hashes: dict[str, str] = {}
    for name, renderer in _SEAM_RENDERERS.items():
        path = _project_file(root, f"src/{name}", f"candidate seam {name}")
        disk_sha = _sha256_file(path)
        rendered_sha = _sha256_bytes(renderer().encode("utf-8"))
        if disk_sha != rendered_sha or str(seam_manifest.get(name, "")).lower() != disk_sha.lower():
            raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
                f"candidate generated seam no longer matches reviewed renderer: {name}"
            )
        seam_hashes[name] = disk_sha
    return main_sha, menu_sha, runtime_sha, seam_hashes


def _verify_build_report(root: Path, manifest_sha: str) -> str:
    report_path = root / _REPORT_NAME
    if not report_path.is_file():
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"candidate build report is missing: {report_path}"
        )
    report = _load_json(report_path, "candidate build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate build report is not a successful standalone build"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate build report does not match the current candidate manifest"
        )
    return _sha256_file(report_path)


def inspect_midi_68k_resident_state_physical_candidate_pre_media(
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
) -> SaturnMidi68KResidentStatePhysicalCandidatePreMediaResult:
    """Revalidate Phase B independently and return a read-only SAROO media plan."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"candidate project is not a directory: {root}"
        )
    expected_bin = _require_sha256(expected_bin_sha256, "expected BIN SHA-256")
    expected_cue = _require_sha256(expected_cue_sha256, "expected CUE SHA-256")

    manifest_path = root / _MANIFEST_NAME
    if not manifest_path.is_file():
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"candidate manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "candidate manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "candidate manifest identity is unsupported"
        )

    manifest_sha = _sha256_file(manifest_path)
    _verify_generated_inventory(root, manifest)
    image_sha = _verify_state_decoder_provenance(
        manifest,
        expected_image_sha256=expected_image_sha256,
        expected_compiler_source_sha256=expected_compiler_source_sha256,
        expected_compiler_header_sha256=expected_compiler_header_sha256,
        expected_compiler_object_sha256=expected_compiler_object_sha256,
    )
    summary_count, controller_count, active_count = _verify_proof_program()
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
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected Phase-B candidate: {exc}"
        ) from exc

    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "fresh deployable BIN SHA-256 does not match externally accepted Phase-B build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KResidentStatePhysicalCandidatePreMediaGateError(
            "fresh deployable CUE SHA-256 does not match externally accepted Phase-B build output"
        )

    return SaturnMidi68KResidentStatePhysicalCandidatePreMediaResult(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        runtime_after_sha256=runtime_sha,
        seam_sha256=seam_hashes,
        proof_records=20,
        proof_final_time_us=20000,
        summary_words_verified=summary_count,
        controller_words_verified=controller_count,
        active_note_words_verified=active_count,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
