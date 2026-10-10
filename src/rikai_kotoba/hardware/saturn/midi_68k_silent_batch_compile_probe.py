"""Off-card compiler gate for the silent full-batch MC68EC000 image.

The large generated program remains constant data from the SH-2 compiler's
point of view.  This probe renders the reviewed header/source into a fresh
off-card directory and asks the same SH-ELF GCC backend used by the standalone
build to compile it with the production C policy.

No link, ISO build, SAROO write, Sound-RAM installation, MC68EC000 execution or
SCSP access occurs here.
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

from .midi_68k_silent_batch_consumer import (
    build_srk_saturn_midi_68k_silent_batch_consumer_image,
    render_srk_saturn_midi_68k_silent_batch_header,
    render_srk_saturn_midi_68k_silent_batch_source,
)
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidi68KSilentBatchCompileProbeError(RuntimeError):
    """Raised when the silent full-batch compiler probe cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KSilentBatchCompileProbeResult:
    output_root: Path
    compiler: Path
    source_path: Path
    header_path: Path
    object_path: Path | None
    log_path: Path
    report_path: Path
    image_sha256: str
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
_SOURCE_NAME = "srk_saturn_midi_68k_silent_batch_program.c"
_HEADER_NAME = "srk_saturn_midi_68k_silent_batch_program.h"
_OBJECT_NAME = "srk_saturn_midi_68k_silent_batch_program.o"
_LOG_NAME = "SRK_MIDI_68K_SILENT_BATCH_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_68K_SILENT_BATCH_COMPILE_PROBE.json"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_midi_68k_silent_batch_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KSilentBatchCompileProbeResult:
    """Generate and compile the silent full-batch constant program off-card."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KSilentBatchCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KSilentBatchCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    image = build_srk_saturn_midi_68k_silent_batch_consumer_image()
    header_text = render_srk_saturn_midi_68k_silent_batch_header()
    source_text = render_srk_saturn_midi_68k_silent_batch_source()
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    source_path = temp_root / _SOURCE_NAME
    header_path = temp_root / _HEADER_NAME
    object_path = temp_root / _OBJECT_NAME
    log_path = temp_root / _LOG_NAME
    report_path = temp_root / _REPORT_NAME

    source_path.write_text(source_text, encoding="utf-8", newline="\n")
    header_path.write_text(header_text, encoding="utf-8", newline="\n")
    source_sha_before = _sha256_file(source_path)
    header_sha_before = _sha256_file(header_path)

    runner = _runner or subprocess.run
    argv = (
        str(compiler),
        "-c",
        str(source_path),
        "-o",
        str(object_path),
        *_COMPILE_FLAGS,
        f"-I{temp_root}",
    )

    try:
        completed = runner(
            list(argv),
            cwd=str(temp_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        returncode = int(getattr(completed, "returncode", 1))
        command_output = _decode_output(getattr(completed, "stdout", b""))

        source_sha_after = _sha256_file(source_path)
        header_sha_after = _sha256_file(header_path)
        generated_inputs_unchanged = (
            source_sha_after == source_sha_before
            and header_sha_after == header_sha_before
        )
        path_unchanged = os.environ.get("PATH") == path_before
        object_ok = object_path.is_file() and object_path.stat().st_size > 0
        successful = (
            returncode == 0
            and object_ok
            and generated_inputs_unchanged
            and path_unchanged
        )
        object_sha = _sha256_file(object_path) if object_ok else None

        log_lines = [
            "SRK silent full-batch Saturn MIDI 68K compiler probe",
            "====================================================",
            f"returncode={returncode}",
            "argv: " + " ".join(argv),
            "",
        ]
        if command_output:
            log_lines.extend((command_output.rstrip(), ""))
        log_lines.extend(
            (
                f"image_sha256={image.sha256}",
                f"image_word_count={len(image.words)}",
                f"image_byte_size={image.byte_size}",
                f"image_start=0x{0x4000:08X}",
                f"image_end=0x{image.end_address:08X}",
                f"source_sha256_before={source_sha_before}",
                f"source_sha256_after={source_sha_after}",
                f"header_sha256_before={header_sha_before}",
                f"header_sha256_after={header_sha_after}",
                f"generated_inputs_unchanged={str(generated_inputs_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"object_present={str(object_ok).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-68k-silent-batch-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "image": {
                "address": 0x4000,
                "end_address": image.end_address,
                "word_count": len(image.words),
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "expected_records": image.expected_records,
                "queue_word_count": image.queue_word_count,
            },
            "generated_source": {
                "path": _SOURCE_NAME,
                "sha256": source_sha_before,
            },
            "generated_header": {
                "path": _HEADER_NAME,
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
            "command": {"argv": list(argv), "returncode": returncode},
            "policy": {
                "python_native_orchestration": True,
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "generated_inputs_unchanged": generated_inputs_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "scsp_mmio": False,
                "smpc_commands": False,
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
        return SaturnMidi68KSilentBatchCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            source_path=output_root / _SOURCE_NAME,
            header_path=output_root / _HEADER_NAME,
            object_path=final_object,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            image_sha256=image.sha256,
            source_sha256=source_sha_before,
            header_sha256=header_sha_before,
            object_sha256=object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_midi_68k_silent_batch_compile_flags() -> tuple[str, ...]:
    """Expose the pinned production C policy for regression tests."""

    return _COMPILE_FLAGS
