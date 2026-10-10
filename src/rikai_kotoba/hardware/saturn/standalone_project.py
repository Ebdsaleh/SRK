"""Generate SRK's isolated standalone Sega Saturn diagnostics project.

The generated tree is deliberately separate from the user's installed Saturn
SDK/examples. It combines SRK-owned standalone host/startup/linker sources, the
reusable diagnostics core, one reviewed local bitmap-font asset, a deterministic
SRK-owned PCM payload, and a patched copy of a caller-supplied Saturn IP.BIN.
Source SDK/example trees are read only.

Generation does not compile, link, package, execute, or modify PATH. The
preferred build path is SRK's Python-native standalone builder. ``build.bat`` is
only a thin convenience wrapper around that Python command; it contains no
compiler/linker/package recipe of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from rikai_kotoba.formats.saturn.ip_bin import (
    parse_saturn_system_id,
    patch_saturn_system_id,
)
from rikai_kotoba.formats.saturn.packaged_pcm import (
    PACKAGED_PCM_CHANNELS_MONO,
    PACKAGED_PCM_ENCODING_PCM16_BE,
    PACKAGED_PCM_FILENAME,
    PACKAGED_PCM_LOOP_END,
    PACKAGED_PCM_LOOP_START,
    PACKAGED_PCM_SAMPLE_COUNT,
    PACKAGED_PCM_VERSION,
    build_deterministic_packaged_pcm,
)
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnStandaloneProjectError(RuntimeError):
    """Raised when an isolated standalone project cannot be prepared safely."""


@dataclass(frozen=True)
class SaturnStandaloneProjectResult:
    output_root: Path
    source_root: Path
    build_script: Path
    ip_bin: Path
    packaged_pcm: Path
    manifest: Path
    gcc: Path
    assembler: Path
    iso_builder: Path


_DIAGNOSTIC_FILES = (
    "srk_diag_app.c",
    "srk_diag_app.h",
    "srk_diag_audio.c",
    "srk_diag_audio.h",
    "srk_diag_flight_recorder.c",
    "srk_diag_flight_recorder.h",
    "srk_diag_host.h",
    "srk_diag_input.c",
    "srk_diag_input.h",
    "srk_diag_menu.c",
    "srk_diag_menu.h",
    "srk_diag_vdp1.c",
    "srk_diag_vdp1.h",
    "srk_diag_video.c",
    "srk_diag_video.h",
)

_STANDALONE_FILES = (
    "srk_saturn_audio.c",
    "srk_saturn_audio.h",
    "srk_saturn_host.c",
    "srk_saturn_host.h",
    "srk_saturn_main.c",
    "srk_saturn_packaged_pcm.c",
    "srk_saturn_packaged_pcm.h",
    "srk_saturn_startup.S",
)

_STAGE6B_SBL_ROOT = Path("SaturnOrbit-Inspect/payload/app/SBL_601/SEGALIB")


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
        if (parent / "integrations" / "saturn" / "diagnostics").is_dir():
            return parent
    raise SaturnStandaloneProjectError(
        "cannot locate SRK repository integrations/saturn/diagnostics source"
    )


def _require_file(path: Path, description: str) -> Path:
    if not path.is_file():
        raise SaturnStandaloneProjectError(f"{description} is not a file: {path}")
    return path


def _private_dependency(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _stage6b_gfs_dependencies(saturn_root: Path) -> dict[str, object]:
    segalib = saturn_root / _STAGE6B_SBL_ROOT
    include_dir = segalib / "INCLUDE"
    lib_dir = segalib / "LIB_ELF"
    gfs_header = _require_file(include_dir / "SEGA_GFS.H", "SBL 6.01 GFS header")
    gfs_library = _require_file(lib_dir / "sega_gfs.a", "SBL 6.01 ELF GFS library")
    cdc_library = _require_file(lib_dir / "SEGA_CDC.A", "SBL 6.01 ELF CDC library")
    return {
        "include_dir": str(include_dir.resolve()),
        "gfs_header": _private_dependency(gfs_header.resolve()),
        "gfs_library": _private_dependency(gfs_library.resolve()),
        "cdc_library": _private_dependency(cdc_library.resolve()),
        "copied_into_project": False,
    }


def _build_script() -> str:
    lines = [
        "@echo off",
        "setlocal",
        "python -m rikai_kotoba.tools.saturn_standalone_build --project \"%~dp0.\"",
        "exit /b %errorlevel%",
        "",
    ]
    return "\r\n".join(lines)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def prepare_saturn_standalone_project(
    saturn_root: os.PathLike[str] | str,
    template_directory: os.PathLike[str] | str,
    ip_bin_source: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    release_date: str | None = None,
) -> SaturnStandaloneProjectResult:
    """Prepare an isolated, not-yet-built SRK Saturn diagnostics project."""

    saturn_root = _canonical(saturn_root)
    template_directory = _canonical(template_directory)
    ip_bin_source = _canonical(ip_bin_source)
    output_root = _canonical(output_directory)

    if output_root.exists():
        raise SaturnStandaloneProjectError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )
    if not template_directory.is_dir():
        raise SaturnStandaloneProjectError(
            f"reviewed template directory is not a directory: {template_directory}"
        )

    font_source = _require_file(
        template_directory / "vga_font.h",
        "reviewed vdp1ex VGA font",
    )
    _require_file(ip_bin_source, "reviewed Saturn IP.BIN source")

    environment = inspect_saturn_standalone_environment(saturn_root)
    if not environment.compiler_ready:
        missing = ", ".join(environment.compiler.missing)
        raise SaturnStandaloneProjectError(
            f"SH-ELF compiler set is incomplete: {missing or 'unknown missing tools'}"
        )

    gcc = environment.compiler.path_for("sh-elf-gcc")
    assembler = environment.compiler.path_for("sh-elf-as")
    iso_probe = environment.tool_for("iso-builder")
    iso_builder = iso_probe.resolved_path if iso_probe else None
    if gcc is None or assembler is None:
        raise SaturnStandaloneProjectError("SH-ELF gcc/as paths were not resolved")
    if iso_builder is None:
        raise SaturnStandaloneProjectError("mkisofs/genisoimage/xorriso was not resolved")

    stage6b_gfs = _stage6b_gfs_dependencies(saturn_root)

    repo_root = _repo_root()
    diagnostics_source = repo_root / "integrations" / "saturn" / "diagnostics"
    standalone_source = repo_root / "integrations" / "saturn" / "standalone"
    for filename in _DIAGNOSTIC_FILES:
        _require_file(diagnostics_source / filename, f"SRK diagnostic core {filename}")
    for filename in _STANDALONE_FILES:
        _require_file(standalone_source / filename, f"SRK standalone host {filename}")
    linker_source = _require_file(
        standalone_source / "srk_saturn.ld",
        "SRK standalone linker script",
    )

    base_ip = ip_bin_source.read_bytes()
    metadata = parse_saturn_system_id(base_ip)
    if metadata.get("hardware_id") != "SEGA SEGASATURN":
        raise SaturnStandaloneProjectError(
            "reviewed IP.BIN does not contain the expected SEGA SEGASATURN hardware ID"
        )

    if release_date is None:
        release_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    if len(release_date) != 8 or not release_date.isdigit():
        raise SaturnStandaloneProjectError("release_date must be exactly YYYYMMDD")

    patched_ip = patch_saturn_system_id(
        base_ip,
        maker_id="SRK PROJECT",
        product_number="SRK-DIAG",
        game_version="V0.001",
        game_date=release_date,
        device_info="CD-1/1",
        area_symbols="JTUE",
        peripherals="J",
        game_title="SRK SATURN DIAGNOSTICS",
        first_read_address=0x06004000,
        first_read_size=0,
    )
    packaged_pcm = build_deterministic_packaged_pcm()

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    try:
        source_root = temp_root / "src"
        source_root.mkdir()
        (temp_root / "build").mkdir()
        cd_root = temp_root / "cd"
        cd_root.mkdir()

        for filename in _DIAGNOSTIC_FILES:
            shutil.copy2(diagnostics_source / filename, source_root / filename)
        for filename in _STANDALONE_FILES:
            shutil.copy2(standalone_source / filename, source_root / filename)
        shutil.copy2(font_source, source_root / "vga_font.h")
        shutil.copy2(linker_source, temp_root / "srk_saturn.ld")

        (temp_root / "IP.BIN").write_bytes(patched_ip)
        packaged_pcm_path = cd_root / PACKAGED_PCM_FILENAME
        packaged_pcm_path.write_bytes(packaged_pcm)
        _write_text(temp_root / "build.bat", _build_script())
        _write_text(
            temp_root / "README_BUILD.txt",
            "SRK Saturn Diagnostics Generated Project\n"
            "========================================\n\n"
            "This tree was generated separately from the installed Saturn SDK/example tree.\n"
            "The source template, IP.BIN, and private SBL dependencies were read only.\n\n"
            "cd\\SRKPCM.BIN is an SRK-owned deterministic packaged PCM payload.\n"
            "Its exact bytes are pinned in the project manifest and verified again inside the ISO.\n\n"
            "Stage 6B compiles against the installed SBL 6.01 SEGA_GFS.H and links the\n"
            "installed ELF sega_gfs.a + SEGA_CDC.A by absolute path. Their exact hashes\n"
            "are pinned in the manifest; they are never copied into this generated tree.\n\n"
            "Preferred build (from the SRK virtual environment):\n"
            "  python -m rikai_kotoba.tools.saturn_standalone_build --project <this-directory>\n\n"
            "build.bat is only a thin wrapper around the same Python-native command.\n"
            "Python orchestrates the recorded SH-ELF gcc/as and mkisofs executables directly;\n"
            "GNU Make and shell build recipes are not used.\n\n"
            "The ISO is an internal verification/intermediate artifact.\n"
            "The deployable SAROO image is build\\SRK-Diagnostics\\SRK-Diagnostics.cue + .bin.\n\n"
            "Project generation and building do not write the SAROO SD card.\n"
            "Deployment remains a separate guarded operation.\n",
        )

        generated_files = []
        for path in sorted(temp_root.rglob("*"), key=lambda item: str(item).casefold()):
            if path.is_file() and path.name != "SRK_STANDALONE_PROJECT.json":
                generated_files.append(
                    {
                        "path": path.relative_to(temp_root).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": _sha256_file(path),
                    }
                )

        manifest_data = {
            "schema": "srk.saturn.standalone-project.v1",
            "mode": "standalone-master",
            "build_orchestration": "python-native",
            "deployable_format": "cue-bin-mode1-2352",
            "policy": {
                "source_trees_read_only": True,
                "build_executed": False,
                "sd_writes": False,
                "commercial_image_changes": False,
                "private_sdk_dependencies_copied": False,
            },
            "load_address": "0x06004000",
            "template_directory": str(template_directory),
            "font_source": str(font_source),
            "font_source_sha256": _sha256_file(font_source),
            "ip_bin_source": str(ip_bin_source),
            "ip_bin_source_sha256": _sha256_file(ip_bin_source),
            "generated_ip_bin_sha256": _sha256_file(temp_root / "IP.BIN"),
            "generated_ip_metadata": parse_saturn_system_id(patched_ip),
            "packaged_pcm": {
                "path": f"cd/{PACKAGED_PCM_FILENAME}",
                "version": PACKAGED_PCM_VERSION,
                "encoding": "pcm16-be-signed",
                "encoding_id": PACKAGED_PCM_ENCODING_PCM16_BE,
                "channels": PACKAGED_PCM_CHANNELS_MONO,
                "sample_count": PACKAGED_PCM_SAMPLE_COUNT,
                "loop_start": PACKAGED_PCM_LOOP_START,
                "loop_end": PACKAGED_PCM_LOOP_END,
                "size": packaged_pcm_path.stat().st_size,
                "sha256": _sha256_file(packaged_pcm_path),
            },
            "stage6b_gfs": stage6b_gfs,
            "tools": {
                "sh-elf-gcc": str(gcc),
                "sh-elf-as": str(assembler),
                "iso-builder": str(iso_builder),
            },
            "generated_files": generated_files,
        }
        manifest_path = temp_root / "SRK_STANDALONE_PROJECT.json"
        _write_text(
            manifest_path,
            json.dumps(manifest_data, indent=2, sort_keys=True) + "\n",
        )

        temp_root.rename(output_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    return SaturnStandaloneProjectResult(
        output_root=output_root,
        source_root=output_root / "src",
        build_script=output_root / "build.bat",
        ip_bin=output_root / "IP.BIN",
        packaged_pcm=output_root / "cd" / PACKAGED_PCM_FILENAME,
        manifest=output_root / "SRK_STANDALONE_PROJECT.json",
        gcc=gcc,
        assembler=assembler,
        iso_builder=iso_builder,
    )