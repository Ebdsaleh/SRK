"""Fresh off-card inert standalone integration for R24 real-SMF playback.

The baseline is the exact physically accepted R23 first-audio candidate.  R24
copies only the baseline's manifest-tracked generated inputs, preserves the R23
callable proof/main/menu byte-for-byte, and links three new representations into
the fixed standalone runtime compilation unit:

* the new two-slot resident MC68EC000 image as constant data,
* the actual 310-event / ten-refill Melody Town Theme producer, and
* the SH-2 FRT backend functions.

Nothing calls those R24 symbols in this gate.  Therefore the build proves legacy
compiler/linker/ISO integration without installing the new sound-CPU image,
executing SCSP/FRT MMIO, selecting a physical clock frequency or touching SAROO.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_r24_frt_backend import (
    render_saturn_midi_68k_r24_frt_backend_header,
    render_saturn_midi_68k_r24_frt_backend_source,
)
from .midi_68k_r24_player import (
    render_saturn_midi_68k_r24_player_header,
    render_saturn_midi_68k_r24_player_source,
    validate_saturn_midi_68k_r24_complete_player,
)
from .midi_68k_r24_resident_audio_service import (
    SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END,
    SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS,
    SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS,
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
    render_srk_saturn_midi_68k_r24_resident_audio_service_header,
    render_srk_saturn_midi_68k_r24_resident_audio_service_source,
    render_srk_saturn_midi_68k_r24_voice_header,
)
from .midi_68k_r24_song import (
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from .midi_68k_r24_voice_allocator import (
    SATURN_MIDI_68K_R24_OWNED_SLOTS,
    trace_saturn_midi_68k_r24_program_voices,
    validate_saturn_midi_68k_r24_reference_voice_trace,
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
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KR24InertFullBuildGateError(RuntimeError):
    """Raised when the R24 inert integration cannot preserve R23 provenance."""


@dataclass(frozen=True)
class SaturnMidi68KR24InertFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    source_midi_path: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    baseline_r23_image_sha256: str
    r24_image_sha256: str
    r24_image_word_count: int
    r24_image_byte_size: int
    r24_program_end_address: int
    source_midi_sha256: str
    song_records: int
    song_batches: int
    peak_polyphony: int
    resident_source_sha256: str
    resident_header_sha256: str
    voice_header_sha256: str
    player_source_sha256: str
    player_header_sha256: str
    frt_source_sha256: str
    frt_header_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KR24InertFullBuildGateResult:
    prepared: SaturnMidi68KR24InertFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R23_PROOF_SOURCE = "src/srk_saturn_midi_68k_r23_physical_proof.c"
_R23_PROOF_HEADER = "src/srk_saturn_midi_68k_r23_physical_proof.h"
_R23_AUDIO_SOURCE = "src/srk_saturn_midi_68k_resident_audio_service.c"
_R23_AUDIO_HEADER = "src/srk_saturn_midi_68k_resident_audio_service.h"
_R23_VOICE_HEADER = "src/srk_saturn_midi_68k_voice_state.h"
_R23_PRODUCER_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_R23_PRODUCER_HEADER = "src/srk_saturn_midi_68k_stream_service.h"

_R24_AUDIO_SOURCE = "src/srk_saturn_midi_68k_r24_resident_audio_service.c"
_R24_AUDIO_HEADER = "src/srk_saturn_midi_68k_r24_resident_audio_service.h"
_R24_VOICE_HEADER = "src/srk_saturn_midi_68k_r24_voice_state.h"
_R24_PLAYER_SOURCE = "src/srk_saturn_midi_68k_r24_player.c"
_R24_PLAYER_HEADER = "src/srk_saturn_midi_68k_r24_player.h"
_R24_FRT_SOURCE = "src/srk_saturn_midi_68k_r24_frt_backend.c"
_R24_FRT_HEADER = "src/srk_saturn_midi_68k_r24_frt_backend.h"

_R23_GATE_KEY = "midi_68k_resident_audio_physical_candidate_full_build_gate"
_R23_GATE_SCHEMA = "srk.saturn.midi-68k-resident-audio-physical-candidate-full-build-gate.v1"
_R24_GATE_KEY = "midi_68k_r24_inert_full_build_gate"
_R24_GATE_SCHEMA = "srk.saturn.midi-68k-r24-inert-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K R24 REAL-SMF INERT FULL-BUILD GATE: linked representations follow. */"


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
    normalized = str(value or "").strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise SaturnMidi68KR24InertFullBuildGateError(f"{label} must be an exact SHA-256")
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR24InertFullBuildGateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR24InertFullBuildGateError(f"{label} root must be an object")
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
        raise SaturnMidi68KR24InertFullBuildGateError("R23 baseline has no generated-file inventory")
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR24InertFullBuildGateError("invalid R23 generated-file entry")
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
            raise SaturnMidi68KR24InertFullBuildGateError(
                "invalid or duplicate R23 generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size or _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KR24InertFullBuildGateError(f"R23 generated input changed: {relative}")
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR24InertFullBuildGateError("R23 build report has no artifact inventory")
    return {
        str(item["path"]): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def _verify_r23_physical_baseline(
    root: Path,
    *,
    expected_manifest_sha256: str,
    expected_report_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_r23_image_sha256: str,
    expected_r23_resident_source_sha256: str,
    expected_r23_resident_header_sha256: str,
    expected_r23_voice_header_sha256: str,
    expected_r23_producer_source_sha256: str,
    expected_r23_producer_header_sha256: str,
    expected_r23_proof_source_sha256: str,
    expected_r23_proof_header_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KR24InertFullBuildGateError(
            "R23 physical baseline must contain manifest and successful build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    if manifest_sha != _require_sha(expected_manifest_sha256, "expected R23 manifest"):
        raise SaturnMidi68KR24InertFullBuildGateError("R23 manifest hash mismatch")
    if report_sha != _require_sha(expected_report_sha256, "expected R23 report"):
        raise SaturnMidi68KR24InertFullBuildGateError("R23 build report hash mismatch")

    manifest = _load_json(manifest_path, "R23 manifest")
    report = _load_json(report_path, "R23 build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KR24InertFullBuildGateError("R23 manifest identity changed")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 build report is not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 report no longer matches manifest")

    gate = manifest.get(_R23_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _R23_GATE_SCHEMA:
        raise SaturnMidi68KR24InertFullBuildGateError(
            "baseline is not the reviewed R23 physical audio candidate"
        )
    required_gate = {
        "candidate_menu_label": "MIDI 68K Audio Proof",
        "proof_records": 34,
        "batch1_records": 32,
        "batch2_records": 2,
        "expected_final_read_sequence": 2,
        "expected_final_read_index": 2,
        "expected_final_batch_count": 2,
        "expected_total_records": 34,
        "scsp_key_on_readback_required": True,
        "audible_midi_note_required": True,
        "scheduled_note_off_required": True,
        "scsp_key_off_readback_required": True,
        "resident_audio_candidate_bound": True,
        "producer_linked": True,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
    }
    for key, expected in required_gate.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KR24InertFullBuildGateError(f"R23 physical gate changed: {key}")

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted_bin = _require_sha(expected_bin_sha256, "expected R23 BIN")
    accepted_cue = _require_sha(expected_cue_sha256, "expected R23 CUE")
    for relative, expected, label in (
        (_DEPLOY_BIN, accepted_bin, "R23 BIN"),
        (_DEPLOY_CUE, accepted_cue, "R23 CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KR24InertFullBuildGateError(f"{label} report hash changed")
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KR24InertFullBuildGateError(f"{label} disk hash changed")

    r23_image_sha = _require_sha(expected_r23_image_sha256, "expected R23 image")
    r23_image = build_srk_saturn_midi_68k_resident_audio_service_image()
    if r23_image.sha256 != r23_image_sha or str(gate.get("image_sha256", "")).lower() != r23_image_sha:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 resident image provenance changed")

    rendered = {
        _R23_AUDIO_SOURCE: _sha256_bytes(render_srk_saturn_midi_68k_resident_audio_service_source().encode("utf-8")),
        _R23_AUDIO_HEADER: _sha256_bytes(render_srk_saturn_midi_68k_resident_audio_service_header().encode("utf-8")),
        _R23_VOICE_HEADER: _sha256_bytes(render_srk_saturn_midi_68k_resident_audio_voice_header().encode("utf-8")),
        _R23_PRODUCER_SOURCE: _sha256_bytes(render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")),
        _R23_PRODUCER_HEADER: _sha256_bytes(render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")),
    }
    expected_rendered = {
        _R23_AUDIO_SOURCE: _require_sha(expected_r23_resident_source_sha256, "R23 resident source"),
        _R23_AUDIO_HEADER: _require_sha(expected_r23_resident_header_sha256, "R23 resident header"),
        _R23_VOICE_HEADER: _require_sha(expected_r23_voice_header_sha256, "R23 voice header"),
        _R23_PRODUCER_SOURCE: _require_sha(expected_r23_producer_source_sha256, "R23 producer source"),
        _R23_PRODUCER_HEADER: _require_sha(expected_r23_producer_header_sha256, "R23 producer header"),
    }
    for relative, actual in rendered.items():
        if actual != expected_rendered[relative]:
            raise SaturnMidi68KR24InertFullBuildGateError(f"current R23 generator changed: {relative}")
        path = root / relative
        if not path.is_file() or _sha256_file(path) != actual:
            raise SaturnMidi68KR24InertFullBuildGateError(f"R23 candidate representation changed: {relative}")

    proof_source = _require_sha(expected_r23_proof_source_sha256, "R23 proof source")
    proof_header = _require_sha(expected_r23_proof_header_sha256, "R23 proof header")
    if _sha256_file(root / _R23_PROOF_SOURCE) != proof_source:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 proof source hash mismatch")
    if _sha256_file(root / _R23_PROOF_HEADER) != proof_header:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 proof header hash mismatch")
    if str(gate.get("proof_source_sha256", "")).lower() != proof_source:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 gate/proof source mismatch")
    if str(gate.get("proof_header_sha256", "")).lower() != proof_header:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 gate/proof header mismatch")

    main_sha = _sha256_file(root / _MAIN)
    menu_sha = _sha256_file(root / _MENU)
    runtime_sha = _sha256_file(root / _RUNTIME)
    if str(gate.get("candidate_main_sha256", "")).lower() != main_sha:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 main/gate mismatch")
    if str(gate.get("candidate_menu_sha256", "")).lower() != menu_sha:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 menu/gate mismatch")
    if str(gate.get("runtime_after_sha256", "")).lower() != runtime_sha:
        raise SaturnMidi68KR24InertFullBuildGateError("R23 runtime/gate mismatch")

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


def prepare_saturn_midi_68k_r24_inert_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_r23_image_sha256: str,
    expected_r23_resident_source_sha256: str,
    expected_r23_resident_header_sha256: str,
    expected_r23_voice_header_sha256: str,
    expected_r23_producer_source_sha256: str,
    expected_r23_producer_header_sha256: str,
    expected_r23_proof_source_sha256: str,
    expected_r23_proof_header_sha256: str,
) -> SaturnMidi68KR24InertFullBuildGatePrepared:
    baseline = _canonical(baseline_project)
    source_midi_path = _canonical(source_midi)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KR24InertFullBuildGateError(f"R23 baseline is not a directory: {baseline}")
    if not source_midi_path.is_file():
        raise SaturnMidi68KR24InertFullBuildGateError(f"R24 source MIDI is not a file: {source_midi_path}")
    if output.exists():
        raise SaturnMidi68KR24InertFullBuildGateError(
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
    ) = _verify_r23_physical_baseline(
        baseline,
        expected_manifest_sha256=expected_baseline_manifest_sha256,
        expected_report_sha256=expected_baseline_report_sha256,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_r23_image_sha256=expected_r23_image_sha256,
        expected_r23_resident_source_sha256=expected_r23_resident_source_sha256,
        expected_r23_resident_header_sha256=expected_r23_resident_header_sha256,
        expected_r23_voice_header_sha256=expected_r23_voice_header_sha256,
        expected_r23_producer_source_sha256=expected_r23_producer_source_sha256,
        expected_r23_producer_header_sha256=expected_r23_producer_header_sha256,
        expected_r23_proof_source_sha256=expected_r23_proof_source_sha256,
        expected_r23_proof_header_sha256=expected_r23_proof_header_sha256,
    )

    profile = build_saturn_midi_68k_r24_song_profile(source_midi_path)
    validate_saturn_midi_68k_r24_reference_song(profile)
    voice_trace = trace_saturn_midi_68k_r24_program_voices(profile.program)
    validate_saturn_midi_68k_r24_reference_voice_trace(voice_trace)
    validate_saturn_midi_68k_r24_complete_player(profile.program)
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()

    blobs = {
        _R24_AUDIO_SOURCE: render_srk_saturn_midi_68k_r24_resident_audio_service_source().encode("utf-8"),
        _R24_AUDIO_HEADER: render_srk_saturn_midi_68k_r24_resident_audio_service_header().encode("utf-8"),
        _R24_VOICE_HEADER: render_srk_saturn_midi_68k_r24_voice_header().encode("utf-8"),
        _R24_PLAYER_SOURCE: render_saturn_midi_68k_r24_player_source(profile.program).encode("utf-8"),
        _R24_PLAYER_HEADER: render_saturn_midi_68k_r24_player_header().encode("utf-8"),
        _R24_FRT_SOURCE: render_saturn_midi_68k_r24_frt_backend_source().encode("utf-8"),
        _R24_FRT_HEADER: render_saturn_midi_68k_r24_frt_backend_header().encode("utf-8"),
    }
    hashes = {name: _sha256_bytes(data) for name, data in blobs.items()}

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

        if _sha256_file(staging / _MAIN) != main_sha or _sha256_file(staging / _MENU) != menu_sha:
            raise SaturnMidi68KR24InertFullBuildGateError("R23 main/menu changed during staging")
        runtime_path = staging / _RUNTIME
        runtime_before = runtime_path.read_bytes()
        if _sha256_bytes(runtime_before) != runtime_sha:
            raise SaturnMidi68KR24InertFullBuildGateError("R23 runtime changed during staging")
        marker = _MARKER.encode("ascii")
        if marker in runtime_before:
            raise SaturnMidi68KR24InertFullBuildGateError("R23 runtime already contains R24 inert injection")

        for relative, data in blobs.items():
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        runtime_after = runtime_before
        if not runtime_after.endswith(b"\n"):
            runtime_after += b"\n"
        runtime_after += b"\n" + marker + b"\n"
        for relative in (_R24_AUDIO_SOURCE, _R24_PLAYER_SOURCE, _R24_FRT_SOURCE):
            runtime_after += blobs[relative]
            if not runtime_after.endswith(b"\n"):
                runtime_after += b"\n"
            runtime_after += b"\n"
        runtime_path.write_bytes(runtime_after)

        candidate = dict(manifest)
        policy = dict(candidate.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "midi_68k_r24_present": True,
                "midi_68k_r24_linked": True,
                "midi_68k_r24_resident_installed": False,
                "midi_68k_r24_resident_executed": False,
                "midi_68k_r24_player_invoked": False,
                "midi_68k_r24_frt_invoked": False,
                "midi_68k_r24_scsp_mmio": False,
                "midi_68k_r24_sound_ram_writes": False,
            }
        )
        candidate["policy"] = policy
        candidate[_R24_GATE_KEY] = {
            "schema": _R24_GATE_SCHEMA,
            "baseline_project": str(baseline),
            "baseline_manifest_sha256": manifest_sha,
            "baseline_report_sha256": report_sha,
            "baseline_deploy_bin_sha256": baseline_bin,
            "baseline_deploy_cue_sha256": baseline_cue,
            "accepted_r23_candidate_binding_preserved": True,
            "r23_main_sha256": main_sha,
            "r23_menu_sha256": menu_sha,
            "r23_runtime_sha256": runtime_sha,
            "r23_image_sha256": expected_r23_image_sha256.lower(),
            "source_midi_path": str(source_midi_path),
            "source_midi_sha256": profile.source_sha256,
            "song_records": profile.record_count,
            "song_duration_us": profile.duration_us,
            "song_batches": len(profile.batches),
            "song_batch_sizes": [batch.record_count for batch in profile.batches],
            "note_on_count": profile.note_on_count,
            "note_off_count": profile.note_off_count,
            "peak_polyphony": profile.peak_polyphony,
            "r24_image_sha256": image.sha256,
            "r24_image_word_count": image.word_count,
            "r24_image_byte_size": image.byte_size,
            "r24_program_address": SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS,
            "r24_program_end_address": image.end_address,
            "r24_owned_slots": SATURN_MIDI_68K_R24_OWNED_SLOTS,
            "r24_voice_state_address": SATURN_MIDI_68K_R24_VOICE_STATE_ADDRESS,
            "r24_mixer_table_address": SATURN_MIDI_68K_R24_MIXER_TABLE_ADDRESS,
            "r24_audio_ownership_end": SATURN_MIDI_68K_R24_AUDIO_OWNERSHIP_END,
            "r24_resident_source_sha256": hashes[_R24_AUDIO_SOURCE],
            "r24_resident_header_sha256": hashes[_R24_AUDIO_HEADER],
            "r24_voice_header_sha256": hashes[_R24_VOICE_HEADER],
            "r24_player_source_sha256": hashes[_R24_PLAYER_SOURCE],
            "r24_player_header_sha256": hashes[_R24_PLAYER_HEADER],
            "r24_frt_source_sha256": hashes[_R24_FRT_SOURCE],
            "r24_frt_header_sha256": hashes[_R24_FRT_HEADER],
            "compile_injection": _RUNTIME,
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "resident_linked_as_constant_data": True,
            "resident_installed": False,
            "resident_executed": False,
            "player_linked": True,
            "player_invoked": False,
            "frt_backend_linked": True,
            "frt_backend_invoked": False,
            "physical_clock_frequency_selected": False,
            "scsp_mmio_executed": False,
            "sound_ram_writes": False,
            "frt_mmio_executed": False,
            "build_time_hardware_io": False,
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

    return SaturnMidi68KR24InertFullBuildGatePrepared(
        baseline_root=baseline,
        output_root=output,
        source_midi_path=source_midi_path,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin,
        baseline_cue_sha256=baseline_cue,
        baseline_r23_image_sha256=expected_r23_image_sha256.lower(),
        r24_image_sha256=image.sha256,
        r24_image_word_count=image.word_count,
        r24_image_byte_size=image.byte_size,
        r24_program_end_address=image.end_address,
        source_midi_sha256=profile.source_sha256,
        song_records=profile.record_count,
        song_batches=len(profile.batches),
        peak_polyphony=profile.peak_polyphony,
        resident_source_sha256=hashes[_R24_AUDIO_SOURCE],
        resident_header_sha256=hashes[_R24_AUDIO_HEADER],
        voice_header_sha256=hashes[_R24_VOICE_HEADER],
        player_source_sha256=hashes[_R24_PLAYER_SOURCE],
        player_header_sha256=hashes[_R24_PLAYER_HEADER],
        frt_source_sha256=hashes[_R24_FRT_SOURCE],
        frt_header_sha256=hashes[_R24_FRT_HEADER],
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
    )


def run_saturn_midi_68k_r24_inert_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KR24InertFullBuildGateResult:
    prepared = prepare_saturn_midi_68k_r24_inert_full_build_gate(
        baseline_project,
        source_midi,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KR24InertFullBuildGateResult(prepared=prepared, build=build)
