"""Prepare a persistent resident-runtime proof using SAROO's BIOS trampoline shape.

This diagnostic starts from the hardware-validated SRK capture-menu tree, not
from the later controller-hook experiments.  It adds one title-neutral menu arm
action and installs an SRK-owned version of SAROO's established cheat-style BIOS
interrupt trampoline after ``patch_game()`` has loaded the title's 1ST_READ.

The runtime callback does not inspect controller input or touch the VDP.  A fixed
96-byte proof file is created while arming.  Installation appends a second
32-byte slot, and the 600th trampoline callback appends a third slot containing
the SAROO FPGA hardware timer.  The callback then restores the original BIOS
vector immediately.

The source capture-menu tree is never modified in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeResidentProofIntegrationError(RuntimeError):
    """Raised when a resident-runtime proof tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeResidentProofIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    main_path: Path
    game_load_path: Path
    helper_source_path: Path
    helper_header_path: Path
    marker_path: Path


_MAKEFILE_CAPTURE_OBJECT = "\t\tobj/srk_capture_helper.o  \\\n"
_MAKEFILE_RESIDENT_OBJECT = "\t\tobj/srk_runtime_resident_proof.o  \\\n"

_MAIN_CAPTURE_INCLUDE = '#include "srk_capture_helper.h"\n'
_MAIN_RESIDENT_INCLUDE = '#include "srk_runtime_resident_proof.h"\n'
_MAIN_INDEX_ANCHOR = "int srk_wramh_index = -1;\n"
_MAIN_INDEX_PATCH = _MAIN_INDEX_ANCHOR + "int srk_runtime_resident_index = -1;\n"
_MAIN_MENU_ANCHOR = '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
_MAIN_MENU_PATCH = (
    _MAIN_MENU_ANCHOR
    + "\tsrk_runtime_resident_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Arm Resident Proof");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_PATCH = r'''	}else if(index==srk_runtime_resident_index){
		int retv;
		retv = srk_runtime_resident_proof_arm();
		if(retv==SRK_RUNTIME_RESIDENT_PROOF_OK){
			menu_status(&main_menu, "SRK: resident proof armed");
		}else{
			char buf[64];
			sprintf(buf, "SRK: resident proof arm failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
'''

