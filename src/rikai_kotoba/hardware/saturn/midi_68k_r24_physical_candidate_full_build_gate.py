"""Fresh off-card full-build gate for the R24 real-SMF physical candidate.

The input must be the successful R24 inert integration.  This gate verifies its
manifest/report pairing, generated-file inventory, accepted R23 provenance and
all R24 generated representation hashes, then derives a fresh callable physical
candidate.  Building the candidate is still off-card: no Saturn hardware is
accessed and no SAROO file is written.
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
from .midi_68k_r24_physical_candidate import (
    SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
    build_srk_saturn_midi_68k_r24_expected_midi_words,
    derive_r24_physical_candidate_main,
    derive_r24_physical_candidate_menu,
    render_srk_saturn_midi_68k_r24_physical_proof_header,
    render_srk_saturn_midi_68k_r24_physical_proof_source,
)
from .midi_68k_r24_player import (
    render_saturn_midi_68k_r24_player_header,
    render_saturn_midi_68k_r24_player_source,
)
from .midi_68k_r24_resident_audio_service import (
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
    render_srk_saturn_midi_68k_r24_resident_audio_service_header,
    render_srk_saturn_midi_68k_r24_resident_audio_service_source,
    render_srk_saturn_midi_68k_r24_voice_header,
)
from .midi_68k_r24_song import (
    SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
    SATURN_MIDI_68K_R24_REFERENCE_DURATION_US,
    SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
    SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
    SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
    SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
    SATURN_MIDI_68K_R24_REFERENCE_SHA256,
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from .midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .standalone_build import SaturnStandaloneBuildResult, build_saturn_standalone_project


class SaturnMidi68KR24PhysicalCandidateFullBuildGateError(RuntimeError):
    """Raised when the R24 physical candidate cannot be derived safely."""


@dataclass(frozen=True)
class SaturnMidi68KR24PhysicalCandidatePrepared:
    baseline_root: Path
    output_root: Path
    source_midi_path: Path
    baseline_manifest_sha256: str
    baseline_report_sha256: str
    baseline_bin_sha256: str
    baseline_cue_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_before_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str
    song_records: int
    song_batches: int
    song_duration_us: int
    state_summary_words_verified: int
    controller_words_verified: int
    active_note_words_verified: int


@dataclass(frozen=True)
class SaturnMidi68KR24PhysicalCandidateFullBuildResult:
    prepared: SaturnMidi68KR24PhysicalCandidatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_R24_AUDIO_SOURCE = "src/srk_saturn_midi_68k_r24_resident_audio_service.c"
_R24_AUDIO_HEADER = "src/srk_saturn_midi_68k_r24_resident_audio_service.h"
_R24_VOICE_HEADER = "src/srk_saturn_midi_68k_r24_voice_state.h"
_R24_PLAYER_SOURCE = "src/srk_saturn_midi_68k_r24_player.c"
_R24_PLAYER_HEADER = "src/srk_saturn_midi_68k_r24_player.h"
_R24_FRT_SOURCE = "src/srk_saturn_midi_68k_r24_frt_backend.c"
_R24_FRT_HEADER = "src/srk_saturn_midi_68k_r24_frt_backend.h"
_STREAM_SOURCE = "src/srk_saturn_midi_68k_stream_service.c"
_STREAM_HEADER = "src/srk_saturn_midi_68k_stream_service.h"
_PROOF_SOURCE = "src/srk_saturn_midi_68k_r24_physical_proof.c"
_PROOF_HEADER = "src/srk_saturn_midi_68k_r24_physical_proof.h"
_INERT_KEY = "midi_68k_r24_inert_full_build_gate"
_INERT_SCHEMA = "srk.saturn.midi-68k-r24-inert-full-build-gate.v1"
_GATE_KEY = "midi_68k_r24_physical_candidate_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-r24-physical-candidate-full-build-gate.v1"
_MARKER = "/* SRK MIDI 68K R24 REAL-SMF PHYSICAL CANDIDATE: generated proof follows. */"


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
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"{label} root must be an object"
        )
    return value


def _verify_generated(root: Path, manifest: dict) -> list[dict[str, object]]:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert baseline has no generated-file inventory"
        )
    verified: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                "invalid R24 inert generated-file entry"
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
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                "invalid or duplicate R24 inert generated-file metadata"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != size:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"R24 inert generated input changed: {relative}"
            )
        if _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"R24 inert generated input hash mismatch: {relative}"
            )
        verified.append(entry)
    return verified


def _artifact_map(report: dict) -> dict[str, dict]:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert build report has no artifact inventory"
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


def _verify_inert(
    root: Path,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_player_source_sha256: str,
    expected_player_header_sha256: str,
    expected_frt_source_sha256: str,
    expected_frt_header_sha256: str,
) -> tuple[dict, list[dict[str, object]], str, str, str, str]:
    manifest_path = root / _MANIFEST
    report_path = root / _REPORT
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert baseline must contain manifest and successful build report"
        )
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "R24 inert manifest")
    report = _load_json(report_path, "R24 inert build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert manifest identity changed"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha:
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert report no longer matches manifest"
        )

    gate = manifest.get(_INERT_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _INERT_SCHEMA:
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "baseline is not the reviewed R24 inert integration"
        )

    exact = {
        "source_midi_sha256": SATURN_MIDI_68K_R24_REFERENCE_SHA256,
        "song_records": SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
        "song_batches": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
        "peak_polyphony": SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
        "r24_image_sha256": _require_sha(expected_image_sha256, "R24 image"),
        "r24_resident_source_sha256": _require_sha(expected_resident_source_sha256, "R24 resident source"),
        "r24_resident_header_sha256": _require_sha(expected_resident_header_sha256, "R24 resident header"),
        "r24_voice_header_sha256": _require_sha(expected_voice_header_sha256, "R24 voice header"),
        "r24_player_source_sha256": _require_sha(expected_player_source_sha256, "R24 player source"),
        "r24_player_header_sha256": _require_sha(expected_player_header_sha256, "R24 player header"),
        "r24_frt_source_sha256": _require_sha(expected_frt_source_sha256, "R24 FRT source"),
        "r24_frt_header_sha256": _require_sha(expected_frt_header_sha256, "R24 FRT header"),
    }
    for key, expected in exact.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"R24 inert gate changed: {key}"
            )

    required = {
        "accepted_r23_candidate_binding_preserved": True,
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
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"R24 inert policy changed: {key}"
            )

    generated = _verify_generated(root, manifest)
    artifacts = _artifact_map(report)
    accepted_bin = _require_sha(expected_bin_sha256, "R24 inert BIN")
    accepted_cue = _require_sha(expected_cue_sha256, "R24 inert CUE")
    for relative, expected, label in (
        (_DEPLOY_BIN, accepted_bin, "R24 inert BIN"),
        (_DEPLOY_CUE, accepted_cue, "R24 inert CUE"),
    ):
        entry = artifacts.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"{label} report hash changed"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"{label} disk hash changed"
            )

    runtime_sha = _sha256_file(root / _RUNTIME)
    if runtime_sha != _require_sha(expected_runtime_sha256, "R24 inert runtime"):
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert runtime hash mismatch"
        )
    if runtime_sha != str(gate.get("runtime_after_sha256", "")).lower():
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "R24 inert gate/runtime mismatch"
        )

    return manifest, generated, manifest_sha, report_sha, accepted_bin, accepted_cue


def prepare_saturn_midi_68k_r24_physical_candidate(
    baseline_project: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_baseline_runtime_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_player_source_sha256: str,
    expected_player_header_sha256: str,
    expected_frt_source_sha256: str,
    expected_frt_header_sha256: str,
) -> SaturnMidi68KR24PhysicalCandidatePrepared:
    baseline = _canonical(baseline_project)
    source = _canonical(source_midi)
    output = _canonical(output_directory)
    if not baseline.is_dir():
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"R24 inert baseline is not a directory: {baseline}"
        )
    if not source.is_file():
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"R24 source MIDI is not a file: {source}"
        )
    if output.exists():
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output}"
        )

    (
        manifest,
        generated,
        manifest_sha,
        report_sha,
        baseline_bin,
        baseline_cue,
    ) = _verify_inert(
        baseline,
        expected_bin_sha256=expected_baseline_bin_sha256,
        expected_cue_sha256=expected_baseline_cue_sha256,
        expected_runtime_sha256=expected_baseline_runtime_sha256,
        expected_image_sha256=expected_image_sha256,
        expected_resident_source_sha256=expected_resident_source_sha256,
        expected_resident_header_sha256=expected_resident_header_sha256,
        expected_voice_header_sha256=expected_voice_header_sha256,
        expected_player_source_sha256=expected_player_source_sha256,
        expected_player_header_sha256=expected_player_header_sha256,
        expected_frt_source_sha256=expected_frt_source_sha256,
        expected_frt_header_sha256=expected_frt_header_sha256,
    )

    profile = build_saturn_midi_68k_r24_song_profile(source)
    validate_saturn_midi_68k_r24_reference_song(profile)
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    if image.sha256 != _require_sha(expected_image_sha256, "R24 image"):
        raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
            "current R24 resident image no longer matches accepted compiler/inert evidence"
        )

    blobs = {
        _R24_AUDIO_SOURCE: render_srk_saturn_midi_68k_r24_resident_audio_service_source().encode("utf-8"),
        _R24_AUDIO_HEADER: render_srk_saturn_midi_68k_r24_resident_audio_service_header().encode("utf-8"),
        _R24_VOICE_HEADER: render_srk_saturn_midi_68k_r24_voice_header().encode("utf-8"),
        _R24_PLAYER_SOURCE: render_saturn_midi_68k_r24_player_source(profile.program).encode("utf-8"),
        _R24_PLAYER_HEADER: render_saturn_midi_68k_r24_player_header().encode("utf-8"),
        _R24_FRT_SOURCE: render_saturn_midi_68k_r24_frt_backend_source().encode("utf-8"),
        _R24_FRT_HEADER: render_saturn_midi_68k_r24_frt_backend_header().encode("utf-8"),
        _STREAM_SOURCE: render_srk_saturn_midi_68k_stream_service_source().encode("utf-8"),
        _STREAM_HEADER: render_srk_saturn_midi_68k_stream_service_header().encode("utf-8"),
    }
    hashes = {name: _sha256_bytes(data) for name, data in blobs.items()}
    expected_hashes = {
        _R24_AUDIO_SOURCE: _require_sha(expected_resident_source_sha256, "R24 resident source"),
        _R24_AUDIO_HEADER: _require_sha(expected_resident_header_sha256, "R24 resident header"),
        _R24_VOICE_HEADER: _require_sha(expected_voice_header_sha256, "R24 voice header"),
        _R24_PLAYER_SOURCE: _require_sha(expected_player_source_sha256, "R24 player source"),
        _R24_PLAYER_HEADER: _require_sha(expected_player_header_sha256, "R24 player header"),
        _R24_FRT_SOURCE: _require_sha(expected_frt_source_sha256, "R24 FRT source"),
        _R24_FRT_HEADER: _require_sha(expected_frt_header_sha256, "R24 FRT header"),
    }
    for relative, expected in expected_hashes.items():
        if hashes[relative] != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"current R24 generated representation changed: {relative}"
            )
        if not (baseline / relative).is_file() or _sha256_file(baseline / relative) != expected:
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                f"R24 inert representation changed on disk: {relative}"
            )

    proof_header = render_srk_saturn_midi_68k_r24_physical_proof_header()
    proof_source = render_srk_saturn_midi_68k_r24_physical_proof_source(profile)
    summaries, controllers, active = build_srk_saturn_midi_68k_r24_expected_midi_words(profile)

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
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                "R24 inert baseline is missing runtime/main/menu source"
            )
        runtime_before = runtime_path.read_bytes()
        if _sha256_bytes(runtime_before) != _require_sha(
            expected_baseline_runtime_sha256, "R24 inert runtime"
        ):
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                "R24 inert runtime changed during staging"
            )

        candidate_main = derive_r24_physical_candidate_main(
            main_path.read_text(encoding="utf-8")
        ).encode("utf-8")
        candidate_menu = derive_r24_physical_candidate_menu(
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
            raise SaturnMidi68KR24PhysicalCandidateFullBuildGateError(
                "R24 inert runtime already contains physical candidate injection"
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
                "midi_68k_r24_present": True,
                "midi_68k_r24_linked": True,
                "midi_68k_r24_resident_installed": False,
                "midi_68k_r24_resident_executed": False,
                "midi_68k_r24_player_invoked": False,
                "midi_68k_r24_frt_invoked": False,
                "midi_68k_r24_physical_candidate_bound": True,
                "midi_68k_r24_build_time_hardware_io": False,
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
            "source_midi_path": str(source),
            "source_midi_sha256": profile.source_sha256,
            "candidate_define": "#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1",
            "candidate_menu_label": "MIDI 68K Song Proof",
            "trigger_button": "A",
            "trigger_requires_release_after_screen_entry": True,
            "poll_mode": "at-most-once-per-frame-while-running",
            "proof_records": profile.record_count,
            "proof_duration_us": profile.duration_us,
            "queue_batches": len(profile.batches),
            "batch_sizes": [batch.record_count for batch in profile.batches],
            "expected_final_read_sequence": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
            "expected_final_read_index": SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
            "expected_final_batch_count": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
            "expected_total_records": SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
            "expected_note_on_count": SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
            "expected_note_off_count": SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
            "expected_peak_polyphony": SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
            "expected_busy_count": 0,
            "expected_final_active_count": 0,
            "state_summary_words_verified": len(summaries),
            "controller_words_verified": len(controllers),
            "active_note_words_verified": len(active),
            "clock_backend": "sh2-frt-div128-runtime-vdp2-clock-selection",
            "clock_ntsc_a_hz": SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
            "clock_ntsc_b_hz": SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
            "clock_pal_a_hz": SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
            "clock_pal_b_hz": SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
            "clock_tvstat_pal_bit": 0,
            "clock_tvmd_group_bit": 0,
            "frt_original_tcr_restored_on_terminal_path": True,
            "r24_image_sha256": image.sha256,
            "r24_resident_source_sha256": hashes[_R24_AUDIO_SOURCE],
            "r24_resident_header_sha256": hashes[_R24_AUDIO_HEADER],
            "r24_voice_header_sha256": hashes[_R24_VOICE_HEADER],
            "r24_player_source_sha256": hashes[_R24_PLAYER_SOURCE],
            "r24_player_header_sha256": hashes[_R24_PLAYER_HEADER],
            "r24_frt_source_sha256": hashes[_R24_FRT_SOURCE],
            "r24_frt_header_sha256": hashes[_R24_FRT_HEADER],
            "candidate_main_sha256": _sha256_bytes(candidate_main),
            "candidate_menu_sha256": _sha256_bytes(candidate_menu),
            "runtime_before_sha256": _sha256_bytes(runtime_before),
            "runtime_after_sha256": _sha256_bytes(runtime_after),
            "proof_header_sha256": _sha256_bytes(proof_header.encode("utf-8")),
            "proof_source_sha256": _sha256_bytes(proof_source.encode("utf-8")),
            "resident_installed_during_build": False,
            "resident_executed_during_build": False,
            "player_invoked_during_build": False,
            "frt_invoked_during_build": False,
            "scsp_mmio_during_build": False,
            "sound_ram_writes_during_build": False,
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

    return SaturnMidi68KR24PhysicalCandidatePrepared(
        baseline_root=baseline,
        output_root=output,
        source_midi_path=source,
        baseline_manifest_sha256=manifest_sha,
        baseline_report_sha256=report_sha,
        baseline_bin_sha256=baseline_bin,
        baseline_cue_sha256=baseline_cue,
        image_sha256=image.sha256,
        candidate_main_sha256=_sha256_bytes(candidate_main),
        candidate_menu_sha256=_sha256_bytes(candidate_menu),
        runtime_before_sha256=_sha256_bytes(runtime_before),
        runtime_after_sha256=_sha256_bytes(runtime_after),
        proof_header_sha256=_sha256_bytes(proof_header.encode("utf-8")),
        proof_source_sha256=_sha256_bytes(proof_source.encode("utf-8")),
        song_records=profile.record_count,
        song_batches=len(profile.batches),
        song_duration_us=profile.duration_us,
        state_summary_words_verified=len(summaries),
        controller_words_verified=len(controllers),
        active_note_words_verified=len(active),
    )


def run_saturn_midi_68k_r24_physical_candidate_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    **kwargs: str,
) -> SaturnMidi68KR24PhysicalCandidateFullBuildResult:
    prepared = prepare_saturn_midi_68k_r24_physical_candidate(
        baseline_project,
        source_midi,
        output_directory,
        **kwargs,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KR24PhysicalCandidateFullBuildResult(prepared=prepared, build=build)
