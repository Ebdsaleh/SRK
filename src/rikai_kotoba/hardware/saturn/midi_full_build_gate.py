"""Fresh off-card full-build gate for SRK's inert Saturn MIDI bridge.

This gate deliberately derives from one already-built, already-accepted
standalone project instead of mutating it.  It copies only the baseline
project's manifest-pinned generated inputs into a fresh directory, injects the
SRK-owned inert MIDI bridge into the existing runtime translation unit, updates
all generated-input hashes, and then hands the fresh tree to the normal
Python-native standalone builder.

The MIDI bridge remains behaviorally inert: no new control path, Sound RAM
write, SCSP MMIO, or MC68EC000 program is enabled by this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidiFullBuildGateError(RuntimeError):
    """Raised when the inert MIDI full-build gate cannot be prepared safely."""


@dataclass(frozen=True)
class SaturnMidiFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    bridge_source_sha256: str
    bridge_header_sha256: str


@dataclass(frozen=True)
class SaturnMidiFullBuildGateResult:
    prepared: SaturnMidiFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_BUILD_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_BRIDGE_SOURCE_NAME = "srk_saturn_midi_generated.c"
_BRIDGE_HEADER_NAME = "srk_saturn_midi_generated.h"
_INJECTION_MARKER = "/* SRK MIDI INERT FULL-BUILD GATE: generated bridge follows. */"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise SaturnMidiFullBuildGateError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidiFullBuildGateError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise SaturnMidiFullBuildGateError(f"{label} root must be an object")
    return value


def _repo_bridge_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        directory = parent / "integrations" / "saturn" / "standalone"
        source = directory / _BRIDGE_SOURCE_NAME
        header = directory / _BRIDGE_HEADER_NAME
        if source.is_file() and header.is_file():
            return source, header
    raise SaturnMidiFullBuildGateError(
        "cannot locate SRK generated Saturn MIDI bridge source/header"
    )


def _safe_manifest_relative(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative:
        raise SaturnMidiFullBuildGateError(
            f"generated-file path must use a non-empty POSIX relative path: {relative!r}"
        )
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SaturnMidiFullBuildGateError(
            f"generated-file path escapes project root: {relative!r}"
        )
    resolved = (root / candidate).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SaturnMidiFullBuildGateError(
            f"generated-file path escapes project root: {relative!r}"
        ) from exc
    return resolved


def _validate_baseline(baseline_root: Path) -> tuple[dict, str]:
    manifest_path = baseline_root / _MANIFEST_NAME
    manifest = _read_json(manifest_path, "baseline project manifest")
    if manifest.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnMidiFullBuildGateError("unsupported baseline project manifest schema")
    if manifest.get("mode") != "standalone-master":
        raise SaturnMidiFullBuildGateError("baseline project is not standalone-master mode")

    manifest_sha = _sha256_file(manifest_path)
    report = _read_json(
        baseline_root / _BUILD_REPORT_NAME,
        "baseline standalone build report",
    )
    if report.get("schema") != "srk.saturn.standalone-build.v1":
        raise SaturnMidiFullBuildGateError("unsupported baseline build-report schema")
    if report.get("successful") is not True:
        raise SaturnMidiFullBuildGateError("baseline standalone build was not successful")
    if str(report.get("project_manifest_sha256", "")).lower() != manifest_sha.lower():
        raise SaturnMidiFullBuildGateError(
            "baseline build report does not match the baseline project manifest"
        )

    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnMidiFullBuildGateError("baseline manifest has no generated-file inventory")
    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnMidiFullBuildGateError("invalid baseline generated-file entry")
        relative = entry.get("path")
        expected_size = entry.get("size")
        expected_sha = entry.get("sha256")
        if not isinstance(relative, str):
            raise SaturnMidiFullBuildGateError("baseline generated-file path is invalid")
        source = _safe_manifest_relative(baseline_root, relative)
        if not source.is_file():
            raise SaturnMidiFullBuildGateError(
                f"baseline generated input is missing: {relative}"
            )
        if not isinstance(expected_size, int) or source.stat().st_size != expected_size:
            raise SaturnMidiFullBuildGateError(
                f"baseline generated input size mismatch: {relative}"
            )
        if not isinstance(expected_sha, str) or _sha256_file(source).lower() != expected_sha.lower():
            raise SaturnMidiFullBuildGateError(
                f"baseline generated input hash mismatch: {relative}"
            )
    return manifest, manifest_sha


def _inventory_generated_files(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.name == _MANIFEST_NAME:
            continue
        relative = path.relative_to(root).as_posix()
        entries.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def prepare_inert_midi_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidiFullBuildGatePrepared:
    """Derive one fresh, manifest-pinned inert MIDI gate tree from a built baseline."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if not baseline_root.is_dir():
        raise SaturnMidiFullBuildGateError(
            f"baseline project is not a directory: {baseline_root}"
        )
    if output_root.exists():
        raise SaturnMidiFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    manifest, baseline_manifest_sha = _validate_baseline(baseline_root)
    bridge_source, bridge_header = _repo_bridge_paths()
    bridge_source_bytes = bridge_source.read_bytes()
    bridge_header_bytes = bridge_header.read_bytes()
    if b"volatile" in bridge_source_bytes or b"volatile" in bridge_header_bytes:
        raise SaturnMidiFullBuildGateError(
            "inert MIDI bridge unexpectedly contains volatile hardware-facing declarations"
        )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    try:
        entries = manifest["generated_files"]
        for entry in entries:
            relative = str(entry["path"])
            source = _safe_manifest_relative(baseline_root, relative)
            destination = _safe_manifest_relative(temp_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

        source_dir = temp_root / "src"
        runtime = source_dir / _RUNTIME_NAME
        if not runtime.is_file():
            raise SaturnMidiFullBuildGateError(
                f"baseline generated runtime source is missing: src/{_RUNTIME_NAME}"
            )
        if _INJECTION_MARKER.encode("ascii") in runtime.read_bytes():
            raise SaturnMidiFullBuildGateError("baseline runtime already contains MIDI gate injection")

        (source_dir / _BRIDGE_SOURCE_NAME).write_bytes(bridge_source_bytes)
        (source_dir / _BRIDGE_HEADER_NAME).write_bytes(bridge_header_bytes)

        runtime_bytes = runtime.read_bytes()
        if not runtime_bytes.endswith(b"\n"):
            runtime_bytes += b"\n"
        runtime.write_bytes(
            runtime_bytes
            + b"\n"
            + _INJECTION_MARKER.encode("ascii")
            + b"\n"
            + bridge_source_bytes
            + (b"" if bridge_source_bytes.endswith(b"\n") else b"\n")
        )

        gate_manifest = dict(manifest)
        gate_policy = dict(gate_manifest.get("policy") or {})
        gate_policy["midi_bridge_active"] = False
        gate_policy["midi_sound_ram_writes"] = False
        gate_policy["midi_scsp_mmio"] = False
        gate_policy["midi_mc68ec000_execution"] = False
        gate_manifest["policy"] = gate_policy
        gate_manifest["midi_bridge_gate"] = {
            "schema": "srk.saturn.midi-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": baseline_manifest_sha,
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "source_copy": f"src/{_BRIDGE_SOURCE_NAME}",
            "header_copy": f"src/{_BRIDGE_HEADER_NAME}",
            "source_sha256": _sha256_bytes(bridge_source_bytes),
            "header_sha256": _sha256_bytes(bridge_header_bytes),
            "behaviorally_active": False,
        }
        gate_manifest["generated_files"] = _inventory_generated_files(temp_root)
        (temp_root / _MANIFEST_NAME).write_text(
            json.dumps(gate_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temp_root.replace(output_root)
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    return SaturnMidiFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=baseline_manifest_sha,
        bridge_source_sha256=_sha256_bytes(bridge_source_bytes),
        bridge_header_sha256=_sha256_bytes(bridge_header_bytes),
    )


def run_inert_midi_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidiFullBuildGateResult:
    """Prepare and run the normal full standalone build on the inert MIDI gate tree."""

    prepared = prepare_inert_midi_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidiFullBuildGateResult(prepared=prepared, build=build)
