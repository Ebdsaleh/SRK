"""Off-card compiler gate for SRK's silent Saturn MIDI 68K physical-proof controller.

This gate asks the same SH-ELF GCC backend used by the standalone build to
compile ``srk_saturn_midi_68k_physical_proof.c`` with the production C policy.
The controller remains uncalled: no link, ISO build, SAROO write, SMPC command,
Sound-RAM access, SCSP access, reset-vector change, mailbox publication, or
MC68EC000 execution occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
from typing import Callable

from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidi68KPhysicalProofCompileProbeError(RuntimeError):
    """Raised when the physical-proof compiler probe cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KPhysicalProofCompileProbeResult:
    output_root: Path
    compiler: Path
    object_path: Path | None
    log_path: Path
    report_path: Path
    source_sha256: str
    proof_header_sha256: str
    runtime_header_sha256: str
    adapter_header_sha256: str
    object_sha256: str | None
    successful: bool


_COMPILE_FLAGS = (
    "-Wall",
    "-Werror",
    "-m2",
    "-O0",
    "-ffreestanding",
    "-fno-builtin",
)
_SOURCE_NAME = "srk_saturn_midi_68k_physical_proof.c"
_PROOF_HEADER_NAME = "srk_saturn_midi_68k_physical_proof.h"
_RUNTIME_HEADER_NAME = "srk_saturn_midi_68k_runtime.h"
_ADAPTER_HEADER_NAME = "srk_saturn_midi_68k_hardware_adapter.h"
_OBJECT_NAME = "srk_saturn_midi_68k_physical_proof.o"
_LOG_NAME = "SRK_MIDI_68K_PHYSICAL_PROOF_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_68K_PHYSICAL_PROOF_COMPILE_PROBE.json"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_root() -> Path:
    names = (
        _SOURCE_NAME,
        _PROOF_HEADER_NAME,
        _RUNTIME_HEADER_NAME,
        _ADAPTER_HEADER_NAME,
    )
    for parent in Path(__file__).resolve().parents:
        source_dir = parent / "integrations" / "saturn" / "standalone"
        if all((source_dir / name).is_file() for name in names):
            return parent
    raise SaturnMidi68KPhysicalProofCompileProbeError(
        "cannot locate SRK Saturn MIDI 68K physical-proof compiler inputs"
    )


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_midi_68k_physical_proof_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KPhysicalProofCompileProbeResult:
    """Compile the still-uninvoked physical-proof controller once off-card."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KPhysicalProofCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KPhysicalProofCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    repo_root = _repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    source = source_dir / _SOURCE_NAME
    proof_header = source_dir / _PROOF_HEADER_NAME
    runtime_header = source_dir / _RUNTIME_HEADER_NAME
    adapter_header = source_dir / _ADAPTER_HEADER_NAME

    source_sha_before = _sha256_file(source)
    proof_header_sha_before = _sha256_file(proof_header)
    runtime_header_sha_before = _sha256_file(runtime_header)
    adapter_header_sha_before = _sha256_file(adapter_header)
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    runner = _runner or subprocess.run
    object_path = temp_root / _OBJECT_NAME
    log_path = temp_root / _LOG_NAME
    report_path = temp_root / _REPORT_NAME

    argv = (
        str(compiler),
        "-c",
        str(source),
        "-o",
        str(object_path),
        *_COMPILE_FLAGS,
        f"-I{source_dir}",
    )

    try:
        completed = runner(
            list(argv),
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        returncode = int(getattr(completed, "returncode", 1))
        command_output = _decode_output(getattr(completed, "stdout", b""))

        source_sha_after = _sha256_file(source)
        proof_header_sha_after = _sha256_file(proof_header)
        runtime_header_sha_after = _sha256_file(runtime_header)
        adapter_header_sha_after = _sha256_file(adapter_header)
        sources_unchanged = (
            source_sha_after == source_sha_before
            and proof_header_sha_after == proof_header_sha_before
            and runtime_header_sha_after == runtime_header_sha_before
            and adapter_header_sha_after == adapter_header_sha_before
        )
        path_unchanged = os.environ.get("PATH") == path_before
        object_ok = object_path.is_file() and object_path.stat().st_size > 0
        successful = returncode == 0 and object_ok and sources_unchanged and path_unchanged
        object_sha = _sha256_file(object_path) if object_ok else None

        log_lines = [
            "SRK silent Saturn MIDI 68K physical-proof compiler probe",
            "========================================================",
            f"returncode={returncode}",
            "argv: " + " ".join(argv),
            "",
        ]
        if command_output:
            log_lines.extend((command_output.rstrip(), ""))
        log_lines.extend(
            (
                f"source_sha256_before={source_sha_before}",
                f"source_sha256_after={source_sha_after}",
                f"proof_header_sha256_before={proof_header_sha_before}",
                f"proof_header_sha256_after={proof_header_sha_after}",
                f"runtime_header_sha256_before={runtime_header_sha_before}",
                f"runtime_header_sha256_after={runtime_header_sha_after}",
                f"adapter_header_sha256_before={adapter_header_sha_before}",
                f"adapter_header_sha256_after={adapter_header_sha_after}",
                f"source_inputs_unchanged={str(sources_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"object_present={str(object_ok).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-68k-physical-proof-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "source": {"path": str(source), "sha256": source_sha_before},
            "proof_header": {"path": str(proof_header), "sha256": proof_header_sha_before},
            "runtime_header": {"path": str(runtime_header), "sha256": runtime_header_sha_before},
            "adapter_header": {"path": str(adapter_header), "sha256": adapter_header_sha_before},
            "object": (
                {
                    "path": _OBJECT_NAME,
                    "size": object_path.stat().st_size,
                    "sha256": object_sha,
                }
                if object_ok
                else None
            ),
            "command": {"argv": list(argv), "returncode": returncode},
            "policy": {
                "python_native_orchestration": True,
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "source_inputs_unchanged": sources_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "physical_proof_controller_called": False,
                "hardware_adapter_called": False,
                "runtime_called": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "reset_vectors_changed": False,
                "scsp_mmio": False,
                "smpc_commands": False,
                "mailbox_published": False,
                "mc68ec000_program_installed": False,
                "mc68ec000_execution": False,
            },
        }
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temp_root.replace(output_root)
        final_object = output_root / _OBJECT_NAME if object_ok else None
        return SaturnMidi68KPhysicalProofCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            object_path=final_object,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            source_sha256=source_sha_before,
            proof_header_sha256=proof_header_sha_before,
            runtime_header_sha256=runtime_header_sha_before,
            adapter_header_sha256=adapter_header_sha_before,
            object_sha256=object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_midi_68k_physical_proof_compile_flags() -> tuple[str, ...]:
    """Expose the pinned production C policy for regression tests."""

    return _COMPILE_FLAGS
