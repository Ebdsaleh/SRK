"""Prepare a fresh callable physical candidate for the stream/scheduler milestone."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_resident_stream_service import (
    build_srk_saturn_midi_68k_resident_stream_service_image,
)
from .midi_68k_resident_stream_physical_candidate import (
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US,
    SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS,
    build_srk_saturn_midi_68k_stream_expected_words,
    build_srk_saturn_midi_68k_stream_physical_snapshot,
    derive_resident_stream_candidate_main,
    derive_resident_stream_candidate_menu,
    render_srk_saturn_midi_68k_stream_physical_proof_header,
    render_srk_saturn_midi_68k_stream_physical_proof_source,
)


class SaturnMidi68KResidentStreamCandidatePrepareError(RuntimeError):
    """Raised when the physical stream candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamCandidatePrepared:
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
    batch1_records: int
    batch2_records: int
    final_clock_us: int
    state_summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_PROOF_SOURCE = "src/srk_saturn_midi_68k_stream_physical_proof.c"
_PROOF_HEADER = "src/srk_saturn_midi_68k_stream_physical_proof.h"

_INERT_GATE_KEY = "midi_68k_resident_stream_full_build_gate"
_INERT_GATE_SCHEMA = "srk.saturn.midi-68k-resident-stream-full-build-gate.v1"
_GATE_KEY = "midi_68k_resident_stream_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-stream-physical-candidate-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K STREAM PHYSICAL CANDIDATE: generated proof follows. */"


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


def _require_sha(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            f"{label} root must be an object"
        )
    return value


def _verify_generated(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "inert stream baseline has no generated-file inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                "invalid inert generated-file entry"
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
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                "invalid or duplicate inert generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size:
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"inert generated input size/path mismatch: {relative}"
            )
        if _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"inert generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "inert stream build report has no artifact inventory"
        )
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


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


def _verify_inert_baseline(
    root: Path,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_producer_source_sha256: str,
    expected_producer_header_sha256: str,
    expected_resident_object_sha256: str,
    expected_producer_object_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert baseline must contain manifest and successful build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "stream inert manifest")
    report = _load_json(report_path, "stream inert build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert manifest identity changed"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert report no longer matches manifest"
        )

    gate = manifest.get(_INERT_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _INERT_GATE_SCHEMA:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "baseline is not the reviewed stream/scheduler inert integration"
        )

    exact_gate = {
        "image_sha256": _require_sha(expected_image_sha256, "expected stream image"),
        "resident_source_sha256": _require_sha(expected_resident_source_sha256, "resident source"),
        "resident_header_sha256": _require_sha(expected_resident_header_sha256, "resident header"),
        "producer_source_sha256": _require_sha(expected_producer_source_sha256, "producer source"),
        "producer_header_sha256": _require_sha(expected_producer_header_sha256, "producer header"),
        "accepted_resident_object_sha256_evidence": _require_sha(
            expected_resident_object_sha256, "resident object"
        ),
        "accepted_producer_object_sha256_evidence": _require_sha(
            expected_producer_object_sha256, "producer object"
        ),
    }
    for key, expected in exact_gate.items():
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"stream inert gate changed: {key}"
            )
    required = {
        "existing_r21_candidate_binding_preserved": True,
        "multi_batch_refill": True,
        "strict_sequence_service": True,
        "timestamp_scheduler": True,
        "published_clock_seqlock": True,
        "state_persistent_across_refills": True,
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
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"stream inert gate changed: {key}"
            )

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted_bin = _require_sha(expected_bin_sha256, "expected inert BIN")
    accepted_cue = _require_sha(expected_cue_sha256, "expected inert CUE")
    for relative, expected, label in (
        (_DEPLOY_BIN, accepted_bin, "inert BIN"),
        (_DEPLOY_CUE, accepted_cue, "inert CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"{label} report hash changed"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                f"{label} disk hash changed"
            )

    runtime = root / _RUNTIME
    runtime_sha = _sha256_file(runtime)
    accepted_runtime = _require_sha(expected_runtime_sha256, "expected inert runtime")
    if runtime_sha != accepted_runtime:
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert runtime hash mismatch"
        )
    if runtime_sha.lower() != str(gate.get("runtime_after_sha256", "")).lower():
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "stream inert gate/runtime hash mismatch"
        )

    return manifest, generated, manifest_sha, report_sha, accepted_bin, accepted_cue


def prepare_midi_68k_resident_stream_physical_candidate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
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
) -> SaturnMidi68KResidentStreamCandidatePrepared:
    baseline = _canonical(baseline_project)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            f"stream inert baseline is not a directory: {baseline}"
        )
    if output.exists():
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
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
        expected_producer_source_sha256=expected_producer_source_sha256,
        expected_producer_header_sha256=expected_producer_header_sha256,
        expected_resident_object_sha256=expected_resident_object_sha256,
        expected_producer_object_sha256=expected_producer_object_sha256,
    )

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    if image.sha256 != _require_sha(expected_image_sha256, "expected stream image"):
        raise SaturnMidi68KResidentStreamCandidatePrepareError(
            "current resident stream generator no longer matches compiler evidence"
        )

    proof_header = render_srk_saturn_midi_68k_stream_physical_proof_header()
    proof_source = render_srk_saturn_midi_68k_stream_physical_proof_source()
    summaries, controllers, active = build_srk_saturn_midi_68k_stream_expected_words()
    snapshot = build_srk_saturn_midi_68k_stream_physical_snapshot()

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
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                "stream inert baseline is missing runtime/main/menu source"
            )

        runtime_before = runtime_path.read_bytes()
        candidate_main = derive_resident_stream_candidate_main(
            main_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        candidate_menu = derive_resident_stream_candidate_menu(
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
            raise SaturnMidi68KResidentStreamCandidatePrepareError(
                "stream inert runtime already contains physical candidate injection"
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
        )
        candidate["policy"] = policy
        candidate[_GATE_KEY] = {
            "schema": _GATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "accepted_inert_deploy_bin_sha256": baseline_bin,
            "accepted_inert_deploy_cue_sha256": baseline_cue,
            "candidate_define": "#define SRK_MIDI_68K_RESIDENT_STREAM_PHYSICAL_CANDIDATE 1",
            "candidate_menu_label": "MIDI 68K Stream Proof",
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "proof_records": SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS,
            "batch1_records": SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
            "batch2_records": SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
            "partial_clock_us": SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_PARTIAL_US,
            "batch1_clock_us": SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_BATCH1_US,
            "final_clock_us": SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
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
            "state_summary_words_verified": len(summaries),
            "controller_words_verified": len(controllers),
            "active_note_words_verified": len(active),
            "expected_state_snapshot": asdict(snapshot),
            "image_sha256": image.sha256,
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "proof_header_sha256": _sha256_bytes(proof_header.encode("utf-8")),
            "proof_source_sha256": _sha256_bytes(proof_source.encode("utf-8")),
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

    return SaturnMidi68KResidentStreamCandidatePrepared(
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
        proof_records=SATURN_MIDI_68K_STREAM_PHYSICAL_RECORDS,
        batch1_records=SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH1_RECORDS,
        batch2_records=SATURN_MIDI_68K_STREAM_PHYSICAL_BATCH2_RECORDS,
        final_clock_us=SATURN_MIDI_68K_STREAM_PHYSICAL_CLOCK_FINAL_US,
        state_summary_words_verified=len(summaries),
        controller_words_verified=len(controllers),
        active_note_words_verified=len(active),
    )
