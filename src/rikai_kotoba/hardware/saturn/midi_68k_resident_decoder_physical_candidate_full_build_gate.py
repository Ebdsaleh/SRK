"""Fresh off-card callable candidate for the general silent resident decoder.

The input must be the successful inert resident-decoder full-build tree.  The
derived tree preserves that baseline, binds a seven-record all-opcode proof to
the existing diagnostics screen, reuses the physically accepted R19 SMPC
adapter, and remains silent.  Building the candidate performs no Saturn or
SAROO action.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

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
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_header,
    render_srk_saturn_midi_68k_resident_decoder_proof_preload_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the resident-decoder physical candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderPhysicalCandidatePrepared:
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
    proof_records: int


@dataclass(frozen=True)
class SaturnMidi68KResidentDecoderPhysicalCandidateResult:
    prepared: SaturnMidi68KResidentDecoderPhysicalCandidatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_MAIN_NAME = "srk_saturn_main.c"
_MENU_NAME = "srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_INERT_GATE_KEY = "midi_68k_resident_decoder_full_build_gate"
_INERT_GATE_SCHEMA = "srk.saturn.midi-68k-resident-decoder-full-build-gate.v1"
_CANDIDATE_GATE_KEY = "midi_68k_resident_decoder_physical_candidate_full_build_gate"
_CANDIDATE_SCHEMA = "srk.saturn.midi-68k-resident-decoder-physical-candidate-full-build-gate.v1"
_R19_DEFINE = "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1"
_CANDIDATE_DEFINE = "#define SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE 1"
_R19_MENU_LABEL = '"MIDI 68K Batch Proof"'
_CANDIDATE_MENU_LABEL = '"MIDI 68K Decoder Proof"'
_INJECTION_MARKER = (
    "/* SRK MIDI 68K RESIDENT DECODER PHYSICAL CANDIDATE: generated seams follow. */"
)

_INSTALLER_SOURCE = "srk_saturn_midi_68k_resident_decoder_installer.c"
_INSTALLER_HEADER = "srk_saturn_midi_68k_resident_decoder_installer.h"
_PRELOAD_SOURCE = "srk_saturn_midi_68k_resident_decoder_proof_preload.c"
_PRELOAD_HEADER = "srk_saturn_midi_68k_resident_decoder_proof_preload.h"
_RUNTIME_SOURCE = "srk_saturn_midi_68k_resident_decoder_runtime.c"
_RUNTIME_HEADER = "srk_saturn_midi_68k_resident_decoder_runtime.h"
_PROOF_SOURCE = "srk_saturn_midi_68k_resident_decoder_physical_proof.c"
_PROOF_HEADER = "srk_saturn_midi_68k_resident_decoder_physical_proof.h"


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
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            f"{label} root must be an object"
        )
    return value


def _artifact_map(report: dict) -> dict[str, dict]:
    values = report.get("artifacts")
    if not isinstance(values, list):
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert build report has no artifact inventory"
        )
    return {
        str(value["path"]): value
        for value in values
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    }


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    values = manifest.get("generated_files")
    if not isinstance(values, list) or not values:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert manifest has no generated-file inventory"
        )
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                "inert generated-file inventory contains an invalid entry"
            )
        relative = value.get("path")
        size = value.get("size")
        expected_sha = value.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                "inert generated-file metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"inert generated input is missing: {relative}"
            )
        if path.stat().st_size != size or _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"inert generated input changed: {relative}"
            )
        result.append(value)
    return result


def _verify_inert_baseline(
    root: Path,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_image_sha256: str,
    expected_source_sha256: str,
    expected_header_sha256: str,
    expected_object_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert resident-decoder baseline must contain manifest and build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "inert resident-decoder manifest")
    report = _load_json(report_path, "inert resident-decoder build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert baseline manifest identity is unsupported"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert baseline build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert build report does not match its current manifest"
        )

    gate = manifest.get(_INERT_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _INERT_GATE_SCHEMA:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "baseline is not the resident-decoder inert full-build gate"
        )
    required = {
        "existing_r19_candidate_binding_preserved": True,
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
        "embedded_records": 0,
        "runtime_record_minimum": 1,
        "runtime_record_maximum": 32,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"inert resident-decoder gate state changed: {key}"
            )

    for key, supplied, label in (
        ("image_sha256", expected_image_sha256, "decoder image"),
        ("source_sha256", expected_source_sha256, "compiler source"),
        ("header_sha256", expected_header_sha256, "compiler header"),
        ("accepted_compile_object_sha256_evidence", expected_object_sha256, "compiler object evidence"),
    ):
        expected = _require_sha256(supplied, f"expected {label} SHA-256")
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"inert baseline {label} provenance mismatch"
            )

    image = build_srk_saturn_midi_68k_resident_decoder_image()
    if image.sha256.lower() != _require_sha256(expected_image_sha256, "expected decoder image SHA-256"):
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "current decoder generator no longer matches the accepted inert image"
        )

    artifacts = _artifact_map(report)
    accepted: list[str] = []
    for relative, supplied, label in (
        (_DEPLOY_BIN, expected_bin_sha256, "inert deployable BIN"),
        (_DEPLOY_CUE, expected_cue_sha256, "inert deployable CUE"),
    ):
        expected = _require_sha256(supplied, f"expected {label} SHA-256")
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"{label} report hash does not match accepted evidence"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"{label} file no longer matches accepted evidence"
            )
        accepted.append(expected)

    main = root / "src" / _MAIN_NAME
    menu = root / "src" / _MENU_NAME
    if not main.is_file() or not menu.is_file():
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert baseline is missing the preserved R19 main/menu"
        )
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    if not main_text.startswith(_R19_DEFINE + "\n"):
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert baseline no longer begins with the accepted R19 candidate define"
        )
    if menu_text.count(_R19_MENU_LABEL) != 1:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "inert baseline no longer contains exactly one R19 proof menu label"
        )

    return manifest, _verify_generated_inputs(root, manifest), manifest_sha, report_sha, accepted[0], accepted[1]


def _copy_generated_inputs(baseline: Path, staging: Path, entries: list[dict[str, object]]) -> None:
    for entry in entries:
        relative = str(entry["path"])
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline / relative, destination)


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


def _derive_candidate_main(r19_main: str) -> str:
    if not r19_main.startswith(_R19_DEFINE + "\n"):
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "R19 main candidate define is missing"
        )
    main = _CANDIDATE_DEFINE + r19_main[len(_R19_DEFINE):]

    old_guard = (
        "#if defined(SRK_MIDI_68K_PHYSICAL_PROOF_CANDIDATE) || \\\n"
        "    defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)"
    )
    new_guard = old_guard + " || \\\n    defined(SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE)"
    count = main.count(old_guard)
    if count < 2:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "R19 main proof guard shape changed"
        )
    main = main.replace(old_guard, new_guard)

    include = '#include "srk_saturn_midi_68k_physical_proof.h"'
    if main.count(include) != 1:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "R19 main physical-proof include shape changed"
        )
    main = main.replace(
        include,
        include
        + "\n#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE"
        + '\n#include "srk_saturn_midi_68k_resident_decoder_physical_proof.h"'
        + "\n#endif",
        1,
    )

    marker = "#ifdef SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE\n"
    if main.count(marker) != 1:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "R19 main alias block shape changed"
        )
    resident = "\n".join(
        (
            "#ifdef SRK_MIDI_68K_RESIDENT_DECODER_PHYSICAL_CANDIDATE",
            "typedef SRK_SATURN_MIDI_68K_RESIDENT_DECODER_PHYSICAL_PROOF_STATE",
            "    SRK_MIDI_68K_ACTIVE_PROOF_STATE;",
            "#define SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u",
            '#define SRK_MIDI_68K_PROOF_TITLE "MIDI / 68K DECODER PROOF"',
            '#define SRK_MIDI_68K_PROOF_SUBTITLE "7 runtime records - no MIDI SCSP note"',
            '#define SRK_MIDI_68K_PROOF_SUCCESS "Success: sequence=1 index=7 error=0"',
            "#define SRK_MIDI_68K_PROOF_RESET srk_saturn_midi_68k_resident_decoder_physical_proof_reset",
            "#define SRK_MIDI_68K_PROOF_BEGIN srk_saturn_midi_68k_resident_decoder_physical_proof_begin",
            "#define SRK_MIDI_68K_PROOF_POLL srk_saturn_midi_68k_resident_decoder_physical_proof_poll",
            "#elif defined(SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE)",
        )
    ) + "\n"
    main = main.replace(marker, resident, 1)

    required = (
        _CANDIDATE_DEFINE,
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 7u",
        '"MIDI / 68K DECODER PROOF"',
        '"Success: sequence=1 index=7 error=0"',
        "srk_saturn_midi_68k_resident_decoder_physical_proof_begin",
        "srk_saturn_midi_68k_resident_decoder_physical_proof_poll",
        "Release A to arm proof action",
    )
    for value in required:
        if value not in main:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                f"derived candidate main is missing reviewed marker: {value}"
            )
    return main


def prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
) -> SaturnMidi68KResidentDecoderPhysicalCandidatePrepared:
    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            f"inert resident-decoder baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )
    if baseline == output or baseline in output.parents:
        raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
            "output must not be the inert baseline or its child"
        )

    manifest, entries, manifest_sha, report_sha, bin_sha, cue_sha = _verify_inert_baseline(
        baseline,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_image_sha256=expected_image_sha256,
        expected_source_sha256=expected_compiler_source_sha256,
        expected_header_sha256=expected_compiler_header_sha256,
        expected_object_sha256=expected_compiler_object_sha256,
    )

    seam_texts = {
        _INSTALLER_SOURCE: render_resident_decoder_installer_source(),
        _INSTALLER_HEADER: render_resident_decoder_installer_header(),
        _PRELOAD_SOURCE: render_srk_saturn_midi_68k_resident_decoder_proof_preload_source(),
        _PRELOAD_HEADER: render_srk_saturn_midi_68k_resident_decoder_proof_preload_header(),
        _RUNTIME_SOURCE: render_resident_decoder_runtime_source(),
        _RUNTIME_HEADER: render_resident_decoder_runtime_header(),
        _PROOF_SOURCE: render_resident_decoder_proof_source(),
        _PROOF_HEADER: render_resident_decoder_proof_header(),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    staging = temporary / "stage"
    staging.mkdir()
    try:
        _copy_generated_inputs(baseline, staging, entries)
        source_dir = staging / "src"
        runtime_path = source_dir / _RUNTIME_NAME
        main_path = source_dir / _MAIN_NAME
        menu_path = source_dir / _MENU_NAME
        if not runtime_path.is_file() or not main_path.is_file() or not menu_path.is_file():
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                "inert baseline is missing runtime/main/menu source"
            )

        runtime_before = runtime_path.read_bytes()
        main_before = main_path.read_text(encoding="utf-8")
        menu_before = menu_path.read_text(encoding="utf-8")
        candidate_main = _derive_candidate_main(main_before).encode("utf-8")
        if menu_before.count(_R19_MENU_LABEL) != 1:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                "R19 menu label is no longer isolated"
            )
        candidate_menu = menu_before.replace(_R19_MENU_LABEL, _CANDIDATE_MENU_LABEL, 1).encode("utf-8")
        main_path.write_bytes(candidate_main)
        menu_path.write_bytes(candidate_menu)

        for name, text in seam_texts.items():
            (source_dir / name).write_text(text, encoding="utf-8", newline="\n")

        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KResidentDecoderPhysicalCandidateFullBuildGateError(
                "inert runtime already contains resident-decoder candidate injection"
            )
        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n"
        for name in (_INSTALLER_SOURCE, _PRELOAD_SOURCE, _RUNTIME_SOURCE, _PROOF_SOURCE):
            payload = seam_texts[name].encode("utf-8")
            runtime_after += payload
            if not runtime_after.endswith(b"\n"):
                runtime_after += b"\n"
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy["sd_writes"] = False
        policy["midi_68k_silent_batch_candidate_bound"] = False
        policy["midi_68k_resident_decoder_present"] = True
        policy["midi_68k_resident_decoder_linked"] = True
        policy["midi_68k_resident_decoder_installed"] = False
        policy["midi_68k_resident_decoder_executed"] = False
        policy["midi_68k_resident_decoder_candidate_bound"] = True
        policy["midi_68k_resident_decoder_user_trigger_required"] = True
        policy["midi_68k_resident_decoder_build_time_hardware_actions"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        candidate_manifest["policy"] = policy

        gate = {
            "schema": _CANDIDATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "accepted_inert_deploy_bin_sha256": bin_sha,
            "accepted_inert_deploy_cue_sha256": cue_sha,
            "candidate_define": _CANDIDATE_DEFINE,
            "candidate_menu_label": _CANDIDATE_MENU_LABEL.strip('"'),
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "expected_read_sequence": 1,
            "expected_read_index": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
            "expected_last_error": 0,
            "proof_records": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
            "proof_final_time_us": SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_FINAL_TIME_US,
            "proof_covers_every_srkm_v1_opcode_once": True,
            "decoder_image_sha256": _require_sha256(expected_image_sha256, "expected decoder image SHA-256"),
            "compiler_source_sha256": _require_sha256(expected_compiler_source_sha256, "expected compiler source SHA-256"),
            "compiler_header_sha256": _require_sha256(expected_compiler_header_sha256, "expected compiler header SHA-256"),
            "compiler_object_sha256_evidence": _require_sha256(expected_compiler_object_sha256, "expected compiler object SHA-256"),
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
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
            "seam_sha256": {
                name: _sha256_bytes(text.encode("utf-8"))
                for name, text in seam_texts.items()
            },
        }
        candidate_manifest[_CANDIDATE_GATE_KEY] = gate
        candidate_manifest["generated_files"] = _inventory(staging)
        (staging / _MANIFEST_NAME).write_text(
            json.dumps(candidate_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        staging.replace(output)
        temporary.rmdir()
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return SaturnMidi68KResidentDecoderPhysicalCandidatePrepared(
        baseline_root=baseline,
        output_root=output,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=bin_sha,
        baseline_cue_sha256=cue_sha,
        image_sha256=_require_sha256(expected_image_sha256, "expected decoder image SHA-256"),
        candidate_main_sha256=_sha256_bytes(candidate_main),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        runtime_after_sha256=_sha256_bytes(runtime_after),
        proof_records=SATURN_MIDI_68K_RESIDENT_DECODER_PROOF_RECORDS,
    )


def run_midi_68k_resident_decoder_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KResidentDecoderPhysicalCandidateResult:
    prepared = prepare_midi_68k_resident_decoder_physical_candidate_full_build_gate(
        baseline_project, output_directory, **kwargs
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KResidentDecoderPhysicalCandidateResult(prepared=prepared, build=build)
