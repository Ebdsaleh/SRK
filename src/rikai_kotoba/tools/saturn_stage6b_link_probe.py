"""Off-card Stage 6B mixed-format linker research probe.

The probe is narrower than the normal standalone builder: it creates only
compiler/assembler/linker outputs and never invokes ISO/SAROO paths.  Mjolnir's
SDK-wide symbol analysis established the complete dedicated SBL closure, so the
probe now consumes the same pinned link contract as the production builder
rather than carrying a second partial dependency recipe.
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


def _mixed_link_tail(deps: standalone.SaturnStage6BDependencies) -> tuple[str, ...]:
    """Expose the production Stage 6B link tail for probe/tests."""

    return standalone._stage6b_link_tail(deps)


def _validate_elf_archive(path: Path, label: str) -> ArchiveFormatSummary:
    try:
        report = inspect_binary(path)
    except (BinaryArchiveError, OSError) as exc:
        raise SaturnStage6BLinkProbeError(f"cannot inspect {label} archive: {exc}") from exc
    if report.container_kind != "unix-ar":
        raise SaturnStage6BLinkProbeError(f"{label} dependency is not a classic Unix ar archive")
    payloads = [member for member in report.members if not member.metadata]
    if not payloads:
        raise SaturnStage6BLinkProbeError(f"{label} archive has no payload members")
    for member in payloads:
        if member.signature.kind != "elf":
            raise SaturnStage6BLinkProbeError(
                f"{label} member {member.name} is not ELF: {member.signature.detail}"
            )
        if "ELF32 big-endian REL machine=SH(42)" not in member.signature.detail:
            raise SaturnStage6BLinkProbeError(
                f"{label} member {member.name} has unexpected ELF contract: "
                f"{member.signature.detail}"
            )
    return ArchiveFormatSummary(
        path=str(path),
        sha256=report.sha256,
        payload_members=len(payloads),
        object_format="elf32-sh",
        detail="all payload members are ELF32 big-endian SH relocatable objects",
    )


def _validate_gfs_elf_archive(path: Path) -> ArchiveFormatSummary:
    return _validate_elf_archive(path, "GFS")


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
                member_bytes = handle.read(member.size)
                header = parse_coff_file_header(member_bytes, total_size=member.size)
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
    deps = standalone._stage6b_gfs_dependencies(manifest)

    formats = {
        "gfs": _validate_gfs_elf_archive(deps.gfs_library),
        "cdc": _validate_cdc_coff_archive(deps.cdc_library),
        "dma": _validate_elf_archive(deps.dma_library, "DMA"),
        "csh": _validate_elf_archive(deps.csh_library, "cache"),
        "int": _validate_elf_archive(deps.int_library, "interrupt"),
    }

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
        f"-I{deps.include_dir}",
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
            *_mixed_link_tail(deps),
        )
        successful = invoke("link complete Stage 6B dependency closure", link_argv)

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
        "schema": "srk.saturn.stage6b-link-probe.v2",
        "project_root": str(root),
        "successful": successful,
        "purpose": "prove complete dedicated mixed-format Stage 6B SBL dependency closure",
        "formats": {
            name: asdict(summary) for name, summary in formats.items()
        },
        "link_contract": {
            "cdc_linker_override": "coff-sh",
            "post_cdc_linker_format": "elf32-sh",
            "library_order": [
                "sega_gfs.a",
                "SEGA_CDC.A",
                "sega_dma.a",
                "sega_csh.a",
                "sega_int.a",
                "-lgcc",
            ],
            "sega_sat_used": False,
            "segadgfs_used": False,
        },
        "policy": {
            "shell_used": False,
            "iso_builder_invoked": False,
            "sd_writes": False,
            "private_sdk_dependencies_copied": False,
            "source_inputs_verified_after_probe": inputs_verified_after,
            "private_sdk_dependencies_verified_after_probe": private_dependencies_verified_after,
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
            "Compile and link one fresh Stage 6B project off-card using the "
            "Mjolnir-proven dedicated mixed ELF/COFF SBL dependency closure."
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
    print("SRK Stage 6B complete mixed-format link probe")
    print("---------------------------------------------")
    print(f"Project : {root}")
    for name in ("gfs", "cdc", "dma", "csh", "int"):
        info = report["formats"][name]
        print(f"{name.upper():<7} : {info['object_format']} ({info['payload_members']} payload members)")
    print("Link    : GFS -> CDC[coff-sh] -> ELF DMA -> CSH -> INT -> libgcc")
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
