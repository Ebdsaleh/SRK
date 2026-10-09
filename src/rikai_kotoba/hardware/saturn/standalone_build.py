"""Python-native build orchestration for generated SRK Saturn projects.

The SH-ELF tools remain the actual compiler/assembler/linker backend. Python
replaces the fragile historical make/shell orchestration: every child process is
invoked directly with an argv list, PATH is not mutated, source/input hashes are
checked before and after the build, and one immutable-style build report is
published into the generated project.

The ISO9660 image produced by mkisofs is retained as an internal verification
artifact. Python then converts it to a verified single-track MODE1/2352 BIN/CUE
pair suitable for SRK's SAROO deployment workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import subprocess
from typing import Callable, Sequence

from rikai_kotoba.formats.saturn.mode1_image import (
    SaturnMode1ImageError,
    SaturnMode1ImageResult,
    write_single_track_mode1_bin_cue,
)


class SaturnStandaloneBuildError(RuntimeError):
    """Raised when a generated standalone project cannot be built safely."""


@dataclass(frozen=True)
class SaturnStandaloneBuildArtifact:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class SaturnStandaloneBuildCommand:
    label: str
    argv: tuple[str, ...]
    returncode: int
    output: str


@dataclass(frozen=True)
class SaturnStandaloneBuildResult:
    project_root: Path
    log_path: Path
    report_path: Path
    commands: tuple[SaturnStandaloneBuildCommand, ...]
    artifacts: tuple[SaturnStandaloneBuildArtifact, ...]
    successful: bool


_C_SOURCES = (
    "srk_saturn_main.c",
    "srk_saturn_host.c",
    "srk_diag_app.c",
    "srk_diag_input.c",
    "srk_diag_menu.c",
    "srk_diag_flight_recorder.c",
    "srk_diag_vdp1.c",
    "srk_diag_video.c",
)

_OBJECTS = tuple(f"build/{Path(source).stem}.o" for source in _C_SOURCES)
_STARTUP_OBJECT = "build/srk_saturn_startup.o"
_MANIFEST_NAME = "SRK_STANDALONE_PROJECT.json"
_REPORT_NAME = "SRK_STANDALONE_BUILD.json"
_LOG_NAME = "SRK_STANDALONE_BUILD_LOG.txt"
_DEPLOY_DIRECTORY = "build/SRK-Diagnostics"
_DEPLOY_BIN = f"{_DEPLOY_DIRECTORY}/SRK-Diagnostics.bin"
_DEPLOY_CUE = f"{_DEPLOY_DIRECTORY}/SRK-Diagnostics.cue"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(root: Path) -> dict:
    path = root / _MANIFEST_NAME
    if not path.is_file():
        raise SaturnStandaloneBuildError(f"project manifest is missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaturnStandaloneBuildError(f"cannot read project manifest: {exc}") from exc
    if data.get("schema") != "srk.saturn.standalone-project.v1":
        raise SaturnStandaloneBuildError("unsupported standalone project manifest schema")
    if data.get("mode") != "standalone-master":
        raise SaturnStandaloneBuildError("project manifest is not standalone-master mode")
    return data


def _verify_generated_inputs(root: Path, manifest: dict) -> None:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list) or not entries:
        raise SaturnStandaloneBuildError("project manifest has no generated file inventory")

    for entry in entries:
        if not isinstance(entry, dict):
            raise SaturnStandaloneBuildError("invalid generated file inventory entry")
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise SaturnStandaloneBuildError("invalid generated file inventory metadata")
        path = root / relative
        if not path.is_file():
            raise SaturnStandaloneBuildError(f"generated project input is missing: {relative}")
        actual = _sha256_file(path)
        if actual.lower() != expected.lower():
            raise SaturnStandaloneBuildError(
                f"generated project input hash mismatch: {relative}; "
                f"expected {expected}, got {actual}"
            )


def _tool(manifest: dict, key: str) -> Path:
    tools = manifest.get("tools")
    if not isinstance(tools, dict):
        raise SaturnStandaloneBuildError("project manifest has no tool inventory")
    value = tools.get(key)
    if not isinstance(value, str) or not value:
        raise SaturnStandaloneBuildError(f"project manifest has no {key} tool path")
    path = _canonical(value)
    if not path.is_file():
        raise SaturnStandaloneBuildError(f"recorded {key} tool does not exist: {path}")
    return path


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _artifact(path: Path) -> SaturnStandaloneBuildArtifact:
    return SaturnStandaloneBuildArtifact(
        path=path,
        size=path.stat().st_size,
        sha256=_sha256_file(path),
    )


def _write_log(path: Path, commands: Sequence[SaturnStandaloneBuildCommand]) -> None:
    lines: list[str] = []
    for command in commands:
        lines.append(f"[{command.label}] returncode={command.returncode}")
        lines.append("argv: " + " ".join(command.argv))
        if command.output:
            lines.append(command.output.rstrip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _write_report(
    path: Path,
    root: Path,
    manifest_path: Path,
    commands: Sequence[SaturnStandaloneBuildCommand],
    artifacts: Sequence[SaturnStandaloneBuildArtifact],
    successful: bool,
    inputs_verified_after: bool,
    mode1_result: SaturnMode1ImageResult | None,
) -> None:
    data = {
        "schema": "srk.saturn.standalone-build.v1",
        "project_root": str(root),
        "project_manifest_sha256": _sha256_file(manifest_path),
        "orchestration": "python-native",
        "successful": bool(successful),
        "policy": {
            "shell_used": False,
            "path_mutated": False,
            "source_inputs_verified_before_build": True,
            "source_inputs_verified_after_build": bool(inputs_verified_after),
            "sd_writes": False,
            "commercial_image_changes": False,
        },
        "commands": [
            {
                "label": command.label,
                "argv": list(command.argv),
                "returncode": command.returncode,
            }
            for command in commands
        ],
        "artifacts": [
            {
                "path": artifact.path.relative_to(root).as_posix(),
                "size": artifact.size,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
    }
    if mode1_result is not None:
        data["deployable"] = {
            "format": "cue-bin-mode1-2352",
            "cue": mode1_result.cue_path.relative_to(root).as_posix(),
            "bin": mode1_result.bin_path.relative_to(root).as_posix(),
            "sector_count": mode1_result.sector_count,
            "user_bytes": mode1_result.user_bytes,
            "raw_bytes": mode1_result.raw_bytes,
            "verified_against_iso": True,
        }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_saturn_standalone_project(
    project_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnStandaloneBuildResult:
    """Build one fresh generated Saturn project without make or shell scripts.

    GCC/binutils are still the SH-2 code-generation backend. Python owns the
    orchestration and invokes each recorded executable directly with shell=False.
    A project that already contains a Python-native build report is refused so
    every generated tree preserves one build attempt as provenance.
    """

    root = _canonical(project_directory)
    if not root.is_dir():
        raise SaturnStandaloneBuildError(f"project directory is not a directory: {root}")

    manifest_path = root / _MANIFEST_NAME
    report_path = root / _REPORT_NAME
    log_path = root / _LOG_NAME
    if report_path.exists() or log_path.exists():
        raise SaturnStandaloneBuildError(
            "Python-native build provenance already exists; generate a fresh project tree"
        )

    manifest = _load_manifest(root)
    _verify_generated_inputs(root, manifest)

    gcc = _tool(manifest, "sh-elf-gcc")
    assembler = _tool(manifest, "sh-elf-as")
    iso_builder = _tool(manifest, "iso-builder")

    build_dir = root / "build"
    cd_dir = root / "cd"
    build_dir.mkdir(exist_ok=True)
    cd_dir.mkdir(exist_ok=True)
    if any(build_dir.iterdir()) or (cd_dir / "0.bin").exists():
        raise SaturnStandaloneBuildError(
            "build outputs already exist; generate a fresh project tree to preserve provenance"
        )

    runner = _runner or subprocess.run
    commands: list[SaturnStandaloneBuildCommand] = []

    def invoke(label: str, argv: Sequence[str]) -> bool:
        completed = runner(
            [str(item) for item in argv],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        returncode = int(getattr(completed, "returncode", 1))
        output = _decode_output(getattr(completed, "stdout", b""))
        commands.append(
            SaturnStandaloneBuildCommand(
                label=label,
                argv=tuple(str(item) for item in argv),
                returncode=returncode,
                output=output,
            )
        )
        return returncode == 0

    compile_flags = (
        "-Wall",
        "-Werror",
        "-m2",
        "-O0",
        "-ffreestanding",
        "-fno-builtin",
        "-Isrc",
    )

    successful = True
    for source in _C_SOURCES:
        obj = f"build/{Path(source).stem}.o"
        argv = (str(gcc), "-c", f"src/{source}", "-o", obj, *compile_flags)
        if not invoke(f"compile {source}", argv):
            successful = False
            break

    if successful:
        successful = invoke(
            "assemble startup",
            (str(assembler), "src/srk_saturn_startup.S", "-o", _STARTUP_OBJECT),
        )

    if successful:
        link_argv = (
            str(gcc),
            "-nostdlib",
            "-m2",
            "-Wl,--script,srk_saturn.ld",
            "-Wl,-Map,build/srk_diag.map",
            "-o",
            "build/srk_diag.bin",
            _STARTUP_OBJECT,
            *_OBJECTS,
            "-lgcc",
        )
        successful = invoke("link binary", link_argv)

    binary = build_dir / "srk_diag.bin"
    if successful:
        if not binary.is_file() or binary.stat().st_size <= 0:
            successful = False
            commands.append(
                SaturnStandaloneBuildCommand(
                    label="verify binary",
                    argv=tuple(),
                    returncode=1,
                    output="link command returned success but build/srk_diag.bin is missing or empty",
                )
            )
        else:
            shutil.copy2(binary, cd_dir / "0.bin")

    if successful:
        iso_prefix: tuple[str, ...] = (str(iso_builder),)
        if iso_builder.name.casefold().startswith("xorriso"):
            iso_prefix = (str(iso_builder), "-as", "mkisofs")
        iso_argv = (
            *iso_prefix,
            "-quiet",
            "-sysid", "SEGA SATURN",
            "-volid", "SRKDIAG",
            "-volset", "SRKDIAG",
            "-publisher", "SRK PROJECT",
            "-preparer", "SRK",
            "-appid", "SRK SATURN DIAGNOSTICS",
            "-generic-boot", "IP.BIN",
            "-full-iso9660-filenames",
            "-o", "build/srk_diag.iso",
            "cd",
        )
        successful = invoke("package ISO", iso_argv)

    iso = build_dir / "srk_diag.iso"
    if successful and (not iso.is_file() or iso.stat().st_size <= 0):
        successful = False
        commands.append(
            SaturnStandaloneBuildCommand(
                label="verify ISO",
                argv=tuple(),
                returncode=1,
                output="ISO builder returned success but build/srk_diag.iso is missing or empty",
            )
        )

    mode1_result: SaturnMode1ImageResult | None = None
    if successful:
        deploy_dir = root / _DEPLOY_DIRECTORY
        deploy_dir.mkdir(parents=True, exist_ok=False)
        try:
            mode1_result = write_single_track_mode1_bin_cue(
                iso,
                root / _DEPLOY_BIN,
                root / _DEPLOY_CUE,
            )
            commands.append(
                SaturnStandaloneBuildCommand(
                    label="package MODE1/2352 BIN/CUE",
                    argv=tuple(),
                    returncode=0,
                    output=(
                        f"{mode1_result.sector_count} sectors; "
                        f"{mode1_result.raw_bytes} raw bytes; verified against ISO"
                    ),
                )
            )
        except (OSError, SaturnMode1ImageError) as exc:
            successful = False
            commands.append(
                SaturnStandaloneBuildCommand(
                    label="package MODE1/2352 BIN/CUE",
                    argv=tuple(),
                    returncode=1,
                    output=str(exc),
                )
            )

    inputs_verified_after = False
    if successful:
        try:
            _verify_generated_inputs(root, manifest)
            inputs_verified_after = True
        except SaturnStandaloneBuildError as exc:
            successful = False
            commands.append(
                SaturnStandaloneBuildCommand(
                    label="verify generated inputs",
                    argv=tuple(),
                    returncode=1,
                    output=str(exc),
                )
            )

    artifacts: list[SaturnStandaloneBuildArtifact] = []
    for relative in (
        "build/srk_diag.bin",
        "build/srk_diag.iso",
        "build/srk_diag.map",
        "cd/0.bin",
        _DEPLOY_BIN,
        _DEPLOY_CUE,
    ):
        path = root / relative
        if path.is_file():
            artifacts.append(_artifact(path))

    _write_log(log_path, commands)
    _write_report(
        report_path,
        root,
        manifest_path,
        commands,
        artifacts,
        successful,
        inputs_verified_after,
        mode1_result if successful else None,
    )

    return SaturnStandaloneBuildResult(
        project_root=root,
        log_path=log_path,
        report_path=report_path,
        commands=tuple(commands),
        artifacts=tuple(artifacts),
        successful=successful,
    )
