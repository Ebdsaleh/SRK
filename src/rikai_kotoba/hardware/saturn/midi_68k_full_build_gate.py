"""Fresh off-card full-build gate for SRK's protocol-only MIDI 68K image.

This gate derives from the accepted Stage-6B baseline, re-applies the inert MIDI
bridge plus uncalled SH-2 mailbox producer, then links the protocol-only
MC68EC000 program representation as constant data.  The 68K image remains
uninstalled and unexecuted: reset vectors, Sound RAM runtime state, SCSP, SMPC,
and SAROO are untouched by this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_mailbox_full_build_gate import (
    SaturnMidiMailboxFullBuildGateError,
    prepare_inert_midi_mailbox_full_build_gate,
)
from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidi68KFullBuildGateError(RuntimeError):
    """Raised when the inert MIDI 68K full-build gate cannot be prepared safely."""


@dataclass(frozen=True)
class SaturnMidi68KFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    bridge_source_sha256: str
    bridge_header_sha256: str
    mailbox_source_sha256: str
    mailbox_header_sha256: str
    program_source_sha256: str
    program_header_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KFullBuildGateResult:
    prepared: SaturnMidi68KFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_PROGRAM_SOURCE_NAME = "srk_saturn_midi_68k_program.c"
_PROGRAM_HEADER_NAME = "srk_saturn_midi_68k_program.h"
_INJECTION_MARKER = "/* SRK MIDI 68K INERT FULL-BUILD GATE: protocol image follows. */"


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


def _repo_program_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        directory = parent / "integrations" / "saturn" / "standalone"
        source = directory / _PROGRAM_SOURCE_NAME
        header = directory / _PROGRAM_HEADER_NAME
        if source.is_file() and header.is_file():
            return source, header
    raise SaturnMidi68KFullBuildGateError(
        "cannot locate SRK protocol-only Saturn MIDI 68K program source/header"
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
        raise SaturnMidi68KFullBuildGateError(
            f"cannot read derived project manifest: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KFullBuildGateError(
            "derived project manifest root must be an object"
        )
    return value


def prepare_inert_midi_68k_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KFullBuildGatePrepared:
    """Prepare one fresh tree containing all MIDI layers, with 68K still inert."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    program_source, program_header = _repo_program_paths()
    program_source_bytes = program_source.read_bytes()
    program_header_bytes = program_header.read_bytes()

    if b"srk_saturn_midi_68k_program" not in program_source_bytes:
        raise SaturnMidi68KFullBuildGateError(
            "protocol-only 68K source is missing the reviewed program array"
        )
    if b"SRK_MIDI_68K_PROGRAM_ADDRESS 0x00000600UL" not in program_header_bytes:
        raise SaturnMidi68KFullBuildGateError(
            "protocol-only 68K header no longer declares reviewed program address 0x00000600"
        )
    if b"SRK_MIDI_68K_STACK_ADDRESS 0x0007FFF0UL" not in program_header_bytes:
        raise SaturnMidi68KFullBuildGateError(
            "protocol-only 68K header no longer declares reviewed stack address 0x0007FFF0"
        )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    try:
        try:
            mailbox = prepare_inert_midi_mailbox_full_build_gate(
                baseline_root,
                staging,
            )
        except SaturnMidiMailboxFullBuildGateError as exc:
            raise SaturnMidi68KFullBuildGateError(
                f"cannot derive inert MIDI mailbox baseline: {exc}"
            ) from exc

        source_dir = staging / "src"
        runtime = source_dir / _RUNTIME_NAME
        if not runtime.is_file():
            raise SaturnMidi68KFullBuildGateError(
                f"derived runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_bytes = runtime.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_bytes:
            raise SaturnMidi68KFullBuildGateError(
                "derived runtime already contains MIDI 68K gate injection"
            )

        (source_dir / _PROGRAM_SOURCE_NAME).write_bytes(program_source_bytes)
        (source_dir / _PROGRAM_HEADER_NAME).write_bytes(program_header_bytes)

        if not runtime_bytes.endswith(b"\n"):
            runtime_bytes += b"\n"
        runtime.write_bytes(
            runtime_bytes
            + b"\n"
            + marker
            + b"\n"
            + program_source_bytes
            + (b"" if program_source_bytes.endswith(b"\n") else b"\n")
        )

        manifest = _read_manifest(staging)
        policy = dict(manifest.get("policy") or {})
        policy["midi_bridge_active"] = False
        policy["midi_mailbox_producer_linked"] = True
        policy["midi_mailbox_producer_called"] = False
        policy["midi_68k_program_linked"] = True
        policy["midi_68k_program_installed"] = False
        policy["midi_68k_reset_vectors_changed"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        manifest["policy"] = policy
        manifest["midi_68k_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": mailbox.baseline_manifest_sha256,
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "program_source_copy": f"src/{_PROGRAM_SOURCE_NAME}",
            "program_header_copy": f"src/{_PROGRAM_HEADER_NAME}",
            "program_source_sha256": _sha256_bytes(program_source_bytes),
            "program_header_sha256": _sha256_bytes(program_header_bytes),
            "program_address": "0x00000600",
            "stack_address": "0x0007FFF0",
            "program_linked": True,
            "program_installed": False,
            "reset_vectors_changed": False,
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

    return SaturnMidi68KFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=mailbox.baseline_manifest_sha256,
        bridge_source_sha256=mailbox.bridge_source_sha256,
        bridge_header_sha256=mailbox.bridge_header_sha256,
        mailbox_source_sha256=mailbox.mailbox_source_sha256,
        mailbox_header_sha256=mailbox.mailbox_header_sha256,
        program_source_sha256=_sha256_bytes(program_source_bytes),
        program_header_sha256=_sha256_bytes(program_header_bytes),
    )


def run_inert_midi_68k_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KFullBuildGateResult:
    """Build the full standalone image with the protocol 68K image still inert."""

    prepared = prepare_inert_midi_68k_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KFullBuildGateResult(prepared=prepared, build=build)
