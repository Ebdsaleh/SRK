"""Off-card Stage 6B mixed ELF/COFF linker research probe.

This is deliberately narrower than the normal standalone builder.  It creates
only compiler/assembler/linker outputs in a fresh probe directory and never
runs the ISO builder or any SAROO deployment path.  Its purpose is to validate
one evidence-driven linker change before that change is promoted into the
normal Python-native builder.

The installed SBL 6.01 GFS archive is expected to contain ELF32 big-endian SH
relocatable objects.  The installed CDC archive is expected to contain Hitachi
SH big-endian COFF objects.  GNU ld's input-format override is therefore scoped
only to the CDC archive and reset to ELF before libgcc is searched.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Callable, Optional, Sequence

from rikai_kotoba.core.binary_archive import BinaryArchiveError, inspect_binary
from rikai_kotoba.core.coff import CoffFormatError, parse_coff_file_header
from rikai_kotoba.hardware.saturn import standalone_build as standalone


_PROBE_DIR = "stage6b-link-probe"
_PROBE_LOG = "SRK_STAGE6B_LINK_PROBE_LOG.txt"
_PROBE_REPORT = "SRK_STAGE6B_LINK_PROBE.json"


class SaturnStage6BLinkProbeError(RuntimeError):
    """Raised when the bounded Stage 6B link probe cannot run safely."""


@dataclass(frozen=True)
class ProbeCommand:
    label: str
    argv: tuple[str, ...]
    returncode: int
    output: str


@dataclass(frozen=True)
class ArchiveFormatSummary:
    path: str
    sha256: str
    payload_members: int
    object_format: str
    detail: str


def _mixed_link_tail(gfs_library: Path, cdc_library: Path) -> tuple[str, ...]:
    """Return the evidence-driven mixed-format library tail for GNU ld."""

    return (
        str(gfs_library),
        "-Wl,--format=coff-sh",
        str(cdc_library),
        "-Wl,--format=elf32-sh",
        "-lgcc",
    )


def _validate_gfs_elf_archive(path: Path) -> ArchiveFormatSummary:
    try:
        report = inspect_binary(path)
    except (BinaryArchiveError, OSError) as exc:
        raise SaturnStage6BLinkProbeError(f"cannot inspect GFS archive: {exc}") from exc

    if report.container_kind != "unix-ar":
        raise SaturnStage6BLinkProbeError("GFS dependency is not a classic Unix ar archive")

    payloads = [member for member in report.members if not member.metadata]
    if not payloads:
        raise SaturnStage6BLinkProbeError("GFS archive has no payload members")
    for member in payloads:
        if member.signature.kind != "elf":
            raise SaturnStage6BLinkProbeError(
                f"GFS member {member.name} is not ELF: {member.signature.detail}"
            )
        if "ELF32 big-endian REL machine=SH(42)" not in member.signature.detail:
            raise SaturnStage6BLinkProbeError(
                f"GFS member {member.name} has unexpected ELF contract: "
                f"{member.signature.detail}"
            )

    return ArchiveFormatSummary(
        path=str(path),
        sha256=report.sha256,
        payload_members=len(payloads),
        object_format="elf32-sh",
        detail="all payload members are ELF32 big-endian SH relocatable objects",
    )


def _validate_cdc_coff_archive(path: Path) -> ArchiveFormatSummary:
    try:
        report = inspect_binary(path)
    except (BinaryArchiveError, OSError) as exc:
        raise SaturnStage6BLinkProbeError(f"cannot inspect CDC archive: {exc}") from exc

    if report.container_kind != "unix-ar":
        raise SaturnStage6BLinkProbeError("CDC dependency is not a classic Unix ar archive")

    payloads = [member for member in report.members if not member.metadata]
    if not payloads:
        raise SaturnStage6BLinkProbeError("CDC archive has no payload members")

    try:
        with path.open("rb") as handle:
            for member in payloads:
                handle.seek(member.data_offset)
                header_bytes = handle.read(20)
                header = parse_coff_file_header(header_bytes, total_size=member.size)
                if header.byte_order != "big" or header.magic != 0x0500:
                    raise SaturnStage6BLinkProbeError(
                        f"CDC member {member.name} is not Hitachi SH big-endian COFF"
                    )
    except (OSError, CoffFormatError) as exc:
        raise SaturnStage6BLinkProbeError(f"CDC COFF validation failed: {exc}") from exc

    return ArchiveFormatSummary(
        path=str(path),
        sha256=report.sha256,
        payload_members=len(payloads),
        object_format="coff-sh",
        detail="all payload members have Hitachi SH big-endian COFF magic 0x0500",
    )


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _write_log(path: Path, commands: Sequence[ProbeCommand]) -> None:
    lines: list[str] = []
    for command in commands:
        lines.append(f"[{command.label}] returncode={command.returncode}")
        lines.append("argv: " + " ".join(command.argv))
        if command.output:
            lines.append(command.output.rstrip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run_stage6b_link_probe(
    project_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> int:
    root = Path(project_directory).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise SaturnStage6BLinkProbeError(f"project directory is not a directory: {root}")

    report_path = root / _PROBE_REPORT
    log_path = root / _PROBE_LOG
    probe_dir = root / _PROBE_DIR
    if report_path.exists() or log_path.exists() or probe_dir.exists():
        raise SaturnStage6BLinkProbeError(
            "Stage 6B link-probe provenance already exists; use a fresh prepared project"
        )

    manifest = standalone._load_manifest(root)
    standalone._verify_generated_inputs(root, manifest)
    standalone._packaged_pcm_manifest(root, manifest)
    include_dir, _header, gfs_library, cdc_library = standalone._stage6b_gfs_dependencies(
        manifest
    )

    gfs_summary = _validate_gfs_elf_archive(gfs_library)
    cdc_summary = _validate_cdc_coff_archive(cdc_library)

    gcc = standalone._tool(manifest, "sh-elf-gcc")
    assembler = standalone._tool(manifest, "sh-elf-as")
    probe_dir.mkdir()

    runner = _runner or subprocess.run
    commands: list[ProbeCommand] = []

    def invoke(label: str, argv: Sequence[str]) -> bool:
        completed = runner(
            [str(item) for item in argv],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        command = ProbeCommand(
            label=label,
            argv=tuple(str(item) for item in argv),
            returncode=int(getattr(completed, "returncode", 1)),
            output=_decode_output(getattr(completed, "stdout", b"")),
        )
        commands.append(command)
        return command.returncode == 0

    compile_flags = (
        "-Wall",
        "-Werror",
        "-m2",
        "-O0",
        "-ffreestanding",
        "-fno-builtin",
        "-Isrc",
        f"-I{include_dir}",
    )

    objects: list[str] = []
    successful = True
    for source in standalone._C_SOURCES:
        obj = f"{_PROBE_DIR}/{Path(source).stem}.o"
        objects.append(obj)
        if not invoke(
            f"compile {source}",
            (str(gcc), "-c", f"src/{source}", "-o", obj, *compile_flags),
        ):
            successful = False
            break

    startup_object = f"{_PROBE_DIR}/srk_saturn_startup.o"
    if successful:
        successful = invoke(
            "assemble startup",
            (str(assembler), "src/srk_saturn_startup.S", "-o", startup_object),
        )

    if successful:
        link_argv = (
            str(gcc),
            "-nostdlib",
            "-m2",
            "-Wl,--script,srk_saturn.ld",
            f"-Wl,-Map,{_PROBE_DIR}/srk_diag.map",
            "-o",
            f"{_PROBE_DIR}/srk_diag.bin",
            startup_object,
            *objects,
            *_mixed_link_tail(gfs_library, cdc_library),
        )
        successful = invoke("link mixed ELF/COFF binary", link_argv)

    inputs_verified_after = False
    private_dependencies_verified_after = False
    try:
        standalone._verify_generated_inputs(root, manifest)
        standalone._packaged_pcm_manifest(root, manifest)
        standalone._stage6b_gfs_dependencies(manifest)
        inputs_verified_after = True
        private_dependencies_verified_after = True
    except standalone.SaturnStandaloneBuildError as exc:
        successful = False
        commands.append(
            ProbeCommand(
                label="verify generated/private inputs",
                argv=tuple(),
                returncode=1,
                output=str(exc),
            )
        )

    binary_path = probe_dir / "srk_diag.bin"
    if successful and (not binary_path.is_file() or binary_path.stat().st_size <= 0):
        successful = False
        commands.append(
            ProbeCommand(
                label="verify linked binary",
                argv=tuple(),
                returncode=1,
                output="link returned success but probe binary is missing or empty",
            )
        )

    _write_log(log_path, commands)
    report = {
        "schema": "srk.saturn.stage6b-link-probe.v1",
        "project_root": str(root),
        "successful": successful,
        "purpose": "prove mixed ELF GFS plus Hitachi SH COFF CDC link contract",
        "formats": {
            "gfs": asdict(gfs_summary),
            "cdc": asdict(cdc_summary),
            "cdc_linker_override": "coff-sh",
            "post_cdc_linker_format": "elf32-sh",
        },
        "policy": {
            "shell_used": False,
            "iso_builder_invoked": False,
            "sd_writes": False,
            "private_sdk_dependencies_copied": False,
            "source_inputs_verified_after_probe": inputs_verified_after,
            "private_sdk_dependencies_verified_after_probe": (
                private_dependencies_verified_after
            ),
        },
        "commands": [asdict(command) for command in commands],
        "binary": (
            {
                "path": binary_path.relative_to(root).as_posix(),
                "size": binary_path.stat().st_size,
                "sha256": standalone._sha256_file(binary_path),
            }
            if binary_path.is_file()
            else None
        ),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if successful else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="srk-saturn-stage6b-link-probe",
        description=(
            "Compile and link one fresh Stage 6B project off-card while explicitly "
            "disambiguating the installed Hitachi SH COFF CDC archive."
        ),
    )
    parser.add_argument("--project", required=True, help="Fresh prepared Stage 6B project tree")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_stage6b_link_probe(args.project)
    except (SaturnStage6BLinkProbeError, standalone.SaturnStandaloneBuildError) as exc:
        print(f"srk-saturn-stage6b-link-probe: {type(exc).__name__}: {exc}")
        return 2

    root = Path(args.project).expanduser().resolve(strict=False)
    report = json.loads((root / _PROBE_REPORT).read_text(encoding="utf-8"))
    print("SRK Stage 6B mixed ELF/COFF link probe")
    print("--------------------------------------")
    print(f"Project : {root}")
    print(f"GFS     : {report['formats']['gfs']['object_format']} "
          f"({report['formats']['gfs']['payload_members']} payload members)")
    print(f"CDC     : {report['formats']['cdc']['object_format']} "
          f"({report['formats']['cdc']['payload_members']} payload members)")
    print("Override: --format=coff-sh for CDC; reset elf32-sh before libgcc")
    for command in report["commands"]:
        print(f"  [{command['returncode']}] {command['label']}")
        if command["returncode"] and command["output"]:
            for line in command["output"].splitlines():
                print(f"      {line}")
    print(f"Result  : {'SUCCESS' if report['successful'] else 'FAILED'}")
    print(f"Log     : {root / _PROBE_LOG}")
    print(f"Report  : {root / _PROBE_REPORT}")
    print("No ISO builder or SAROO/card write was executed.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
