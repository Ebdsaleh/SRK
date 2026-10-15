"""Close the exact Sega Direct MIDI link dependencies observed on Eridu.

The preceding link gate proved that sega_snd.a owns SND_CtrlDirMidi and exposed
three remaining undefined symbols on the accepted toolchain:

    ___ashiftrt_r4_8
    _memcpy
    _memset

This gate closes only those requirements:
- memcpy/memset come from SRK's tiny freestanding runtime source;
- the GCC arithmetic helper comes from the exact libgcc selected by the same
  installed SH-ELF compiler via ``-print-libgcc-file-name``.

No executable, ISO, Saturn execution, or SAROO write occurs here.
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
from typing import Callable, Sequence

from . import sbl_direct_midi_compile_probe as compile_gate
from .sbl_direct_midi_link_probe import (
    _direct_midi_resolved,
    _undefined_symbols_from_objdump,
    accepted_saturn_sbl_direct_midi_link_hashes,
)
from .standalone_environment import inspect_saturn_standalone_environment


class SaturnSblDirectMidiClosureGateError(RuntimeError):
    """Raised when the Direct MIDI closure gate cannot run safely."""


@dataclass(frozen=True)
class SaturnSblDirectMidiClosureGateResult:
    output_root: Path
    compiler: Path
    objdump: Path
    sega_library: Path
    libgcc: Path
    linked_object: Path | None
    undefined_symbols: tuple[str, ...]
    direct_midi_resolved: bool
    closure_complete: bool
    successful: bool
    log_path: Path
    report_path: Path


_RUNTIME_SOURCE_NAME = "srk_saturn_sbl_runtime.c"
_ADAPTER_OBJECT = "srk_saturn_sbl_direct_midi.o"
_RUNTIME_OBJECT = "srk_saturn_sbl_runtime.o"
_LINKED_OBJECT = "srk_saturn_sbl_direct_midi_closure.o"
_LOG_NAME = "SRK_SBL_DIRECT_MIDI_CLOSURE_LOG.txt"
_REPORT_NAME = "SRK_SBL_DIRECT_MIDI_CLOSURE.json"


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


def _libgcc_path_from_output(output: str) -> Path:
    text = output.strip().splitlines()
    if not text:
        raise SaturnSblDirectMidiClosureGateError("SH-ELF GCC returned no libgcc path")
    path = Path(text[-1].strip()).expanduser().resolve(strict=False)
    if not path.is_file():
        raise SaturnSblDirectMidiClosureGateError(
            f"SH-ELF GCC reported a missing libgcc archive: {path}"
        )
    return path


def _closure_link_argv(
    compiler: Path,
    adapter_object: Path,
    sega_library: Path,
    runtime_object: Path,
    libgcc: Path,
    linked_object: Path,
) -> tuple[str, ...]:
    return (
        str(compiler),
        "-nostdlib",
        "-m2",
        "-Wl,-r",
        "-o",
        str(linked_object),
        str(adapter_object),
        str(sega_library),
        str(runtime_object),
        str(libgcc),
    )


def probe_saturn_sbl_direct_midi_closure(
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
    *,
    _runner: Callable[..., object] | None = None,
) -> SaturnSblDirectMidiClosureGateResult:
    saturn_root = Path(saturn_root).expanduser().resolve(strict=False)
    output_root = Path(output_directory).expanduser().resolve(strict=False)
    if output_root.exists():
        raise SaturnSblDirectMidiClosureGateError(
            f"output directory already exists; refusing to merge or overwrite: {output_root}"
        )

    environment = inspect_saturn_standalone_environment(saturn_root)
    compiler = environment.compiler.path_for("sh-elf-gcc")
    objdump = environment.compiler.path_for("sh-elf-objdump")
    if compiler is None or not compiler.is_file():
        raise SaturnSblDirectMidiClosureGateError("SH-ELF GCC was not resolved")
    if objdump is None or not objdump.is_file():
        raise SaturnSblDirectMidiClosureGateError("SH-ELF objdump was not resolved")

    sega_header = compile_gate._resolve_sdk_file(
        saturn_root, compile_gate._SEGA_HEADER_NAME, kind="header"
    )
    sega_library = compile_gate._resolve_sdk_file(
        saturn_root, compile_gate._SEGA_LIBRARY_NAME, kind="library"
    )

    repo_root = compile_gate._repo_root()
    source_dir = repo_root / "integrations" / "saturn" / "standalone"
    adapter_source = source_dir / compile_gate._SOURCE_NAME
    adapter_header = source_dir / compile_gate._ADAPTER_HEADER_NAME
    runtime_source = source_dir / _RUNTIME_SOURCE_NAME
    if not runtime_source.is_file():
        raise SaturnSblDirectMidiClosureGateError(
            f"Direct MIDI runtime source is missing: {runtime_source}"
        )

    accepted = accepted_saturn_sbl_direct_midi_link_hashes()
    pinned = {
        "source": adapter_source,
        "adapter_header": adapter_header,
        "sega_header": sega_header,
        "sega_library": sega_library,
    }
    for name, path in pinned.items():
        actual = _sha256_file(path)
        if actual.lower() != accepted[name].lower():
            raise SaturnSblDirectMidiClosureGateError(
                f"{name} changed since accepted Direct MIDI gate: {actual}"
            )

    runner = _runner or subprocess.run
    path_before = os.environ.get("PATH")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=str(output_root.parent))
    )
    adapter_object = temp_root / _ADAPTER_OBJECT
    runtime_object = temp_root / _RUNTIME_OBJECT
    linked_object = temp_root / _LINKED_OBJECT
    log_path = temp_root / _LOG_NAME
    report_path = temp_root / _REPORT_NAME
    command_log: list[tuple[str, tuple[str, ...], int, str]] = []

    def invoke(label: str, argv: Sequence[str]):
        completed = runner(
            [str(item) for item in argv],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
        )
        rc = int(getattr(completed, "returncode", 1))
        out = _decode_output(getattr(completed, "stdout", b""))
        command_log.append((label, tuple(str(item) for item in argv), rc, out))
        return rc, out

    flags = compile_gate.saturn_sbl_direct_midi_compile_flags()
    try:
        rc, _ = invoke(
            "compile Direct MIDI adapter",
            (
                str(compiler), "-c", str(adapter_source), "-o", str(adapter_object),
                *flags, f"-I{source_dir}", f"-I{sega_header.parent}",
            ),
        )
        if rc != 0 or not adapter_object.is_file():
            raise SaturnSblDirectMidiClosureGateError("Direct MIDI adapter compile failed")

        rc, _ = invoke(
            "compile minimal freestanding runtime",
            (str(compiler), "-c", str(runtime_source), "-o", str(runtime_object), *flags),
        )
        if rc != 0 or not runtime_object.is_file():
            raise SaturnSblDirectMidiClosureGateError("Direct MIDI runtime compile failed")

        rc, libgcc_output = invoke("resolve exact libgcc", (str(compiler), "-print-libgcc-file-name"))
        if rc != 0:
            raise SaturnSblDirectMidiClosureGateError("SH-ELF GCC could not resolve libgcc")
        libgcc = _libgcc_path_from_output(libgcc_output)

        rc, _ = invoke(
            "close Direct MIDI relocatable link",
            _closure_link_argv(
                compiler,
                adapter_object,
                sega_library,
                runtime_object,
                libgcc,
                linked_object,
            ),
        )
        link_ok = rc == 0 and linked_object.is_file() and linked_object.stat().st_size > 0

        undefined_symbols: tuple[str, ...] = tuple()
        direct_midi_resolved = False
        inspect_ok = False
        if link_ok:
            rc, objdump_output = invoke(
                "inspect closed SH symbol table",
                (str(objdump), "-t", str(linked_object)),
            )
            inspect_ok = rc == 0
            if inspect_ok:
                undefined_symbols = _undefined_symbols_from_objdump(objdump_output)
                direct_midi_resolved = _direct_midi_resolved(undefined_symbols)

        closure_complete = inspect_ok and direct_midi_resolved and not undefined_symbols
        path_unchanged = os.environ.get("PATH") == path_before
        successful = link_ok and closure_complete and path_unchanged

        lines = ["SRK Sega Direct MIDI dependency closure gate", "============================================"]
        for label, argv, rc, out in command_log:
            lines.extend((f"[{label}] returncode={rc}", "argv: " + " ".join(argv)))
            if out:
                lines.append(out.rstrip())
            lines.append("")
        lines.extend((
            f"libgcc={libgcc}",
            f"libgcc_sha256={_sha256_file(libgcc)}",
            f"runtime_source_sha256={_sha256_file(runtime_source)}",
            f"direct_midi_resolved={str(direct_midi_resolved).lower()}",
            f"undefined_symbol_count={len(undefined_symbols)}",
            "undefined_symbols=" + ",".join(undefined_symbols),
            f"closure_complete={str(closure_complete).lower()}",
            f"path_unchanged={str(path_unchanged).lower()}",
            f"successful={str(successful).lower()}",
            "",
        ))
        log_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

        report = {
            "schema": "srk.saturn.sbl-direct-midi-closure.v1",
            "successful": successful,
            "sega_library": {"path": str(sega_library), "sha256": _sha256_file(sega_library)},
            "libgcc": {"path": str(libgcc), "sha256": _sha256_file(libgcc)},
            "runtime_source": {"path": str(runtime_source), "sha256": _sha256_file(runtime_source)},
            "binding": {
                "function": "SND_CtrlDirMidi",
                "direct_midi_resolved": direct_midi_resolved,
                "undefined_symbols": list(undefined_symbols),
                "transitive_closure_complete": closure_complete,
            },
            "policy": {
                "relocatable_link_only": True,
                "hosted_libc_linked": False,
                "exact_libgcc_from_compiler": True,
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

        adapter_ok = adapter_object.is_file()
        runtime_ok = runtime_object.is_file()
        linked_ok = linked_object.is_file()
        temp_root.replace(output_root)
        return SaturnSblDirectMidiClosureGateResult(
            output_root=output_root,
            compiler=compiler,
            objdump=objdump,
            sega_library=sega_library,
            libgcc=libgcc,
            linked_object=(output_root / _LINKED_OBJECT) if linked_ok else None,
            undefined_symbols=undefined_symbols,
            direct_midi_resolved=direct_midi_resolved,
            closure_complete=closure_complete,
            successful=successful,
            log_path=output_root / _LOG_NAME,
            report_path=output_root / _REPORT_NAME,
        )
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def closure_link_argv_for_test(
    compiler: Path,
    adapter_object: Path,
    sega_library: Path,
    runtime_object: Path,
    libgcc: Path,
    linked_object: Path,
) -> tuple[str, ...]:
    return _closure_link_argv(
        compiler, adapter_object, sega_library, runtime_object, libgcc, linked_object
    )
