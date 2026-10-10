"""Fresh off-card full-build gate for SRK's inert MIDI preload producer.

This gate derives from one already-successful standalone project, first applies
the previously accepted inert generated-MIDI bridge gate, then adds the SH-2
mailbox preload producer to the same fresh tree.  The producer is compiled and
linked but remains uncalled, so no Sound RAM, SCSP, SMPC, SAROO, or MC68EC000
runtime action is enabled by this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_full_build_gate import (
    SaturnMidiFullBuildGateError,
    prepare_inert_midi_full_build_gate,
)
from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidiMailboxFullBuildGateError(RuntimeError):
    """Raised when the inert MIDI mailbox full-build gate cannot be prepared."""


@dataclass(frozen=True)
class SaturnMidiMailboxFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    bridge_source_sha256: str
    bridge_header_sha256: str
    mailbox_source_sha256: str
    mailbox_header_sha256: str


@dataclass(frozen=True)
class SaturnMidiMailboxFullBuildGateResult:
    prepared: SaturnMidiMailboxFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_MAILBOX_SOURCE_NAME = "srk_saturn_midi_mailbox.c"
_MAILBOX_HEADER_NAME = "srk_saturn_midi_mailbox.h"
_INJECTION_MARKER = "/* SRK MIDI MAILBOX INERT FULL-BUILD GATE: preload producer follows. */"


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


def _repo_mailbox_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        directory = parent / "integrations" / "saturn" / "standalone"
        source = directory / _MAILBOX_SOURCE_NAME
        header = directory / _MAILBOX_HEADER_NAME
        if source.is_file() and header.is_file():
            return source, header
    raise SaturnMidiMailboxFullBuildGateError(
        "cannot locate SRK Saturn MIDI mailbox preload source/header"
    )


def _inventory_generated_files(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        if not path.is_file() or path.name == _MANIFEST_NAME:
            continue
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def _read_manifest(root: Path) -> dict:
    path = root / _MANIFEST_NAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnMidiMailboxFullBuildGateError(
            f"cannot read derived project manifest: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidiMailboxFullBuildGateError(
            "derived project manifest root must be an object"
        )
    return value


def prepare_inert_midi_mailbox_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidiMailboxFullBuildGatePrepared:
    """Prepare one fresh full-build tree with bridge + uncalled mailbox producer."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidiMailboxFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    mailbox_source, mailbox_header = _repo_mailbox_paths()
    mailbox_source_bytes = mailbox_source.read_bytes()
    mailbox_header_bytes = mailbox_header.read_bytes()
    if b"srk_saturn_midi_preload_publish" not in mailbox_source_bytes:
        raise SaturnMidiMailboxFullBuildGateError(
            "mailbox preload source is missing its publication entry point"
        )
    if b"0x25A00000UL" not in mailbox_source_bytes:
        raise SaturnMidiMailboxFullBuildGateError(
            "mailbox preload source no longer declares the reviewed Sound-RAM aperture"
        )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    try:
        try:
            bridge = prepare_inert_midi_full_build_gate(
                baseline_root,
                staging,
            )
        except SaturnMidiFullBuildGateError as exc:
            raise SaturnMidiMailboxFullBuildGateError(
                f"cannot derive inert MIDI bridge baseline: {exc}"
            ) from exc

        source_dir = staging / "src"
        runtime = source_dir / _RUNTIME_NAME
        if not runtime.is_file():
            raise SaturnMidiMailboxFullBuildGateError(
                f"derived runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_bytes = runtime.read_bytes()
        if _INJECTION_MARKER.encode("ascii") in runtime_bytes:
            raise SaturnMidiMailboxFullBuildGateError(
                "derived runtime already contains mailbox-gate injection"
            )

        (source_dir / _MAILBOX_SOURCE_NAME).write_bytes(mailbox_source_bytes)
        (source_dir / _MAILBOX_HEADER_NAME).write_bytes(mailbox_header_bytes)

        if not runtime_bytes.endswith(b"\n"):
            runtime_bytes += b"\n"
        runtime.write_bytes(
            runtime_bytes
            + b"\n"
            + _INJECTION_MARKER.encode("ascii")
            + b"\n"
            + mailbox_source_bytes
            + (b"" if mailbox_source_bytes.endswith(b"\n") else b"\n")
        )

        manifest = _read_manifest(staging)
        policy = dict(manifest.get("policy") or {})
        policy["midi_bridge_active"] = False
        policy["midi_mailbox_producer_linked"] = True
        policy["midi_mailbox_producer_called"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        manifest["policy"] = policy
        manifest["midi_mailbox_full_build_gate"] = {
            "schema": "srk.saturn.midi-mailbox-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": bridge.baseline_manifest_sha256,
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "mailbox_source_copy": f"src/{_MAILBOX_SOURCE_NAME}",
            "mailbox_header_copy": f"src/{_MAILBOX_HEADER_NAME}",
            "mailbox_source_sha256": _sha256_bytes(mailbox_source_bytes),
            "mailbox_header_sha256": _sha256_bytes(mailbox_header_bytes),
            "producer_linked": True,
            "producer_called": False,
            "behaviorally_active": False,
        }
        manifest["generated_files"] = _inventory_generated_files(staging)
        (staging / _MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        staging.replace(output_root)
        temporary_parent.rmdir()
    except BaseException:
        shutil.rmtree(temporary_parent, ignore_errors=True)
        raise

    return SaturnMidiMailboxFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=bridge.baseline_manifest_sha256,
        bridge_source_sha256=bridge.bridge_source_sha256,
        bridge_header_sha256=bridge.bridge_header_sha256,
        mailbox_source_sha256=_sha256_bytes(mailbox_source_bytes),
        mailbox_header_sha256=_sha256_bytes(mailbox_header_bytes),
    )


def run_inert_midi_mailbox_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidiMailboxFullBuildGateResult:
    """Prepare and build the full image with the mailbox producer still uncalled."""

    prepared = prepare_inert_midi_mailbox_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidiMailboxFullBuildGateResult(prepared=prepared, build=build)
