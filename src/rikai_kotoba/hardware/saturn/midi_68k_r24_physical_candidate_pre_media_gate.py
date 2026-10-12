"""Independent read-only pre-media gate for the R24 real-SMF candidate.

This gate re-opens the completed R24 physical candidate as external evidence.
It rebuilds the reviewed CC0 song profile, re-renders every generated R24
representation, verifies the physical proof and standalone build provenance,
and asks the existing SAROO image planner for a read-only fresh-destination
plan.  It never writes to the mounted card.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

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
from .midi_program import SaturnMidiOpcode
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KR24PhysicalCandidatePreMediaGateError(RuntimeError):
    """Raised when R24 cannot pass independent read-only media review."""


@dataclass(frozen=True)
class SaturnMidi68KR24PhysicalCandidatePreMediaResult:
    project_root: Path
    source_midi_path: Path
    manifest_sha256: str
    report_sha256: str
    source_midi_sha256: str
    image_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    proof_header_sha256: str
    proof_source_sha256: str
    song_records: int
    song_batches: int
    song_duration_us: int
    note_on_count: int
    note_off_count: int
    peak_polyphony: int
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
_EXPECTED_DEFINE = "#define SRK_MIDI_68K_R24_PHYSICAL_CANDIDATE 1"
_EXPECTED_MENU_LABEL = "MIDI 68K Song Proof"


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
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"{label} must be an exact SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"{label} root must be an object"
        )
    return value


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"{label} path escapes candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"{label} is missing: {path}"
        )
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 candidate has no generated-file inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                "R24 generated-file inventory contains an invalid entry"
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
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                "R24 generated-file inventory metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path).lower() != expected.lower():
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 generated input changed: {relative}"
            )

    required = {
        _MAIN,
        _MENU,
        _RUNTIME,
        _R24_AUDIO_SOURCE,
        _R24_AUDIO_HEADER,
        _R24_VOICE_HEADER,
        _R24_PLAYER_SOURCE,
        _R24_PLAYER_HEADER,
        _R24_FRT_SOURCE,
        _R24_FRT_HEADER,
        _STREAM_SOURCE,
        _STREAM_HEADER,
        _PROOF_SOURCE,
        _PROOF_HEADER,
    }
    missing = sorted(required - seen)
    if missing:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 inventory is missing required inputs: " + ", ".join(missing)
        )


def _verify_song_contract(profile) -> tuple[int, int, int]:
    validate_saturn_midi_68k_r24_reference_song(profile)
    counts = dict(profile.opcode_counts)
    batch_sizes = tuple(batch.record_count for batch in profile.batches)
    if (
        profile.source_sha256 != SATURN_MIDI_68K_R24_REFERENCE_SHA256
        or profile.record_count != SATURN_MIDI_68K_R24_REFERENCE_RECORDS
        or profile.duration_us != SATURN_MIDI_68K_R24_REFERENCE_DURATION_US
        or len(profile.batches) != SATURN_MIDI_68K_R24_REFERENCE_BATCHES
        or batch_sizes != (32, 32, 32, 32, 32, 32, 32, 32, 32, 22)
        or profile.peak_polyphony != SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY
        or counts.get(SaturnMidiOpcode.NOTE_ON, 0) != SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON
        or counts.get(SaturnMidiOpcode.NOTE_OFF, 0) != SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF
    ):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "reviewed R24 real-song contract changed"
        )
    summaries, controllers, active = build_srk_saturn_midi_68k_r24_expected_midi_words(profile)
    if (len(summaries), len(controllers), len(active)) != (256, 1024, 128):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 complete MIDI-state verification surface changed"
        )
    return len(summaries), len(controllers), len(active)


def _verify_representation(
    root: Path,
    manifest: dict,
    profile,
    *,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_player_source_sha256: str,
    expected_player_header_sha256: str,
    expected_frt_source_sha256: str,
    expected_frt_header_sha256: str,
    expected_stream_source_sha256: str,
    expected_stream_header_sha256: str,
) -> str:
    gate = manifest.get(_GATE_KEY)
    inert = manifest.get(_INERT_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _GATE_SCHEMA:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 manifest has no recognized physical-candidate gate"
        )
    if not isinstance(inert, dict) or inert.get("schema") != _INERT_SCHEMA:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 candidate no longer carries accepted inert provenance"
        )

    expected = {
        _R24_AUDIO_SOURCE: _require_sha(expected_resident_source_sha256, "resident source SHA-256"),
        _R24_AUDIO_HEADER: _require_sha(expected_resident_header_sha256, "resident header SHA-256"),
        _R24_VOICE_HEADER: _require_sha(expected_voice_header_sha256, "voice header SHA-256"),
        _R24_PLAYER_SOURCE: _require_sha(expected_player_source_sha256, "player source SHA-256"),
        _R24_PLAYER_HEADER: _require_sha(expected_player_header_sha256, "player header SHA-256"),
        _R24_FRT_SOURCE: _require_sha(expected_frt_source_sha256, "FRT source SHA-256"),
        _R24_FRT_HEADER: _require_sha(expected_frt_header_sha256, "FRT header SHA-256"),
        _STREAM_SOURCE: _require_sha(expected_stream_source_sha256, "stream source SHA-256"),
        _STREAM_HEADER: _require_sha(expected_stream_header_sha256, "stream header SHA-256"),
    }
    rendered = {
        _R24_AUDIO_SOURCE: _sha256_bytes(
            render_srk_saturn_midi_68k_r24_resident_audio_service_source().encode("utf-8")
        ),
        _R24_AUDIO_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_r24_resident_audio_service_header().encode("utf-8")
        ),
        _R24_VOICE_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_r24_voice_header().encode("utf-8")
        ),
        _R24_PLAYER_SOURCE: _sha256_bytes(
            render_saturn_midi_68k_r24_player_source(profile.program).encode("utf-8")
        ),
        _R24_PLAYER_HEADER: _sha256_bytes(
            render_saturn_midi_68k_r24_player_header().encode("utf-8")
        ),
        _R24_FRT_SOURCE: _sha256_bytes(
            render_saturn_midi_68k_r24_frt_backend_source().encode("utf-8")
        ),
        _R24_FRT_HEADER: _sha256_bytes(
            render_saturn_midi_68k_r24_frt_backend_header().encode("utf-8")
        ),
        _STREAM_SOURCE: _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_source().encode("utf-8")
        ),
        _STREAM_HEADER: _sha256_bytes(
            render_srk_saturn_midi_68k_stream_service_header().encode("utf-8")
        ),
    }
    for relative, expected_sha in expected.items():
        if rendered[relative] != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"current R24 generated representation changed: {relative}"
            )
        if _sha256_file(_project_file(root, relative, relative)) != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"candidate generated representation changed: {relative}"
            )

    image_sha = _require_sha(expected_image_sha256, "resident image SHA-256")
    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    if image.sha256 != image_sha:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "current R24 resident generator no longer matches accepted evidence"
        )
    if (image.word_count, image.byte_size, image.end_address) != (7145, 14290, 0x000077D2):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "accepted R24 resident image geometry changed"
        )

    manifest_hash_keys = {
        "r24_image_sha256": image_sha,
        "r24_resident_source_sha256": expected[_R24_AUDIO_SOURCE],
        "r24_resident_header_sha256": expected[_R24_AUDIO_HEADER],
        "r24_voice_header_sha256": expected[_R24_VOICE_HEADER],
        "r24_player_source_sha256": expected[_R24_PLAYER_SOURCE],
        "r24_player_header_sha256": expected[_R24_PLAYER_HEADER],
        "r24_frt_source_sha256": expected[_R24_FRT_SOURCE],
        "r24_frt_header_sha256": expected[_R24_FRT_HEADER],
    }
    for key, expected_sha in manifest_hash_keys.items():
        if str(gate.get(key, "")).lower() != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 physical gate representation mismatch: {key}"
            )
        if str(inert.get(key, "")).lower() != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 inherited inert representation mismatch: {key}"
            )
    return image.sha256


def _verify_candidate_gate(
    root: Path,
    manifest: dict,
    profile,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_candidate_main_sha256: str,
    expected_candidate_menu_sha256: str,
    expected_runtime_sha256: str,
    expected_proof_header_sha256: str,
    expected_proof_source_sha256: str,
) -> tuple[str, str, str, str, str]:
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _GATE_SCHEMA:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 candidate gate is missing"
        )

    required = {
        "source_midi_sha256": SATURN_MIDI_68K_R24_REFERENCE_SHA256,
        "candidate_define": _EXPECTED_DEFINE,
        "candidate_menu_label": _EXPECTED_MENU_LABEL,
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "poll_mode": "at-most-once-per-frame-while-running",
        "proof_records": SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
        "proof_duration_us": SATURN_MIDI_68K_R24_REFERENCE_DURATION_US,
        "queue_batches": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
        "batch_sizes": [32, 32, 32, 32, 32, 32, 32, 32, 32, 22],
        "expected_final_read_sequence": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
        "expected_final_read_index": SATURN_MIDI_68K_R24_REFERENCE_LAST_BATCH_RECORDS,
        "expected_final_batch_count": SATURN_MIDI_68K_R24_REFERENCE_BATCHES,
        "expected_total_records": SATURN_MIDI_68K_R24_REFERENCE_RECORDS,
        "expected_note_on_count": SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
        "expected_note_off_count": SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
        "expected_peak_polyphony": SATURN_MIDI_68K_R24_REFERENCE_PEAK_POLYPHONY,
        "expected_busy_count": 0,
        "expected_final_active_count": 0,
        "state_summary_words_verified": 256,
        "controller_words_verified": 1024,
        "active_note_words_verified": 128,
        "clock_backend": "sh2-frt-div128-runtime-vdp2-clock-selection",
        "clock_ntsc_a_hz": SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
        "clock_ntsc_b_hz": SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
        "clock_pal_a_hz": SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
        "clock_pal_b_hz": SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
        "clock_tvstat_pal_bit": 0,
        "clock_tvmd_group_bit": 0,
        "frt_original_tcr_restored_on_terminal_path": True,
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
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 candidate contract mismatch: {key}"
            )

    chain = {
        "baseline_manifest_sha256": _require_sha(
            expected_baseline_manifest_sha256, "accepted inert manifest SHA-256"
        ),
        "baseline_report_sha256": _require_sha(
            expected_baseline_report_sha256, "accepted inert report SHA-256"
        ),
        "accepted_inert_deploy_bin_sha256": _require_sha(
            expected_baseline_bin_sha256, "accepted inert BIN SHA-256"
        ),
        "accepted_inert_deploy_cue_sha256": _require_sha(
            expected_baseline_cue_sha256, "accepted inert CUE SHA-256"
        ),
    }
    for key, expected in chain.items():
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 accepted inert chain mismatch: {key}"
            )

    policy = manifest.get("policy")
    required_policy = {
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
    if not isinstance(policy, dict):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 policy is missing"
        )
    for key, expected in required_policy.items():
        if policy.get(key) is not expected:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 policy mismatch: {key}"
            )

    main = _project_file(root, _MAIN, "R24 main")
    menu = _project_file(root, _MENU, "R24 menu")
    runtime = _project_file(root, _RUNTIME, "R24 runtime")
    proof_header = _project_file(root, _PROOF_HEADER, "R24 proof header")
    proof_source = _project_file(root, _PROOF_SOURCE, "R24 proof source")
    main_text = main.read_text(encoding="utf-8")
    menu_text = menu.read_text(encoding="utf-8")
    runtime_text = runtime.read_text(encoding="utf-8")

    if not main_text.startswith(_EXPECTED_DEFINE + "\n"):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 main no longer begins with the real-song candidate define"
        )
    for marker in (
        "SRK_MIDI_68K_PROOF_EXPECTED_INDEX 22u",
        "MIDI / 68K REAL SONG",
        "310 events - FRT clock - two SCSP voices",
        "Song PASS: 310 events / peak voices 2",
        "srk_saturn_midi_68k_r24_physical_proof_begin",
        "srk_saturn_midi_68k_r24_physical_proof_poll",
        "telemetry.voice_peak_active",
        "telemetry.player_sequence",
    ):
        if marker not in main_text:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 main is missing reviewed marker: {marker}"
            )
    if _EXPECTED_MENU_LABEL not in menu_text or "MIDI 68K Audio Proof" in menu_text:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 menu no longer isolates the real-song proof"
        )
    for marker in (
        "0x25F80000UL",
        "0x25F80004UL",
        "26874100UL",
        "28636400UL",
        "26687700UL",
        "28437700UL",
        "srk_saturn_midi_r24_frt_configure_div128",
        "SRK_R24_PROOF_FRT_TCR = state->original_tcr",
        "srk_saturn_midi_r24_player_poll",
        "state->telemetry.read_sequence != 10u",
        "state->telemetry.read_index != 22u",
        "state->telemetry.voice_key_on_count != 140u",
        "state->telemetry.voice_key_off_count != 140u",
        "state->telemetry.voice_peak_active != 2u",
        "srk_r24_verify_final_midi_state",
    ):
        if marker not in runtime_text:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 runtime is missing reviewed proof seam: {marker}"
            )

    actual = {
        "candidate_main_sha256": _sha256_file(main),
        "candidate_menu_sha256": _sha256_file(menu),
        "runtime_after_sha256": _sha256_file(runtime),
        "proof_header_sha256": _sha256_file(proof_header),
        "proof_source_sha256": _sha256_file(proof_source),
    }
    external = {
        "candidate_main_sha256": _require_sha(expected_candidate_main_sha256, "candidate main SHA-256"),
        "candidate_menu_sha256": _require_sha(expected_candidate_menu_sha256, "candidate menu SHA-256"),
        "runtime_after_sha256": _require_sha(expected_runtime_sha256, "candidate runtime SHA-256"),
        "proof_header_sha256": _require_sha(expected_proof_header_sha256, "proof header SHA-256"),
        "proof_source_sha256": _require_sha(expected_proof_source_sha256, "proof source SHA-256"),
    }
    for key, actual_sha in actual.items():
        if actual_sha != external[key]:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 externally accepted hash mismatch: {key}"
            )
        if str(gate.get(key, "")).lower() != actual_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 candidate provenance hash mismatch: {key}"
            )

    expected_header = _sha256_bytes(
        render_srk_saturn_midi_68k_r24_physical_proof_header().encode("utf-8")
    )
    expected_source = _sha256_bytes(
        render_srk_saturn_midi_68k_r24_physical_proof_source(profile).encode("utf-8")
    )
    if actual["proof_header_sha256"] != expected_header or actual["proof_source_sha256"] != expected_source:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 physical proof no longer matches its reviewed renderer"
        )

    return (
        actual["candidate_main_sha256"],
        actual["candidate_menu_sha256"],
        actual["runtime_after_sha256"],
        actual["proof_header_sha256"],
        actual["proof_source_sha256"],
    )


def _verify_build_report(
    root: Path,
    manifest_sha256: str,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
) -> tuple[str, str, str]:
    report_path = root / _REPORT
    if not report_path.is_file():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"R24 build report is missing: {report_path}"
        )
    report = _load_json(report_path, "R24 build report")
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 build report is not a successful standalone build"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha256.lower():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 build report does not match the current manifest"
        )

    expected_bin = _require_sha(expected_bin_sha256, "candidate BIN SHA-256")
    expected_cue = _require_sha(expected_cue_sha256, "candidate CUE SHA-256")
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 build report has no artifact inventory"
        )
    by_path = {
        str(entry.get("path")): entry
        for entry in artifacts
        if isinstance(entry, dict) and isinstance(entry.get("path"), str)
    }
    for relative, expected_sha, label in (
        (_DEPLOY_BIN, expected_bin, "candidate BIN"),
        (_DEPLOY_CUE, expected_cue, "candidate CUE"),
    ):
        entry = by_path.get(relative)
        path = _project_file(root, relative, label)
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 {label} report hash mismatch"
            )
        if _sha256_file(path) != expected_sha:
            raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
                f"R24 {label} disk hash mismatch"
            )
    return _sha256_file(report_path), expected_bin, expected_cue


def inspect_saturn_midi_68k_r24_physical_candidate_pre_media(
    project_directory: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    expected_baseline_manifest_sha256: str,
    expected_baseline_report_sha256: str,
    expected_baseline_bin_sha256: str,
    expected_baseline_cue_sha256: str,
    expected_image_sha256: str,
    expected_resident_source_sha256: str,
    expected_resident_header_sha256: str,
    expected_voice_header_sha256: str,
    expected_player_source_sha256: str,
    expected_player_header_sha256: str,
    expected_frt_source_sha256: str,
    expected_frt_header_sha256: str,
    expected_stream_source_sha256: str,
    expected_stream_header_sha256: str,
    expected_candidate_main_sha256: str,
    expected_candidate_menu_sha256: str,
    expected_runtime_sha256: str,
    expected_proof_header_sha256: str,
    expected_proof_source_sha256: str,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR24PhysicalCandidatePreMediaResult:
    """Independently revalidate R24 and return only a read-only SAROO plan."""

    root = _canonical(project_directory)
    source = _canonical(source_midi)
    if not root.is_dir():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"R24 candidate project is not a directory: {root}"
        )
    if not source.is_file():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"R24 source MIDI is not a file: {source}"
        )

    profile = build_saturn_midi_68k_r24_song_profile(source)
    summary_count, controller_count, active_count = _verify_song_contract(profile)

    manifest_path = root / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"R24 manifest is missing: {manifest_path}"
        )
    manifest = _load_json(manifest_path, "R24 manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "R24 manifest identity is unsupported"
        )
    manifest_sha = _sha256_file(manifest_path)

    _verify_generated_inventory(root, manifest)
    image_sha = _verify_representation(
        root,
        manifest,
        profile,
        expected_image_sha256=expected_image_sha256,
        expected_resident_source_sha256=expected_resident_source_sha256,
        expected_resident_header_sha256=expected_resident_header_sha256,
        expected_voice_header_sha256=expected_voice_header_sha256,
        expected_player_source_sha256=expected_player_source_sha256,
        expected_player_header_sha256=expected_player_header_sha256,
        expected_frt_source_sha256=expected_frt_source_sha256,
        expected_frt_header_sha256=expected_frt_header_sha256,
        expected_stream_source_sha256=expected_stream_source_sha256,
        expected_stream_header_sha256=expected_stream_header_sha256,
    )
    main_sha, menu_sha, runtime_sha, proof_header_sha, proof_source_sha = _verify_candidate_gate(
        root,
        manifest,
        profile,
        expected_baseline_manifest_sha256=expected_baseline_manifest_sha256,
        expected_baseline_report_sha256=expected_baseline_report_sha256,
        expected_baseline_bin_sha256=expected_baseline_bin_sha256,
        expected_baseline_cue_sha256=expected_baseline_cue_sha256,
        expected_candidate_main_sha256=expected_candidate_main_sha256,
        expected_candidate_menu_sha256=expected_candidate_menu_sha256,
        expected_runtime_sha256=expected_runtime_sha256,
        expected_proof_header_sha256=expected_proof_header_sha256,
        expected_proof_source_sha256=expected_proof_source_sha256,
    )
    report_sha, expected_bin, expected_cue = _verify_build_report(
        root,
        manifest_sha,
        expected_bin_sha256=expected_bin_sha256,
        expected_cue_sha256=expected_cue_sha256,
    )

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            f"read-only SAROO deployment plan rejected R24 candidate: {exc}"
        ) from exc
    if plan.bin_sha256.lower() != expected_bin:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "fresh R24 BIN SHA-256 does not match externally accepted build output"
        )
    if plan.cue_sha256.lower() != expected_cue:
        raise SaturnMidi68KR24PhysicalCandidatePreMediaGateError(
            "fresh R24 CUE SHA-256 does not match externally accepted build output"
        )

    return SaturnMidi68KR24PhysicalCandidatePreMediaResult(
        project_root=root,
        source_midi_path=source,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        source_midi_sha256=profile.source_sha256,
        image_sha256=image_sha,
        candidate_main_sha256=main_sha,
        candidate_menu_sha256=menu_sha,
        runtime_after_sha256=runtime_sha,
        proof_header_sha256=proof_header_sha,
        proof_source_sha256=proof_source_sha,
        song_records=profile.record_count,
        song_batches=len(profile.batches),
        song_duration_us=profile.duration_us,
        note_on_count=SATURN_MIDI_68K_R24_REFERENCE_NOTE_ON,
        note_off_count=SATURN_MIDI_68K_R24_REFERENCE_NOTE_OFF,
        peak_polyphony=profile.peak_polyphony,
        summary_words_verified=summary_count,
        controller_words_verified=controller_count,
        active_note_words_verified=active_count,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )
