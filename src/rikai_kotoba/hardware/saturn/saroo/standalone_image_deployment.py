"""Guarded deployment of a verified standalone Saturn CUE/BIN image to SAROO.

This workflow is intentionally narrow.  It accepts only a successful SRK
standalone build report whose deployable artifact is the verified single-track
MODE1/2352 CUE/BIN pair, validates the mounted card as a modern SAROO layout,
and writes one new game directory below ``SAROO/ISO``.  Existing card content is
never overwritten or removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil

from rikai_kotoba.formats.saturn.mode1_image import (
    SaturnMode1ImageError,
    verify_mode1_bin_against_iso,
)
from .sd_layout import SAROO_SD_LAYOUT_MODERN, inspect_saroo_sd_layout


CONFIRMATION_TOKEN = "DEPLOY-SATURN-IMAGE"
DEFAULT_DESTINATION_NAME = "SRK-Diagnostics"
_BUILD_REPORT = "SRK_STANDALONE_BUILD.json"
_FORBIDDEN_LEAF_CHARS = set('<>:"/\\|?*')


class SarooStandaloneImageDeploymentError(RuntimeError):
    """Raised when a standalone image cannot be deployed safely."""


@dataclass(frozen=True)
class SarooStandaloneImageDeploymentPlan:
    card_root: Path
    project_root: Path
    iso_directory: Path
    destination_directory: Path
    source_bin: Path
    source_cue: Path
    source_iso: Path
    bin_size: int
    cue_size: int
    bin_sha256: str
    cue_sha256: str
    sector_count: int
    raw_bytes: int


@dataclass(frozen=True)
class SarooStandaloneImageDeploymentResult:
    plan: SarooStandaloneImageDeploymentPlan
    destination_bin: Path
    destination_cue: Path
    bin_sha256: str
    cue_sha256: str


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_leaf(name: str) -> str:
    if not isinstance(name, str):
        raise SarooStandaloneImageDeploymentError("destination name must be text")
    if not name or name in (".", "..") or name != name.strip():
        raise SarooStandaloneImageDeploymentError("destination name is not a safe leaf name")
    if len(name) > 100 or any(ch in _FORBIDDEN_LEAF_CHARS for ch in name):
        raise SarooStandaloneImageDeploymentError("destination name contains unsafe characters")
    if name.endswith(".") or name.endswith(" "):
        raise SarooStandaloneImageDeploymentError("destination name has an unsafe suffix")
    return name


def _casefold_child(parent: Path, name: str) -> Path | None:
    direct = parent / name
    if direct.exists():
        return direct
    wanted = name.casefold()
    matches = [child for child in parent.iterdir() if child.name.casefold() == wanted]
    if len(matches) > 1:
        raise SarooStandaloneImageDeploymentError(
            f"ambiguous case-insensitive entries named {name!r} beneath {parent}"
        )
    return matches[0] if matches else None


def _load_build_report(project_root: Path) -> dict:
    report_path = project_root / _BUILD_REPORT
    if not report_path.is_file():
        raise SarooStandaloneImageDeploymentError(
            f"standalone build report is missing: {report_path}"
        )
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SarooStandaloneImageDeploymentError(f"cannot read build report: {exc}") from exc
    if report.get("schema") != "srk.saturn.standalone-build.v1":
        raise SarooStandaloneImageDeploymentError("unsupported standalone build report schema")
    if report.get("successful") is not True:
        raise SarooStandaloneImageDeploymentError("standalone build report is not successful")
    deployable = report.get("deployable")
    if not isinstance(deployable, dict):
        raise SarooStandaloneImageDeploymentError("build report has no deployable image record")
    if deployable.get("format") != "cue-bin-mode1-2352":
        raise SarooStandaloneImageDeploymentError("deployable image is not MODE1/2352 CUE/BIN")
    if deployable.get("verified_against_iso") is not True:
        raise SarooStandaloneImageDeploymentError("deployable image was not verified against ISO")
    return report


def _project_file(project_root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise SarooStandaloneImageDeploymentError(f"build report has no {label} path")
    path = (project_root / relative).resolve(strict=False)
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise SarooStandaloneImageDeploymentError(
            f"build report {label} path escapes the project root: {relative}"
        ) from exc
    if not path.is_file():
        raise SarooStandaloneImageDeploymentError(f"{label} file is missing: {path}")
    return path


def _artifact_record(report: dict, relative: str) -> dict:
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SarooStandaloneImageDeploymentError("build report has no artifact inventory")
    matches = [entry for entry in artifacts if isinstance(entry, dict) and entry.get("path") == relative]
    if len(matches) != 1:
        raise SarooStandaloneImageDeploymentError(
            f"build report artifact inventory does not uniquely contain {relative}"
        )
    return matches[0]


def _verify_reported_artifact(path: Path, record: dict, label: str) -> tuple[int, str]:
    expected_size = record.get("size")
    expected_sha = record.get("sha256")
    if not isinstance(expected_size, int) or not isinstance(expected_sha, str):
        raise SarooStandaloneImageDeploymentError(f"invalid {label} artifact metadata")
    actual_size = path.stat().st_size
    actual_sha = _sha256_file(path)
    if actual_size != expected_size or actual_sha.lower() != expected_sha.lower():
        raise SarooStandaloneImageDeploymentError(
            f"{label} no longer matches the accepted build report"
        )
    return actual_size, actual_sha


def plan_saroo_standalone_image_deployment(
    card_root: os.PathLike[str] | str,
    project_directory: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
) -> SarooStandaloneImageDeploymentPlan:
    """Return a read-only deployment plan after re-validating all evidence."""

    card = _canonical(card_root)
    project = _canonical(project_directory)
    if not project.is_dir():
        raise SarooStandaloneImageDeploymentError(f"project directory is not a directory: {project}")

    destination_name = _safe_leaf(destination_name)
    report = _load_build_report(project)
    deployable = report["deployable"]

    bin_relative = deployable.get("bin")
    cue_relative = deployable.get("cue")
    source_bin = _project_file(project, bin_relative, "deployable BIN")
    source_cue = _project_file(project, cue_relative, "deployable CUE")
    source_iso = _project_file(project, "build/srk_diag.iso", "intermediate ISO")

    bin_record = _artifact_record(report, str(bin_relative))
    cue_record = _artifact_record(report, str(cue_relative))
    bin_size, bin_sha = _verify_reported_artifact(source_bin, bin_record, "deployable BIN")
    cue_size, cue_sha = _verify_reported_artifact(source_cue, cue_record, "deployable CUE")

    expected_cue = (
        f'FILE "{source_bin.name}" BINARY\r\n'
        "  TRACK 01 MODE1/2352\r\n"
        "    INDEX 01 00:00:00\r\n"
    ).encode("ascii")
    if source_cue.read_bytes() != expected_cue:
        raise SarooStandaloneImageDeploymentError("deployable CUE does not match the single-track contract")

    try:
        verified_sectors = verify_mode1_bin_against_iso(source_iso, source_bin)
    except (OSError, SaturnMode1ImageError) as exc:
        raise SarooStandaloneImageDeploymentError(
            f"deployable BIN failed fresh Mode 1 verification: {exc}"
        ) from exc

    sector_count = deployable.get("sector_count")
    raw_bytes = deployable.get("raw_bytes")
    if verified_sectors != sector_count or bin_size != raw_bytes:
        raise SarooStandaloneImageDeploymentError(
            "deployable BIN geometry no longer matches the accepted build report"
        )

    layout = inspect_saroo_sd_layout(card)
    if layout.layout != SAROO_SD_LAYOUT_MODERN:
        raise SarooStandaloneImageDeploymentError(
            f"card is not an unambiguous modern SAROO layout: {layout.layout}"
        )
    if not layout.iso_directory_present:
        raise SarooStandaloneImageDeploymentError("modern SAROO/ISO directory is missing")

    saroo_dir = _casefold_child(card, "SAROO")
    if saroo_dir is None or not saroo_dir.is_dir():
        raise SarooStandaloneImageDeploymentError("SAROO directory disappeared during inspection")
    iso_dir = _casefold_child(saroo_dir, "ISO")
    if iso_dir is None or not iso_dir.is_dir():
        raise SarooStandaloneImageDeploymentError("SAROO/ISO directory disappeared during inspection")

    existing = _casefold_child(iso_dir, destination_name)
    if existing is not None:
        raise SarooStandaloneImageDeploymentError(
            f"destination already exists; refusing to merge or overwrite: {existing}"
        )
    pending = _casefold_child(iso_dir, f".{destination_name}.srk-pending")
    if pending is not None:
        raise SarooStandaloneImageDeploymentError(
            f"pending deployment path already exists; inspect it manually: {pending}"
        )

    return SarooStandaloneImageDeploymentPlan(
        card_root=card,
        project_root=project,
        iso_directory=iso_dir,
        destination_directory=iso_dir / destination_name,
        source_bin=source_bin,
        source_cue=source_cue,
        source_iso=source_iso,
        bin_size=bin_size,
        cue_size=cue_size,
        bin_sha256=bin_sha,
        cue_sha256=cue_sha,
        sector_count=int(sector_count),
        raw_bytes=int(raw_bytes),
    )


def apply_saroo_standalone_image_deployment(
    card_root: os.PathLike[str] | str,
    project_directory: os.PathLike[str] | str,
    *,
    destination_name: str = DEFAULT_DESTINATION_NAME,
    confirmation: str,
) -> SarooStandaloneImageDeploymentResult:
    """Copy one verified CUE/BIN pair into a new SAROO/ISO game directory."""

    if confirmation != CONFIRMATION_TOKEN:
        raise SarooStandaloneImageDeploymentError(
            f"confirmation token must be exactly {CONFIRMATION_TOKEN}"
        )

    plan = plan_saroo_standalone_image_deployment(
        card_root,
        project_directory,
        destination_name=destination_name,
    )
    pending = plan.iso_directory / f".{plan.destination_directory.name}.srk-pending"
    if pending.exists():
        raise SarooStandaloneImageDeploymentError(f"pending deployment path already exists: {pending}")

    pending.mkdir()
    destination_bin = pending / plan.source_bin.name
    destination_cue = pending / plan.source_cue.name
    try:
        shutil.copyfile(plan.source_bin, destination_bin)
        shutil.copyfile(plan.source_cue, destination_cue)

        copied_bin_sha = _sha256_file(destination_bin)
        copied_cue_sha = _sha256_file(destination_cue)
        if destination_bin.stat().st_size != plan.bin_size or copied_bin_sha != plan.bin_sha256:
            raise SarooStandaloneImageDeploymentError("copied BIN failed size/SHA-256 verification")
        if destination_cue.stat().st_size != plan.cue_size or copied_cue_sha != plan.cue_sha256:
            raise SarooStandaloneImageDeploymentError("copied CUE failed size/SHA-256 verification")

        pending.rename(plan.destination_directory)
    except Exception:
        if pending.exists():
            shutil.rmtree(pending, ignore_errors=True)
        raise

    final_bin = plan.destination_directory / plan.source_bin.name
    final_cue = plan.destination_directory / plan.source_cue.name
    final_bin_sha = _sha256_file(final_bin)
    final_cue_sha = _sha256_file(final_cue)
    if final_bin_sha != plan.bin_sha256 or final_cue_sha != plan.cue_sha256:
        raise SarooStandaloneImageDeploymentError(
            "final SAROO image hashes do not match the accepted source artifacts"
        )

    return SarooStandaloneImageDeploymentResult(
        plan=plan,
        destination_bin=final_bin,
        destination_cue=final_cue,
        bin_sha256=final_bin_sha,
        cue_sha256=final_cue_sha,
    )
