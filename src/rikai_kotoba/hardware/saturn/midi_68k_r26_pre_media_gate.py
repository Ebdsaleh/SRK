"""Independent read-only pre-media review for the accepted R26 Space Spectre candidate.

The R26 full-build output is treated as external Eridu evidence. This gate
revalidates the exact Space Spectre source/profile, re-renders every R26
representation, re-derives main/menu from the physically accepted R24 baseline,
reconstructs the runtime injection byte-for-byte, verifies the successful build
report and MODE1/2352 artifacts, then asks the existing SAROO planner for a
read-only fresh-destination plan.

The manifest/report SHA-256 values are intentionally *reported* rather than
hard-coded in this first independent review tranche; every semantically relevant
field and every externally accepted source/build artifact is pinned below. The
subsequent guarded APPLY tranche may therefore pin the manifest/report hashes
returned by Eridu together with the whole-card guard receipt.

There is no write/apply operation in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from . import midi_68k_r26_physical_candidate_full_build_gate as _build
from .midi_68k_r26_physical_candidate import (
    derive_r26_double_impact_candidate_main,
    derive_r26_double_impact_candidate_menu,
    render_srk_saturn_midi_68k_r26_physical_proof_header,
    render_srk_saturn_midi_68k_r26_physical_proof_source,
)
from .midi_68k_r26_player import (
    render_saturn_midi_68k_r26_player_header,
    render_saturn_midi_68k_r26_player_source,
)
from .midi_68k_r26_resident_audio_service import (
    build_srk_saturn_midi_68k_r26_resident_audio_service_image,
    render_srk_saturn_midi_68k_r26_resident_audio_service_header,
    render_srk_saturn_midi_68k_r26_resident_audio_service_source,
)
from .midi_68k_r26_voice_header import render_srk_saturn_midi_68k_r26_voice_header
from .saroo.standalone_image_deployment import (
    SarooStandaloneImageDeploymentPlan,
    plan_saroo_standalone_image_deployment,
)


class SaturnMidi68KR26PreMediaGateError(RuntimeError):
    """Raised when the accepted R26 Space Spectre candidate fails independent review."""


@dataclass(frozen=True)
class SaturnMidi68KR26PreMediaResult:
    project_root: Path
    repository_root: Path
    baseline_root: Path
    manifest_sha256: str
    report_sha256: str
    resident_image_sha256: str
    resident_source_sha256: str
    resident_header_sha256: str
    voice_header_sha256: str
    player_source_sha256: str
    player_header_sha256: str
    proof_source_sha256: str
    proof_header_sha256: str
    candidate_main_sha256: str
    candidate_menu_sha256: str
    runtime_after_sha256: str
    build_bin_sha256: str
    build_iso_sha256: str
    build_map_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    sector_count: int
    raw_bytes: int
    user_bytes: int
    plan: SarooStandaloneImageDeploymentPlan


_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MAIN = "src/srk_saturn_main.c"
_MENU = "src/srk_diag_menu.c"
_RUNTIME = "src/srk_saturn_runtime.c"
_R26_AUDIO_SOURCE = "src/srk_saturn_midi_68k_r26_resident_audio_service.c"
_R26_AUDIO_HEADER = "src/srk_saturn_midi_68k_r26_resident_audio_service.h"
_R26_VOICE_HEADER = "src/srk_saturn_midi_68k_r26_voice_state.h"
_R26_PLAYER_SOURCE = "src/srk_saturn_midi_68k_r26_player.c"
_R26_PLAYER_HEADER = "src/srk_saturn_midi_68k_r26_player.h"
_R26_PROOF_SOURCE = "src/srk_saturn_midi_68k_r26_physical_proof.c"
_R26_PROOF_HEADER = "src/srk_saturn_midi_68k_r26_physical_proof.h"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_GATE_KEY = _build._GATE_KEY
_GATE_SCHEMA = _build._GATE_SCHEMA
_MARKER = _build._MARKER

# Eridu-accepted R26 physical full-build evidence, 2026-10-14.
ACCEPTED_R26_SOURCE_MIDI_SHA256 = "984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01"
ACCEPTED_R26_RESIDENT_IMAGE_SHA256 = "7bcc139b2a689f77f03de79c0efae5e018e3584bfe15826baafa09c7aef32b40"
ACCEPTED_R26_RESIDENT_SOURCE_SHA256 = "20713d64c643bc6189893147c262992a1bb91cd6853147a0740b8d1e25130193"
ACCEPTED_R26_RESIDENT_HEADER_SHA256 = "e4ed298d3494cc6d2793b61968a7acbc801ab9f1215e5aef66fb8fb47e6bc0b4"
ACCEPTED_R26_VOICE_HEADER_SHA256 = "cc30bf7836ff86dc112cd97e6ca7c2da1dc67b05a0b8b748a9f34335f3c83f7d"
ACCEPTED_R26_PLAYER_SOURCE_SHA256 = "1b2bd2cd61bf23458f648d54aea47dc01bb90d747f1084f85403896815a448a6"
ACCEPTED_R26_PLAYER_HEADER_SHA256 = "2e4396094d7298043e1fde4bcd24d5b291904d26504462437f73e7fde83c27cc"
ACCEPTED_R26_PROOF_SOURCE_SHA256 = "3ad8974b5f9622d1e2ee7b84c541ed2274258c18d3b859d2bba32d8c5a97125d"
ACCEPTED_R26_PROOF_HEADER_SHA256 = "b4f030c90db972bc580dec9ae37eb61b27136f31a71fb7ad4f4c391d6289f8bc"
ACCEPTED_R26_MAIN_SHA256 = "5fb1983ed8541db31afd98088d69ba7b306ff1148ee5b1d0888eb4b148f67b1e"
ACCEPTED_R26_MENU_SHA256 = "18ebab83bf3cff6029237668b52d00981de92a22f1c204220d6d9cc36204b1dc"
ACCEPTED_R26_RUNTIME_SHA256 = "064fc2654ef42624e49b6baa5de94836efbbfd7d45e0dc95e7e94b5a3013c31e"

ACCEPTED_R26_BUILD_BIN_SIZE = 321536
ACCEPTED_R26_BUILD_BIN_SHA256 = "69f1a767c379fb1af5a84fab75dce3e57ef6b4324502877fb31a71fdbba6ca06"
ACCEPTED_R26_BUILD_ISO_SIZE = 425984
ACCEPTED_R26_BUILD_ISO_SHA256 = "3bff2e8a0ec40882baaeadd37c0f27f08ebef6900a5f1bc303d12c3815db2f46"
ACCEPTED_R26_BUILD_MAP_SIZE = 72667
ACCEPTED_R26_BUILD_MAP_SHA256 = "47bbcf3cfb98bc3597fa9e6e1f35b879fb0e47363b461450aaf1323a7708f055"
ACCEPTED_R26_PACKAGED_PCM_SIZE = 1040
ACCEPTED_R26_PACKAGED_PCM_SHA256 = "d4b9e26d0e3b0e54085b6169c5c0fc784ec9c3f005bcbbda96529db443c07b39"
ACCEPTED_R26_BIN_SIZE = 489216
ACCEPTED_R26_BIN_SHA256 = "4e1e45c411c78a1b08460e788ca4667044d2fed8769fc2d182da878e17ad47d7"
ACCEPTED_R26_CUE_SIZE = 81
ACCEPTED_R26_CUE_SHA256 = "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
ACCEPTED_R26_SECTOR_COUNT = 208
ACCEPTED_R26_RAW_BYTES = 489216
ACCEPTED_R26_USER_BYTES = 425984


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


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR26PreMediaGateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KR26PreMediaGateError(f"{label} root must be an object")
    return value


def _file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnMidi68KR26PreMediaGateError(
            f"{label} path escapes project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnMidi68KR26PreMediaGateError(f"{label} is missing: {path}")
    return path


def _expect(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise SaturnMidi68KR26PreMediaGateError(
            f"R26 pre-media contract mismatch: {label}"
        )


def _verify_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidi68KR26PreMediaGateError(
            "R26 candidate has no generated input inventory"
        )
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidi68KR26PreMediaGateError(
                "invalid R26 generated inventory entry"
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
            raise SaturnMidi68KR26PreMediaGateError(
                "invalid or duplicate R26 generated inventory metadata"
            )
        seen.add(relative)
        path = _file(root, relative, "R26 generated input")
        if path.stat().st_size != size or _sha256_file(path) != expected.lower():
            raise SaturnMidi68KR26PreMediaGateError(
                f"R26 generated input changed: {relative}"
            )

    required = {
        _MAIN,
        _MENU,
        _RUNTIME,
        _R26_AUDIO_SOURCE,
        _R26_AUDIO_HEADER,
        _R26_VOICE_HEADER,
        _R26_PLAYER_SOURCE,
        _R26_PLAYER_HEADER,
        _R26_PROOF_SOURCE,
        _R26_PROOF_HEADER,
    }
    if not required.issubset(seen):
        missing = ", ".join(sorted(required - seen))
        raise SaturnMidi68KR26PreMediaGateError(
            f"R26 generated inventory is missing required files: {missing}"
        )


def _render_current_r26(
    repository_root: Path,
) -> tuple[object, dict[str, bytes], str]:
    profile = _build._validate_profile(repository_root)
    image = build_srk_saturn_midi_68k_r26_resident_audio_service_image(
        release_rate=_build.ACCEPTED_R26_RELEASE_RATE
    )
    _expect(
        image.sha256,
        ACCEPTED_R26_RESIDENT_IMAGE_SHA256,
        "current resident image SHA-256",
    )
    _expect(image.word_count, _build.ACCEPTED_R26_IMAGE_WORDS, "resident image words")
    _expect(image.byte_size, _build.ACCEPTED_R26_IMAGE_BYTES, "resident image bytes")

    blobs = {
        _R26_AUDIO_SOURCE: render_srk_saturn_midi_68k_r26_resident_audio_service_source(
            release_rate=_build.ACCEPTED_R26_RELEASE_RATE
        ).encode("utf-8"),
        _R26_AUDIO_HEADER: render_srk_saturn_midi_68k_r26_resident_audio_service_header(
            release_rate=_build.ACCEPTED_R26_RELEASE_RATE
        ).encode("utf-8"),
        _R26_VOICE_HEADER: render_srk_saturn_midi_68k_r26_voice_header().encode("utf-8"),
        _R26_PLAYER_SOURCE: render_saturn_midi_68k_r26_player_source(
            profile.program
        ).encode("utf-8"),
        _R26_PLAYER_HEADER: render_saturn_midi_68k_r26_player_header().encode("utf-8"),
        _R26_PROOF_SOURCE: render_srk_saturn_midi_68k_r26_physical_proof_source(
            profile, release_rate=_build.ACCEPTED_R26_RELEASE_RATE
        ).encode("utf-8"),
        _R26_PROOF_HEADER: render_srk_saturn_midi_68k_r26_physical_proof_header().encode(
            "utf-8"
        ),
    }
    return profile, blobs, image.sha256


def inspect_saturn_midi_68k_r26_pre_media(
    project_directory: os.PathLike[str] | str,
    repository_root: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR26PreMediaResult:
    """Revalidate R26 and return only a read-only fresh SAROO destination plan."""

    root = _canonical(project_directory)
    repo = _canonical(repository_root)
    if not root.is_dir():
        raise SaturnMidi68KR26PreMediaGateError(
            f"R26 Space Spectre candidate project is not a directory: {root}"
        )
    if not repo.is_dir():
        raise SaturnMidi68KR26PreMediaGateError(
            f"SRK repository root is not a directory: {repo}"
        )

    manifest_path = _file(root, _MANIFEST, "R26 manifest")
    report_path = _file(root, _REPORT, "R26 build report")
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "R26 manifest")
    report = _load_json(report_path, "R26 build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict):
        raise SaturnMidi68KR26PreMediaGateError("R26 physical-candidate gate is missing")
    _expect(gate.get("schema"), _GATE_SCHEMA, "gate schema")
    _verify_inventory(root, manifest)

    required_gate = {
        "baseline_manifest_sha256": _build._r25_gate.ACCEPTED_R24_MANIFEST_SHA256,
        "baseline_report_sha256": _build._r25_gate.ACCEPTED_R24_REPORT_SHA256,
        "baseline_deploy_bin_sha256": _build._r25_gate.ACCEPTED_R24_BIN_SHA256,
        "baseline_deploy_cue_sha256": _build._r25_gate.ACCEPTED_R24_CUE_SHA256,
        "source_midi_sha256": ACCEPTED_R26_SOURCE_MIDI_SHA256,
        "record_count": _build.ACCEPTED_R26_RECORDS,
        "batch_count": _build.ACCEPTED_R26_BATCHES,
        "last_batch_records": 2,
        "duration_us": _build.ACCEPTED_R26_DURATION_US,
        "note_on_count": _build.ACCEPTED_R26_NOTE_ON,
        "note_off_count": _build.ACCEPTED_R26_NOTE_OFF,
        "raw_peak_polyphony": _build.ACCEPTED_R26_RAW_PEAK,
        "r25_tail_peak_owned": _build.ACCEPTED_R26_PEAK_OWNED,
        "release_tail_steals": _build.ACCEPTED_R26_RELEASE_STEALS,
        "busy_allocations": _build.ACCEPTED_R26_BUSY,
        "release_rate": _build.ACCEPTED_R26_RELEASE_RATE,
        "release_rate_status": "PROVISIONAL-R25-CALIBRATION-VALUE-NOT-PRODUCTION-SELECTION",
        "resident_image_sha256": ACCEPTED_R26_RESIDENT_IMAGE_SHA256,
        "resident_image_words": _build.ACCEPTED_R26_IMAGE_WORDS,
        "resident_image_bytes": _build.ACCEPTED_R26_IMAGE_BYTES,
        "resident_source_sha256": ACCEPTED_R26_RESIDENT_SOURCE_SHA256,
        "resident_header_sha256": ACCEPTED_R26_RESIDENT_HEADER_SHA256,
        "voice_header_sha256": ACCEPTED_R26_VOICE_HEADER_SHA256,
        "player_source_sha256": ACCEPTED_R26_PLAYER_SOURCE_SHA256,
        "player_header_sha256": ACCEPTED_R26_PLAYER_HEADER_SHA256,
        "proof_source_sha256": ACCEPTED_R26_PROOF_SOURCE_SHA256,
        "proof_header_sha256": ACCEPTED_R26_PROOF_HEADER_SHA256,
        "candidate_main_sha256": ACCEPTED_R26_MAIN_SHA256,
        "candidate_menu_sha256": ACCEPTED_R26_MENU_SHA256,
        "runtime_before_sha256": _build._r25_gate.ACCEPTED_R24_RUNTIME_SHA256,
        "runtime_after_sha256": ACCEPTED_R26_RUNTIME_SHA256,
        "candidate_define": "#define SRK_MIDI_68K_R26_DOUBLE_IMPACT_CANDIDATE 1",
        "candidate_menu_label": "MIDI R26 Space Spectre",
        "trigger_button": "A",
        "trigger_requires_release_after_screen_entry": True,
        "clock_backend": "accepted-r24-sh2-frt-div128-runtime-vdp2-selection",
        "final_release_drain_required_before_pass": True,
        "frt_original_tcr_restored_on_terminal_path": True,
        "resident_installed_during_build": False,
        "resident_executed_during_build": False,
        "frt_invoked_during_build": False,
        "scsp_mmio_during_build": False,
        "sound_ram_writes_during_build": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active_when_deployed_and_explicitly_triggered": True,
    }
    for key, expected in required_gate.items():
        _expect(gate.get(key), expected, key)

    baseline_text = gate.get("baseline_project")
    if not isinstance(baseline_text, str) or not baseline_text:
        raise SaturnMidi68KR26PreMediaGateError("R26 gate has no accepted R24 baseline path")
    baseline = _canonical(baseline_text)
    if not baseline.is_dir():
        raise SaturnMidi68KR26PreMediaGateError(
            f"accepted R24 baseline is unavailable: {baseline}"
        )
    _build._r25_gate._verify_r24_baseline(baseline)

    profile, blobs, image_sha = _render_current_r26(repo)
    _expect(profile.member_sha256, ACCEPTED_R26_SOURCE_MIDI_SHA256, "source MIDI SHA-256")
    _expect(image_sha, ACCEPTED_R26_RESIDENT_IMAGE_SHA256, "resident image SHA-256")

    render_contract = {
        _R26_AUDIO_SOURCE: ACCEPTED_R26_RESIDENT_SOURCE_SHA256,
        _R26_AUDIO_HEADER: ACCEPTED_R26_RESIDENT_HEADER_SHA256,
        _R26_VOICE_HEADER: ACCEPTED_R26_VOICE_HEADER_SHA256,
        _R26_PLAYER_SOURCE: ACCEPTED_R26_PLAYER_SOURCE_SHA256,
        _R26_PLAYER_HEADER: ACCEPTED_R26_PLAYER_HEADER_SHA256,
        _R26_PROOF_SOURCE: ACCEPTED_R26_PROOF_SOURCE_SHA256,
        _R26_PROOF_HEADER: ACCEPTED_R26_PROOF_HEADER_SHA256,
    }
    for relative, accepted in render_contract.items():
        _expect(_sha256_bytes(blobs[relative]), accepted, f"current renderer {relative}")
        _expect(_sha256_file(_file(root, relative, relative)), accepted, f"disk {relative}")

    baseline_main = _file(baseline, _MAIN, "accepted R24 main").read_text(
        encoding="utf-8"
    )
    baseline_menu = _file(baseline, _MENU, "accepted R24 menu").read_text(
        encoding="utf-8"
    )
    expected_main = derive_r26_double_impact_candidate_main(baseline_main).encode("utf-8")
    expected_menu = derive_r26_double_impact_candidate_menu(baseline_menu).encode("utf-8")
    _expect(_sha256_bytes(expected_main), ACCEPTED_R26_MAIN_SHA256, "derived main hash")
    _expect(_file(root, _MAIN, "R26 main").read_bytes(), expected_main, "derived main bytes")
    _expect(_sha256_bytes(expected_menu), ACCEPTED_R26_MENU_SHA256, "derived menu hash")
    _expect(_file(root, _MENU, "R26 menu").read_bytes(), expected_menu, "derived menu bytes")

    expected_runtime = _file(baseline, _RUNTIME, "accepted R24 runtime").read_bytes()
    if not expected_runtime.endswith(b"\n"):
        expected_runtime += b"\n"
    expected_runtime += b"\n" + _MARKER.encode("ascii") + b"\n"
    for relative in (_R26_AUDIO_SOURCE, _R26_PLAYER_SOURCE, _R26_PROOF_SOURCE):
        expected_runtime += blobs[relative]
        if not expected_runtime.endswith(b"\n"):
            expected_runtime += b"\n"
        expected_runtime += b"\n"
    _expect(
        _sha256_bytes(expected_runtime),
        ACCEPTED_R26_RUNTIME_SHA256,
        "reconstructed runtime hash",
    )
    _expect(
        _file(root, _RUNTIME, "R26 runtime").read_bytes(),
        expected_runtime,
        "reconstructed runtime bytes",
    )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnMidi68KR26PreMediaGateError("R26 manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "midi_68k_r24_physical_baseline_preserved": True,
        "midi_68k_r26_double_impact_present": True,
        "midi_68k_r26_double_impact_bound": True,
        "midi_68k_r26_resident_installed_during_build": False,
        "midi_68k_r26_resident_executed_during_build": False,
        "midi_68k_r26_frt_invoked_during_build": False,
        "midi_68k_r26_build_time_hardware_io": False,
        "midi_68k_r26_production_rr_selected": False,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")

    _expect(report.get("schema"), "srk.saturn.standalone-build.v1", "report schema")
    _expect(report.get("successful"), True, "successful build")
    _expect(
        str(report.get("project_manifest_sha256", "")).lower(),
        manifest_sha,
        "report/manifest pairing",
    )
    report_policy = report.get("policy")
    if not isinstance(report_policy, dict):
        raise SaturnMidi68KR26PreMediaGateError("R26 build policy is missing")
    for key, expected in {
        "commercial_image_changes": False,
        "path_mutated": False,
        "private_sdk_dependencies_copied": False,
        "private_sdk_dependencies_verified_after_build": True,
        "private_sdk_dependencies_verified_before_build": True,
        "sd_writes": False,
        "shell_used": False,
        "source_inputs_verified_after_build": True,
        "source_inputs_verified_before_build": True,
    }.items():
        _expect(report_policy.get(key), expected, f"build policy {key}")

    deployable = report.get("deployable")
    if not isinstance(deployable, dict):
        raise SaturnMidi68KR26PreMediaGateError("R26 deployable record is missing")
    for actual, expected, label in (
        (deployable.get("format"), "cue-bin-mode1-2352", "deployable format"),
        (deployable.get("verified_against_iso"), True, "MODE1/ISO verification"),
        (deployable.get("sector_count"), ACCEPTED_R26_SECTOR_COUNT, "sector count"),
        (deployable.get("raw_bytes"), ACCEPTED_R26_RAW_BYTES, "raw bytes"),
        (deployable.get("user_bytes"), ACCEPTED_R26_USER_BYTES, "user bytes"),
        (deployable.get("bin"), _DEPLOY_BIN, "deployable BIN path"),
        (deployable.get("cue"), _DEPLOY_CUE, "deployable CUE path"),
    ):
        _expect(actual, expected, label)

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KR26PreMediaGateError("R26 report has no artifact inventory")
    by_path = {
        str(entry.get("path")): entry
        for entry in artifacts
        if isinstance(entry, dict)
    }
    exact_artifacts = {
        "build/srk_diag.bin": (
            ACCEPTED_R26_BUILD_BIN_SIZE,
            ACCEPTED_R26_BUILD_BIN_SHA256,
        ),
        "build/srk_diag.iso": (
            ACCEPTED_R26_BUILD_ISO_SIZE,
            ACCEPTED_R26_BUILD_ISO_SHA256,
        ),
        "build/srk_diag.map": (
            ACCEPTED_R26_BUILD_MAP_SIZE,
            ACCEPTED_R26_BUILD_MAP_SHA256,
        ),
        "cd/SRKPCM.BIN": (
            ACCEPTED_R26_PACKAGED_PCM_SIZE,
            ACCEPTED_R26_PACKAGED_PCM_SHA256,
        ),
        _DEPLOY_BIN: (ACCEPTED_R26_BIN_SIZE, ACCEPTED_R26_BIN_SHA256),
        _DEPLOY_CUE: (ACCEPTED_R26_CUE_SIZE, ACCEPTED_R26_CUE_SHA256),
    }
    for relative, (size, accepted) in exact_artifacts.items():
        entry = by_path.get(relative)
        if not isinstance(entry, dict):
            raise SaturnMidi68KR26PreMediaGateError(
                f"missing accepted artifact: {relative}"
            )
        _expect(entry.get("size"), size, f"reported size {relative}")
        _expect(
            str(entry.get("sha256", "")).lower(),
            accepted,
            f"reported hash {relative}",
        )
        path = _file(root, relative, relative)
        _expect(path.stat().st_size, size, f"disk size {relative}")
        _expect(_sha256_file(path), accepted, f"disk hash {relative}")

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnMidi68KR26PreMediaGateError(
            f"read-only SAROO plan rejected R26 Space Spectre candidate: {exc}"
        ) from exc
    _expect(plan.bin_sha256.lower(), ACCEPTED_R26_BIN_SHA256, "planned BIN hash")
    _expect(plan.cue_sha256.lower(), ACCEPTED_R26_CUE_SHA256, "planned CUE hash")
    _expect(plan.bin_size, ACCEPTED_R26_BIN_SIZE, "planned BIN size")
    _expect(plan.cue_size, ACCEPTED_R26_CUE_SIZE, "planned CUE size")

    return SaturnMidi68KR26PreMediaResult(
        project_root=root,
        repository_root=repo,
        baseline_root=baseline,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        resident_image_sha256=ACCEPTED_R26_RESIDENT_IMAGE_SHA256,
        resident_source_sha256=ACCEPTED_R26_RESIDENT_SOURCE_SHA256,
        resident_header_sha256=ACCEPTED_R26_RESIDENT_HEADER_SHA256,
        voice_header_sha256=ACCEPTED_R26_VOICE_HEADER_SHA256,
        player_source_sha256=ACCEPTED_R26_PLAYER_SOURCE_SHA256,
        player_header_sha256=ACCEPTED_R26_PLAYER_HEADER_SHA256,
        proof_source_sha256=ACCEPTED_R26_PROOF_SOURCE_SHA256,
        proof_header_sha256=ACCEPTED_R26_PROOF_HEADER_SHA256,
        candidate_main_sha256=ACCEPTED_R26_MAIN_SHA256,
        candidate_menu_sha256=ACCEPTED_R26_MENU_SHA256,
        runtime_after_sha256=ACCEPTED_R26_RUNTIME_SHA256,
        build_bin_sha256=ACCEPTED_R26_BUILD_BIN_SHA256,
        build_iso_sha256=ACCEPTED_R26_BUILD_ISO_SHA256,
        build_map_sha256=ACCEPTED_R26_BUILD_MAP_SHA256,
        deployable_bin_sha256=ACCEPTED_R26_BIN_SHA256,
        deployable_cue_sha256=ACCEPTED_R26_CUE_SHA256,
        sector_count=ACCEPTED_R26_SECTOR_COUNT,
        raw_bytes=ACCEPTED_R26_RAW_BYTES,
        user_bytes=ACCEPTED_R26_USER_BYTES,
        plan=plan,
    )
