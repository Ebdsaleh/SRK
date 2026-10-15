"""Preserve-first hardware gate for Space Spectre native SDDRV sequence playback.

This gate operates only on an already-built native GATE3 candidate.  It locks the
Eridu-observed GATE3D audio assets and sound-RAM layout, revalidates the successful
standalone build, verifies that the runtime uses SDDRV sequence playback rather
than Direct MIDI streaming, and delegates the single permitted SAROO write to the
existing fresh-destination standalone deployer under a whole-card inventory guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from .midi_68k_r26_double_impact import SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
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
from .sbl_sequence import (
    SBL_AREA_SEQUENCE,
    SBL_AREA_TONE,
    SaturnSblArea,
    encode_sbl_external_area_map,
)


CONFIRMATION_TOKEN = "DEPLOY-SBL-NATIVE-SPACE-SPECTRE"
DEFAULT_DESTINATION_NAME = "SRK-Space-Spectre-SBL-NATIVE-GATE3D"

EXPECTED_NOTE_COUNT = 4381
EXPECTED_DURATION_US = 148_093_750
EXPECTED_SEQUENCE_BYTES = 23_127
EXPECTED_SEQUENCE_SHA256 = (
    "56eef2dda77221e861b6e34724a493597d0e8e4b9523a2b48b2af18adac49967"
)
EXPECTED_MELODIC_BANK_SHA256 = (
    "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
)
EXPECTED_DRUM_BANK_SHA256 = (
    "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"
)
EXPECTED_AREA_MAP_SHA256 = (
    "b0c223db1907af25af5ffc237574ed11390ea4ee28a283810ae256077b479e3b"
)
EXPECTED_SOUND_DRIVER_SHA256 = (
    "76754e5bae4217e48d6a3c53c181033ddaab050deabda638bc41bf2f7f4906e3"
)
EXPECTED_SEGA_SND_SHA256 = (
    "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
)
EXPECTED_MELODIC_START = 0x0000B000
EXPECTED_DRUM_START = 0x0005966C
EXPECTED_SEQUENCE_START = 0x00074B0C
EXPECTED_AREA_MAP_BYTES = 26

_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_REPORT = "SRK_STANDALONE_BUILD.json"
_MELODIC = "cd/SRKGM.BIN"
_DRUM = "cd/SRKDRUM.BIN"
_SEQUENCE = "cd/SPACESEQ.BNK"
_AREA_MAP = "cd/SRKMAP.BIN"
_DRIVER = "cd/SDDRVS.TSK"
_GM_HEADER = "src/srk_saturn_sbl_gm_candidate.h"
_RUNTIME = "src/srk_saturn_runtime.c"
_MAIN = "src/srk_saturn_main.c"
_SOUND_RAM_END = 0x00080000


class SaturnSblNativeSequenceHardwareGateError(RuntimeError):
    """Raised when native SDDRV GATE3 cannot safely cross the media boundary."""


@dataclass(frozen=True)
class SaturnSblNativeSequenceHardwareEvidence:
    project_root: Path
    manifest_sha256: str
    report_sha256: str
    melodic_bank_sha256: str
    drum_bank_sha256: str
    sequence_bank_sha256: str
    area_map_sha256: str
    sound_driver_sha256: str
    sega_sound_library_sha256: str
    deployable_bin_sha256: str
    deployable_cue_sha256: str
    plan: SarooStandaloneImageDeploymentPlan


@dataclass(frozen=True)
class SaturnSblNativeSequenceHardwareResult:
    evidence: SaturnSblNativeSequenceHardwareEvidence
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
        raise SaturnSblNativeSequenceHardwareGateError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnSblNativeSequenceHardwareGateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaturnSblNativeSequenceHardwareGateError(f"{label} root must be an object")
    return value


def _expect(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise SaturnSblNativeSequenceHardwareGateError(
            f"native Space Spectre hardware contract mismatch: {label}; "
            f"expected {expected!r}, got {actual!r}"
        )


def _project_file(root: Path, relative: str, label: str) -> Path:
    path = (root / relative).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SaturnSblNativeSequenceHardwareGateError(
            f"{label} path escapes candidate project: {relative}"
        ) from exc
    if not path.is_file():
        raise SaturnSblNativeSequenceHardwareGateError(f"{label} is missing: {path}")
    return path


def _verify_generated_inventory(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnSblNativeSequenceHardwareGateError("candidate has no generated-file inventory")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnSblNativeSequenceHardwareGateError("invalid generated-file inventory entry")
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
            raise SaturnSblNativeSequenceHardwareGateError(
                "invalid or duplicate generated-file inventory metadata"
            )
        seen.add(relative)
        path = _project_file(root, relative, "generated candidate input")
        if path.stat().st_size != size or _sha256_file(path) != expected_sha.lower():
            raise SaturnSblNativeSequenceHardwareGateError(
                f"generated candidate input changed: {relative}"
            )

    required = {_MELODIC, _DRUM, _SEQUENCE, _AREA_MAP, _DRIVER, _GM_HEADER, _RUNTIME, _MAIN}
    missing = required - seen
    if missing:
        raise SaturnSblNativeSequenceHardwareGateError(
            "generated native candidate inventory is missing required files: "
            + ", ".join(sorted(missing))
        )


def _validate_external_sega_snd(record: object) -> str:
    if not isinstance(record, dict):
        raise SaturnSblNativeSequenceHardwareGateError("candidate Sega sound-library record is missing")
    path_text = record.get("path")
    expected = record.get("sha256")
    if not isinstance(path_text, str) or not path_text:
        raise SaturnSblNativeSequenceHardwareGateError("candidate Sega sound-library path is invalid")
    _expect(expected, EXPECTED_SEGA_SND_SHA256, "sega_snd.a manifest SHA-256")
    path = _canonical(path_text)
    if not path.is_file():
        raise SaturnSblNativeSequenceHardwareGateError(f"candidate sega_snd.a is unavailable: {path}")
    actual = _sha256_file(path)
    _expect(actual, EXPECTED_SEGA_SND_SHA256, "sega_snd.a disk SHA-256")
    return actual


def _validate_area_map(
    root: Path,
    melodic_size: int,
    drum_size: int,
    sequence_size: int,
) -> str:
    path = _project_file(root, _AREA_MAP, "native external area map")
    payload = path.read_bytes()
    _expect(len(payload), EXPECTED_AREA_MAP_BYTES, "external area-map byte count")
    _expect(_sha256_file(path), EXPECTED_AREA_MAP_SHA256, "external area-map SHA-256")

    expected = encode_sbl_external_area_map(
        (
            SaturnSblArea(SBL_AREA_TONE, 0, EXPECTED_MELODIC_START, melodic_size),
            SaturnSblArea(SBL_AREA_TONE, 1, EXPECTED_DRUM_START, drum_size),
            SaturnSblArea(SBL_AREA_SEQUENCE, 0, EXPECTED_SEQUENCE_START, sequence_size),
        )
    )
    _expect(payload, expected, "external Sega .MP payload")
    if EXPECTED_SEQUENCE_START + sequence_size > _SOUND_RAM_END:
        raise SaturnSblNativeSequenceHardwareGateError("native sequence exceeds Saturn sound RAM")
    return EXPECTED_AREA_MAP_SHA256


def _validate_candidate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None,
) -> SaturnSblNativeSequenceHardwareEvidence:
    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnSblNativeSequenceHardwareGateError(
            f"native candidate project is not a directory: {root}"
        )

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
        raise SaturnSblNativeSequenceHardwareGateError("candidate manifest policy is missing")
    for key, expected in {
        "sd_writes": False,
        "sbl_direct_midi_gm_candidate": False,
        "sbl_native_sequence_gm_candidate": True,
        "direct_midi_streaming": False,
        "sh2_midi_priming": False,
        "synthetic_r26_r28_timbres_used": False,
        "hardware_executed_during_build": False,
    }.items():
        _expect(policy.get(key), expected, f"manifest policy {key}")

    native = manifest.get("sbl_native_sequence_gm")
    if not isinstance(native, dict):
        raise SaturnSblNativeSequenceHardwareGateError("native SDDRV manifest record is missing")
    for actual, expected, label in (
        (native.get("schema"), "srk.saturn.sbl-native-sequence-gm-candidate.v1", "native schema"),
        (native.get("source_midi_sha256"), SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256, "source MIDI"),
        (native.get("note_count"), EXPECTED_NOTE_COUNT, "note count"),
        (native.get("duration_us"), EXPECTED_DURATION_US, "duration"),
        (native.get("off_card_only"), True, "off-card generation policy"),
    ):
        _expect(actual, expected, label)

    playback = native.get("playback")
    if not isinstance(playback, dict):
        raise SaturnSblNativeSequenceHardwareGateError("native playback record is missing")
    for key, expected in {
        "api": "SND_StartSeq",
        "sequence_number": 1,
        "bank": 0,
        "song": 0,
        "priority": 1,
        "direct_midi_streaming": False,
        "sh2_event_scheduler": False,
    }.items():
        _expect(playback.get(key), expected, f"native playback {key}")

    melodic_record = native.get("melodic_bank")
    drum_record = native.get("drum_bank")
    sequence_record = native.get("sequence_bank")
    area_record = native.get("area_map")
    driver_record = native.get("sound_driver")
    if not all(isinstance(item, dict) for item in (
        melodic_record, drum_record, sequence_record, area_record, driver_record
    )):
        raise SaturnSblNativeSequenceHardwareGateError("native asset records are incomplete")

    _expect(melodic_record.get("bank"), 0, "melodic bank number")
    _expect(melodic_record.get("sha256"), EXPECTED_MELODIC_BANK_SHA256, "melodic manifest SHA-256")
    _expect(drum_record.get("bank"), 1, "drum bank number")
    _expect(drum_record.get("sha256"), EXPECTED_DRUM_BANK_SHA256, "drum manifest SHA-256")
    _expect(sequence_record.get("bytes"), EXPECTED_SEQUENCE_BYTES, "sequence manifest bytes")
    _expect(sequence_record.get("sha256"), EXPECTED_SEQUENCE_SHA256, "sequence manifest SHA-256")
    _expect(
        sequence_record.get("conversion_manifest_schema"),
        "srk.saturn.sbl-space-spectre-sequence.v2",
        "sequence conversion schema",
    )
    _expect(driver_record.get("sha256"), EXPECTED_SOUND_DRIVER_SHA256, "sound-driver manifest SHA-256")

    for key, expected in {
        "format": "sega-external-mp",
        "bytes": EXPECTED_AREA_MAP_BYTES,
        "sha256": EXPECTED_AREA_MAP_SHA256,
        "melodic_start": EXPECTED_MELODIC_START,
        "drum_start": EXPECTED_DRUM_START,
        "sequence_start": EXPECTED_SEQUENCE_START,
    }.items():
        _expect(area_record.get(key), expected, f"area-map {key}")

    melodic_path = _project_file(root, _MELODIC, "melodic tone bank")
    drum_path = _project_file(root, _DRUM, "drum tone bank")
    sequence_path = _project_file(root, _SEQUENCE, "native sequence bank")
    driver_path = _project_file(root, _DRIVER, "Sega sound driver")

    melodic_sha = _sha256_file(melodic_path)
    drum_sha = _sha256_file(drum_path)
    sequence_sha = _sha256_file(sequence_path)
    driver_sha = _sha256_file(driver_path)
    _expect(melodic_sha, EXPECTED_MELODIC_BANK_SHA256, "disk melodic bank SHA-256")
    _expect(drum_sha, EXPECTED_DRUM_BANK_SHA256, "disk drum bank SHA-256")
    _expect(sequence_path.stat().st_size, EXPECTED_SEQUENCE_BYTES, "disk sequence byte count")
    _expect(sequence_sha, EXPECTED_SEQUENCE_SHA256, "disk sequence SHA-256")
    _expect(driver_sha, EXPECTED_SOUND_DRIVER_SHA256, "disk sound-driver SHA-256")

    area_sha = _validate_area_map(
        root,
        melodic_path.stat().st_size,
        drum_path.stat().st_size,
        sequence_path.stat().st_size,
    )
    sega_snd_sha = _validate_external_sega_snd(native.get("sega_snd"))

    runtime = _project_file(root, _RUNTIME, "candidate runtime").read_text(
        encoding="utf-8", errors="strict"
    )
    main = _project_file(root, _MAIN, "candidate generated main").read_text(
        encoding="utf-8", errors="strict"
    )
    for marker in (
        "SND_Init(&ini)",
        "SND_ChgMap(0)",
        "SND_MoveData((Uint16 *)tone",
        "SND_MoveData((Uint16 *)drum",
        "SND_MoveData((Uint16 *)sequence",
        "SND_KD_SEQ,0",
        "SND_SetTlVl(15)",
        "SND_StartSeq(1,0,0,1)",
        "SND_GetSeqStat(&stat,1)",
    ):
        if marker not in runtime:
            raise SaturnSblNativeSequenceHardwareGateError(
                f"native runtime is missing required SDDRV marker: {marker}"
            )
    for forbidden in ("SND_CtrlDirMidi", "SND_GetSeqPlayPos", "SndSeqPlayPos"):
        if forbidden in runtime:
            raise SaturnSblNativeSequenceHardwareGateError(
                f"native runtime contains forbidden streaming/telemetry marker: {forbidden}"
            )
    for marker in ("SEGA NATIVE SEQUENCE / REAL GM", "PASS: native sequence completed"):
        if marker not in main:
            raise SaturnSblNativeSequenceHardwareGateError(
                f"native diagnostic UI is missing marker: {marker}"
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
        raise SaturnSblNativeSequenceHardwareGateError("candidate build policy is missing")
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
        raise SaturnSblNativeSequenceHardwareGateError("successful build has no deployable record")
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
        raise SaturnSblNativeSequenceHardwareGateError(
            f"read-only SAROO deployment plan rejected native candidate: {exc}"
        ) from exc

    return SaturnSblNativeSequenceHardwareEvidence(
        project_root=root,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        melodic_bank_sha256=melodic_sha,
        drum_bank_sha256=drum_sha,
        sequence_bank_sha256=sequence_sha,
        area_map_sha256=area_sha,
        sound_driver_sha256=driver_sha,
        sega_sound_library_sha256=sega_snd_sha,
        deployable_bin_sha256=plan.bin_sha256,
        deployable_cue_sha256=plan.cue_sha256,
        plan=plan,
    )


def inspect_saturn_sbl_native_sequence_hardware_gate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
) -> SaturnSblNativeSequenceHardwareEvidence:
    """Perform the complete read-only native candidate/card pre-media review."""
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
        raise SaturnSblNativeSequenceHardwareGateError(
            "planned destination is outside the mounted SAROO card"
        ) from exc
    return (
        destination,
        f"{destination}/{plan.source_bin.name}",
        f"{destination}/{plan.source_cue.name}",
    )


def run_saturn_sbl_native_sequence_hardware_gate(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    category: str | None = "TEST",
    apply: bool = False,
    confirmation: str = "",
) -> SaturnSblNativeSequenceHardwareResult:
    """Revalidate GATE3D and optionally deploy through a whole-card guard."""

    if apply and confirmation != CONFIRMATION_TOKEN:
        raise SaturnSblNativeSequenceHardwareGateError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    card = _canonical(card_root)
    guard_path = _canonical(guard_manifest)
    if _inside(guard_path, card):
        raise SaturnSblNativeSequenceHardwareGateError(
            "whole-card guard manifest must be stored outside the SAROO card"
        )

    evidence = _validate_candidate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    if not apply:
        return SaturnSblNativeSequenceHardwareResult(evidence, None, None, None)

    try:
        guard = create_saroo_card_inventory(card, guard_path)
        pre_verify = verify_saroo_card_inventory(card, guard.manifest_path)
    except Exception as exc:
        raise SaturnSblNativeSequenceHardwareGateError(
            f"cannot establish fresh whole-card SAROO baseline: {exc}"
        ) from exc
    if not pre_verify.valid:
        detail = "; ".join(pre_verify.differences[:8])
        raise SaturnSblNativeSequenceHardwareGateError(
            "fresh whole-card SAROO baseline did not immediately verify: " + detail
        )

    before_write = _validate_candidate(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    _expect(before_write.manifest_sha256, evidence.manifest_sha256, "manifest changed before write")
    _expect(before_write.report_sha256, evidence.report_sha256, "report changed before write")
    _expect(before_write.sequence_bank_sha256, evidence.sequence_bank_sha256, "sequence changed before write")
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
        raise SaturnSblNativeSequenceHardwareGateError(
            f"native sequence deployment failed; {detail}: {exc}"
        ) from exc

    _expect(deployment.bin_sha256, evidence.deployable_bin_sha256, "deployed BIN SHA-256")
    _expect(deployment.cue_sha256, evidence.deployable_cue_sha256, "deployed CUE SHA-256")

    try:
        verification = verify_saroo_card_inventory(
            card,
            guard.manifest_path,
            allowed_changed_paths=_allowed_paths(deployment.plan),
        )
    except Exception as exc:
        raise SaturnSblNativeSequenceHardwareGateError(
            "native candidate was written but whole-card verification could not run; "
            "do not retry, delete or alter the card until reviewed: " + str(exc)
        ) from exc
    if not verification.valid:
        detail = "; ".join(verification.differences[:8])
        raise SaturnSblNativeSequenceHardwareGateError(
            "native candidate was written but whole-card guard found an unauthorized difference; "
            "do not retry, delete or alter the card until reviewed: " + detail
        )

    return SaturnSblNativeSequenceHardwareResult(evidence, guard, deployment, verification)
