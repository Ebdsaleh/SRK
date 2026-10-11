"""Strict verification of the accepted Phase-B inert full-build tree."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os


class SaturnMidi68KResidentStateCandidateBaselineError(RuntimeError):
    """Raised when the Phase-B inert baseline no longer matches accepted evidence."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStateCandidateBaseline:
    root: Path
    manifest: dict
    generated_files: tuple[dict[str, object], ...]
    manifest_sha256: str
    report_sha256: str
    deploy_bin_sha256: str
    deploy_cue_sha256: str
    r20_main_sha256: str
    r20_menu_sha256: str


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_DEPLOY_BIN = "build/SRK-Diagnostics/SRK-Diagnostics.bin"
_DEPLOY_CUE = "build/SRK-Diagnostics/SRK-Diagnostics.cue"
_GATE_KEY = "midi_68k_resident_state_decoder_full_build_gate"
_GATE_SCHEMA = "srk.saturn.midi-68k-resident-state-decoder-full-build-gate.v1"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: str, label: str) -> str:
    normalized = str(value).strip().lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            f"{label} must be an exact 64-character SHA-256"
        )
    return normalized


def _load_json(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            f"cannot read {label}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            f"{label} root must be an object"
        )
    return value


def _verify_generated_files(root: Path, manifest: dict) -> tuple[dict[str, object], ...]:
    values = manifest.get("generated_files")
    if not isinstance(values, list) or not values:
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert manifest has no generated-file inventory"
        )
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                "Phase-B generated-file inventory contains an invalid entry"
            )
        relative = value.get("path")
        size = value.get("size")
        expected_sha = value.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative in seen
            or not isinstance(size, int)
            or size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                "Phase-B generated-file metadata is invalid or duplicated"
            )
        seen.add(relative)
        path = root / relative
        if not path.is_file():
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"Phase-B generated input is missing: {relative}"
            )
        if path.stat().st_size != size or _sha256_file(path).lower() != expected_sha.lower():
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"Phase-B generated input changed: {relative}"
            )
        result.append(value)
    return tuple(result)


def verify_resident_state_decoder_inert_baseline(
    project_directory: os.PathLike[str] | str,
    *,
    expected_bin_sha256: str,
    expected_cue_sha256: str,
    expected_image_sha256: str,
    expected_compiler_source_sha256: str,
    expected_compiler_header_sha256: str,
    expected_compiler_object_sha256: str,
    expected_runtime_after_sha256: str,
) -> SaturnMidi68KResidentStateCandidateBaseline:
    """Verify the complete Phase-B inert tree against accepted external evidence."""

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            f"Phase-B inert baseline is not a directory: {root}"
        )

    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    if not manifest_path.is_file() or not report_path.is_file():
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert baseline must contain its manifest and successful build report"
        )

    manifest_sha = _sha256_file(manifest_path)
    report_sha = _sha256_file(report_path)
    manifest = _load_json(manifest_path, "Phase-B inert manifest")
    report = _load_json(report_path, "Phase-B inert build report")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1" or manifest.get("mode") != "standalone-master":
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert baseline manifest identity is unsupported"
        )
    if report.get("schema") != "srk.saturn.standalone-build.v1" or report.get("successful") is not True:
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert build report is not successful"
        )
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B build report does not match its current manifest"
        )

    generated = _verify_generated_files(root, manifest)
    gate = manifest.get(_GATE_KEY)
    if not isinstance(gate, dict) or gate.get("schema") != _GATE_SCHEMA:
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "baseline is not the accepted Phase-B inert full-build gate"
        )

    required = {
        "existing_r20_candidate_binding_preserved": True,
        "dynamic_state_mutation": True,
        "state_decoder_linked": True,
        "state_decoder_installed": False,
        "state_decoder_executed": False,
        "state_decoder_candidate_bound": False,
        "midi_scsp_note_attempted": False,
        "build_time_hardware_io": False,
        "saroo_write": False,
        "off_card_only": True,
        "behaviorally_active": False,
        "runtime_record_minimum": 1,
        "runtime_record_maximum": 32,
    }
    for key, expected in required.items():
        if gate.get(key) != expected:
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"Phase-B inert gate state changed: {key}"
            )

    hash_requirements = (
        ("image_sha256", expected_image_sha256, "state decoder image"),
        ("source_sha256", expected_compiler_source_sha256, "compiler source"),
        ("header_sha256", expected_compiler_header_sha256, "compiler header"),
        (
            "accepted_compile_object_sha256_evidence",
            expected_compiler_object_sha256,
            "compiler object evidence",
        ),
        ("runtime_after_sha256", expected_runtime_after_sha256, "Phase-B runtime-after"),
    )
    for key, supplied, label in hash_requirements:
        expected = _require_sha256(supplied, f"expected {label} SHA-256")
        if str(gate.get(key, "")).lower() != expected:
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"Phase-B baseline {label} provenance mismatch"
            )

    artifacts = report.get("artifacts")
    if not isinstance(artifacts, list):
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B build report has no artifact inventory"
        )
    artifact_map = {
        str(value.get("path")): value
        for value in artifacts
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    }
    accepted_media: list[str] = []
    for relative, supplied, label in (
        (_DEPLOY_BIN, expected_bin_sha256, "Phase-B inert deployable BIN"),
        (_DEPLOY_CUE, expected_cue_sha256, "Phase-B inert deployable CUE"),
    ):
        expected = _require_sha256(supplied, f"expected {label} SHA-256")
        entry = artifact_map.get(relative)
        path = root / relative
        if not isinstance(entry, dict) or str(entry.get("sha256", "")).lower() != expected:
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"{label} report hash does not match accepted evidence"
            )
        if not path.is_file() or _sha256_file(path).lower() != expected:
            raise SaturnMidi68KResidentStateCandidateBaselineError(
                f"{label} file no longer matches accepted evidence"
            )
        accepted_media.append(expected)

    main_sha = _sha256_file(root / "src/srk_saturn_main.c")
    menu_sha = _sha256_file(root / "src/srk_diag_menu.c")
    if main_sha.lower() != str(gate.get("r20_main_sha256", "")).lower():
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert tree no longer preserves the accepted R20 main"
        )
    if menu_sha.lower() != str(gate.get("r20_menu_sha256", "")).lower():
        raise SaturnMidi68KResidentStateCandidateBaselineError(
            "Phase-B inert tree no longer preserves the accepted R20 menu"
        )

    return SaturnMidi68KResidentStateCandidateBaseline(
        root=root,
        manifest=manifest,
        generated_files=generated,
        manifest_sha256=manifest_sha,
        report_sha256=report_sha,
        deploy_bin_sha256=accepted_media[0],
        deploy_cue_sha256=accepted_media[1],
        r20_main_sha256=main_sha,
        r20_menu_sha256=menu_sha,
    )
