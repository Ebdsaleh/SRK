"""Compile SRK's Sega Sound I/F Direct MIDI adapter off-card.

This is not a generic SDK discovery probe.  It is the production compiler gate
for one concrete source file that includes Sega's documented ``sega_snd.h`` and
calls ``SND_CtrlDirMidi`` with the documented function signature.

The gate resolves only the exact header/library needed for this backend, invokes
the already-installed SH-ELF GCC directly, and performs no link, ISO build,
hardware access or SAROO write.
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


class SaturnSblDirectMidiCompileProbeError(RuntimeError):
    """Raised when the Direct MIDI compiler gate cannot run safely."""


@dataclass(frozen=True)
class SaturnSblDirectMidiCompileProbeResult:
    output_root: Path
    compiler: Path
    sega_header: Path
    sega_library: Path
    object_path: Path | None
    log_path: Path
    report_path: Path
    source_sha256: str
    adapter_header_sha256: str
    sega_header_sha256: str
    sega_library_sha256: str
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
_SOURCE_NAME = "srk_saturn_sbl_direct_midi.c"
_ADAPTER_HEADER_NAME = "srk_saturn_sbl_direct_midi.h"
_SEGA_HEADER_NAME = "sega_snd.h"
_SEGA_LIBRARY_NAME = "sega_snd.a"
_OBJECT_NAME = "srk_saturn_sbl_direct_midi.o"
_LOG_NAME = "SRK_SBL_DIRECT_MIDI_COMPILE_LOG.txt"
_REPORT_NAME = "SRK_SBL_DIRECT_MIDI_COMPILE.json"
_MAX_DEPTH = 9
_SKIP_DIRS = {".git", ".svn", "__pycache__", "node_modules"}


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
        if (
            (source_dir / _SOURCE_NAME).is_file()
            and (source_dir / _ADAPTER_HEADER_NAME).is_file()
        ):
            return parent
    raise SaturnSblDirectMidiCompileProbeError(
        "cannot locate SRK Sega Direct MIDI adapter sources"
    )


def _sdk_candidates(root: Path, filename: str) -> tuple[Path, ...]:
    wanted = filename.casefold()
    root_depth = len(root.parts)
    found: list[Path] = []
    for current_text, dirs, files in os.walk(root):
        current = Path(current_text)
        depth = len(current.parts) - root_depth
        dirs[:] = [
            name
            for name in sorted(dirs, key=str.casefold)
            if name not in _SKIP_DIRS and depth < _MAX_DEPTH
        ]
        for item in files:
            if item.casefold() == wanted:
                candidate = (current / item).resolve(strict=False)
                if candidate.is_file():
                    found.append(candidate)
    unique = {str(path).casefold(): path for path in found}
    return tuple(sorted(unique.values(), key=lambda path: str(path).casefold()))


def _rank_sdk_path(path: Path, *, kind: str) -> tuple[int, str]:
    parts = {part.casefold() for part in path.parts}
    score = 0
    if "sbl_601" in parts:
        score += 8
    if "segalib" in parts:
        score += 8
    if kind == "header" and "include" in parts:
        score += 8
    if kind == "library" and "lib_elf" in parts:
        score += 8
    # Prefer the direct installed SDK over analysis/copy trees when both exist.
    if "saturnorbit-inspect" not in parts:
        score += 2
    return (-score, str(path).casefold())


def _resolve_sdk_file(root: Path, filename: str, *, kind: str) -> Path:
    candidates = _sdk_candidates(root, filename)
    if not candidates:
        raise SaturnSblDirectMidiCompileProbeError(
            f"required Sega Sound Driver {kind} was not found under {root}: {filename}"
        )
    ranked = sorted(candidates, key=lambda path: _rank_sdk_path(path, kind=kind))
    best = ranked[0]
    best_score = _rank_sdk_path(best, kind=kind)[0]
    tied = [path for path in ranked if _rank_sdk_path(path, kind=kind)[0] == best_score]
    if len(tied) > 1:
        hashes = {_sha256_file(path) for path in tied}
        if len(hashes) != 1:
            joined = "\n  ".join(str(path) for path in tied)
            raise SaturnSblDirectMidiCompileProbeError(
                f"multiple non-identical best {filename} candidates exist:\n  {joined}"
            )
    return best


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def probe_saturn_sbl_direct_midi_compile(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnSblDirectMidiCompileProbeResult:
    """Compile the exact Sega Direct MIDI adapter in a fresh off-card directory."""

    saturn_root = _canonical(saturn_root)
    output_root = _canonical(output_directory)
    if output_root.exists():
        raise SaturnSblDirectMidiCompileProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    if compiler is None or not compiler.is_file():
        raise SaturnSblDirectMidiCompileProbeError(
            "SH-ELF GCC was not resolved from the supplied Saturn development root"
        )

    sega_header = _resolve_sdk_file(saturn_root, _SEGA_HEADER_NAME, kind="header")
    sega_library = _resolve_sdk_file(saturn_root, _SEGA_LIBRARY_NAME, kind="library")

    repo_root = _repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    source = source_dir / _SOURCE_NAME
    adapter_header = source_dir / _ADAPTER_HEADER_NAME
    inputs = {
        "source": source,
        "adapter_header": adapter_header,
        "sega_header": sega_header,
        "sega_library": sega_library,
    }
    hashes_before = {name: _sha256_file(path) for name, path in inputs.items()}
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
        f"-I{sega_header.parent}",
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
        hashes_after = {name: _sha256_file(path) for name, path in inputs.items()}
        sources_unchanged = hashes_after == hashes_before
        path_unchanged = os.environ.get("PATH") == path_before
        object_ok = object_path.is_file() and object_path.stat().st_size > 0
        object_sha = _sha256_file(object_path) if object_ok else None
        successful = returncode == 0 and object_ok and sources_unchanged and path_unchanged

        lines = [
            "SRK Sega Sound I/F Direct MIDI compiler gate",
            "==============================================",
            f"returncode={returncode}",
            "argv: " + " ".join(argv),
            f"sega_header={sega_header}",
            f"sega_library={sega_library}",
            "",
        ]
        if command_output:
            lines.extend((command_output.rstrip(), ""))
        for name in inputs:
            lines.append(f"{name}_sha256_before={hashes_before[name]}")
            lines.append(f"{name}_sha256_after={hashes_after[name]}")
        lines.extend(
            (
                f"source_inputs_unchanged={str(sources_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"object_present={str(object_ok).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.sbl-direct-midi-compile.v1",
            "successful": successful,
            "compiler": str(compiler),
            "inputs": {
                name: {"path": str(path), "sha256": hashes_before[name]}
                for name, path in inputs.items()
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
            "contract": {
                "header": "sega_snd.h",
                "function": "SND_CtrlDirMidi",
                "library_present": True,
                "library_linked": False,
            },
            "policy": {
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "inputs_unchanged": sources_unchanged,
                "linker_invoked": False,
                "iso_builder_invoked": False,
                "hardware_executed": False,
                "saroo_writes": False,
            },
        }
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temp_root.replace(output_root)
        return SaturnSblDirectMidiCompileProbeResult(
            output_root=output_root,
            compiler=compiler,
            sega_header=sega_header,
            sega_library=sega_library,
            object_path=(output_root / _OBJECT_NAME) if object_ok else None,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            source_sha256=hashes_before["source"],
            adapter_header_sha256=hashes_before["adapter_header"],
            sega_header_sha256=hashes_before["sega_header"],
            sega_library_sha256=hashes_before["sega_library"],
            object_sha256=object_sha,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def saturn_sbl_direct_midi_compile_flags() -> tuple[str, ...]:
    return _COMPILE_FLAGS
