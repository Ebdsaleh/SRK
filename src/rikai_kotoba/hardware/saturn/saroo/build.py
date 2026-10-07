"""Controlled builds for an SRK-generated SAROO ``Firm_Saturn`` tree.

The build runner only accepts a tree produced by SRK's source-preparation step.
It resolves the external SH-ELF programs from an explicit toolchain root, creates
one process-local PATH for the child build, captures complete command output,
and hashes the expected artifacts. It never installs or flashes firmware and it
never mutates the caller's process environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import subprocess
import sys
from typing import Mapping

from .toolchain import SarooToolchainReport, inspect_saroo_toolchain


class SarooBuildError(RuntimeError):
    """Raised when a controlled Firm_Saturn build cannot be started safely."""


@dataclass(frozen=True)
class SarooBuildArtifact:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class SarooBuildResult:
    generated_root: Path
    firm_saturn_directory: Path
    toolchain_root: Path
    log_path: Path
    clean_returncode: int
    build_returncode: int | None
    artifacts: tuple[SarooBuildArtifact, ...]
    successful: bool


_EXPECTED_ARTIFACTS = ("ssfirm.elf", "ssfirm.bin", "dump.txt")
_INTEGRATION_MARKER = "SRK_INTEGRATION.txt"
_BUILD_HELPER = "srk_build_support.py"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _artifact(path: Path) -> SarooBuildArtifact:
    stat = path.stat()
    return SarooBuildArtifact(path=path, size=stat.st_size, sha256=_hash_file(path))


def _unique_log_path(generated_root: Path, requested: os.PathLike[str] | str | None) -> Path:
    if requested is not None:
        path = _canonical(requested)
        if path.exists():
            raise SarooBuildError(f"build log already exists; choose a new path: {path}")
        return path

    first = generated_root / "SRK_BUILD_LOG.txt"
    if not first.exists():
        return first
    for number in range(1, 10000):
        candidate = generated_root / f"SRK_BUILD_LOG_{number:03d}.txt"
        if not candidate.exists():
            return candidate
    raise SarooBuildError("could not allocate a unique SRK build-log filename")


def _validate_generated_tree(generated_root: Path) -> Path:
    marker = generated_root / _INTEGRATION_MARKER
    firm = generated_root / "Firm_Saturn"
    makefile = firm / "Makefile"
    helper = firm / _BUILD_HELPER

    if not marker.is_file():
        raise SarooBuildError(
            f"SRK integration marker is missing; refusing arbitrary SAROO tree: {marker}"
        )
    if not firm.is_dir() or not makefile.is_file() or not helper.is_file():
        raise SarooBuildError(
            "generated Firm_Saturn tree is incomplete; expected Makefile and "
            f"{_BUILD_HELPER} beneath: {firm}"
        )
    return firm


def _build_environment(report: SarooToolchainReport) -> dict[str, str]:
    env = dict(os.environ)
    directories: list[str] = []
    seen: set[str] = set()
    for probe in report.probes:
        if probe.resolved_path is None:
            continue
        parent = str(probe.resolved_path.parent)
        key = os.path.normcase(parent)
        if key not in seen:
            seen.add(key)
            directories.append(parent)

    existing_path = env.get("PATH", "")
    if existing_path:
        directories.append(existing_path)
    env["PATH"] = os.pathsep.join(directories)

    python_path = Path(sys.executable).resolve().as_posix()
    env["PYTHON"] = f'"{python_path}"' if " " in python_path else python_path
    return env


def _run_make(
    command: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _append_command_log(lines: list[str], label: str, command: list[str], result: subprocess.CompletedProcess[str]) -> None:
    lines.extend(
        (
            "",
            f"[{label}]",
            "Command: " + " ".join(command),
            f"Exit code: {result.returncode}",
            "Output:",
            result.stdout or "",
        )
    )


def build_firm_saturn_tree(
    generated_root: os.PathLike[str] | str,
    toolchain_root: os.PathLike[str] | str,
    *,
    log_path: os.PathLike[str] | str | None = None,
) -> SarooBuildResult:
    """Clean and build one SRK-generated ``Firm_Saturn`` tree.

    Tool discovery is intentionally restricted to ``toolchain_root``. The
    discovered executable directories are prepended only to the child process
    environment. The caller's global/process PATH is never modified.
    """

    generated = _canonical(generated_root)
    toolchain = _canonical(toolchain_root)
    firm = _validate_generated_tree(generated)

    report = inspect_saroo_toolchain(toolchain, path_env="")
    if not report.ready:
        raise SarooBuildError(
            "SAROO toolchain is not READY; missing: " + ", ".join(report.missing)
        )

    make_path = report.path_for("make")
    if make_path is None:
        raise SarooBuildError("READY report did not provide a Make executable")

    build_log = _unique_log_path(generated, log_path)
    build_log.parent.mkdir(parents=True, exist_ok=True)
    env = _build_environment(report)

    lines = [
        "SRK controlled SAROO Firm_Saturn build",
        f"Generated root: {generated}",
        f"Firm_Saturn: {firm}",
        f"Toolchain root: {toolchain}",
        f"Make: {make_path}",
        f"Python: {sys.executable}",
        "Process-local PATH additions:",
    ]
    for probe in report.probes:
        lines.append(f"  {probe.requirement.name}: {probe.resolved_path}")

    clean_command = [str(make_path), "-f", "Makefile", "clean"]
    clean_result = _run_make(clean_command, cwd=firm, env=env)
    _append_command_log(lines, "CLEAN", clean_command, clean_result)

    build_result: subprocess.CompletedProcess[str] | None = None
    if clean_result.returncode == 0:
        build_command = [str(make_path), "-f", "Makefile"]
        build_result = _run_make(build_command, cwd=firm, env=env)
        _append_command_log(lines, "BUILD", build_command, build_result)

    artifacts = tuple(
        _artifact(firm / name)
        for name in _EXPECTED_ARTIFACTS
        if (firm / name).is_file()
    )
    artifact_names = {item.path.name for item in artifacts}
    build_returncode = None if build_result is None else build_result.returncode
    successful = (
        clean_result.returncode == 0
        and build_returncode == 0
        and artifact_names == set(_EXPECTED_ARTIFACTS)
    )

    lines.extend(("", "[ARTIFACTS]"))
    if artifacts:
        for item in artifacts:
            lines.append(f"{item.path.name} | {item.size} bytes | SHA-256 {item.sha256}")
    else:
        lines.append("No expected build artifacts were produced.")
    missing_artifacts = [name for name in _EXPECTED_ARTIFACTS if name not in artifact_names]
    if missing_artifacts:
        lines.append("Missing expected artifacts: " + ", ".join(missing_artifacts))
    lines.extend(("", "Build result: " + ("SUCCESS" if successful else "FAILED"), ""))

    build_log.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    return SarooBuildResult(
        generated_root=generated,
        firm_saturn_directory=firm,
        toolchain_root=toolchain,
        log_path=build_log,
        clean_returncode=clean_result.returncode,
        build_returncode=build_returncode,
        artifacts=artifacts,
        successful=successful,
    )
