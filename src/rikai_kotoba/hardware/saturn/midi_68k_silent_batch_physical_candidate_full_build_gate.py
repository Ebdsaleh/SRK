"""Fresh off-card full-build gate for the callable silent 27-record MIDI/68K proof.

The input must be the successful inert silent-batch full-build tree.  That tree
already carries the compiler-accepted 0x4000 MC68EC000 image, but leaves it
unbound, uninstalled and unexecuted.  This gate derives a fresh project,
replaces only the reviewed diagnostic main/menu binding, adds the batch
installer/runtime/proof seams, and runs the normal standalone builder.

The build command itself performs no Saturn hardware action and has no
SAROO/card deployment path.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the callable silent-batch candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchPhysicalCandidatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    reviewed_main_sha256: str
    candidate_main_sha256: str
    reviewed_menu_sha256: str
    candidate_menu_sha256: str
    installer_source_sha256: str
    installer_header_sha256: str
    batch_runtime_source_sha256: str
    batch_runtime_header_sha256: str
    proof_header_sha256: str
    proof_batch_suffix_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchPhysicalCandidateResult:
    prepared: SaturnMidi68KSilentBatchPhysicalCandidatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_MAIN_NAME = "srk_saturn_main.c"
_MENU_NAME = "srk_diag_menu.c"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_INSTALLER_SOURCE = "srk_saturn_midi_68k_silent_batch_installer.c"
_INSTALLER_HEADER = "srk_saturn_midi_68k_silent_batch_installer.h"
_BATCH_RUNTIME_SOURCE = "srk_saturn_midi_68k_silent_batch_runtime.c"
_BATCH_RUNTIME_HEADER = "srk_saturn_midi_68k_silent_batch_runtime.h"
_PROOF_SOURCE = "srk_saturn_midi_68k_physical_proof.c"
_PROOF_HEADER = "srk_saturn_midi_68k_physical_proof.h"
_CANDIDATE_DEFINE = "#define SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE 1"
_OLD_MENU_LABEL = '"Timing / Interrupt Test"'
_NEW_MENU_LABEL = '"MIDI 68K Batch Proof"'
_BATCH_PROOF_MARKER = "void srk_saturn_midi_68k_silent_batch_physical_proof_reset("
_INJECTION_MARKER = (
    "/* SRK MIDI 68K SILENT BATCH PHYSICAL CANDIDATE: runtime seams follow. */"
)
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"


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
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, description: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            f"cannot read {description}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            f"{description} root must be an object"
        )
    return value


def _artifact_map(report: dict) -> dict[str, dict]:
    values = report.get("artifacts")
    if not isinstance(values, list):
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline build report has no artifact inventory"
        )
    result: dict[str, dict] = {}
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            result[str(value["path"])] = value
    return result


def _verify_generated_inputs(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline manifest has no generated file inventory"
        )
    verified: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                "inert generated file inventory contains an invalid entry"
            )
        relative = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or not isinstance(expected_size, int)
            or expected_size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                "inert generated-file metadata is invalid"
            )
        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"inert generated input is missing: {relative}"
            )
        if path.stat().st_size != expected_size:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"inert generated input size mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"inert generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _verify_inert_baseline(
    root: Path,
    *,
    expected_image_sha256: str,
    expected_deploy_bin_sha256: str,
    expected_deploy_cue_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str]:
    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline must contain both manifest and successful build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "inert silent-batch manifest")
    report = _load_json(report_path, "inert silent-batch build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline manifest schema is unsupported"
        )
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline is not standalone-master mode"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert silent-batch full build was not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert build report does not match its manifest"
        )

    gate = manifest.get("midi_68k_silent_batch_full_build_gate")
    if not isinstance(gate, dict):
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "baseline is not the inert silent-batch full-build gate"
        )
    expected_image = _require_sha256(expected_image_sha256, "expected silent-batch image SHA-256")
    if str(gate.get("image_sha256", "")).lower() != expected_image:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "inert baseline carries a different silent-batch image"
        )
    required_gate = {
        "existing_r18_candidate_binding_preserved": True,
        "batch_program_linked": True,
        "batch_program_installed": False,
        "batch_program_executed": False,
        "batch_candidate_bound": False,
        "midi_scsp_note_attempted": False,
        "build_time_smpc_commands": False,
        "build_time_sound_ram_writes": False,
        "build_time_mc68ec000_execution": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active": False,
    }
    for key, expected in required_gate.items():
        if gate.get(key) is not expected:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"inert silent-batch gate state changed: {key}"
            )

    artifacts = _artifact_map(report)
    for relative, expected_hash, label in (
        (_DEPLOY_BIN, expected_deploy_bin_sha256, "inert deployable BIN"),
        (_DEPLOY_CUE, expected_deploy_cue_sha256, "inert deployable CUE"),
    ):
        entry = artifacts.get(relative)
        expected = _require_sha256(expected_hash, f"expected {label} SHA-256")
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"{label} hash does not match the accepted console evidence"
            )
        path = root / relative
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"{label} file no longer matches the accepted hash"
            )

    return manifest, _verify_generated_inputs(root, manifest), manifest_sha, report_sha


def _repo_sources() -> dict[str, Path]:
    for parent in Path(__file__).resolve().parents:
        standalone = parent / "integrations" / "saturn" / "standalone"
        diagnostics = parent / "integrations" / "saturn" / "diagnostics"
        paths = {
            "main": standalone / _MAIN_NAME,
            "menu": diagnostics / _MENU_NAME,
            "installer_source": standalone / _INSTALLER_SOURCE,
            "installer_header": standalone / _INSTALLER_HEADER,
            "batch_runtime_source": standalone / _BATCH_RUNTIME_SOURCE,
            "batch_runtime_header": standalone / _BATCH_RUNTIME_HEADER,
            "proof_source": standalone / _PROOF_SOURCE,
            "proof_header": standalone / _PROOF_HEADER,
        }
        if all(path.is_file() for path in paths.values()):
            return paths
    raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
        "cannot locate reviewed silent-batch physical candidate sources"
    )


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


def prepare_midi_68k_silent_batch_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_deploy_bin_sha256: str,
    expected_deploy_cue_sha256: str,
) -> SaturnMidi68KSilentBatchPhysicalCandidatePrepared:
    """Derive one fresh callable-but-off-card silent 27-record proof candidate."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if not baseline_root.is_dir():
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            f"inert silent-batch baseline is not a directory: {baseline_root}"
        )
    if output_root.exists():
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if baseline_root == output_root or baseline_root in output_root.parents:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "output directory must not be the inert baseline or its child"
        )

    manifest, generated_entries, manifest_sha, report_sha = _verify_inert_baseline(
        baseline_root,
        expected_image_sha256=expected_image_sha256,
        expected_deploy_bin_sha256=expected_deploy_bin_sha256,
        expected_deploy_cue_sha256=expected_deploy_cue_sha256,
    )
    paths = _repo_sources()
    reviewed_main = paths["main"].read_text(encoding="utf-8")
    reviewed_menu = paths["menu"].read_text(encoding="utf-8")
    installer_source = paths["installer_source"].read_bytes()
    installer_header = paths["installer_header"].read_bytes()
    batch_runtime_source = paths["batch_runtime_source"].read_bytes()
    batch_runtime_header = paths["batch_runtime_header"].read_bytes()
    proof_source_text = paths["proof_source"].read_text(encoding="utf-8")
    proof_header = paths["proof_header"].read_bytes()

    required_main_markers = (
        "SRK_MIDI_68K_SILENT_BATCH_PHYSICAL_CANDIDATE",
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 27u",
        '"MIDI / 68K BATCH PROOF"',
        '"Success: sequence=1 index=27 error=0"',
        "Release A to arm proof action",
    )
    for marker in required_main_markers:
        if marker not in reviewed_main:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"reviewed main is missing silent-batch binding marker: {marker}"
            )
    if _CANDIDATE_DEFINE in reviewed_main:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "reviewed repository main unexpectedly enables the batch candidate"
        )
    if reviewed_menu.count(_OLD_MENU_LABEL) != 1:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "reviewed menu no longer has exactly one isolated placeholder label"
        )
    if _BATCH_PROOF_MARKER not in proof_source_text:
        raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
            "reviewed proof source has no batch-controller suffix"
        )
    proof_batch_suffix = proof_source_text[proof_source_text.index(_BATCH_PROOF_MARKER):].encode("utf-8")

    candidate_main = (_CANDIDATE_DEFINE + "\n" + reviewed_main).encode("utf-8")
    candidate_menu = reviewed_menu.replace(_OLD_MENU_LABEL, _NEW_MENU_LABEL, 1).encode("utf-8")

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
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                f"inert runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_before = runtime_path.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KSilentBatchPhysicalCandidateFullBuildGateError(
                "inert runtime already contains batch physical-candidate injection"
            )

        (source_dir / _MAIN_NAME).write_bytes(candidate_main)
        (source_dir / _MENU_NAME).write_bytes(candidate_menu)
        (source_dir / _INSTALLER_SOURCE).write_bytes(installer_source)
        (source_dir / _INSTALLER_HEADER).write_bytes(installer_header)
        (source_dir / _BATCH_RUNTIME_SOURCE).write_bytes(batch_runtime_source)
        (source_dir / _BATCH_RUNTIME_HEADER).write_bytes(batch_runtime_header)
        (source_dir / _PROOF_HEADER).write_bytes(proof_header)

        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        for payload in (installer_source, batch_runtime_source, proof_batch_suffix):
            runtime_after += b"\n" + marker + b"\n" + payload
            if not runtime_after.endswith(b"\n"):
                runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy["sd_writes"] = False
        policy["midi_68k_silent_batch_program_present"] = True
        policy["midi_68k_silent_batch_program_linked"] = True
        policy["midi_68k_silent_batch_program_installed"] = False
        policy["midi_68k_silent_batch_program_executed"] = False
        policy["midi_68k_silent_batch_candidate_bound"] = True
        policy["midi_68k_silent_batch_user_trigger_required"] = True
        policy["midi_68k_silent_batch_build_time_hardware_actions"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        candidate_manifest["policy"] = policy
        candidate_manifest["midi_68k_silent_batch_physical_candidate_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-silent-batch-physical-candidate-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "candidate_define": _CANDIDATE_DEFINE,
            "candidate_menu_label": _NEW_MENU_LABEL.strip('"'),
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
            "reviewed_main_sha256": _sha256_bytes(reviewed_main.encode("utf-8")),
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "reviewed_menu_sha256": _sha256_bytes(reviewed_menu.encode("utf-8")),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "installer_source_sha256": _sha256_bytes(installer_source),
            "installer_header_sha256": _sha256_bytes(installer_header),
            "batch_runtime_source_sha256": _sha256_bytes(batch_runtime_source),
            "batch_runtime_header_sha256": _sha256_bytes(batch_runtime_header),
            "proof_header_sha256": _sha256_bytes(proof_header),
            "proof_batch_suffix_sha256": _sha256_bytes(proof_batch_suffix),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "accepted_inert_deploy_bin_sha256": _require_sha256(expected_deploy_bin_sha256, "expected inert deployable BIN SHA-256"),
            "accepted_inert_deploy_cue_sha256": _require_sha256(expected_deploy_cue_sha256, "expected inert deployable CUE SHA-256"),
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

    return SaturnMidi68KSilentBatchPhysicalCandidatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        reviewed_main_sha256=_sha256_bytes(reviewed_main.encode("utf-8")),
        candidate_main_sha256=_sha256_bytes(candidate_main),
        reviewed_menu_sha256=_sha256_bytes(reviewed_menu.encode("utf-8")),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        installer_source_sha256=_sha256_bytes(installer_source),
        installer_header_sha256=_sha256_bytes(installer_header),
        batch_runtime_source_sha256=_sha256_bytes(batch_runtime_source),
        batch_runtime_header_sha256=_sha256_bytes(batch_runtime_header),
        proof_header_sha256=_sha256_bytes(proof_header),
        proof_batch_suffix_sha256=_sha256_bytes(proof_batch_suffix),
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_midi_68k_silent_batch_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_image_sha256: str,
    expected_deploy_bin_sha256: str,
    expected_deploy_cue_sha256: str,
) -> SaturnMidi68KSilentBatchPhysicalCandidateResult:
    prepared = prepare_midi_68k_silent_batch_physical_candidate_full_build_gate(
        baseline_project,
        output_directory,
        expected_image_sha256=expected_image_sha256,
        expected_deploy_bin_sha256=expected_deploy_bin_sha256,
        expected_deploy_cue_sha256=expected_deploy_cue_sha256,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KSilentBatchPhysicalCandidateResult(prepared=prepared, build=build)
