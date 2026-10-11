"""Fresh inert full-build gate for the Phase-B resident state decoder.

The input is the physically accepted R20 callable candidate tree.  The R20
proof remains byte-for-byte callable while the new Phase-B state-mutating image
is linked only as constant data.  It is not installed, executed or menu-bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_state_decoder import (
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS,
    SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_state_decoder_image,
    render_srk_saturn_midi_68k_resident_state_decoder_header,
    render_srk_saturn_midi_68k_resident_state_decoder_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentStateDecoderFullBuildGateError(RuntimeError):
    """Raised when the Phase-B inert standalone integration cannot be proven safe."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStateDecoderFullBuildGatePrepared:
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
    source_sha256: str
    header_sha256: str
    compiler_object_sha256: str
    r20_main_sha256: str
    r20_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KResidentStateDecoderFullBuildGateResult:
    prepared: SaturnMidi68KResidentStateDecoderFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_STATE_SOURCE = "src/srk_saturn_midi_68k_resident_state_decoder.c"
_STATE_HEADER = "src/srk_saturn_midi_68k_resident_state_decoder.h"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R20_GATE_KEY = "midi_68k_resident_decoder_physical_candidate_full_build_gate"
_R20_GATE_SCHEMA = "srk.saturn.midi-68k-resident-decoder-physical-candidate-full-build-gate.v1"
_PHASE_B_GATE_KEY = "midi_68k_resident_state_decoder_full_build_gate"
_PHASE_B_GATE_SCHEMA = "srk.saturn.midi-68k-resident-state-decoder-full-build-gate.v1"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K RESIDENT STATE DECODER INERT FULL-BUILD GATE: constant image follows. */"
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
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            f"{label} root must be an object"
        )
    return value


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            "accepted R20 manifest has no generated-file inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                "accepted R20 generated-file inventory contains an invalid entry"
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
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                "accepted R20 generated-file metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size:
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                f"accepted R20 generated input size/path mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                f"accepted R20 generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    values = report.get("artifacts")
    if not isinstance(values, list):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            "accepted R20 build report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in values
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_r20_baseline(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str, str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            "accepted R20 baseline must contain manifest and build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    if manifest_sha.lower() != _require_sha256(expected_manifest_sha256, "expected R20 manifest SHA-256"):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("R20 manifest hash mismatch")
    if report_sha.lower() != _require_sha256(expected_report_sha256, "expected R20 report SHA-256"):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("R20 report hash mismatch")

    manifest = _load_json(manifest_path, "accepted R20 manifest")
    report = _load_json(report_path, "accepted R20 build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("accepted R20 manifest identity changed")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("accepted R20 build report is not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("accepted R20 report no longer matches manifest")

    gate = manifest.get(_R20_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R20_GATE_SCHEMA:
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("baseline is not the accepted R20 candidate")
    required_gate = {
        "candidate_define": "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1",
        "candidate_menu_label": "MIDI 68K Decoder Proof",
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
    }
    for key, expected in required_gate.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                f"accepted R20 gate changed: {key}"
            )

    generated = _verify_generated_inputs(root, manifest)
    artifacts = _artifact_map(report)
    accepted_hashes: list[str] = []
    for relative, expected_value, label in (
        (_DEPLOY_BIN, expected_bin_sha256, "R20 deployable BIN"),
        (_DEPLOY_CUE, expected_cue_sha256, "R20 deployable CUE"),
    ):
        expected = _require_sha256(expected_value, f"expected {label} SHA-256")
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                f"{label} no longer matches build report"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                f"{label} no longer matches accepted disk artifact"
            )
        accepted_hashes.append(expected)

    main_sha = _sha256_file(root / _MAIN)
    menu_sha = _sha256_file(root / _MENU)
    if main_sha.lower() != str(gate.get("candidate_main_sha256", "")).lower():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("accepted R20 main hash changed")
    if menu_sha.lower() != str(gate.get("candidate_menu_sha256", "")).lower():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("accepted R20 menu hash changed")

    return (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        accepted_hashes[0],
        accepted_hashes[1],
        main_sha,
        menu_sha,
    )


def _copy_generated_inputs(root: Path, staging: Path, entries: list[dict[str, object]]) -> None:
    for entry in entries:
        relative = str(entry["path"])
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, destination)


def _inventory(root: Path) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if path.is_file() and path.name != _MANIFEST_NAME:
            values.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256_file(path),
                }
            )
    return values


