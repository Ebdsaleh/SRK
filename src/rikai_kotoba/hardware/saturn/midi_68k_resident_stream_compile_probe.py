"""Off-card legacy compiler gate for the continuous MIDI 68K stream service."""

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

from .midi_68k_resident_stream_service import (
    SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_resident_stream_service_image,
    render_srk_saturn_midi_68k_resident_stream_service_header,
    render_srk_saturn_midi_68k_resident_stream_service_source,
)
from .midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .midi_bridge import build_srk_saturn_midi_bridge_assets
from .midi_mailbox import render_srk_saturn_midi_mailbox_header
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidi68KResidentStreamCompileProbeError(RuntimeError):
    """Raised when the stream-service compiler probe cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KResidentStreamCompileProbeResult:
    output_root: Path
    compiler: Path
    resident_source_path: Path
    resident_header_path: Path
    producer_source_path: Path
    producer_header_path: Path
    resident_object_path: Path | None
    producer_object_path: Path | None
    log_path: Path
    report_path: Path
    image_sha256: str
    resident_source_sha256: str
    resident_header_sha256: str
    producer_source_sha256: str
    producer_header_sha256: str
    resident_object_sha256: str | None
    producer_object_sha256: str | None
    successful: bool


_COMPILE_FLAGS = (
    "-Wall",
    "-Werror",
    "-m2",
    "-O0",
    "-ffreestanding",
    "-fno-builtin",
)
_RESIDENT_SOURCE = "srk_saturn_midi_68k_resident_stream_service.c"
_RESIDENT_HEADER = "srk_saturn_midi_68k_resident_stream_service.h"
_PRODUCER_SOURCE = "srk_saturn_midi_68k_stream_service.c"
_PRODUCER_HEADER = "srk_saturn_midi_68k_stream_service.h"
_GENERATED_HEADER = "srk_saturn_midi_generated.h"
_MAILBOX_HEADER = "srk_saturn_midi_mailbox.h"
_RESIDENT_OBJECT = "srk_saturn_midi_68k_resident_stream_service.o"
_PRODUCER_OBJECT = "srk_saturn_midi_68k_stream_service.o"
_LOG_NAME = "SRK_MIDI_68K_RESIDENT_STREAM_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_68K_RESIDENT_STREAM_COMPILE_PROBE.json"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_midi_68k_resident_stream_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KResidentStreamCompileProbeResult:
    """Compile both the inert resident image and SH-2 refill/timebase producer."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KResidentStreamCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KResidentStreamCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    image = build_srk_saturn_midi_68k_resident_stream_service_image()
    files = {
        _RESIDENT_SOURCE: render_srk_saturn_midi_68k_resident_stream_service_source(),
        _RESIDENT_HEADER: render_srk_saturn_midi_68k_resident_stream_service_header(),
        _PRODUCER_SOURCE: render_srk_saturn_midi_68k_stream_service_source(),
        _PRODUCER_HEADER: render_srk_saturn_midi_68k_stream_service_header(),
        _GENERATED_HEADER: build_srk_saturn_midi_bridge_assets().header_text,
        _MAILBOX_HEADER: render_srk_saturn_midi_mailbox_header(),
    }
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent)))
    try:
        for name, text in files.items():
            (temp_root / name).write_text(text, encoding="utf-8", newline="\n")
        before = {name: _sha256_file(temp_root / name) for name in files}

        runner = _runner or subprocess.run
        commands = []
        outputs = []
        for source_name, object_name in (
            (_RESIDENT_SOURCE, _RESIDENT_OBJECT),
            (_PRODUCER_SOURCE, _PRODUCER_OBJECT),
        ):
            argv = (
                str(compiler),
                "-c",
                str(temp_root / source_name),
                "-o",
                str(temp_root / object_name),
                *_COMPILE_FLAGS,
                f"-I{temp_root}",
            )
            completed = runner(
                list(argv),
                cwd=str(temp_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                shell=False,
            )
            commands.append((argv, int(getattr(completed, "returncode", 1))))
            outputs.append(_decode(getattr(completed, "stdout", b"")))

        after = {name: _sha256_file(temp_root / name) for name in files}
        inputs_unchanged = before == after
        path_unchanged = os.environ.get("PATH") == path_before
        resident_object = temp_root / _RESIDENT_OBJECT
        producer_object = temp_root / _PRODUCER_OBJECT
        resident_ok = resident_object.is_file() and resident_object.stat().st_size > 0
        producer_ok = producer_object.is_file() and producer_object.stat().st_size > 0
        successful = (
            all(returncode == 0 for _argv, returncode in commands)
            and resident_ok
            and producer_ok
            and inputs_unchanged
            and path_unchanged
        )
        resident_object_sha = _sha256_file(resident_object) if resident_ok else None
        producer_object_sha = _sha256_file(producer_object) if producer_ok else None

        log_lines = [
            "SRK Saturn MIDI 68K resident stream compiler probe",
            "===================================================",
        ]
        for index, ((argv, returncode), output) in enumerate(zip(commands, outputs)):
            log_lines.extend(
                (
                    f"command[{index}].returncode={returncode}",
                    f"command[{index}].argv=" + " ".join(argv),
                    output.rstrip(),
                )
            )
        log_lines.extend(
            (
                f"image_sha256={image.sha256}",
                f"image_word_count={image.word_count}",
                f"image_byte_size={image.byte_size}",
                f"image_start=0x{SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS:08X}",
                f"image_end=0x{image.end_address:08X}",
                f"resident_source_sha256={before[_RESIDENT_SOURCE]}",
                f"resident_header_sha256={before[_RESIDENT_HEADER]}",
                f"producer_source_sha256={before[_PRODUCER_SOURCE]}",
                f"producer_header_sha256={before[_PRODUCER_HEADER]}",
                f"resident_object_sha256={resident_object_sha or ''}",
                f"producer_object_sha256={producer_object_sha or ''}",
                f"generated_inputs_unchanged={str(inputs_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        (temp_root / _LOG_NAME).write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-68k-resident-stream-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "image": {
                "address": SATURN_MIDI_68K_RESIDENT_STREAM_PROGRAM_ADDRESS,
                "end_address": image.end_address,
                "word_count": image.word_count,
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "queue_capacity": 32,
                "multi_batch_refill": True,
                "timestamp_scheduler": True,
                "state_persistent_across_refills": True,
                "scsp_access": False,
            },
            "generated": {
                name: {"sha256": before[name], "size": (temp_root / name).stat().st_size}
                for name in files
            },
            "objects": {
                _RESIDENT_OBJECT: {
                    "sha256": resident_object_sha,
                    "size": resident_object.stat().st_size if resident_ok else 0,
                },
                _PRODUCER_OBJECT: {
                    "sha256": producer_object_sha,
                    "size": producer_object.stat().st_size if producer_ok else 0,
                },
            },
            "commands": [
                {"argv": list(argv), "returncode": returncode}
                for argv, returncode in commands
            ],
            "policy": {
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "generated_inputs_unchanged": inputs_unchanged,
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
        (temp_root / _REPORT_NAME).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temp_root.replace(output_root)
        return SaturnMidi68KResidentStreamCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            resident_source_path=output_root / _RESIDENT_SOURCE,
            resident_header_path=output_root / _RESIDENT_HEADER,
            producer_source_path=output_root / _PRODUCER_SOURCE,
            producer_header_path=output_root / _PRODUCER_HEADER,
            resident_object_path=(output_root / _RESIDENT_OBJECT) if resident_ok else None,
            producer_object_path=(output_root / _PRODUCER_OBJECT) if producer_ok else None,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            image_sha256=image.sha256,
            resident_source_sha256=before[_RESIDENT_SOURCE],
            resident_header_sha256=before[_RESIDENT_HEADER],
            producer_source_sha256=before[_PRODUCER_SOURCE],
            producer_header_sha256=before[_PRODUCER_HEADER],
            resident_object_sha256=resident_object_sha,
            producer_object_sha256=producer_object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_midi_68k_resident_stream_compile_flags() -> tuple[str, ...]:
    return _COMPILE_FLAGS
