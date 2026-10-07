"""Create a second SRK SAROO build tree with controller-accessible captures.

This layer intentionally starts from an already generated SRK SAROO tree and
copies it to a new output directory before patching ``Firm_Saturn/main.c``.
Neither the known-good upstream checkout nor the previously hardware-validated
SRK-generated tree is edited in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil


class SarooCaptureMenuIntegrationError(RuntimeError):
    """Raised when the capture-menu tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooCaptureMenuIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    main_path: Path
    marker_path: Path


_MAIN_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_MAIN_HELPER_INCLUDE = '#include "srk_capture_helper.h"\n'
_MAIN_INDEX_ANCHOR = "int update_index;\n"
_MAIN_INDEX_BLOCK = (
    "int update_index;\n"
    "int srk_wraml_index = -1;\n"
    "int srk_wramh_index = -1;\n"
)
_MAIN_MENU_BUILD_ANCHOR = (
    "\tfor(i=0; i<menu_str_nr; i++){\n"
    "\t\tadd_menu_item(&main_menu, TT(menu_str[i]));\n"
    "\t}\n"
)
_MAIN_MENU_BUILD_BLOCK = (
    _MAIN_MENU_BUILD_ANCHOR
    + "\tsrk_wraml_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Capture WRAM-L");\n'
    + "\tsrk_wramh_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_BLOCK = r'''	}else if(index==srk_wraml_index){
		int retv;
		char buf[64];
		menu_status(&main_menu, "SRK: capturing Work RAM-L ...");
		retv = srk_capture_work_ram_low("/SAROO/SRK_WRAML.BIN");
		if(retv==SRK_CAPTURE_OK){
			menu_status(&main_menu, "SRK: WRAM-L capture complete");
		}else{
			sprintf(buf, "SRK: WRAM-L capture failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
	}else if(index==srk_wramh_index){
		int retv;
		char buf[64];
		menu_status(&main_menu, "SRK: capturing Work RAM-H ...");
		retv = srk_capture_work_ram_high("/SAROO/SRK_WRAMH.BIN");
		if(retv==SRK_CAPTURE_OK){
			menu_status(&main_menu, "SRK: WRAM-H capture complete");
		}else{
			sprintf(buf, "SRK: WRAM-H capture failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
'''


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SarooCaptureMenuIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooCaptureMenuIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooCaptureMenuIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "the generated SAROO tree may not match the validated integration"
        )
    return text.replace(anchor, replacement, 1)


def _validate_main(main_text: str) -> None:
    if _MAIN_HELPER_INCLUDE not in main_text and main_text.count(_MAIN_INCLUDE_ANCHOR) != 1:
        raise SarooCaptureMenuIntegrationError(
            "Firm_Saturn/main.c does not contain the expected include anchor"
        )
    if "srk_wraml_index" not in main_text and main_text.count(_MAIN_INDEX_ANCHOR) != 1:
        raise SarooCaptureMenuIntegrationError(
            "Firm_Saturn/main.c does not contain the expected menu-index anchor"
        )
    if "SRK Capture WRAM-L" not in main_text and main_text.count(_MAIN_MENU_BUILD_ANCHOR) != 1:
        raise SarooCaptureMenuIntegrationError(
            "Firm_Saturn/main.c does not contain the expected menu-construction anchor"
        )
    if "index==srk_wraml_index" not in main_text and main_text.count(_MAIN_HANDLER_ANCHOR) != 1:
        raise SarooCaptureMenuIntegrationError(
            "Firm_Saturn/main.c does not contain the expected menu-handler anchor"
        )


def prepare_capture_menu_tree(
    integrated_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
) -> SarooCaptureMenuIntegrationResult:
    """Copy an SRK-generated SAROO tree and add two explicit capture menu items."""

    source = _canonical(integrated_source_root)
    output = _canonical(output_root)
    source_firm = source / "Firm_Saturn"
    main_path = source_firm / "main.c"
    helper_source = source_firm / "srk_capture_helper.c"
    helper_header = source_firm / "srk_capture_helper.h"

    if not source_firm.is_dir():
        raise SarooCaptureMenuIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not main_path.is_file():
        raise SarooCaptureMenuIntegrationError(f"generated Firm_Saturn/main.c is missing: {main_path}")
    if not helper_source.is_file() or not helper_header.is_file():
        raise SarooCaptureMenuIntegrationError(
            "source tree is not an SRK capture-enabled SAROO tree; capture helper files are missing"
        )
    if output.exists():
        raise SarooCaptureMenuIntegrationError(
            f"output already exists; choose a new capture-menu directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooCaptureMenuIntegrationError(
            "output must be outside the existing generated SAROO tree"
        )

    main_text = _read_text(main_path)
    _validate_main(main_text)

    patched = main_text
    if _MAIN_HELPER_INCLUDE not in patched:
        patched = _replace_once(
            patched,
            _MAIN_INCLUDE_ANCHOR,
            _MAIN_INCLUDE_ANCHOR + _MAIN_HELPER_INCLUDE,
            label="main.c include",
        )
    if "srk_wraml_index" not in patched:
        patched = _replace_once(
            patched,
            _MAIN_INDEX_ANCHOR,
            _MAIN_INDEX_BLOCK,
            label="main.c menu-index",
        )
    if "SRK Capture WRAM-L" not in patched:
        patched = _replace_once(
            patched,
            _MAIN_MENU_BUILD_ANCHOR,
            _MAIN_MENU_BUILD_BLOCK,
            label="main.c menu-construction",
        )
    if "index==srk_wraml_index" not in patched:
        patched = _replace_once(
            patched,
            _MAIN_HANDLER_ANCHOR,
            _MAIN_HANDLER_BLOCK + _MAIN_HANDLER_ANCHOR,
            label="main.c menu-handler",
        )

    try:
        shutil.copytree(source, output)
        target_main = output / "Firm_Saturn" / "main.c"
        _write_text(target_main, patched)
        marker = output / "SRK_CAPTURE_MENU.txt"
        _write_text(
            marker,
            "SRK SAROO controller-accessible capture menu\n"
            f"Source generated tree: {source}\n"
            "The source generated tree was not modified.\n"
            "Menu action: SRK Capture WRAM-L -> /SAROO/SRK_WRAML.BIN\n"
            "Menu action: SRK Capture WRAM-H -> /SAROO/SRK_WRAMH.BIN\n"
            "Each capture is 1 MiB and uses the existing 64 KiB chunked helper.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooCaptureMenuIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        main_path=output / "Firm_Saturn" / "main.c",
        marker_path=output / "SRK_CAPTURE_MENU.txt",
    )
