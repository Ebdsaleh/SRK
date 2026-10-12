"""Off-card legacy compiler matrix for all 32 inert R25 RR images."""

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

from .midi_68k_r25_resident_audio_service import (
    build_srk_saturn_midi_68k_r25_resident_audio_service_image,
    render_srk_saturn_midi_68k_r25_resident_audio_service_header,
    render_srk_saturn_midi_68k_r25_resident_audio_service_source,
    render_srk_saturn_midi_68k_r25_voice_header,
)
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnMidi68KR25CompileProbeError(RuntimeError):
    """Raised when the R25 inert compiler matrix cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KR25CompileMatrixEntry:
    release_rate: int
    eg1_word: int
    eg2_word: int
    image_sha256: str
    object_sha256: str | None
    returncode: int


@dataclass(frozen=True)
class SaturnMidi68KR25CompileProbeResult:
    output_root: Path
    compiler: Path
    report_path: Path
    log_path: Path
    entries: tuple[SaturnMidi68KR25CompileMatrixEntry, ...]
    successful: bool


_COMPILE_FLAGS = ("-Wall", "-Werror", "-m2", "-O0", "-ffreestanding", "-fno-builtin")
_SOURCE = "srk_saturn_midi_68k_r25_resident_audio_service.c"
_HEADER = "srk_saturn_midi_68k_r25_resident_audio_service.h"
_VOICE_HEADER = "srk_saturn_midi_68k_r25_voice_state.h"
_OBJECT = "srk_saturn_midi_68k_r25_resident_audio_service.o"
_LOG = "SRK_MIDI_68K_R25_RR_COMPILE_MATRIX_LOG.txt"
_REPORT = "SRK_MIDI_68K_R25_RR_COMPILE_MATRIX.json"


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


def probe_saturn_midi_68k_r25_rr_compile_matrix(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KR25CompileProbeResult:
    """Compile each RR 0..31 as data-only C without linking or execution."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KR25CompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KR25CompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent)))
    path_before = os.environ.get("PATH")
    runner = _runner or subprocess.run
    entries: list[SaturnMidi68KR25CompileMatrixEntry] = []
    logs = [
        "SRK Saturn MIDI 68K R25 inert RR compiler matrix",
        "================================================",
    ]
    generated_unchanged = True
    try:
        for rr in range(32):
            rr_root = temporary / f"rr{rr:02d}"
            rr_root.mkdir()
            image = build_srk_saturn_midi_68k_r25_resident_audio_service_image(release_rate=rr)
            files = {
                _SOURCE: render_srk_saturn_midi_68k_r25_resident_audio_service_source(release_rate=rr),
                _HEADER: render_srk_saturn_midi_68k_r25_resident_audio_service_header(release_rate=rr),
                _VOICE_HEADER: render_srk_saturn_midi_68k_r25_voice_header(),
            }
            for name, source in files.items():
                (rr_root / name).write_text(source, encoding="utf-8", newline="\n")
            before = {name: _sha256_file(rr_root / name) for name in files}
            argv = (
                str(compiler), "-c", str(rr_root / _SOURCE), "-o", str(rr_root / _OBJECT),
                *_COMPILE_FLAGS, f"-I{rr_root}",
            )
            completed = runner(
                list(argv), cwd=str(rr_root), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False, shell=False,
            )
            returncode = int(getattr(completed, "returncode", 1))
            output = _decode(getattr(completed, "stdout", b""))
            after = {name: _sha256_file(rr_root / name) for name in files}
            generated_unchanged = generated_unchanged and before == after
            object_path = rr_root / _OBJECT
            object_sha256 = (
                _sha256_file(object_path)
                if object_path.is_file() and object_path.stat().st_size > 0
                else None
            )
            entries.append(
                SaturnMidi68KR25CompileMatrixEntry(
                    release_rate=rr,
                    eg1_word=image.eg1_word,
                    eg2_word=image.eg2_word,
                    image_sha256=image.sha256,
                    object_sha256=object_sha256,
                    returncode=returncode,
                )
            )
            logs.extend(
                (
                    f"rr[{rr:02d}].returncode={returncode}",
                    f"rr[{rr:02d}].eg1=0x{image.eg1_word:04X}",
                    f"rr[{rr:02d}].eg2=0x{image.eg2_word:04X}",
                    f"rr[{rr:02d}].image_sha256={image.sha256}",
                    f"rr[{rr:02d}].object_sha256={object_sha256 or ''}",
                    "argv=" + " ".join(argv),
                    output.rstrip(),
                )
            )

        path_unchanged = os.environ.get("PATH") == path_before
        successful = (
            len(entries) == 32
            and all(entry.returncode == 0 and entry.object_sha256 for entry in entries)
            and len({entry.image_sha256 for entry in entries}) == 32
            and generated_unchanged
            and path_unchanged
        )
        logs.extend(
            (
                f"generated_inputs_unchanged={str(generated_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        (temporary / _LOG).write_text("\n".join(logs), encoding="utf-8", newline="\n")
        report = {
            "schema": "srk.saturn.midi-68k-r25-rr-compile-matrix.v1",
            "successful": successful,
            "compiler": str(compiler),
            "compile_flags": list(_COMPILE_FLAGS),
            "matrix": [
                {
                    "release_rate": entry.release_rate,
                    "eg1_word": entry.eg1_word,
                    "eg2_word": entry.eg2_word,
                    "image_sha256": entry.image_sha256,
                    "object_sha256": entry.object_sha256,
                    "returncode": entry.returncode,
                }
                for entry in entries
            ],
            "policy": {
                "rr_selected": False,
                "physical_measurements_supplied": False,
                "generated_inputs_unchanged": generated_unchanged,
                "path_mutated": not path_unchanged,
                "shell_used": False,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "scsp_mmio_executed": False,
                "mc68ec000_program_installed": False,
                "mc68ec000_execution": False,
            },
        }
        (temporary / _REPORT).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(output_root)
        return SaturnMidi68KR25CompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            report_path=output_root / _REPORT,
            log_path=output_root / _LOG,
            entries=tuple(entries),
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def saturn_midi_68k_r25_compile_flags() -> tuple[str, ...]:
    return _COMPILE_FLAGS
