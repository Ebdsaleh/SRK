"""Off-card compiler gate for SRK's bounded Saturn MIDI MC68EC000 installer.

This gate asks the same SH-ELF GCC backend used by the standalone build to
compile ``srk_saturn_midi_68k_installer.c`` with the production C policy.  The
installer remains uncalled: no link, ISO build, SAROO write, Sound RAM write,
reset-vector change, SMPC command, SCSP access, or MC68EC000 execution occurs.
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


class SaturnMidi68KInstallerCompileProbeError(RuntimeError):
    """Raised when the bounded 68K installer compiler probe cannot run safely."""


@dataclass(frozen=True)
class SaturnMidi68KInstallerCompileProbeResult:
    output_root: Path
    compiler: Path
    object_path: Path | None
    log_path: Path
    report_path: Path
    source_sha256: str
    installer_header_sha256: str
    program_header_sha256: str
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
_SOURCE_NAME = "srk_saturn_midi_68k_installer.c"
_INSTALLER_HEADER_NAME = "srk_saturn_midi_68k_installer.h"
_PROGRAM_HEADER_NAME = "srk_saturn_midi_68k_program.h"
_OBJECT_NAME = "srk_saturn_midi_68k_installer.o"
_LOG_NAME = "SRK_MIDI_68K_INSTALLER_COMPILE_PROBE_LOG.txt"
_REPORT_NAME = "SRK_MIDI_68K_INSTALLER_COMPILE_PROBE.json"


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
        source_dir = parent / "integrations" / "saturn" / "standalone"
        if all(
            (source_dir / name).is_file()
            for name in (_SOURCE_NAME, _INSTALLER_HEADER_NAME, _PROGRAM_HEADER_NAME)
        ):
            return parent
    raise SaturnMidi68KInstallerCompileProbeError(
        "cannot locate SRK Saturn MIDI 68K installer compiler inputs"
    )


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_midi_68k_installer_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnMidi68KInstallerCompileProbeResult:
    """Compile the still-uninvoked installer once in a fresh off-card directory."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnMidi68KInstallerCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnMidi68KInstallerCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    repo_root = _repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    source = source_dir / _SOURCE_NAME
    installer_header = source_dir / _INSTALLER_HEADER_NAME
    program_header = source_dir / _PROGRAM_HEADER_NAME

    source_sha_before = _sha256_file(source)
    installer_header_sha_before = _sha256_file(installer_header)
    program_header_sha_before = _sha256_file(program_header)
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
        installer_header_sha_after = _sha256_file(installer_header)
        program_header_sha_after = _sha256_file(program_header)
        sources_unchanged = (
            source_sha_after == source_sha_before
            and installer_header_sha_after == installer_header_sha_before
            and program_header_sha_after == program_header_sha_before
        )
        path_unchanged = os.environ.get("PATH") == path_before
        object_ok = object_path.is_file() and object_path.stat().st_size > 0
        successful = returncode == 0 and object_ok and sources_unchanged and path_unchanged
        object_sha = _sha256_file(object_path) if object_ok else None

        log_lines = [
            "SRK bounded Saturn MIDI 68K installer compiler probe",
            "====================================================",
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
                f"installer_header_sha256_before={installer_header_sha_before}",
                f"installer_header_sha256_after={installer_header_sha_after}",
                f"program_header_sha256_before={program_header_sha_before}",
                f"program_header_sha256_after={program_header_sha_after}",
                f"source_inputs_unchanged={str(sources_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"object_present={str(object_ok).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(log_lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.midi-68k-installer-compile-probe.v1",
            "successful": successful,
            "compiler": str(compiler),
            "source": {"path": str(source), "sha256": source_sha_before},
            "installer_header": {
                "path": str(installer_header),
                "sha256": installer_header_sha_before,
            },
            "program_header": {
                "path": str(program_header),
                "sha256": program_header_sha_before,
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
                "source_inputs_unchanged": sources_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "sd_writes": False,
                "sound_ram_writes": False,
                "reset_vectors_changed": False,
                "scsp_mmio": False,
                "smpc_commands": False,
                "mailbox_published": False,
                "mc68ec000_program_installed": False,
                "mc68ec000_execution": False,
                "installer_called": False,
            },
        }
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temp_root.replace(output_root)
        final_object = output_root / _OBJECT_NAME if object_ok else None
        return SaturnMidi68KInstallerCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            object_path=final_object,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            source_sha256=source_sha_before,
            installer_header_sha256=installer_header_sha_before,
            program_header_sha256=program_header_sha_before,
            object_sha256=object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_midi_68k_installer_compile_flags() -> tuple[str, ...]:
    """Expose the pinned production C policy for regression tests."""

    return _COMPILE_FLAGS
