"""Explicit reviewed whole-card APPLY for the accepted R25 RR16 calibration candidate."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SarooCardInventoryVerification,
    verify_saroo_card_inventory,
)
from rikai_kotoba.hardware.saturn.saroo.standalone_image_deployment import (
    CONFIRMATION_TOKEN as STANDALONE_CONFIRMATION_TOKEN,
    SarooStandaloneImageDeploymentResult,
    apply_saroo_standalone_image_deployment,
)
from . import midi_68k_r25_rr_calibration_guard_prepare as _prepare
from . import midi_68k_r25_rr_calibration_pre_media_gate as _pre
from .midi_68k_r25_rr_calibration_pre_media_gate import (
    SaturnMidi68KR25RRCalibrationPreMediaResult,
    inspect_saturn_midi_68k_r25_rr_calibration_pre_media,
)

CONFIRMATION_TOKEN = "DEPLOY-R25-RR16-CALIBRATION"
ACCEPTED_GUARD_MANIFEST_SHA256 = "5c17df50023c47955b4814eea648a506b3c30dafaa50ebfa157de65cffb9eac6"
ACCEPTED_PREPARE_RECEIPT_SHA256 = "c78b7702f0ed27af0a0f0d42baa4d5754b102adfd1bb148055fb7be960980f6f"
ACCEPTED_CARD_FILE_COUNT = 1616
ACCEPTED_CARD_DIRECTORY_COUNT = 149
ACCEPTED_CARD_TOTAL_FILE_BYTES = 60693834694
ACCEPTED_CARD_HASHED_FILE_COUNT = 192


class SaturnMidi68KR25RRCalibrationGuardedApplyError(RuntimeError):
    """Raised when the reviewed R25 RR16 media boundary cannot be crossed safely."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationGuardedApplyResult:
    pre_media: SaturnMidi68KR25RRCalibrationPreMediaResult
    guard_manifest_path: Path
    guard_manifest_sha256: str
    prepare_receipt_path: Path
    prepare_receipt_sha256: str
    pre_guard: SarooCardInventoryVerification
    deployment: SarooStandaloneImageDeploymentResult
    post_guard: SarooCardInventoryVerification
    allowed_changed_paths: tuple[str, ...]


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _canonical_text(value: os.PathLike[str] | str) -> str:
    return str(_canonical(value)).casefold()


def _payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_bound_document(path: Path, field: str, expected: str, label: str) -> dict[str, object]:
    if not path.is_file():
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(f"{label} is not a file: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(document, dict):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(f"{label} root must be an object")
    if document.get(field) != expected:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            f"{label} does not match the physically reviewed R25 PREPARE digest"
        )
    payload = dict(document)
    payload.pop(field, None)
    if sha256(_payload_bytes(payload)).hexdigest() != expected:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            f"{label} canonical content digest verification failed"
        )
    return document


def _expect(mapping: dict, key: str, expected: object, label: str) -> None:
    if mapping.get(key) != expected:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            f"reviewed preparation receipt mismatch: {label}"
        )