def prepare_midi_68k_resident_state_decoder_full_build_gate(
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
) -> SaturnMidi68KResidentStateDecoderFullBuildGatePrepared:
    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            f"accepted R20 baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        baseline_bin_sha,
        baseline_cue_sha,
        main_sha,
        menu_sha,
    ) = _verify_r20_baseline(
        baseline,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_state_decoder_image()
    if image.sha256.lower() != _require_sha256(expected_image_sha256, "expected Phase-B image SHA-256"):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError("Phase-B image hash mismatch")

    source_bytes = render_srk_saturn_midi_68k_resident_state_decoder_source().encode("utf-8")
    header_bytes = render_srk_saturn_midi_68k_resident_state_decoder_header().encode("utf-8")
    source_sha = _sha256_bytes(source_bytes)
    header_sha = _sha256_bytes(header_bytes)
    if source_sha != _require_sha256(expected_compiler_source_sha256, "expected compiler source SHA-256"):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            "Phase-B source no longer matches compiler-accepted representation"
        )
    if header_sha != _require_sha256(expected_compiler_header_sha256, "expected compiler header SHA-256"):
        raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
            "Phase-B header no longer matches compiler-accepted representation"
        )
    object_sha = _require_sha256(expected_compiler_object_sha256, "expected compiler object SHA-256")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    staging = temporary / "stage"
    staging.mkdir()
    try:
        _copy_generated_inputs(baseline, staging, generated)
        runtime_path = staging / _RUNTIME
        runtime_before = runtime_path.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentStateDecoderFullBuildGateError(
                "accepted R20 runtime already contains Phase-B inert injection"
            )

        (staging / _STATE_SOURCE).write_bytes(source_bytes)
        (staging / _STATE_HEADER).write_bytes(header_bytes)
        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n" + source_bytes
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate = dict(manifest)
        policy = dict(candidate.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_resident_state_decoder_present": True,
                "midi_68k_resident_state_decoder_linked": True,
                "midi_68k_resident_state_decoder_installed": False,
                "midi_68k_resident_state_decoder_executed": False,
                "midi_68k_resident_state_decoder_candidate_bound": False,
                "midi_68k_resident_state_decoder_build_time_hardware_actions": False,
                "midi_sound_ram_writes": False,
                "midi_scsp_mmio": False,
                "midi_smpc_commands": False,
                "midi_mc68ec000_execution": False,
            }
        )
        candidate["policy"] = policy
        candidate[_PHASE_B_GATE_KEY] = {
            "schema": _PHASE_B_GATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "baseline_deploy_bin_sha256": baseline_bin_sha,
            "baseline_deploy_cue_sha256": baseline_cue_sha,
            "existing_r20_candidate_binding_preserved": True,
            "r20_main_sha256": main_sha,
            "r20_menu_sha256": menu_sha,
            "state_decoder_source_copy": _STATE_SOURCE,
            "state_decoder_header_copy": _STATE_HEADER,
            "compile_injection": _RUNTIME,
            "image_sha256": image.sha256,
            "image_word_count": image.word_count,
            "image_byte_size": image.byte_size,
            "program_address": SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS,
            "program_end_address": image.end_address,
            "runtime_record_minimum": 1,
            "runtime_record_maximum": SATURN_MIDI_68K_RESIDENT_STATE_DECODER_MAX_RECORDS,
            "dynamic_state_mutation": True,
            "source_sha256": source_sha,
            "header_sha256": header_sha,
            "accepted_compile_object_sha256_evidence": object_sha,
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "state_decoder_linked": True,
            "state_decoder_installed": False,
            "state_decoder_executed": False,
            "state_decoder_candidate_bound": False,
            "midi_scsp_note_attempted": False,
            "build_time_hardware_io": False,
            "saroo_write": False,
            "off_card_only": True,
            "behaviorally_active": False,
        }
        candidate["generated_files"] = _inventory(staging)
        (staging / _MANIFEST_NAME).write_text(
            json.dumps(candidate, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        staging.replace(output)
        temporary.rmdir()
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return SaturnMidi68KResidentStateDecoderFullBuildGatePrepared(
        baseline_root=baseline,
        output_root=output,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin_sha,
        baseline_cue_sha256=baseline_cue_sha,
        image_sha256=image.sha256,
        image_word_count=image.word_count,
        image_byte_size=image.byte_size,
        program_address=SATURN_MIDI_68K_RESIDENT_STATE_DECODER_PROGRAM_ADDRESS,
        program_end_address=image.end_address,
        source_sha256=source_sha,
        header_sha256=header_sha,
        compiler_object_sha256=object_sha,
        r20_main_sha256=main_sha,
        r20_menu_sha256=menu_sha,
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_resident_state_decoder_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs,
) -> SaturnMidi68KResidentStateDecoderFullBuildGateResult:
    prepared = prepare_midi_68k_resident_state_decoder_full_build_gate(
        baseline_project,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentStateDecoderFullBuildGateResult(prepared=prepared, build=build)
