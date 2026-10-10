"""Off-card compiler compatibility probe for SRK's generated Saturn MIDI bridge.

This gate deliberately stops before standalone-project integration.  It asks the
same SH-ELF GCC backend used by SRK's Python-native Saturn builder to compile the
inert generated MIDI C data with the same C flags.  No linker, ISO builder,
SAROO card, SCSP register, Sound RAM, or MC68EC000 path is touched.
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
from typing import Callable, Sequence

from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidiCompileProbeError(RuntimeError):
    """Raised when the inert MIDI bridge compile probe cannot run safely."""


@dataclass(frozen=True)
class SaturnMidiCompileProbeResult:
    output_root: Path
    compiler: Path
    object_path: Path | None
    log_path: Path
    report_path: Path
    source_sha256: str
    header_sha256: str
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
_SOURCE_NAME = "srk_saturn_midi_generated.c"
_HEADER_NAME = "srk_saturn_midi_generated.h"
_OBJECT_NAME = "srk_saturn_midi_generated.o"
_LOG_NAME = "SRK_MIDI_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_COMPILE_PROBE.json"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        source = parent / "integrations" / "saturn" / "standalone" / _SOURCE_NAME
        header = parent / "integrations" / "saturn" / "standalone" / _HEADER_NAME
        if source.is_file() and header.is_file():
            return parent
    raise SaturnMidiCompileProbeError(
        "cannot locate SRK generated Saturn MIDI bridge sources"
    )


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_midi_bridge_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidiCompileProbeResult:
    """Compile the generated MIDI bridge once in a fresh off-card directory."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidiCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidiCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    repo_root = _repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    source = source_dir / _SOURCE_NAME
    header = source_dir / _HEADER_NAME
    if not source.is_file() or not header.is_file():
        raise SaturnMidiCompileProbeError("generated MIDI bridge source/header is missing")

    source_sha_before = _sha256_file(source)
    header_sha_before = _sha256_file(header)
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    runner = _runner or subprocess.run
    object_path = temp_root / _OBJECT_NAME
    log_path = temp_root / _LOG_NAME
    report_path = temp_root / _REPORT_NAME

    argv: tuple[str, ...] = (
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
        header_sha_after = _sha256_file(header)
        sources_unchanged = (
            source_sha_after == source_sha_before
            and header_sha_after == header_sha_before
        )
        path_unchanged = os.environ.get("PATH") == path_before
        object_ok = object_path.is_file() and object_path.stat().st_size > 0
        successful = returncode == 0 and object_ok and sources_unchanged and path_unchanged
        object_sha = _sha256_file(object_path) if object_ok else None

        log_lines = [
            "SRK inert Saturn MIDI bridge compiler probe",
            "============================================",
            f"returncode={returncode}",
            "argv: " + " ".join(argv),
            "",
        ]
        if command_output:
            log_lines.append(command_output.rstrip())
            log_lines.append("")
        log_lines.extend(
            (
                f"source_sha256_before={source_sha_before}",
                f"source_sha256_after={source_sha_after}",
                f"header_sha256_before={header_sha_before}",
                f"header_sha256_after={header_sha_after}",
                f"source_inputs_unchanged={str(sources_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"object_present={str(object_ok).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "source": {
                "path": str(source),
                "sha256": source_sha_before,
            },
            "header": {
                "path": str(header),
                "sha256": header_sha_before,
            },
            "object": (
                {
                    "path": _OBJECT_NAME,
                    "size": object_path.stat().st_size,
                    "sha256": object_sha,
                }
                if object_ok
                else None
            ),
            "command": {
                "argv": list(argv),
                "returncode": returncode,
            },
            "policy": {
                "python_native_orchestration": True,
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "source_inputs_unchanged": sources_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "scsp_mmio": False,
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
        return SaturnMidiCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            object_path=final_object,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            source_sha256=source_sha_before,
            header_sha256=header_sha_before,
            object_sha256=object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_midi_compile_flags() -> tuple[str, ...]:
    """Expose the pinned C flags so tests can compare them with standalone policy."""

    return _COMPILE_FLAGS
