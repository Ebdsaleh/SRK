"""Prepare an armed, input-independent post-entry runtime execution proof.

This diagnostic starts from the already generated R4 runtime-video canary tree.
It adds a SAROO-menu arm action, gates proof collection on the title-neutral
IP.BIN 1st-read UBR breakpoint, and then counts later invocations of SAROO's
existing BIOS controller hook.  After 600 post-entry hook calls it blanks only
the VDP2 display-enable bit for 120 display frames and restores the exact TVMD
value.

The proof intentionally does not depend on controller button semantics.  It
performs no SD write, Work RAM capture, direct SMPC polling, VRAM/CRAM write, or
VDP1 write.  The source generated tree is never modified in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeExecutionProofIntegrationError(RuntimeError):
    """Raised when the runtime execution-proof tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeExecutionProofIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    main_path: Path
    game_load_path: Path
    helper_source_path: Path
    helper_header_path: Path
    marker_path: Path


_MAKEFILE_CANARY_OBJECT = "\t\tobj/srk_runtime_video_canary.o  \\\n"
_MAKEFILE_PROOF_OBJECT = "\t\tobj/srk_runtime_execution_proof.o  \\\n"

_MAIN_CAPTURE_INCLUDE = '#include "srk_capture_helper.h"\n'
_MAIN_PROOF_INCLUDE = '#include "srk_runtime_execution_proof.h"\n'
_MAIN_INDEX_ANCHOR = "int srk_wramh_index = -1;\n"
_MAIN_INDEX_PATCH = _MAIN_INDEX_ANCHOR + "int srk_runtime_proof_index = -1;\n"
_MAIN_MENU_ANCHOR = '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
_MAIN_MENU_PATCH = (
    _MAIN_MENU_ANCHOR
    + "\tsrk_runtime_proof_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Arm Runtime Proof");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_PATCH = r'''	}else if(index==srk_runtime_proof_index){
		int retv;
		retv = srk_runtime_execution_proof_arm();
		if(retv==SRK_RUNTIME_EXECUTION_PROOF_OK){
			menu_status(&main_menu, "SRK: runtime proof armed");
		}else{
			char buf[64];
			sprintf(buf, "SRK: runtime proof arm failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
'''

