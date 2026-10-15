"""Preserve-first hardware gate for the real Space Spectre SBL/GM candidate.

This module deliberately operates on an already-built, successful candidate.
It revalidates the candidate manifest, every generated input, the Sega sound
assets and compact tone-bank contract, then asks SRK's existing standalone
SAROO deployer for a fresh-destination plan.

When APPLY is explicitly requested, a complete off-card SAROO inventory is
captured and verified immediately before the single permitted write.  Only one
new candidate directory and its CUE/BIN pair may differ afterwards.  Existing
card content is never overwritten, removed or reformatted.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import struct

from .midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
)
from .saroo.card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from .saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN as STANDALONE_CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentPlan,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
    plan_saroo_standalone_image_deployment,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-GM-SPACE-SPECTRE"
DEFAULT_DESTINATION_NAME = "SRK-Space-Spectre-SBL-GM-GATE2"
EXPECTED_RECORD_COUNT = 9154
EXPECTED_DURATION_US = 148_093_750
EXPECTED_MELODIC_PROGRAMS = (30, 39, 73, 120)
EXPECTED_PERCUSSION_CHANNEL = 9
EXPECTED_PERCUSSION_NOTES = (35, 40, 42, 51)
EXPECTED_MELODIC_BANK_SHA256 = (
    "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
)
EXPECTED_DRUM_BANK_SHA256 = (
    "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"
)
SEGA_BOOTTONE_VELOCITY_TABLE0 = bytes(
    (0x08, 0x00, 0x7F, 0x0C, 0x7F, 0x7F, 0x08, 0x7F, 0x7F, 0x08)
)

_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MELODIC = "cd/SRKGM.BIN"
_DRUM = "cd/SRKDRUM.BIN"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_DIRECT_HEADER = "src/srk_saturn_sbl_direct_midi.h"
_GM_HEADER = "src/srk_saturn_sbl_gm_candidate.h"
_RUNTIME = "src/srk_saturn_runtime.c"
_TONE_START = 0x0000B000
_SOUND_RAM_END = 0x00080000


class SaturnSblGmHardwareGateError(RuntimeError):
    """Raised when the SBL/GM candidate cannot cross the hardware boundary."""


@dataclass(frozen=True)
class SaturnSblGmHardwareEvidence:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    melodic_bank_sha256: str
    drum_bank_sha256: str
    sound_driver_sha256: str
    sega_sound_library_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


@dataclass(frozen=True)
class SaturnSblGmHardwareResult:
    evidence: SaturnSblGmHardwareEvidence
    guard: SarooCardInventoryResult | None
    deployment: SarooStandaloneImageDeploymentResult | None
    verification: SarooCardInventoryVerification | None

    @property
    def applied(self) -> bool:
        return self.deployment is not None

    @property
    def card_verified(self) -> bool:
        return self.verification is not None and self.verification.valid


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise SaturnSblGmHardwareGateError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblGmHardwareGateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaturnSblGmHardwareGateError(f"{label} root must be an object")
    return value


def _expect(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise SaturnSblGmHardwareGateError(
            f"Space Spectre SBL/GM hardware contract mismatch: {label}; "
            f"expected {expected!r}, got {actual!r}"
        )


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnSblGmHardwareGateError(
            f"{label} path escapes candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnSblGmHardwareGateError(f"{label} is missing: {path}")
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblGmHardwareGateError("candidate has no generated-file inventory")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblGmHardwareGateError("invalid generated-file inventory entry")
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
            raise SaturnSblGmHardwareGateError(
                "invalid or duplicate generated-file inventory metadata"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated input")
        if path.stat().st_size != size or _sha256_file(path) != expected_sha.lower():
            raise SaturnSblGmHardwareGateError(f"generated candidate input changed: {relative}")

    required = {
        _MELODIC,
        _DRUM,
        _AREA_MAP,
        _DRIVER,
        _DIRECT_HEADER,
        _GM_HEADER,
        _RUNTIME,
    }
    if not required.issubset(seen):
        raise SaturnSblGmHardwareGateError(
            "generated candidate inventory is missing required SBL/GM files: "
            + ", ".join(sorted(required - seen))
        )


def _validate_tone_bank(payload: bytes, *, expected_voices: int, label: str) -> None:
    if len(payload) < 18:
        raise SaturnSblGmHardwareGateError(f"{label} tone bank is too small")
    mix, velocity, peg, plfo = struct.unpack_from(">HHHH", payload, 0)
    if mix < 8 or (mix - 8) % 2:
        raise SaturnSblGmHardwareGateError(f"{label} tone-bank voice table is malformed")
    voice_count = (mix - 8) // 2
    _expect(voice_count, expected_voices, f"{label} voice count")
    if not (mix < velocity < peg < plfo <= len(payload)):
        raise SaturnSblGmHardwareGateError(f"{label} tone-bank table offsets are invalid")
    if velocity + len(SEGA_BOOTTONE_VELOCITY_TABLE0) > len(payload):
        raise SaturnSblGmHardwareGateError(f"{label} velocity table is truncated")
    _expect(
        payload[velocity : velocity + len(SEGA_BOOTTONE_VELOCITY_TABLE0)],
        SEGA_BOOTTONE_VELOCITY_TABLE0,
        f"{label} Sega BOOTTONE velocity curve",
    )


def _validate_area_map(root: Path, melodic_size: int, drum_size: int) -> None:
    path = _project_file(root, _AREA_MAP, "SBL area map")
    payload = path.read_bytes()
    _expect(len(payload), 20, "SBL area-map byte count")
    bank0_word, bank0_size, bank1_word, bank1_size, end_word = struct.unpack(">IIIII", payload)
    drum_start = (_TONE_START + melodic_size + 3) & ~3
    _expect(bank0_word, _TONE_START, "area-map bank-0 word")
    _expect(bank0_size, melodic_size, "area-map bank-0 size")
    _expect(bank1_word, 0x01000000 | drum_start, "area-map bank-1 word")
    _expect(bank1_size, drum_size, "area-map bank-1 size")
    _expect(end_word, 0x80000000, "area-map terminator")
    if drum_start + drum_size > _SOUND_RAM_END:
        raise SaturnSblGmHardwareGateError("tone banks exceed Saturn sound RAM")


def _validate_external_asset(record: object, label: str) -> str:
    if not isinstance(record, dict):
        raise SaturnSblGmHardwareGateError(f"candidate has no {label} record")
    path_text = record.get("path")
    expected = record.get("sha256")
    if not isinstance(path_text, str) or not path_text:
        raise SaturnSblGmHardwareGateError(f"candidate {label} path is invalid")
    if not isinstance(expected, str) or len(expected) != 64:
        raise SaturnSblGmHardwareGateError(f"candidate {label} SHA-256 is invalid")
    path = _canonical(path_text)
    if not path.is_file():
        raise SaturnSblGmHardwareGateError(f"candidate {label} is unavailable: {path}")
    actual = _sha256_file(path)
    if actual != expected.lower():
        raise SaturnSblGmHardwareGateError(f"candidate {label} changed since build")
    return actual


def _validate_candidate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None,
) -> SaturnSblGmHardwareEvidence:
    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnSblGmHardwareGateError(f"candidate project is not a directory: {root}")

    manifest_path = _project_file(root, _MANIFEST, "candidate manifest")
    report_path = _project_file(root, _REPORT, "candidate build report")
    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "candidate manifest")
    report = _load_json(report_path, "candidate build report")

    _expect(manifest.get("schema"), "srk.saturn.standalone-project.v1", "manifest schema")
    _expect(manifest.get("mode"), "standalone-master", "manifest mode")
    _verify_generated_inventory(root, manifest)

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise SaturnSblGmHardwareGateError("candidate manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "sbl_direct_midi_gm_candidate": True,
        "synthetic_r26_r28_timbres_used": False,
        "hardware_executed_during_build": False,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")

    gm = manifest.get("sbl_direct_midi_gm")
    if not isinstance(gm, dict):
        raise SaturnSblGmHardwareGateError("SBL/GM manifest record is missing")
    for actual, expected, label in (
        (gm.get("schema"), "srk.saturn.sbl-direct-midi-gm-candidate.v1", "SBL/GM schema"),
        (gm.get("source_midi_sha256"), SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256, "source MIDI"),
        (gm.get("record_count"), EXPECTED_RECORD_COUNT, "record count"),
        (gm.get("duration_us"), EXPECTED_DURATION_US, "duration"),
        (gm.get("percussion_channel_zero_based"), EXPECTED_PERCUSSION_CHANNEL, "percussion channel"),
        (tuple(gm.get("percussion_notes", ())), EXPECTED_PERCUSSION_NOTES, "percussion notes"),
        (gm.get("channel10_program_changes_normalized_to_drum_voice"), True, "channel-10 program normalization"),
        (gm.get("off_card_only"), True, "off-card generation policy"),
    ):
        _expect(actual, expected, label)

    melodic_record = gm.get("melodic_bank")
    drum_record = gm.get("drum_bank")
    if not isinstance(melodic_record, dict) or not isinstance(drum_record, dict):
        raise SaturnSblGmHardwareGateError("candidate tone-bank records are missing")
    _expect(melodic_record.get("bank"), 0, "melodic bank number")
    _expect(melodic_record.get("sha256"), EXPECTED_MELODIC_BANK_SHA256, "melodic bank SHA-256")
    _expect(drum_record.get("bank"), 1, "drum bank number")
    _expect(drum_record.get("program"), 0, "drum program")
    _expect(drum_record.get("gm_note_map_preserved"), True, "GM drum-note preservation")
    _expect(drum_record.get("sha256"), EXPECTED_DRUM_BANK_SHA256, "drum bank SHA-256")

    melodic_path = _project_file(root, _MELODIC, "derived melodic bank")
    drum_path = _project_file(root, _DRUM, "derived drum bank")
    melodic_sha = _sha256_file(melodic_path)
    drum_sha = _sha256_file(drum_path)
    _expect(melodic_sha, EXPECTED_MELODIC_BANK_SHA256, "disk melodic bank SHA-256")
    _expect(drum_sha, EXPECTED_DRUM_BANK_SHA256, "disk drum bank SHA-256")
    _validate_tone_bank(melodic_path.read_bytes(), expected_voices=121, label="melodic")
    _validate_tone_bank(drum_path.read_bytes(), expected_voices=1, label="drum")
    _validate_area_map(root, melodic_path.stat().st_size, drum_path.stat().st_size)

    sound_driver_sha = _validate_external_asset(gm.get("sound_driver"), "sound driver")
    sega_snd_sha = _validate_external_asset(gm.get("sega_snd"), "Sega sound library")

    runtime = _project_file(root, _RUNTIME, "candidate runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    for marker in (
        "SND_CtrlDirMidi",
        "SND_MoveData((Uint16 *)tone",
        "SND_MoveData((Uint16 *)drum",
        "SEGA DIRECT MIDI / REAL GM",
        "SRK_SBL_GM_RECORD_COUNT",
    ):
        if marker not in runtime:
            raise SaturnSblGmHardwareGateError(
                f"candidate runtime is missing required Sega Direct-MIDI marker: {marker}"
            )

    _expect(report.get("schema"), "srk.saturn.standalone-build.v1", "build-report schema")
    _expect(report.get("successful"), True, "successful build")
    _expect(
        str(report.get("project_manifest_sha256", "")).lower(),
        manifest_sha,
        "build-report/manifest pairing",
    )
    report_policy = report.get("policy")
    if not isinstance(report_policy, dict):
        raise SaturnSblGmHardwareGateError("candidate build policy is missing")
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
        raise SaturnSblGmHardwareGateError("successful build has no deployable record")
    _expect(deployable.get("format"), "cue-bin-mode1-2352", "deployable format")
    _expect(deployable.get("verified_against_iso"), True, "deployable ISO verification")

    try:
        plan = plan_saroo_standalone_image_deployment(
            card_root,
            root,
            destination_name=destination_name,
            category=category,
        )
    except Exception as exc:
        raise SaturnSblGmHardwareGateError(
            f"read-only SAROO deployment plan rejected candidate: {exc}"
        ) from exc

    return SaturnSblGmHardwareEvidence(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        melodic_bank_sha256=melodic_sha,
        drum_bank_sha256=drum_sha,
        sound_driver_sha256=sound_driver_sha,
        sega_sound_library_sha256=sega_snd_sha,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )


def inspect_saturn_sbl_gm_hardware_gate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
) -> SaturnSblGmHardwareEvidence:
    """Perform the complete read-only candidate/card pre-media review."""

    return _validate_candidate(
        project_directory,
        card_root,
        destination_name=destination_name,
        category=category,
    )


def _allowed_paths(plan: SarooStandaloneImageDeploymentPlan) -> tuple[str, str, str]:
    try:
        destination = plan.destination_directory.relative_to(plan.card_root).as_posix()
    except ValueError as exc:
        raise SaturnSblGmHardwareGateError(
            "planned destination is outside the mounted SAROO card"
        ) from exc
    return (
        destination,
        f"{destination}/{plan.source_bin.name}",
        f"{destination}/{plan.source_cue.name}",
    )


def run_saturn_sbl_gm_hardware_gate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
    apply: bool = False,
    confirmation: str = "",
) -> SaturnSblGmHardwareResult:
    """Revalidate GATE2 and optionally deploy it through a whole-card guard."""

    if apply and confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblGmHardwareGateError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    guard_path = _canonical(guard_manifest)
    if _inside(guard_path, card):
        raise SaturnSblGmHardwareGateError(
            "whole-card guard manifest must be stored outside the SAROO card"
        )

    evidence = _validate_candidate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    if not apply:
        return SaturnSblGmHardwareResult(evidence, None, None, None)

    try:
        guard = create_saroo_card_inventory(card, guard_path)
        pre_verify = verify_saroo_card_inventory(card, guard.manifest_path)
    except Exception as exc:
        raise SaturnSblGmHardwareGateError(
            f"cannot establish fresh whole-card SAROO baseline: {exc}"
        ) from exc
    if not pre_verify.valid:
        detail = "; ".join(pre_verify.differences[:8])
        raise SaturnSblGmHardwareGateError(
            "fresh whole-card SAROO baseline did not immediately verify: " + detail
        )

    # Revalidate the off-card candidate and destination after the card snapshot.
    before_write = _validate_candidate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    _expect(before_write.manifest_sha256, evidence.manifest_sha256, "manifest changed before write")
    _expect(before_write.report_sha256, evidence.report_sha256, "report changed before write")
    _expect(before_write.deployable_bin_sha256, evidence.deployable_bin_sha256, "BIN changed before write")
    _expect(before_write.deployable_cue_sha256, evidence.deployable_cue_sha256, "CUE changed before write")

    try:
        deployment = apply_saroo_standalone_image_deployment(
            card,
            project_directory,
            destination_name=destination_name,
            category=category,
            confirmation=STANDALONE_CONFIRMATION_TOKEN,
        )
    except Exception as exc:
        try:
            state = verify_saroo_card_inventory(card, guard.manifest_path)
            detail = (
                "original whole-card baseline still matches"
                if state.valid
                else "card differs from baseline: " + "; ".join(state.differences[:8])
            )
        except Exception as verify_exc:
            detail = f"card state could not be rechecked: {verify_exc}"
        raise SaturnSblGmHardwareGateError(
            f"SBL/GM deployment failed; {detail}: {exc}"
        ) from exc

    _expect(deployment.bin_sha256, evidence.deployable_bin_sha256, "deployed BIN SHA-256")
    _expect(deployment.cue_sha256, evidence.deployable_cue_sha256, "deployed CUE SHA-256")

    allowed = _allowed_paths(deployment.plan)
    try:
        verification = verify_saroo_card_inventory(
            card,
            guard.manifest_path,
            allowed_changed_paths=allowed,
        )
    except Exception as exc:
        raise SaturnSblGmHardwareGateError(
            "candidate was written but whole-card post-write verification could not run; "
            "do not retry, delete or alter the card until reviewed: " + str(exc)
        ) from exc
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        raise SaturnSblGmHardwareGateError(
            "candidate was written but whole-card guard found an unauthorized difference; "
            "do not retry, delete or alter the card until reviewed: " + detail
        )

    return SaturnSblGmHardwareResult(evidence, guard, deployment, verification)