_GAME_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_GAME_RESIDENT_INCLUDE = '#include "srk_runtime_resident_proof.h"\n'
_GAME_PATCH_ANCHOR = '\tpatch_game((char*)0x06002020);\n'
_GAME_PATCH_REPLACEMENT = (
    _GAME_PATCH_ANCHOR
    + "\t{\n"
    + "\t\tint srk_resident_ret = srk_runtime_resident_proof_install();\n"
    + "\t\tif(srk_resident_ret<0)\n"
    + '\t\t\tprintk("SRK resident proof install failed: %d\\n", srk_resident_ret);\n'
    + "\t}\n"
)


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
        raise SarooRuntimeResidentProofIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeResidentProofIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeResidentProofIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree may not match the validated capture-menu shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_resident_proof_tree(
    capture_menu_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeResidentProofIntegrationResult:
    """Create a separate resident-runtime proof tree from the capture-menu tree."""

    source = _canonical(capture_menu_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    main_path = firm / "main.c"
    game_load_path = firm / "game_load.c"
    capture_marker = source / "SRK_CAPTURE_MENU.txt"

    if not firm.is_dir():
        raise SarooRuntimeResidentProofIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not capture_marker.is_file():
        raise SarooRuntimeResidentProofIntegrationError(
            "source is not a validated SRK capture-menu tree; marker is missing"
        )
    if not makefile_path.is_file() or not main_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeResidentProofIntegrationError(
            "source capture-menu tree is incomplete; Makefile/main.c/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeResidentProofIntegrationError(
            f"output already exists; choose a new resident-proof directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeResidentProofIntegrationError(
            "output must be outside the existing capture-menu tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    resident_source = helpers / "srk_runtime_resident_proof.c"
    resident_header = helpers / "srk_runtime_resident_proof.h"
    if not resident_source.is_file() or not resident_header.is_file():
        raise SarooRuntimeResidentProofIntegrationError(
            f"SRK resident-runtime proof helpers are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    main_text = _read_text(main_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_RESIDENT_OBJECT in makefile_text or _MAIN_RESIDENT_INCLUDE in main_text:
        raise SarooRuntimeResidentProofIntegrationError(
            "source tree already contains SRK resident-runtime proof integration"
        )

    for text, anchor, label in (
        (makefile_text, _MAKEFILE_CAPTURE_OBJECT, "capture-helper Makefile object"),
        (main_text, _MAIN_CAPTURE_INCLUDE, "main capture-helper include"),
        (main_text, _MAIN_INDEX_ANCHOR, "main menu index"),
        (main_text, _MAIN_MENU_ANCHOR, "main capture menu item"),
        (main_text, _MAIN_HANDLER_ANCHOR, "main menu handler"),
        (game_text, _GAME_INCLUDE_ANCHOR, "game include"),
        (game_text, _GAME_PATCH_ANCHOR, "post-1ST_READ patch_game call"),
    ):
        if text.count(anchor) != 1:
            raise SarooRuntimeResidentProofIntegrationError(
                f"expected exactly one {label}; source tree may not match the validated capture-menu revision"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_CAPTURE_OBJECT,
        _MAKEFILE_CAPTURE_OBJECT + _MAKEFILE_RESIDENT_OBJECT,
        1,
    )
    patched_main = _replace_once(
        main_text,
        _MAIN_CAPTURE_INCLUDE,
        _MAIN_CAPTURE_INCLUDE + _MAIN_RESIDENT_INCLUDE,
        label="main capture-helper include",
    )
    patched_main = _replace_once(
        patched_main,
        _MAIN_INDEX_ANCHOR,
        _MAIN_INDEX_PATCH,
        label="main menu index",
    )
    patched_main = _replace_once(
        patched_main,
        _MAIN_MENU_ANCHOR,
        _MAIN_MENU_PATCH,
        label="main capture menu item",
    )
    patched_main = _replace_once(
        patched_main,
        _MAIN_HANDLER_ANCHOR,
        _MAIN_HANDLER_PATCH + _MAIN_HANDLER_ANCHOR,
        label="main menu handler",
    )

    patched_game = _replace_once(
        game_text,
        _GAME_INCLUDE_ANCHOR,
        _GAME_INCLUDE_ANCHOR + _GAME_RESIDENT_INCLUDE,
        label="game include",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_PATCH_ANCHOR,
        _GAME_PATCH_REPLACEMENT,
        label="post-1ST_READ patch_game call",
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_main = target_firm / "main.c"
        target_game = target_firm / "game_load.c"
        target_resident_source = target_firm / resident_source.name
        target_resident_header = target_firm / resident_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_main, patched_main)
        _write_text(target_game, patched_game)
        shutil.copy2(resident_source, target_resident_source)
        shutil.copy2(resident_header, target_resident_header)

        marker = output / "SRK_RUNTIME_RESIDENT_PROOF.txt"
        _write_text(
            marker,
            "SRK SAROO persistent resident-runtime proof\n"
            f"Source capture-menu tree: {source}\n"
            "The source capture-menu tree was not modified.\n"
            "Arm: SRK Arm Resident Proof in SAROO menu.\n"
            "Hook: SRK-owned form of SAROO's BIOS interrupt cheat trampoline.\n"
            "Install point: immediately after patch_game() once 1ST_READ is loaded.\n"
            "Vector: 0x0600090C; return: 0x0600091A.\n"
            "Vector shape is verified before patching; unexpected BIOS code is rejected.\n"
            "Persistent evidence: /SAROO/SRK_RUNTIME_PROOF.BIN (96 bytes).\n"
            "Slots: armed, installed, proven. Proven is written on callback 600.\n"
            "Time source: SAROO FPGA SS_TIMER; slots store raw 32-bit hardware ticks.\n"
            "Runtime input dependency: none. VDP dependency: none.\n"
            "The callback performs one preallocated 32-byte SD update, then restores the BIOS vector.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeResidentProofIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        main_path=output / "Firm_Saturn" / "main.c",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        helper_source_path=output / "Firm_Saturn" / resident_source.name,
        helper_header_path=output / "Firm_Saturn" / resident_header.name,
        marker_path=output / "SRK_RUNTIME_RESIDENT_PROOF.txt",
    )
