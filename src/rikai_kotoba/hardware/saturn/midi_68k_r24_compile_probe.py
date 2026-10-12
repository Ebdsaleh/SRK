"""Off-card legacy compiler gate for the complete R24 real-song stack."""

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

from .midi_68k_r24_frt_backend import (
    render_saturn_midi_68k_r24_frt_backend_header,
    render_saturn_midi_68k_r24_frt_backend_source,
)
from .midi_68k_r24_player import (
    render_saturn_midi_68k_r24_player_header,
    render_saturn_midi_68k_r24_player_source,
    validate_saturn_midi_68k_r24_complete_player,
)
from .midi_68k_r24_resident_audio_service import (
    SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS,
    build_srk_saturn_midi_68k_r24_resident_audio_service_image,
    render_srk_saturn_midi_68k_r24_resident_audio_service_header,
    render_srk_saturn_midi_68k_r24_resident_audio_service_source,
    render_srk_saturn_midi_68k_r24_voice_header,
)
from .midi_68k_r24_song import (
    build_saturn_midi_68k_r24_song_profile,
    validate_saturn_midi_68k_r24_reference_song,
)
from .midi_68k_r24_voice_allocator import (
    trace_saturn_midi_68k_r24_program_voices,
    validate_saturn_midi_68k_r24_reference_voice_trace,
)
from .midi_68k_stream_service import (
    render_srk_saturn_midi_68k_stream_service_header,
    render_srk_saturn_midi_68k_stream_service_source,
)
from .midi_bridge import build_srk_saturn_midi_bridge_assets
from .midi_mailbox import render_srk_saturn_midi_mailbox_header
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidi68KR24CompileProbeError(RuntimeError):
    """Raised when the R24 compiler gate cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KR24CompileProbeResult:
    output_root: Path
    compiler: Path
    source_midi_path: Path
    report_path: Path
    log_path: Path
    image_sha256: str
    source_midi_sha256: str
    generated_sha256: tuple[tuple[str, str], ...]
    object_sha256: tuple[tuple[str, str], ...]
    successful: bool


_COMPILE_FLAGS = (
    "-Wall",
    "-Werror",
    "-m2",
    "-O0",
    "-ffreestanding",
    "-fno-builtin",
)

_RESIDENT_SOURCE = "srk_saturn_midi_68k_r24_resident_audio_service.c"
_RESIDENT_HEADER = "srk_saturn_midi_68k_r24_resident_audio_service.h"
_VOICE_HEADER = "srk_saturn_midi_68k_r24_voice_state.h"
_STREAM_SOURCE = "srk_saturn_midi_68k_stream_service.c"
_STREAM_HEADER = "srk_saturn_midi_68k_stream_service.h"
_PLAYER_SOURCE = "srk_saturn_midi_68k_r24_player.c"
_PLAYER_HEADER = "srk_saturn_midi_68k_r24_player.h"
_FRT_SOURCE = "srk_saturn_midi_68k_r24_frt_backend.c"
_FRT_HEADER = "srk_saturn_midi_68k_r24_frt_backend.h"
_GENERATED_HEADER = "srk_saturn_midi_generated.h"
_MAILBOX_HEADER = "srk_saturn_midi_mailbox.h"

_SOURCES = (_RESIDENT_SOURCE, _STREAM_SOURCE, _PLAYER_SOURCE, _FRT_SOURCE)
_OBJECTS = {
    _RESIDENT_SOURCE: "srk_saturn_midi_68k_r24_resident_audio_service.o",
    _STREAM_SOURCE: "srk_saturn_midi_68k_stream_service.o",
    _PLAYER_SOURCE: "srk_saturn_midi_68k_r24_player.o",
    _FRT_SOURCE: "srk_saturn_midi_68k_r24_frt_backend.o",
}
_LOG_NAME = "SRK_MIDI_68K_R24_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_68K_R24_COMPILE_PROBE.json"


def _canonical(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


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


def probe_saturn_midi_68k_r24_compile(
    saturn_root: os.PathLike[str] | str,
    source_midi: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KR24CompileProbeResult:
    """Compile the two-slot resident image, real-song producer and FRT backend."""

    saturn_root = _canonical(saturn_root)
    source_midi_path = _canonical(source_midi)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KR24CompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if not source_midi_path.is_file():
        raise SaturnMidi68KR24CompileProbeError(
            f"R24 source MIDI is not a file: {source_midi_path}"
        )

    profile = build_saturn_midi_68k_r24_song_profile(source_midi_path)
    validate_saturn_midi_68k_r24_reference_song(profile)
    voice_trace = trace_saturn_midi_68k_r24_program_voices(profile.program)
    validate_saturn_midi_68k_r24_reference_voice_trace(voice_trace)
    validate_saturn_midi_68k_r24_complete_player(profile.program)

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KR24CompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    image = build_srk_saturn_midi_68k_r24_resident_audio_service_image()
    files = {
        _RESIDENT_SOURCE: render_srk_saturn_midi_68k_r24_resident_audio_service_source(),
        _RESIDENT_HEADER: render_srk_saturn_midi_68k_r24_resident_audio_service_header(),
        _VOICE_HEADER: render_srk_saturn_midi_68k_r24_voice_header(),
        _STREAM_SOURCE: render_srk_saturn_midi_68k_stream_service_source(),
        _STREAM_HEADER: render_srk_saturn_midi_68k_stream_service_header(),
        _PLAYER_SOURCE: render_saturn_midi_68k_r24_player_source(profile.program),
        _PLAYER_HEADER: render_saturn_midi_68k_r24_player_header(),
        _FRT_SOURCE: render_saturn_midi_68k_r24_frt_backend_source(),
        _FRT_HEADER: render_saturn_midi_68k_r24_frt_backend_header(),
        _GENERATED_HEADER: build_srk_saturn_midi_bridge_assets().header_text,
        _MAILBOX_HEADER: render_srk_saturn_midi_mailbox_header(),
    }
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent)))
    try:
        for name, text in files.items():
            (temporary / name).write_text(text, encoding="utf-8", newline="\n")
        before = {name: _sha256_file(temporary / name) for name in files}

        runner = _runner or subprocess.run
        command_results: list[tuple[tuple[str, ...], int, str]] = []
        for source_name in _SOURCES:
            object_name = _OBJECTS[source_name]
            argv = (
                str(compiler),
                "-c",
                str(temporary / source_name),
                "-o",
                str(temporary / object_name),
                *_COMPILE_FLAGS,
                f"-I{temporary}",
            )
            completed = runner(
                list(argv),
                cwd=str(temporary),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                shell=False,
            )
            command_results.append(
                (
                    argv,
                    int(getattr(completed, "returncode", 1)),
                    _decode(getattr(completed, "stdout", b"")),
                )
            )

        after = {name: _sha256_file(temporary / name) for name in files}
        inputs_unchanged = before == after
        path_unchanged = os.environ.get("PATH") == path_before
        object_hashes: dict[str, str] = {}
        objects_ok = True
        for object_name in _OBJECTS.values():
            object_path = temporary / object_name
            if not object_path.is_file() or object_path.stat().st_size <= 0:
                objects_ok = False
                continue
            object_hashes[object_name] = _sha256_file(object_path)

        successful = (
            all(returncode == 0 for _argv, returncode, _output in command_results)
            and objects_ok
            and len(object_hashes) == len(_OBJECTS)
            and inputs_unchanged
            and path_unchanged
        )

        log_lines = [
            "SRK Saturn MIDI 68K R24 complete-song compiler probe",
            "======================================================",
        ]
        for index, (argv, returncode, output) in enumerate(command_results):
            log_lines.extend(
                (
                    f"command[{index}].returncode={returncode}",
                    f"command[{index}].argv=" + " ".join(argv),
                    output.rstrip(),
                )
            )
        log_lines.extend(
            (
                f"source_midi={source_midi_path}",
                f"source_midi_sha256={profile.source_sha256}",
                f"records={profile.record_count}",
                f"duration_us={profile.duration_us}",
                f"batches={len(profile.batches)}",
                f"peak_polyphony={profile.peak_polyphony}",
                f"image_sha256={image.sha256}",
                f"image_word_count={image.word_count}",
                f"image_byte_size={image.byte_size}",
                f"image_start=0x{SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS:08X}",
                f"image_end=0x{image.end_address:08X}",
            )
        )
        for name in sorted(before):
            log_lines.append(f"generated.{name}.sha256={before[name]}")
        for name in sorted(object_hashes):
            log_lines.append(f"object.{name}.sha256={object_hashes[name]}")
        log_lines.extend(
            (
                f"generated_inputs_unchanged={str(inputs_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        (temporary / _LOG_NAME).write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-68k-r24-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "source_midi": {
                "path": str(source_midi_path),
                "sha256": profile.source_sha256,
                "records": profile.record_count,
                "duration_us": profile.duration_us,
                "batches": len(profile.batches),
                "batch_sizes": [batch.record_count for batch in profile.batches],
                "peak_polyphony": profile.peak_polyphony,
                "note_min": profile.note_min,
                "note_max": profile.note_max,
            },
            "resident_image": {
                "address": SATURN_MIDI_68K_R24_RESIDENT_AUDIO_PROGRAM_ADDRESS,
                "end_address": image.end_address,
                "word_count": image.word_count,
                "byte_size": image.byte_size,
                "sha256": image.sha256,
                "queue_capacity": 32,
                "voice_allocator": "slots0-1-lowest-free-no-steal",
                "calibrated_pitch_table": True,
                "velocity_mixer_table": True,
                "scsp_capable": True,
            },
            "generated": {
                name: {"sha256": before[name], "size": (temporary / name).stat().st_size}
                for name in sorted(files)
            },
            "objects": {
                name: {
                    "sha256": object_hashes.get(name),
                    "size": (temporary / name).stat().st_size if (temporary / name).is_file() else 0,
                }
                for name in sorted(_OBJECTS.values())
            },
            "commands": [
                {"argv": list(argv), "returncode": returncode}
                for argv, returncode, _output in command_results
            ],
            "policy": {
                "source_midi_modified": False,
                "generated_inputs_unchanged": inputs_unchanged,
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "scsp_mmio_executed": False,
                "frt_mmio_executed": False,
                "mc68ec000_program_installed": False,
                "mc68ec000_execution": False,
                "physical_clock_frequency_selected": False,
            },
        }
        (temporary / _REPORT_NAME).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(output_root)
        return SaturnMidi68KR24CompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            source_midi_path=source_midi_path,
            report_path=output_root / _REPORT_NAME,
            log_path=output_root / _LOG_NAME,
            image_sha256=image.sha256,
            source_midi_sha256=profile.source_sha256,
            generated_sha256=tuple(sorted(before.items())),
            object_sha256=tuple(sorted(object_hashes.items())),
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def saturn_midi_68k_r24_compile_flags() -> tuple[str, ...]:
    return _COMPILE_FLAGS