def _require_guard_valid(value: SarooCardInventoryVerification, label: str) -> None:
    if value.valid:
        return
    detail = "; ".join(value.differences[:8])
    raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _review_prepare_evidence(
    card: Path,
    project: Path,
    guard_path: Path,
    receipt_path: Path,
    *,
    destination_name: str,
    category: str | None,
) -> dict[str, object]:
    if guard_path == receipt_path:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            "guard manifest and preparation receipt must be different files"
        )
    for path, label in ((guard_path, "whole-card guard manifest"), (receipt_path, "preparation receipt")):
        if _inside(path, card):
            raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
                f"{label} must remain outside the mounted SAROO card"
            )
    guard = _load_bound_document(
        guard_path, "manifest_sha256", ACCEPTED_GUARD_MANIFEST_SHA256, "whole-card guard manifest"
    )
    receipt = _load_bound_document(
        receipt_path, "receipt_sha256", ACCEPTED_PREPARE_RECEIPT_SHA256, "preparation receipt"
    )
    if guard.get("schema") != "srk.saroo.card-inventory" or guard.get("schema_version") != 1:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("unexpected whole-card guard schema")
    for key, expected in {
        "file_count": ACCEPTED_CARD_FILE_COUNT,
        "directory_count": ACCEPTED_CARD_DIRECTORY_COUNT,
        "total_file_bytes": ACCEPTED_CARD_TOTAL_FILE_BYTES,
        "hashed_file_count": ACCEPTED_CARD_HASHED_FILE_COUNT,
    }.items():
        _expect(guard, key, expected, f"guard {key}")
    if receipt.get("schema") != _prepare.PREPARE_RECEIPT_SCHEMA:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("unexpected R25 preparation receipt schema")
    candidate = receipt.get("candidate")
    card_guard = receipt.get("card_guard")
    future = receipt.get("future_deployment")
    policy = receipt.get("policy")
    if not all(isinstance(v, dict) for v in (candidate, card_guard, future, policy)):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("preparation receipt is incomplete")
    assert isinstance(candidate, dict) and isinstance(card_guard, dict)
    assert isinstance(future, dict) and isinstance(policy, dict)
    exact_candidate = {
        "manifest_sha256": _pre.ACCEPTED_R25_MANIFEST_SHA256,
        "report_sha256": _pre.ACCEPTED_R25_REPORT_SHA256,
        "calibration_image_sha256": _pre.ACCEPTED_R25_IMAGE_SHA256,
        "candidate_main_sha256": _pre.ACCEPTED_R25_MAIN_SHA256,
        "candidate_menu_sha256": _pre.ACCEPTED_R25_MENU_SHA256,
        "runtime_after_sha256": _pre.ACCEPTED_R25_RUNTIME_SHA256,
        "proof_header_sha256": _pre.ACCEPTED_R25_PROOF_HEADER_SHA256,
        "proof_source_sha256": _pre.ACCEPTED_R25_PROOF_SOURCE_SHA256,
        "deployable_bin_sha256": _pre.ACCEPTED_R25_BIN_SHA256,
        "deployable_cue_sha256": _pre.ACCEPTED_R25_CUE_SHA256,
        "mode1_sector_count": _pre.ACCEPTED_R25_SECTOR_COUNT,
        "raw_track_bytes": _pre.ACCEPTED_R25_RAW_BYTES,
        "release_rate_probe": 16,
        "eg1_word": 0x001F,
        "eg2_word": 0x3C10,
        "production_rr_selected": False,
        "measurement_mode": "operator-observed-audio",
        "scsp_envelope_readback": False,
    }
    for key, expected in exact_candidate.items():
        _expect(candidate, key, expected, f"candidate {key}")
    if _canonical_text(candidate.get("project_root", "")) != _canonical_text(project):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("receipt is bound to a different R25 project")
    if _canonical_text(card_guard.get("card_root_at_prepare", "")) != _canonical_text(card):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("receipt is bound to a different card root")
    if _canonical_text(card_guard.get("manifest_path", "")) != _canonical_text(guard_path):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("receipt is bound to a different guard path")
    for key, expected in {
        "manifest_sha256": ACCEPTED_GUARD_MANIFEST_SHA256,
        "file_count": ACCEPTED_CARD_FILE_COUNT,
        "directory_count": ACCEPTED_CARD_DIRECTORY_COUNT,
        "total_file_bytes": ACCEPTED_CARD_TOTAL_FILE_BYTES,
        "hashed_file_count": ACCEPTED_CARD_HASHED_FILE_COUNT,
        "exact_verification": True,
    }.items():
        _expect(card_guard, key, expected, f"card guard {key}")
    _expect(future, "category", category, "future category")
    _expect(future, "destination_name", destination_name, "future destination name")
    _expect(future, "destination_fresh_at_prepare", True, "future freshness")
    for key, expected in {
        "prepare_only": True,
        "apply_available_in_this_module": False,
        "saroo_writes": False,
        "existing_card_content_modified": False,
        "guard_manifest_off_card": True,
        "receipt_off_card": True,
        "production_rr_selected": False,
    }.items():
        _expect(policy, key, expected, f"policy {key}")
    return receipt


def _bind_receipt(receipt: dict[str, object], pre_media: SaturnMidi68KR25RRCalibrationPreMediaResult) -> None:
    _prepare._require_pre_media_anchor(pre_media)
    candidate = receipt["candidate"]
    future = receipt["future_deployment"]
    assert isinstance(candidate, dict) and isinstance(future, dict)
    if _canonical_text(candidate.get("accepted_r24_baseline", "")) != _canonical_text(pre_media.baseline_root):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("receipt R24 baseline changed since PREPARE")
    if _canonical_text(future.get("destination_path", "")) != _canonical_text(pre_media.plan.destination_directory):
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError("destination no longer matches PREPARE")


def _saroo_guard_key(path: Path) -> str:
    parts = path.parts
    hits = [i for i in range(len(parts) - 1) if parts[i].casefold() == "saroo" and parts[i + 1].casefold() == "iso"]
    if len(hits) != 1:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(f"ambiguous SAROO/ISO path: {path}")
    return Path(*parts[hits[0]:]).as_posix()


