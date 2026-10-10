"""Fresh off-card full-build gate for SRK's Saturn MIDI 68K hardware adapter.

This gate derives from the accepted adapter-neutral runtime full-build tree and
links the real Saturn hardware adapter into that fresh tree.  The adapter is
still uncalled: no runtime path supplies its operation table, so no SMPC command,
Sound-RAM runtime write, reset-vector change, SCSP access, MC68EC000 execution,
or SAROO action occurs in this gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from .midi_68k_runtime_full_build_gate import (
    SaturnMidi68KRuntimeFullBuildGateError,
    prepare_inert_midi_68k_runtime_full_build_gate,
)
from .standalone_build import (
    SaturnStandaloneBuildResult,
    build_saturn_standalone_project,
)


class SaturnMidi68KHardwareAdapterFullBuildGateError(RuntimeError):
    """Raised when the inert hardware-adapter full-build gate is unsafe."""


@dataclass(frozen=True)
class SaturnMidi68KHardwareAdapterFullBuildGatePrepared:
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
    adapter_source_sha256: str
    adapter_header_sha256: str


@dataclass(frozen=True)
class SaturnMidi68KHardwareAdapterFullBuildGateResult:
    prepared: SaturnMidi68KHardwareAdapterFullBuildGatePrepared
    build: SaturnStandaloneBuildResult


_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_NAME = "srk_saturn_runtime.c"
_ADAPTER_SOURCE_NAME = "srk_saturn_midi_68k_hardware_adapter.c"
_ADAPTER_HEADER_NAME = "srk_saturn_midi_68k_hardware_adapter.h"
_INJECTION_MARKER = (
    "/* SRK MIDI 68K HARDWARE ADAPTER INERT FULL-BUILD GATE: adapter follows. */"
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


def _repo_adapter_paths() -> tuple[Path, Path]:
    for parent in Path(__file__).resolve().parents:
        directory = parent / "integrations" / "saturn" / "standalone"
        source = directory / _ADAPTER_SOURCE_NAME
        header = directory / _ADAPTER_HEADER_NAME
        if source.is_file() and header.is_file():
            return source, header
    raise SaturnMidi68KHardwareAdapterFullBuildGateError(
        "cannot locate SRK Saturn MIDI 68K hardware-adapter source/header"
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
        raise SaturnMidi68KHardwareAdapterFullBuildGateError(
            f"cannot read derived project manifest: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise SaturnMidi68KHardwareAdapterFullBuildGateError(
            "derived project manifest root must be an object"
        )
    return value


def prepare_inert_midi_68k_hardware_adapter_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KHardwareAdapterFullBuildGatePrepared:
    """Prepare a fresh full-build tree with the hardware adapter still uncalled."""

    baseline_root = _canonical(baseline_project)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KHardwareAdapterFullBuildGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    adapter_source, adapter_header = _repo_adapter_paths()
    adapter_source_bytes = adapter_source.read_bytes()
    adapter_header_bytes = adapter_header.read_bytes()

    required = (
        b"srk_saturn_midi_68k_hardware_adapter_ops",
        b"SRK_MIDI_ADAPTER_SMPC_SNDOFF",
        b"SRK_MIDI_ADAPTER_SMPC_SNDON",
        b"0x2010001F",
        b"0x20100063",
        b"0x25F80004",
        b"0x25A00000",
    )
    for symbol in required:
        if symbol not in adapter_source_bytes + adapter_header_bytes:
            raise SaturnMidi68KHardwareAdapterFullBuildGateError(
                "hardware adapter is missing a reviewed Saturn binding"
            )

    if b"0x25B00000" in adapter_source_bytes or b"0x25B00400" in adapter_source_bytes:
        raise SaturnMidi68KHardwareAdapterFullBuildGateError(
            "silent hardware adapter unexpectedly contains SCSP MMIO"
        )
    if b"srk_saturn_midi_68k_protocol_begin(" in adapter_source_bytes:
        raise SaturnMidi68KHardwareAdapterFullBuildGateError(
            "hardware adapter unexpectedly calls the runtime orchestrator"
        )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary_parent = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    staging = temporary_parent / "stage"
    try:
        try:
            base = prepare_inert_midi_68k_runtime_full_build_gate(
                baseline_root,
                staging,
            )
        except SaturnMidi68KRuntimeFullBuildGateError as exc:
            raise SaturnMidi68KHardwareAdapterFullBuildGateError(
                f"cannot derive inert MIDI 68K runtime baseline: {exc}"
            ) from exc

        source_dir = staging / "src"
        runtime = source_dir / _RUNTIME_NAME
        if not runtime.is_file():
            raise SaturnMidi68KHardwareAdapterFullBuildGateError(
                f"derived runtime source is missing: src/{_RUNTIME_NAME}"
            )
        runtime_bytes = runtime.read_bytes()
        marker = _INJECTION_MARKER.encode("ascii")
        if marker in runtime_bytes:
            raise SaturnMidi68KHardwareAdapterFullBuildGateError(
                "derived runtime already contains hardware-adapter gate injection"
            )

        (source_dir / _ADAPTER_SOURCE_NAME).write_bytes(adapter_source_bytes)
        (source_dir / _ADAPTER_HEADER_NAME).write_bytes(adapter_header_bytes)

        if not runtime_bytes.endswith(b"\n"):
            runtime_bytes += b"\n"
        runtime.write_bytes(
            runtime_bytes
            + b"\n"
            + marker
            + b"\n"
            + adapter_source_bytes
            + (b"" if adapter_source_bytes.endswith(b"\n") else b"\n")
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
        policy["midi_68k_hardware_adapter_present"] = True
        policy["midi_68k_hardware_adapter_linked"] = True
        policy["midi_68k_hardware_adapter_called"] = False
        policy["midi_68k_reset_vectors_changed"] = False
        policy["midi_sound_ram_writes"] = False
        policy["midi_scsp_mmio"] = False
        policy["midi_smpc_commands"] = False
        policy["midi_mc68ec000_execution"] = False
        manifest["policy"] = policy
        manifest["midi_68k_hardware_adapter_full_build_gate"] = {
            "schema": "srk.saturn.midi-68k-hardware-adapter-full-build-gate.v1",
            "baseline_project": str(baseline_root),
            "baseline_manifest_sha256": base.baseline_manifest_sha256,
            "compile_injection": f"src/{_RUNTIME_NAME}",
            "adapter_source_copy": f"src/{_ADAPTER_SOURCE_NAME}",
            "adapter_header_copy": f"src/{_ADAPTER_HEADER_NAME}",
            "adapter_source_sha256": _sha256_bytes(adapter_source_bytes),
            "adapter_header_sha256": _sha256_bytes(adapter_header_bytes),
            "adapter_linked": True,
            "adapter_called": False,
            "runtime_called": False,
            "installer_called": False,
            "program_installed": False,
            "reset_vectors_changed": False,
            "producer_called": False,
            "smpc_commands_executed": False,
            "sound_ram_runtime_writes": False,
            "mc68ec000_execution": False,
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

    return SaturnMidi68KHardwareAdapterFullBuildGatePrepared(
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
        runtime_source_sha256=base.runtime_source_sha256,
        runtime_header_sha256=base.runtime_header_sha256,
        adapter_source_sha256=_sha256_bytes(adapter_source_bytes),
        adapter_header_sha256=_sha256_bytes(adapter_header_bytes),
    )


def run_inert_midi_68k_hardware_adapter_full_build_gate(
    baseline_project: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnMidi68KHardwareAdapterFullBuildGateResult:
    """Build the complete standalone image with the hardware adapter still uncalled."""

    prepared = prepare_inert_midi_68k_hardware_adapter_full_build_gate(
        baseline_project,
        output_directory,
    )
    build = build_saturn_standalone_project(prepared.output_root)
    return SaturnMidi68KHardwareAdapterFullBuildGateResult(prepared=prepared, build=build)
