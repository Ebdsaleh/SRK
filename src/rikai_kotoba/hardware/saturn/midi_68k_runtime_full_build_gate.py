"""Fresh off-card full-build gate for SRK's adapter-neutral MIDI 68K runtime.

This gate derives from the accepted Stage-6B baseline, re-applies the inert MIDI
bridge, uncalled SH-2 mailbox producer, uninstalled protocol-only MC68EC000
program image, and uncalled bounded installer, then links the adapter-neutral
silent runtime orchestrator.  The runtime remains uncalled and no Saturn
hardware adapter is present, so no SMPC, Sound RAM, SCSP, MC68EC000 execution,
or SAROO action is enabled by this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_installer_full_build_gate import (
    SaturnMidi68KInstallerFullBuildGateError,
    prepare_inert_midi_68k_installer_full_build_gate,
)
from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidi68KRuntimeFullBuildGateError(RuntimeError):
    """Raised when the inert MIDI 68K runtime full-build gate is unsafe."""


@dataclass(frozen=True)
class SaturnMidi68KRuntimeFullBuildGatePrepared:
    baseline_root: Path
    output_root: Path
    baseline_manifest_sha256: str
    bridge_source_sha256: str
    bridge_header_sha256: str
    mailbox_source_sha256: str
    mailbox_header_sha256: str
    program_source_sha256: str
    program_header_sha256: str
    installer_source_sha256: str
    installer_header_sha256: str
    runtime_source_sha256: str
    runtime_header_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KRuntimeFullBuildGateResult:
    prepared: SaturnMidi68KRuntimeFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_PROTOCOL_SOURCE_NAME = "srk_saturn_midi_68k_runtime.c"
_PROTOCOL_HEADER_NAME = "srk_saturn_midi_68k_runtime.h"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K RUNTIME INERT FULL-BUILD GATE: adapter-neutral runtime follows. */"
)


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


def _repo_runtime_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        directory = parent / "integrations" / "saturn" / "standalone"
        source = directory / _PROTOCOL_SOURCE_NAME
        header = directory / _PROTOCOL_HEADER_NAME
        if source.is_file() and header.is_file():
            return source, header
    raise SaturnMidi68KRuntimeFullBuildGateError(
        "cannot locate SRK adapter-neutral Saturn MIDI 68K runtime source/header"
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
        raise SaturnMidi68KRuntimeFullBuildGateError(
            f"cannot read derived project manifest: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KRuntimeFullBuildGateError(
            "derived project manifest root must be an object"
        )
    return value


def prepare_inert_midi_68k_runtime_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KRuntimeFullBuildGatePrepared:
    """Prepare a fresh full-build tree with the runtime linked but still uncalled."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KRuntimeFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    protocol_source, protocol_header = _repo_runtime_paths()
    protocol_source_bytes = protocol_source.read_bytes()
    protocol_header_bytes = protocol_header.read_bytes()

    for required in (
        b"srk_saturn_midi_68k_protocol_begin",
        b"srk_saturn_midi_68k_protocol_poll",
        b"SRK_SATURN_MIDI_68K_RUNTIME_OPS",
    ):
        if required not in protocol_source_bytes + protocol_header_bytes:
            raise SaturnMidi68KRuntimeFullBuildGateError(
                "adapter-neutral 68K runtime is missing a reviewed protocol symbol"
            )

    for forbidden in (
        b"0x2010001F",
        b"0x20100063",
        b"0x25F80004",
        b"0x25A00000",
        b"0x25B00000",
    ):
        if forbidden in protocol_source_bytes or forbidden in protocol_header_bytes:
            raise SaturnMidi68KRuntimeFullBuildGateError(
                "adapter-neutral 68K runtime unexpectedly contains Saturn hardware MMIO"
            )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    try:
        try:
            base = prepare_inert_midi_68k_installer_full_build_gate(
                baseline_root,
                staging,
            )
        except SaturnMidi68KInstallerFullBuildGateError as exc:
            raise SaturnMidi68KRuntimeFullBuildGateError(
                f"cannot derive inert MIDI 68K installer baseline: {exc}"
            ) from exc

        source_dir = staging / "src"
        runtime = source_dir / _RUNTIME_NAME
        if not runtime.is_file():
            raise SaturnMidi68KRuntimeFullBuildGateError(
                f"derived runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_bytes = runtime.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_bytes:
            raise SaturnMidi68KRuntimeFullBuildGateError(
                "derived runtime already contains MIDI 68K runtime gate injection"
            )

        (source_dir / _PROTOCOL_SOURCE_NAME).write_bytes(protocol_source_bytes)
        (source_dir / _PROTOCOL_HEADER_NAME).write_bytes(protocol_header_bytes)

        if not runtime_bytes.endswith(b"\n"):
            runtime_bytes += b"\n"
        runtime.write_bytes(
            runtime_bytes
            + b"\n"
            + marker
            + b"\n"
            + protocol_source_bytes
            + (b"" if protocol_source_bytes.endswith(b"\n") else b"\n")
        )

        manifest = _read_manifest(staging)
        policy = dict(manifest.get("policy") or {})
        policy["midi_bridge_active"] = False
        policy["midi_mailbox_producer_linked"] = True
        policy["midi_mailbox_producer_called"] = False
        policy["midi_68k_program_linked"] = True
        policy["midi_68k_program_installed"] = False
        policy["midi_68k_installer_linked"] = True
        policy["midi_68k_installer_called"] = False
        policy["midi_68k_runtime_linked"] = True
        policy["midi_68k_runtime_called"] = False
        policy["midi_68k_hardware_adapter_present"] = False
        policy["midi_68k_reset_vectors_changed"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        manifest["policy"] = policy
        manifest["midi_68k_runtime_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-runtime-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": base.baseline_manifest_sha256,
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "runtime_source_copy": f"src/{_PROTOCOL_SOURCE_NAME}",
            "runtime_header_copy": f"src/{_PROTOCOL_HEADER_NAME}",
            "runtime_source_sha256": _sha256_bytes(protocol_source_bytes),
            "runtime_header_sha256": _sha256_bytes(protocol_header_bytes),
            "runtime_linked": True,
            "runtime_called": False,
            "hardware_adapter_present": False,
            "installer_called": False,
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

    return SaturnMidi68KRuntimeFullBuildGatePrepared(
        baseline_root=baseline_root,
        output_root=output_root,
        baseline_manifest_sha256=base.baseline_manifest_sha256,
        bridge_source_sha256=base.bridge_source_sha256,
        bridge_header_sha256=base.bridge_header_sha256,
        mailbox_source_sha256=base.mailbox_source_sha256,
        mailbox_header_sha256=base.mailbox_header_sha256,
        program_source_sha256=base.program_source_sha256,
        program_header_sha256=base.program_header_sha256,
        installer_source_sha256=base.installer_source_sha256,
        installer_header_sha256=base.installer_header_sha256,
        runtime_source_sha256=_sha256_bytes(protocol_source_bytes),
        runtime_header_sha256=_sha256_bytes(protocol_header_bytes),
    )


def run_inert_midi_68k_runtime_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KRuntimeFullBuildGateResult:
    """Build the complete standalone image with the silent runtime still uncalled."""

    prepared = prepare_inert_midi_68k_runtime_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KRuntimeFullBuildGateResult(prepared=prepared, build=build)
