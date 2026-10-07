"""Generate an SRK-enabled copy of upstream SAROO's Firm_Saturn tree.

The source SAROO checkout is never edited in place.  SRK copies only the
``Firm_Saturn`` directory to a new destination, adds the SRK-authored capture
helper, and applies small anchor-validated build/shell integrations there.

This is intentionally source preparation, not firmware flashing.  The user can
inspect and build the generated tree with the upstream SH-ELF toolchain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


class SarooFirmwareIntegrationError(RuntimeError):
    """Raised when a SAROO source tree cannot be integrated safely."""


@dataclass(frozen=True)
class SarooFirmwareIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    shell_path: Path
    helper_source_path: Path
    helper_header_path: Path


_MAKEFILE_OBJECT_ANCHOR = "\t\tobj/sci_shell.o  \\\n"
_MAKEFILE_HELPER_OBJECT = "\t\tobj/srk_capture_helper.o  \\\n"
_SHELL_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_SHELL_HELPER_INCLUDE = '#include "srk_capture_helper.h"\n'
_SHELL_COMMAND_ANCHOR = "\t\tCMD(q) {\n"
_SHELL_COMMAND_BLOCK = r'''		CMD(srkwl) {
			int retv = srk_capture_work_ram_low("/SAROO/SRK_WRAML.BIN");
			printk("SRK WRAM-L capture: %d\n", retv);
		}
		CMD(srkwh) {
			int retv = srk_capture_work_ram_high("/SAROO/SRK_WRAMH.BIN");
			printk("SRK WRAM-H capture: %d\n", retv);
		}

'''


def _repo_root() -> Path:
    # .../src/rikai_kotoba/hardware/saturn/saroo/firmware_integration.py
    return Path(__file__).resolve().parents[5]


def default_helper_root() -> Path:
    return _repo_root() / "integrations" / "saroo" / "Firm_Saturn"


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooFirmwareIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "the SAROO revision may not match this integration"
        )
    return text.replace(anchor, replacement, 1)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SarooFirmwareIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooFirmwareIntegrationError(f"cannot write {path}: {exc}") from exc


def prepare_firm_saturn_tree(
    saroo_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooFirmwareIntegrationResult:
    """Create a separate SRK-enabled ``Firm_Saturn`` build tree.

    ``saroo_source_root`` must be the root of an upstream SAROO checkout.  The
    original checkout remains untouched.  ``output_root`` must not already
    exist; refusing replacement makes repeated experiments explicit and keeps a
    known-good upstream source tree available for comparison.
    """

    source_root = _canonical(saroo_source_root)
    destination = _canonical(output_root)
    source_firm = source_root / "Firm_Saturn"

    if not source_firm.is_dir():
        raise SarooFirmwareIntegrationError(
            f"SAROO Firm_Saturn directory not found beneath: {source_root}"
        )
    if destination.exists():
        raise SarooFirmwareIntegrationError(
            f"output already exists; choose a new integration directory: {destination}"
        )
    if destination == source_root or source_root in destination.parents:
        raise SarooFirmwareIntegrationError(
            "output must be outside the source SAROO checkout"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    helper_source = helpers / "srk_capture_helper.c"
    helper_header = helpers / "srk_capture_helper.h"
    if not helper_source.is_file() or not helper_header.is_file():
        raise SarooFirmwareIntegrationError(
            f"SRK capture helper sources are unavailable beneath: {helpers}"
        )

    source_makefile = source_firm / "Makefile"
    source_shell = source_firm / "sci_shell.c"
    makefile_text = _read_text(source_makefile)
    shell_text = _read_text(source_shell)

    # Validate all anchors before creating any output, so an incompatible SAROO
    # revision cannot leave a misleading half-integrated build tree behind.
    if _MAKEFILE_HELPER_OBJECT not in makefile_text:
        if makefile_text.count(_MAKEFILE_OBJECT_ANCHOR) != 1:
            raise SarooFirmwareIntegrationError(
                "SAROO Makefile does not contain the expected sci_shell object anchor"
            )
    if _SHELL_HELPER_INCLUDE not in shell_text:
        if shell_text.count(_SHELL_INCLUDE_ANCHOR) != 1:
            raise SarooFirmwareIntegrationError(
                "SAROO sci_shell.c does not contain the expected include anchor"
            )
    if "CMD(srkwl)" not in shell_text and shell_text.count(_SHELL_COMMAND_ANCHOR) != 1:
        raise SarooFirmwareIntegrationError(
            "SAROO sci_shell.c does not contain the expected command anchor"
        )

    destination_firm = destination / "Firm_Saturn"
    try:
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copytree(source_firm, destination_firm)

        target_makefile = destination_firm / "Makefile"
        target_shell = destination_firm / "sci_shell.c"

        patched_makefile = makefile_text
        if _MAKEFILE_HELPER_OBJECT not in patched_makefile:
            patched_makefile = _replace_once(
                patched_makefile,
                _MAKEFILE_OBJECT_ANCHOR,
                _MAKEFILE_OBJECT_ANCHOR + _MAKEFILE_HELPER_OBJECT,
                label="Makefile object",
            )

        patched_shell = shell_text
        if _SHELL_HELPER_INCLUDE not in patched_shell:
            patched_shell = _replace_once(
                patched_shell,
                _SHELL_INCLUDE_ANCHOR,
                _SHELL_INCLUDE_ANCHOR + _SHELL_HELPER_INCLUDE,
                label="sci_shell include",
            )
        if "CMD(srkwl)" not in patched_shell:
            patched_shell = _replace_once(
                patched_shell,
                _SHELL_COMMAND_ANCHOR,
                _SHELL_COMMAND_BLOCK + _SHELL_COMMAND_ANCHOR,
                label="sci_shell command",
            )

        _write_text(target_makefile, patched_makefile)
        _write_text(target_shell, patched_shell)
        shutil.copy2(helper_source, destination_firm / helper_source.name)
        shutil.copy2(helper_header, destination_firm / helper_header.name)

        marker = destination / "SRK_INTEGRATION.txt"
        _write_text(
            marker,
            "SRK SAROO Firm_Saturn integration\n"
            f"Source: {source_root}\n"
            "The original source checkout was not modified.\n"
            "Capture shell commands: srkwl, srkwh\n"
            "Generated files: /SAROO/SRK_WRAML.BIN, /SAROO/SRK_WRAMH.BIN\n",
        )
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise

    return SarooFirmwareIntegrationResult(
        source_root=source_root,
        output_root=destination,
        firm_saturn_directory=destination_firm,
        makefile_path=destination_firm / "Makefile",
        shell_path=destination_firm / "sci_shell.c",
        helper_source_path=destination_firm / helper_source.name,
        helper_header_path=destination_firm / helper_header.name,
    )