def _allowed_paths(deployment: SarooStandaloneImageDeploymentResult) -> tuple[str, ...]:
    return tuple(
        _saroo_guard_key(path)
        for path in (
            deployment.plan.destination_directory,
            deployment.destination_bin,
            deployment.destination_cue,
        )
    )


def _safe_rollback_new_directory(card: Path, deployment: SarooStandaloneImageDeploymentResult, guard_path: Path) -> str:
    destination = deployment.plan.destination_directory
    if not destination.is_dir():
        return "automatic rollback not attempted: deployed destination is missing"
    try:
        children = sorted(destination.iterdir(), key=lambda p: p.name.casefold())
    except OSError as exc:
        return f"automatic rollback not attempted: cannot inspect destination: {exc}"
    expected = {
        deployment.destination_bin.name.casefold(): _pre.ACCEPTED_R25_BIN_SHA256,
        deployment.destination_cue.name.casefold(): _pre.ACCEPTED_R25_CUE_SHA256,
    }
    if len(children) != 2:
        return "automatic rollback not attempted: destination contains unexpected entries"
    for child in children:
        if child.is_symlink() or not child.is_file() or child.name.casefold() not in expected:
            return "automatic rollback not attempted: destination contains an unexpected entry"
        if _sha256_file(child) != expected[child.name.casefold()]:
            return "automatic rollback not attempted: destination file hash changed"
    try:
        for child in children:
            child.unlink()
        destination.rmdir()
    except OSError as exc:
        return f"automatic rollback failed: {exc}"
    verification = verify_saroo_card_inventory(card, guard_path)
    if not verification.valid:
        return "rollback removed R25 but original whole-card baseline still mismatches: " + "; ".join(verification.differences[:8])
    return "verified rollback succeeded; original whole-card baseline restored"


def apply_saturn_midi_68k_r25_rr16_calibration_guarded_deployment(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    prepare_receipt: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
    confirmation: str,
) -> SaturnMidi68KR25RRCalibrationGuardedApplyResult:
    if confirmation != CONFIRMATION_TOKEN:
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )
    card = _canonical(card_root)
    project = _canonical(project_directory)
    guard_path = _canonical(guard_manifest)
    receipt_path = _canonical(prepare_receipt)
    receipt = _review_prepare_evidence(
        card, project, guard_path, receipt_path,
        destination_name=destination_name, category=category,
    )
    pre_media = inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
        project, card, destination_name=destination_name, category=category
    )
    _bind_receipt(receipt, pre_media)
    pre_guard = verify_saroo_card_inventory(card, guard_path)
    _require_guard_valid(pre_guard, "pre-deployment")
    try:
        deployment = apply_saroo_standalone_image_deployment(
            card, project,
            destination_name=destination_name,
            category=category,
            confirmation=STANDALONE_CONFIRMATION_TOKEN,
        )
    except Exception as exc:
        state = verify_saroo_card_inventory(card, guard_path)
        summary = "original baseline still matches" if state.valid else "baseline mismatch: " + "; ".join(state.differences[:8])
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(f"R25 deployment failed; {summary}: {exc}") from exc
    if deployment.bin_sha256 != _pre.ACCEPTED_R25_BIN_SHA256 or deployment.cue_sha256 != _pre.ACCEPTED_R25_CUE_SHA256:
        rollback = _safe_rollback_new_directory(card, deployment, guard_path)
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            "deployed artifact hash mismatch; " + rollback
        )
    allowed = _allowed_paths(deployment)
    post_guard = verify_saroo_card_inventory(card, guard_path, allowed_changed_paths=allowed)
    if not post_guard.valid:
        detail = "; ".join(post_guard.differences[:8])
        rollback = _safe_rollback_new_directory(card, deployment, guard_path)
        raise SaturnMidi68KR25RRCalibrationGuardedApplyError(
            "R25 post-write whole-card guard found an unauthorized difference: " + detail + "; " + rollback
        )
    return SaturnMidi68KR25RRCalibrationGuardedApplyResult(
        pre_media=pre_media,
        guard_manifest_path=guard_path,
        guard_manifest_sha256=ACCEPTED_GUARD_MANIFEST_SHA256,
        prepare_receipt_path=receipt_path,
        prepare_receipt_sha256=ACCEPTED_PREPARE_RECEIPT_SHA256,
        pre_guard=pre_guard,
        deployment=deployment,
        post_guard=post_guard,
        allowed_changed_paths=allowed,
    )
