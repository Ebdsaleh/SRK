"""Read-only whole-card guard PREPARE for the accepted R25 RR16 calibration candidate.

This module deliberately stops before deployment.  It re-runs the independent
R25 pre-media gate, creates a fresh off-card inventory of the complete mounted
SAROO card, verifies that inventory exactly, re-runs pre-media after the
snapshot, verifies the card again, and publishes an off-card preparation receipt
that binds the reviewed card snapshot to the exact accepted R25 candidate and
future fresh destination.

There is no apply/copy/write-to-card operation in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os

from rikai_kotoba.hardware.saturn.saroo.card_guard import (
    SarooCardInventoryResult,
    SarooCardInventoryVerification,
    create_saroo_card_inventory,
    verify_saroo_card_inventory,
)
from . import midi_68k_r25_rr_calibration_pre_media_gate as _pre
from .midi_68k_r25_rr_calibration_pre_media_gate import (
    SaturnMidi68KR25RRCalibrationPreMediaResult,
    inspect_saturn_midi_68k_r25_rr_calibration_pre_media,
)


PREPARE_RECEIPT_SCHEMA = "srk.saturn.midi-68k-r25-rr16-guard-prepare-receipt.v1"


class SaturnMidi68KR25RRCalibrationGuardPrepareError(RuntimeError):
    """Raised when R25 cannot establish a read-only whole-card deployment guard."""


@dataclass(frozen=True)
class SaturnMidi68KR25RRCalibrationGuardPrepareResult:
    pre_media: SaturnMidi68KR25RRCalibrationPreMediaResult
    guard_inventory: SarooCardInventoryResult
    exact_verification: SarooCardInventoryVerification
    receipt_path: Path
    receipt_sha256: str


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_exact_guard(
    verification: SarooCardInventoryVerification,
    label: str,
) -> None:
    if verification.valid:
        return
    detail = "; ".join(verification.differences[:8])
    if len(verification.differences) > 8:
        detail += f"; ... {len(verification.differences) - 8} more"
    raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
        f"{label} whole-card guard mismatch: {detail}"
    )


def _require_pre_media_anchor(result: SaturnMidi68KR25RRCalibrationPreMediaResult) -> None:
    expected = {
        "manifest": _pre.ACCEPTED_R25_MANIFEST_SHA256,
        "report": _pre.ACCEPTED_R25_REPORT_SHA256,
        "image": _pre.ACCEPTED_R25_IMAGE_SHA256,
        "main": _pre.ACCEPTED_R25_MAIN_SHA256,
        "menu": _pre.ACCEPTED_R25_MENU_SHA256,
        "runtime": _pre.ACCEPTED_R25_RUNTIME_SHA256,
        "proof header": _pre.ACCEPTED_R25_PROOF_HEADER_SHA256,
        "proof source": _pre.ACCEPTED_R25_PROOF_SOURCE_SHA256,
        "BIN": _pre.ACCEPTED_R25_BIN_SHA256,
        "CUE": _pre.ACCEPTED_R25_CUE_SHA256,
    }
    actual = {
        "manifest": result.manifest_sha256,
        "report": result.report_sha256,
        "image": result.calibration_image_sha256,
        "main": result.candidate_main_sha256,
        "menu": result.candidate_menu_sha256,
        "runtime": result.runtime_after_sha256,
        "proof header": result.proof_header_sha256,
        "proof source": result.proof_source_sha256,
        "BIN": result.deployable_bin_sha256,
        "CUE": result.deployable_cue_sha256,
    }
    for label, accepted in expected.items():
        if str(actual[label]).lower() != accepted:
            raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
                f"accepted R25 {label} changed between pre-media and guard preparation"
            )
    if result.sector_count != _pre.ACCEPTED_R25_SECTOR_COUNT:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "accepted R25 MODE1 sector count changed during guard preparation"
        )
    if result.raw_bytes != _pre.ACCEPTED_R25_RAW_BYTES:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "accepted R25 raw track size changed during guard preparation"
        )


def _receipt_payload(
    *,
    pre_media: SaturnMidi68KR25RRCalibrationPreMediaResult,
    inventory: SarooCardInventoryResult,
    category: str | None,
    destination_name: str,
) -> dict[str, object]:
    return {
        "schema": PREPARE_RECEIPT_SCHEMA,
        "candidate": {
            "project_root": str(pre_media.project_root),
            "accepted_r24_baseline": str(pre_media.baseline_root),
            "manifest_sha256": pre_media.manifest_sha256,
            "report_sha256": pre_media.report_sha256,
            "calibration_image_sha256": pre_media.calibration_image_sha256,
            "candidate_main_sha256": pre_media.candidate_main_sha256,
            "candidate_menu_sha256": pre_media.candidate_menu_sha256,
            "runtime_after_sha256": pre_media.runtime_after_sha256,
            "proof_header_sha256": pre_media.proof_header_sha256,
            "proof_source_sha256": pre_media.proof_source_sha256,
            "deployable_bin_sha256": pre_media.deployable_bin_sha256,
            "deployable_cue_sha256": pre_media.deployable_cue_sha256,
            "mode1_sector_count": pre_media.sector_count,
            "raw_track_bytes": pre_media.raw_bytes,
            "release_rate_probe": 16,
            "eg1_word": 0x001F,
            "eg2_word": 0x3C10,
            "production_rr_selected": False,
            "measurement_mode": "operator-observed-audio",
            "scsp_envelope_readback": False,
        },
        "card_guard": {
            "card_root_at_prepare": str(inventory.card_root),
            "manifest_path": str(inventory.manifest_path),
            "manifest_sha256": inventory.manifest_sha256,
            "file_count": inventory.file_count,
            "directory_count": inventory.directory_count,
            "total_file_bytes": inventory.total_file_bytes,
            "hashed_file_count": inventory.hashed_file_count,
            "exact_verification": True,
        },
        "future_deployment": {
            "category": category,
            "destination_name": destination_name,
            "destination_path": str(pre_media.plan.destination_directory),
            "destination_fresh_at_prepare": True,
        },
        "policy": {
            "prepare_only": True,
            "apply_available_in_this_module": False,
            "saroo_writes": False,
            "existing_card_content_modified": False,
            "guard_manifest_off_card": True,
            "receipt_off_card": True,
            "production_rr_selected": False,
        },
    }


def _publish_receipt(path: Path, payload: dict[str, object]) -> str:
    if path.exists():
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"preparation receipt already exists: {path}"
        )
    digest = sha256(_payload_bytes(payload)).hexdigest()
    document = dict(payload)
    document["receipt_sha256"] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".srk-partial")
    if temporary.exists():
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"stale preparation receipt temporary file exists: {temporary}"
        )
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.rename(path)
    except OSError as exc:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"cannot publish off-card preparation receipt: {exc}"
        ) from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"cannot re-open preparation receipt: {exc}"
        ) from exc
    if not isinstance(loaded, dict) or loaded.get("receipt_sha256") != digest:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "published preparation receipt did not preserve its SHA-256"
        )
    verify_payload = dict(loaded)
    verify_payload.pop("receipt_sha256", None)
    if sha256(_payload_bytes(verify_payload)).hexdigest() != digest:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "published preparation receipt content hash verification failed"
        )
    return digest


def prepare_saturn_midi_68k_r25_rr16_calibration_guard(
    project_directory: os.PathLike[str] | str,
    card_root: os.PathLike[str] | str,
    guard_manifest: os.PathLike[str] | str,
    receipt_path: os.PathLike[str] | str,
    *,
    destination_name: str,
    category: str | None = None,
) -> SaturnMidi68KR25RRCalibrationGuardPrepareResult:
    """Create and verify an off-card whole-card baseline with zero SAROO writes."""

    card = _canonical(card_root)
    manifest = _canonical(guard_manifest)
    receipt = _canonical(receipt_path)
    if manifest == receipt:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "guard manifest and preparation receipt must be different off-card files"
        )
    for path, label in ((manifest, "whole-card guard manifest"), (receipt, "preparation receipt")):
        if _inside(path, card):
            raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
                f"{label} must be stored outside the mounted SAROO card"
            )
        if path.exists():
            raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
                f"{label} already exists: {path}"
            )

    first = inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    _require_pre_media_anchor(first)

    try:
        inventory = create_saroo_card_inventory(card, manifest)
        verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"cannot establish fresh R25 whole-card deployment baseline: {exc}"
        ) from exc
    _require_exact_guard(verification, "initial prepare")

    second = inspect_saturn_midi_68k_r25_rr_calibration_pre_media(
        project_directory,
        card,
        destination_name=destination_name,
        category=category,
    )
    _require_pre_media_anchor(second)
    if first != second:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            "R25 pre-media evidence changed while the whole-card snapshot was being prepared"
        )

    try:
        final_verification = verify_saroo_card_inventory(card, manifest)
    except Exception as exc:
        raise SaturnMidi68KR25RRCalibrationGuardPrepareError(
            f"cannot re-verify R25 whole-card baseline after pre-media review: {exc}"
        ) from exc
    _require_exact_guard(final_verification, "final prepare")

    payload = _receipt_payload(
        pre_media=second,
        inventory=inventory,
        category=category,
        destination_name=destination_name,
    )
    receipt_sha = _publish_receipt(receipt, payload)
    return SaturnMidi68KR25RRCalibrationGuardPrepareResult(
        pre_media=second,
        guard_inventory=inventory,
        exact_verification=final_verification,
        receipt_path=receipt,
        receipt_sha256=receipt_sha,
    )
