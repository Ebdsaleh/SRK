"""Off-card link gate for SRK's Sega Sound I/F Direct MIDI adapter.

The preceding compiler gate proved that the installed Sega header accepts the
exact ``SND_CtrlDirMidi`` call.  This gate advances one boundary: it compiles
that same adapter, performs a relocatable link against the exact installed
``sega_snd.a``, then inspects the resulting SH object.

A successful gate means both that ``SND_CtrlDirMidi`` was satisfied by the Sega
sound library and that the pulled library member(s) have no remaining undefined
symbols.  If transitive dependencies remain, the gate preserves and prints
their exact symbol names so the next closure step is evidence-driven.

No executable image, ISO, Saturn hardware action, or SAROO write occurs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
from typing import Callable, Sequence

from . import sbl_direct_midi_compile_probe as compile_gate
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnSblDirectMidiLinkProbeError(RuntimeError):
    """Raised when the Direct MIDI link gate cannot run safely."""


@dataclass(frozen=True)
class LinkProbeCommand:
    label: str
    argv: tuple[str, ...]
    returncode: int
    output: str


@dataclass(frozen=True)
class SaturnSblDirectMidiLinkProbeResult:
    output_root: Path
    compiler: Path
    objdump: Path
    sega_header: Path
    sega_library: Path
    object_path: Path | None
    linked_object_path: Path | None
    log_path: Path
    report_path: Path
    undefined_symbols: tuple[str, ...]
    direct_midi_resolved: bool
    closure_complete: bool
    successful: bool


_ACCEPTED_SOURCE_SHA256 = "364d7a5cd7c1023b797bedb0b97d763a65d2fd131e844c6ab4f032ca7c7b0ec4"
_ACCEPTED_ADAPTER_HEADER_SHA256 = "376cf81f0ffcfe246f084acf46b9d51ead1c57903781bbcdfda927e1843c037f"
_ACCEPTED_SEGA_HEADER_SHA256 = "17e74a4ead1f93f31997755d1a5f8bd6df80bf571d4f5201859d9141d07f9d7e"
_ACCEPTED_SEGA_LIBRARY_SHA256 = "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"

_OBJECT_NAME = "srk_saturn_sbl_direct_midi.o"
_LINKED_OBJECT_NAME = "srk_saturn_sbl_direct_midi_link.o"
_LOG_NAME = "SRK_SBL_DIRECT_MIDI_LINK_LOG.txt"
_REPORT_NAME = "SRK_SBL_DIRECT_MIDI_LINK.json"


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode_output(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _canonical_symbol(symbol: str) -> str:
    return symbol.lstrip("_")


def _undefined_symbols_from_objdump(output: str) -> tuple[str, ...]:
    """Extract stable undefined-symbol names from GNU objdump ``-t`` output."""

    symbols: set[str] = set()
    for raw_line in output.splitlines():
        if "*UND*" not in raw_line:
            continue
        parts = raw_line.split()
        if not parts:
            continue
        symbol = parts[-1].strip()
        if symbol and symbol != "*UND*":
            symbols.add(symbol)
    return tuple(sorted(symbols))


def _direct_midi_resolved(undefined_symbols: Sequence[str]) -> bool:
    return all(
        _canonical_symbol(symbol) != "SND_CtrlDirMidi"
        for symbol in undefined_symbols
    )


def _link_argv(
    compiler: Path,
    object_path: Path,
    sega_library: Path,
    linked_object: Path,
) -> tuple[str, ...]:
    return (
        str(compiler),
        "-nostdlib",
        "-m2",
        "-Wl,-r",
        "-o",
        str(linked_object),
        str(object_path),
        str(sega_library),
    )


def _verify_accepted_hashes(inputs: dict[str, Path]) -> dict[str, str]:
    expected = {
        "source": _ACCEPTED_SOURCE_SHA256,
        "adapter_header": _ACCEPTED_ADAPTER_HEADER_SHA256,
        "sega_header": _ACCEPTED_SEGA_HEADER_SHA256,
        "sega_library": _ACCEPTED_SEGA_LIBRARY_SHA256,
    }
    actual = {name: _sha256_file(path) for name, path in inputs.items()}
    for name, expected_sha in expected.items():
        if actual[name].lower() != expected_sha:
            raise SaturnSblDirectMidiLinkProbeError(
                f"{name} hash changed since the accepted compiler gate; "
                f"expected {expected_sha}, got {actual[name]}"
            )
    return actual


def probe_saturn_sbl_direct_midi_link(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnSblDirectMidiLinkProbeResult:
    """Compile, bind to ``sega_snd.a``, and inspect the transitive closure."""

    saturn_root = Path(saturn_root).expanduser().resolve(strict=False)
    output_root = Path(output_directory).expanduser().resolve(strict=False)
    if output_root.exists():
        raise SaturnSblDirectMidiLinkProbeError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    objdump = environment.compiler.path_for("sh-elf-objdump")
    if compiler is None or not compiler.is_file():
        raise SaturnSblDirectMidiLinkProbeError("SH-ELF GCC was not resolved")
    if objdump is None or not objdump.is_file():
        raise SaturnSblDirectMidiLinkProbeError("SH-ELF objdump was not resolved")

    sega_header = compile_gate._resolve_sdk_file(
        saturn_root, compile_gate._SEGA_HEADER_NAME, kind="header"
    )
    sega_library = compile_gate._resolve_sdk_file(
        saturn_root, compile_gate._SEGA_LIBRARY_NAME, kind="library"
    )

    repo_root = compile_gate._repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    source = source_dir / compile_gate._SOURCE_NAME
    adapter_header = source_dir / compile_gate._ADAPTER_HEADER_NAME
    inputs = {
        "source": source,
        "adapter_header": adapter_header,
        "sega_header": sega_header,
        "sega_library": sega_library,
    }
    hashes_before = _verify_accepted_hashes(inputs)
    path_before = os.environ.get("PATH")

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    object_path = temp_root / _OBJECT_NAME
    linked_object = temp_root / _LINKED_OBJECT_NAME
    log_path = temp_root / _LOG_NAME
    report_path = temp_root / _REPORT_NAME
    runner = _runner or subprocess.run
    commands: list[LinkProbeCommand] = []

    def invoke(label: str, argv: Sequence[str]) -> LinkProbeCommand:
        completed = runner(
            [str(item) for item in argv],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        command = LinkProbeCommand(
            label=label,
            argv=tuple(str(item) for item in argv),
            returncode=int(getattr(completed, "returncode", 1)),
            output=_decode_output(getattr(completed, "stdout", b"")),
        )
        commands.append(command)
        return command

    compile_argv = (
        str(compiler),
        "-c",
        str(source),
        "-o",
        str(object_path),
        *compile_gate.saturn_sbl_direct_midi_compile_flags(),
        f"-I{source_dir}",
        f"-I{sega_header.parent}",
    )

    try:
        compile_command = invoke("compile exact Direct MIDI adapter", compile_argv)
        compile_ok = (
            compile_command.returncode == 0
            and object_path.is_file()
            and object_path.stat().st_size > 0
        )

        link_ok = False
        inspect_ok = False
        undefined_symbols: tuple[str, ...] = tuple()
        direct_midi_resolved = False

        if compile_ok:
            link_command = invoke(
                "relocatable link with exact sega_snd.a",
                _link_argv(compiler, object_path, sega_library, linked_object),
            )
            link_ok = (
                link_command.returncode == 0
                and linked_object.is_file()
                and linked_object.stat().st_size > 0
            )

        if link_ok:
            inspect_command = invoke(
                "inspect linked SH symbol table",
                (str(objdump), "-t", str(linked_object)),
            )
            inspect_ok = inspect_command.returncode == 0
            if inspect_ok:
                undefined_symbols = _undefined_symbols_from_objdump(inspect_command.output)
                direct_midi_resolved = _direct_midi_resolved(undefined_symbols)

        hashes_after = {name: _sha256_file(path) for name, path in inputs.items()}
        inputs_unchanged = hashes_after == hashes_before
        path_unchanged = os.environ.get("PATH") == path_before
        closure_complete = inspect_ok and direct_midi_resolved and not undefined_symbols
        successful = (
            compile_ok
            and link_ok
            and inspect_ok
            and closure_complete
            and inputs_unchanged
            and path_unchanged
        )

        lines = [
            "SRK Sega Sound I/F Direct MIDI link gate",
            "==========================================",
        ]
        for command in commands:
            lines.append(f"[{command.label}] returncode={command.returncode}")
            lines.append("argv: " + " ".join(command.argv))
            if command.output:
                lines.append(command.output.rstrip())
            lines.append("")
        lines.extend(
            (
                f"direct_midi_resolved={str(direct_midi_resolved).lower()}",
                f"undefined_symbol_count={len(undefined_symbols)}",
                "undefined_symbols=" + ",".join(undefined_symbols),
                f"closure_complete={str(closure_complete).lower()}",
                f"inputs_unchanged={str(inputs_unchanged).lower()}",
                f"path_unchanged={str(path_unchanged).lower()}",
                f"successful={str(successful).lower()}",
                "",
            )
        )
        log_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.sbl-direct-midi-link.v1",
            "successful": successful,
            "compiler": str(compiler),
            "objdump": str(objdump),
            "inputs": {
                name: {
                    "path": str(path),
                    "sha256": hashes_before[name],
                }
                for name, path in inputs.items()
            },
            "commands": [asdict(command) for command in commands],
            "binding": {
                "function": "SND_CtrlDirMidi",
                "library": "sega_snd.a",
                "direct_midi_resolved": direct_midi_resolved,
                "undefined_symbols": list(undefined_symbols),
                "transitive_closure_complete": closure_complete,
            },
            "artifacts": {
                "compiled_object": (
                    {
                        "path": _OBJECT_NAME,
                        "size": object_path.stat().st_size,
                        "sha256": _sha256_file(object_path),
                    }
                    if object_path.is_file()
                    else None
                ),
                "linked_object": (
                    {
                        "path": _LINKED_OBJECT_NAME,
                        "size": linked_object.stat().st_size,
                        "sha256": _sha256_file(linked_object),
                    }
                    if linked_object.is_file()
                    else None
                ),
            },
            "policy": {
                "relocatable_link_only": True,
                "shell_used": False,
                "path_mutated": not path_unchanged,
                "inputs_unchanged": inputs_unchanged,
                "executable_image_created": False,
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
        return SaturnSblDirectMidiLinkProbeResult(
            output_root=output_root,
            compiler=compiler,
            objdump=objdump,
            sega_header=sega_header,
            sega_library=sega_library,
            object_path=(output_root / _OBJECT_NAME) if object_path.is_file() else None,
            linked_object_path=(
                output_root / _LINKED_OBJECT_NAME if linked_object.is_file() else None
            ),
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
            undefined_symbols=undefined_symbols,
            direct_midi_resolved=direct_midi_resolved,
            closure_complete=closure_complete,
            successful=successful,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def accepted_saturn_sbl_direct_midi_link_hashes() -> dict[str, str]:
    """Expose the accepted compiler-gate inputs for regression tests."""

    return {
        "source": _ACCEPTED_SOURCE_SHA256,
        "adapter_header": _ACCEPTED_ADAPTER_HEADER_SHA256,
        "sega_header": _ACCEPTED_SEGA_HEADER_SHA256,
        "sega_library": _ACCEPTED_SEGA_LIBRARY_SHA256,
    }