_GAME_CANARY_INCLUDE = '#include "srk_runtime_video_canary.h"\n'
_GAME_PROOF_INCLUDE = '#include "srk_runtime_execution_proof.h"\n'
_GAME_HOOK_TAIL_ANCHOR = (
    "\torig_func();\n"
    "}\n\n\n"
    "static void hook_getkey(void)\n"
)
_GAME_HOOK_TAIL_PATCH = (
    "\torig_func();\n"
    "\tsrk_runtime_execution_proof_on_controller_hook();\n"
    "}\n\n\n"
    "static void hook_getkey(void)\n"
)
_GAME_BREAK_ANCHOR = "\tif(game_break_pc){\n\t\tset_break_pc(game_break_pc, 0);\n"
_GAME_BREAK_PATCH = (
    "\t{\n"
    "\t\tint srk_proof_prepare_ret = srk_runtime_execution_proof_prepare();\n"
    "\t\tif(srk_proof_prepare_ret<0)\n"
    '\t\t\tprintk("SRK runtime proof prepare failed: %d\\n", srk_proof_prepare_ret);\n'
    "\t}\n\n"
    + _GAME_BREAK_ANCHOR
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
        raise SarooRuntimeExecutionProofIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeExecutionProofIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeExecutionProofIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree may not match the validated R4 shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_execution_proof_tree(
    runtime_canary_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeExecutionProofIntegrationResult:
    """Create a separate R6 runtime execution-proof tree from R4."""

    source = _canonical(runtime_canary_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    main_path = firm / "main.c"
    game_load_path = firm / "game_load.c"
    canary_marker = source / "SRK_RUNTIME_VIDEO_CANARY.txt"

    if not firm.is_dir():
        raise SarooRuntimeExecutionProofIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not canary_marker.is_file():
        raise SarooRuntimeExecutionProofIntegrationError(
            "source is not a validated SRK runtime-video canary tree; marker is missing"
        )
    if not makefile_path.is_file() or not main_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeExecutionProofIntegrationError(
            "source R4 tree is incomplete; Makefile/main.c/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeExecutionProofIntegrationError(
            f"output already exists; choose a new runtime-proof directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeExecutionProofIntegrationError(
            "output must be outside the existing R4 tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    proof_source = helpers / "srk_runtime_execution_proof.c"
    proof_header = helpers / "srk_runtime_execution_proof.h"
    if not proof_source.is_file() or not proof_header.is_file():
        raise SarooRuntimeExecutionProofIntegrationError(
            f"SRK runtime execution-proof helpers are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    main_text = _read_text(main_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_PROOF_OBJECT in makefile_text or _MAIN_PROOF_INCLUDE in main_text:
        raise SarooRuntimeExecutionProofIntegrationError(
            "source tree already contains SRK runtime execution-proof integration"
        )

    for text, anchor, label in (
        (makefile_text, _MAKEFILE_CANARY_OBJECT, "R4 canary Makefile object"),
        (main_text, _MAIN_CAPTURE_INCLUDE, "main capture-helper include"),
        (main_text, _MAIN_INDEX_ANCHOR, "main menu index"),
        (main_text, _MAIN_MENU_ANCHOR, "main capture menu item"),
        (main_text, _MAIN_HANDLER_ANCHOR, "main menu handler"),
        (game_text, _GAME_CANARY_INCLUDE, "game canary include"),
        (game_text, _GAME_HOOK_TAIL_ANCHOR, "game controller-hook tail"),
        (game_text, _GAME_BREAK_ANCHOR, "game breakpoint installation"),
    ):
        if text.count(anchor) != 1:
            raise SarooRuntimeExecutionProofIntegrationError(
                f"expected exactly one {label}; source tree may not match the validated R4 revision"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_CANARY_OBJECT,
        _MAKEFILE_CANARY_OBJECT + _MAKEFILE_PROOF_OBJECT,
        1,
    )
    patched_main = _replace_once(
        main_text,
        _MAIN_CAPTURE_INCLUDE,
        _MAIN_CAPTURE_INCLUDE + _MAIN_PROOF_INCLUDE,
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
        _GAME_CANARY_INCLUDE,
        _GAME_CANARY_INCLUDE + _GAME_PROOF_INCLUDE,
        label="game canary include",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_HOOK_TAIL_ANCHOR,
        _GAME_HOOK_TAIL_PATCH,
        label="game controller-hook tail",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_BREAK_ANCHOR,
        _GAME_BREAK_PATCH,
        label="game breakpoint installation",
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_main = target_firm / "main.c"
        target_game = target_firm / "game_load.c"
        target_proof_source = target_firm / proof_source.name
        target_proof_header = target_firm / proof_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_main, patched_main)
        _write_text(target_game, patched_game)
        shutil.copy2(proof_source, target_proof_source)
        shutil.copy2(proof_header, target_proof_header)

        marker = output / "SRK_RUNTIME_EXECUTION_PROOF.txt"
        _write_text(
            marker,
            "SRK SAROO post-entry runtime execution proof\n"
            f"Source R4 tree: {source}\n"
            "The source R4 tree was not modified.\n"
            "Arm: explicit SAROO-menu action before launching a title.\n"
            "Entry gate: dynamic IP.BIN 1st-read UBR breakpoint; no capture/write.\n"
            "Proof callback: existing SAROO cdp_hook after original BIOS refresh.\n"
            "Threshold: 600 post-entry cdp_hook calls.\n"
            "Visible proof: clear only TVMD.DISP for 120 display frames, then exact restore.\n"
            "Controller buttons are not used by this proof.\n"
            "No SD writes, RAM captures, direct SMPC polling, VRAM/CRAM writes, or VDP1 writes.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeExecutionProofIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        main_path=output / "Firm_Saturn" / "main.c",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        helper_source_path=output / "Firm_Saturn" / proof_source.name,
        helper_header_path=output / "Firm_Saturn" / proof_header.name,
        marker_path=output / "SRK_RUNTIME_EXECUTION_PROOF.txt",
    )
