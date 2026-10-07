"""Controlled native builds for an SRK-generated SAROO ``Firm_Saturn`` tree.

The build runner only accepts a tree produced by SRK's source-preparation step.
It resolves the external SH-ELF compiler/object tools from an explicit toolchain
root and invokes them directly from Python. GNU Make, MSYS ``sh.exe``, and shell
recipe compatibility are deliberately not part of this controlled path.

Every compiler command is logged, progress can be streamed to the caller, and
the expected artifacts are hashed. The runner never installs or flashes
firmware and never mutates the caller's process environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
import shlex
import shutil
import subprocess
from typing import Callable, Mapping

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
_TEMP_BINARY = "tmp.bin"


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


def _unique_log_path(
    generated_root: Path,
    requested: os.PathLike[str] | str | None,
) -> Path:
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
    return env


def _read_makefile(firm: Path) -> str:
    try:
        return (firm / "Makefile").read_text(encoding="utf-8")
    except OSError as exc:
        raise SarooBuildError(f"cannot read generated Makefile: {exc}") from exc


def _make_variable(makefile_text: str, name: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=\s*(.*?)\s*$")
    for raw_line in makefile_text.splitlines():
        if raw_line.lstrip().startswith("#"):
            continue
        match = pattern.match(raw_line)
        if match is not None:
            value = match.group(1).strip()
            if not value:
                raise SarooBuildError(f"generated Makefile variable {name} is empty")
            return value
    raise SarooBuildError(f"generated Makefile variable {name} was not found")


def _make_words(value: str, *, label: str) -> list[str]:
    try:
        words = shlex.split(value, posix=True)
    except ValueError as exc:
        raise SarooBuildError(f"cannot parse generated Makefile {label}: {exc}") from exc
    if not words:
        raise SarooBuildError(f"generated Makefile {label} is empty")
    return words


def _object_names(makefile_text: str) -> list[str]:
    pattern = re.compile(r"^\s*OBJ\s*=\s*(.*)$")
    lines = makefile_text.splitlines()

    for index, raw_line in enumerate(lines):
        match = pattern.match(raw_line)
        if match is None:
            continue

        fragments: list[str] = []
        current = match.group(1)
        cursor = index
        while True:
            continued = current.rstrip().endswith("\\")
            fragment = current.rstrip()
            if continued:
                fragment = fragment[:-1]
            fragments.append(fragment.strip())
            if not continued:
                break
            cursor += 1
            if cursor >= len(lines):
                raise SarooBuildError(
                    "generated Makefile OBJ list ends with a dangling continuation"
                )
            current = lines[cursor]

        objects = [word for word in " ".join(fragments).split() if word]
        if not objects:
            raise SarooBuildError("generated Makefile OBJ list is empty")

        for object_name in objects:
            normalized = object_name.replace("\\", "/")
            parts = [part for part in normalized.split("/") if part]
            if (
                len(parts) < 2
                or parts[0].casefold() != "obj"
                or any(part in {".", ".."} for part in parts)
                or not normalized.casefold().endswith(".o")
            ):
                raise SarooBuildError(
                    f"unsupported object path in generated Makefile: {object_name}"
                )
        return objects

    raise SarooBuildError("generated Makefile OBJ list was not found")


def _source_for_object(firm: Path, object_name: str) -> Path:
    normalized = object_name.replace("\\", "/")
    relative = Path(*normalized.split("/"))
    source_relative = Path(*relative.parts[1:]).with_suffix("")
    candidates = (
        firm / source_relative.with_suffix(".c"),
        firm / source_relative.with_suffix(".S"),
    )
    existing = [candidate for candidate in candidates if candidate.is_file()]
    if len(existing) != 1:
        names = ", ".join(str(candidate.relative_to(firm)) for candidate in candidates)
        raise SarooBuildError(
            f"expected exactly one source for {object_name}; checked: {names}"
        )
    return existing[0]


def _tool_path(report: SarooToolchainReport, name: str) -> Path:
    path = report.path_for(name)
    if path is None:
        raise SarooBuildError(f"READY toolchain report did not provide {name}")
    return path


def _format_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    on_output: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output_lines: list[str] = []
    assert process.stdout is not None
    for raw_line in process.stdout:
        output_lines.append(raw_line)
        if on_output is not None:
            on_output(raw_line.rstrip("\r\n"))
    returncode = process.wait()
    return subprocess.CompletedProcess(
        command,
        returncode,
        "".join(output_lines),
    )


def _concat_binary(destination: Path, sources: list[Path]) -> None:
    with destination.open("wb") as output:
        for source in sources:
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)


def build_firm_saturn_tree(
    generated_root: os.PathLike[str] | str,
    toolchain_root: os.PathLike[str] | str,
    *,
    log_path: os.PathLike[str] | str | None = None,
    progress: Callable[[str], None] | None = print,
) -> SarooBuildResult:
    """Clean and build one SRK-generated ``Firm_Saturn`` tree natively.

    The generated Makefile remains the authoritative description of object
    order and compiler/linker flags, but SRK does not execute GNU Make. Python
    performs the small file operations and launches the SH-ELF programs
    directly without ``sh.exe`` or ``cmd.exe`` recipe mediation.

    Tool discovery is intentionally restricted to ``toolchain_root``. Resolved
    executable directories are prepended only to the child-process environment;
    the caller's global/process PATH is never modified.
    """

    generated = _canonical(generated_root)
    toolchain = _canonical(toolchain_root)
    firm = _validate_generated_tree(generated)

    report = inspect_saroo_toolchain(toolchain, path_env="")
    if not report.ready:
        raise SarooBuildError(
            "SAROO toolchain is not READY; missing: " + ", ".join(report.missing)
        )

    gcc = _tool_path(report, "sh-elf-gcc")
    assembler = _tool_path(report, "sh-elf-as")
    objdump = _tool_path(report, "sh-elf-objdump")
    objcopy = _tool_path(report, "sh-elf-objcopy")

    makefile_text = _read_makefile(firm)
    object_names = _object_names(makefile_text)
    compile_flags = _make_words(
        _make_variable(makefile_text, "FLAGS"),
        label="FLAGS",
    )
    link_flags = _make_words(
        _make_variable(makefile_text, "LDFLAGS"),
        label="LDFLAGS",
    )
    libraries = _make_words(
        _make_variable(makefile_text, "LIBS"),
        label="LIBS",
    )
    executable_name = _make_variable(makefile_text, "EXE")
    if executable_name != "ssfirm.elf":
        raise SarooBuildError(
            f"unexpected generated Makefile EXE value: {executable_name!r}"
        )

    sources = [_source_for_object(firm, name) for name in object_names]
    object_paths = [
        firm / Path(*name.replace("\\", "/").split("/"))
        for name in object_names
    ]

    build_log = _unique_log_path(generated, log_path)
    build_log.parent.mkdir(parents=True, exist_ok=True)
    env = _build_environment(report)

    with build_log.open("x", encoding="utf-8", newline="\n") as log:
        def emit(message: str = "", *, show: bool = False) -> None:
            log.write(message + "\n")
            log.flush()
            if show and progress is not None:
                progress(message)

        emit("SRK controlled SAROO Firm_Saturn build")
        emit(f"Generated root: {generated}")
        emit(f"Firm_Saturn: {firm}")
        emit(f"Toolchain root: {toolchain}")
        emit("Build driver: SRK Python native (GNU Make not required)")
        emit("Shell mediation: none (no MSYS sh.exe / cmd.exe recipes)")
        emit("Resolved SH-ELF tools:")
        for probe in report.probes:
            emit(f"  {probe.requirement.name}: {probe.resolved_path}")
        emit()

        emit("SRK native SAROO build", show=True)
        emit(f"Build log: {build_log}", show=True)

        emit("[CLEAN]")
        emit("[1/3] Cleaning previous Firm_Saturn outputs...", show=True)
        obj_directory = firm / "obj"
        obj_directory.mkdir(parents=True, exist_ok=True)
        for old_object in sorted(obj_directory.rglob("*.o")):
            old_object.unlink()
            emit(f"Removed: {old_object.relative_to(firm)}")
        for name in (*_EXPECTED_ARTIFACTS, _TEMP_BINARY):
            candidate = firm / name
            try:
                candidate.unlink()
                emit(f"Removed: {candidate.relative_to(firm)}")
            except FileNotFoundError:
                pass
        (firm / "version.c").touch()
        emit("Touched: version.c")
        emit("Clean exit: 0")
        emit()

        emit("[BUILD]")
        emit(
            f"[2/3] Compiling {len(object_names)} Firm_Saturn objects with SH-ELF...",
            show=True,
        )

        build_returncode: int | None = 0

        def forward(line: str) -> None:
            emit(line, show=True)

        for index, (object_name, source, object_path) in enumerate(
            zip(object_names, sources, object_paths),
            start=1,
        ):
            source_label = str(source.relative_to(firm))
            emit(
                f"  [{index}/{len(object_names)}] {source_label} -> {object_name}",
                show=True,
            )
            if source.suffix == ".S":
                command = [str(assembler), source_label, "-o", object_name]
            else:
                command = [
                    str(gcc),
                    "-c",
                    source_label,
                    "-o",
                    object_name,
                    *compile_flags,
                ]
            emit("Command: " + _format_command(command))
            result = _run_command(
                command,
                cwd=firm,
                env=env,
                on_output=forward,
            )
            emit(f"Exit code: {result.returncode}")
            if result.returncode != 0:
                build_returncode = result.returncode
                emit(f"Compilation stopped at: {source_label}", show=True)
                break

        executable = firm / executable_name
        dump_path = firm / "dump.txt"
        temporary_binary = firm / _TEMP_BINARY
        final_binary = firm / "ssfirm.bin"

        if build_returncode == 0:
            emit("[3/3] Linking and publishing Firm_Saturn artifacts...", show=True)

            link_command = [
                str(gcc),
                *link_flags,
                *[str(path.relative_to(firm)) for path in object_paths],
                *libraries,
                "-o",
                executable_name,
            ]
            emit("Command: " + _format_command(link_command))
            link_result = _run_command(
                link_command,
                cwd=firm,
                env=env,
                on_output=forward,
            )
            emit(f"Exit code: {link_result.returncode}")
            build_returncode = link_result.returncode

        if build_returncode == 0:
            objdump_command = [str(objdump), "-xd", executable_name]
            emit("Command: " + _format_command(objdump_command))
            objdump_result = _run_command(objdump_command, cwd=firm, env=env)
            emit(f"Exit code: {objdump_result.returncode}")
            if objdump_result.returncode == 0:
                dump_path.write_text(
                    objdump_result.stdout or "",
                    encoding="utf-8",
                    newline="\n",
                )
                emit("Output redirected to: dump.txt")
            else:
                for line in (objdump_result.stdout or "").splitlines():
                    emit(line, show=True)
            build_returncode = objdump_result.returncode

        if build_returncode == 0:
            objcopy_command = [
                str(objcopy),
                "-O",
                "binary",
                executable_name,
                _TEMP_BINARY,
            ]
            emit("Command: " + _format_command(objcopy_command))
            objcopy_result = _run_command(
                objcopy_command,
                cwd=firm,
                env=env,
                on_output=forward,
            )
            emit(f"Exit code: {objcopy_result.returncode}")
            build_returncode = objcopy_result.returncode

        if build_returncode == 0:
            font_binary = firm / "font_cjk.bin"
            if not temporary_binary.is_file():
                raise SarooBuildError(
                    f"objcopy reported success but did not create: {temporary_binary}"
                )
            if not font_binary.is_file():
                raise SarooBuildError(
                    f"required SAROO font payload is missing: {font_binary}"
                )
            _concat_binary(final_binary, [temporary_binary, font_binary])
            temporary_binary.unlink()
            emit("Published: ssfirm.bin = tmp.bin + font_cjk.bin")
            emit("Removed: tmp.bin")
            emit("Native build steps complete.", show=True)

        artifacts = tuple(
            _artifact(firm / name)
            for name in _EXPECTED_ARTIFACTS
            if (firm / name).is_file()
        )
        artifact_names = {item.path.name for item in artifacts}
        successful = (
            build_returncode == 0
            and artifact_names == set(_EXPECTED_ARTIFACTS)
        )

        emit()
        emit("[ARTIFACTS]")
        if artifacts:
            for item in artifacts:
                emit(
                    f"{item.path.name} | {item.size} bytes | SHA-256 {item.sha256}"
                )
        else:
            emit("No expected build artifacts were produced.")
        missing_artifacts = [
            name for name in _EXPECTED_ARTIFACTS if name not in artifact_names
        ]
        if missing_artifacts:
            emit("Missing expected artifacts: " + ", ".join(missing_artifacts))
        emit()
        emit(
            "Build result: " + ("SUCCESS" if successful else "FAILED"),
            show=True,
        )

    return SarooBuildResult(
        generated_root=generated,
        firm_saturn_directory=firm,
        toolchain_root=toolchain,
        log_path=build_log,
        clean_returncode=0,
        build_returncode=build_returncode,
        artifacts=artifacts,
        successful=successful,
    )
