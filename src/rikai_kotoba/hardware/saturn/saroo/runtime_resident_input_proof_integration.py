"""Prepare R9: persistent runtime-input proof on the proven resident trampoline.

R8 physically proved that SRK can execute repeatedly through the Saturn BIOS
HBLANK-IN path while a commercial title is active.  R9 keeps that exact
context-safe assembly pattern and asks the next narrow question: can the resident
callback remain installed until the player deliberately holds L+R, then persist
that activation without direct SMPC polling or VDP changes?

The controller-1 value is observed from the same BIOS memory snapshot already
used by upstream SAROO.  Because the resident trampoline is entered from
HBLANK-IN, raw callback frequency is much higher than controller sampling.  R9
therefore rate-limits observations with SAROO's 1 MHz ``SS_TIMER`` to one sample
per 20 ms before feeding the existing 50-sample L+R detector.

The source capture-menu tree is never modified in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeResidentInputProofIntegrationError(RuntimeError):
    """Raised when an R9 resident-input proof tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeResidentInputProofIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    main_path: Path
    game_load_path: Path
    runtime_input_source_path: Path
    runtime_input_header_path: Path
    proof_source_path: Path
    proof_header_path: Path
    trampoline_source_path: Path
    marker_path: Path


_MAKEFILE_CAPTURE_OBJECT = "\t\tobj/srk_capture_helper.o  \\\n"
_MAKEFILE_RUNTIME_INPUT_OBJECT = "\t\tobj/srk_runtime_input.o  \\\n"
_MAKEFILE_PROOF_OBJECT = "\t\tobj/srk_runtime_resident_input_proof.o  \\\n"
_MAKEFILE_TRAMPOLINE_OBJECT = "\t\tobj/srk_runtime_resident_input_trampoline.o  \\\n"

_MAIN_CAPTURE_INCLUDE = '#include "srk_capture_helper.h"\n'
_MAIN_PROOF_INCLUDE = '#include "srk_runtime_resident_input_proof.h"\n'
_MAIN_INDEX_ANCHOR = "int srk_wramh_index = -1;\n"
_MAIN_INDEX_PATCH = _MAIN_INDEX_ANCHOR + "int srk_runtime_resident_input_index = -1;\n"
_MAIN_MENU_ANCHOR = '\tadd_menu_item(&main_menu, "SRK Capture WRAM-H");\n'
_MAIN_MENU_PATCH = (
    _MAIN_MENU_ANCHOR
    + "\tsrk_runtime_resident_input_index = main_menu.num;\n"
    + '\tadd_menu_item(&main_menu, "SRK Arm Runtime Input");\n'
)
_MAIN_HANDLER_ANCHOR = "\t}else if(index==update_index){\n"
_MAIN_HANDLER_PATCH = r'''	}else if(index==srk_runtime_resident_input_index){
		int retv;
		retv = srk_runtime_resident_input_proof_arm();
		if(retv==SRK_RUNTIME_RESIDENT_INPUT_PROOF_OK){
			menu_status(&main_menu, "SRK: runtime input armed");
		}else{
			char buf[64];
			sprintf(buf, "SRK: runtime input arm failed: %d", retv);
			menu_status(&main_menu, buf);
		}
		return 0;
'''

_GAME_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_GAME_PROOF_INCLUDE = '#include "srk_runtime_resident_input_proof.h"\n'
_GAME_PATCH_ANCHOR = '\tpatch_game((char*)0x06002020);\n'
_GAME_PATCH_REPLACEMENT = (
    _GAME_PATCH_ANCHOR
    + "\t{\n"
    + "\t\tint srk_input_ret = srk_runtime_resident_input_proof_install();\n"
    + "\t\tif(srk_input_ret<0)\n"
    + '\t\t\tprintk("SRK resident input proof install failed: %d\\n", srk_input_ret);\n'
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
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"cannot read {path}: {exc}"
        ) from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"cannot write {path}: {exc}"
        ) from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree may not match the validated capture-menu shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_resident_input_proof_tree(
    capture_menu_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeResidentInputProofIntegrationResult:
    """Create a separate R9 resident-input proof tree from the capture-menu tree."""

    source = _canonical(capture_menu_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    main_path = firm / "main.c"
    game_load_path = firm / "game_load.c"
    capture_marker = source / "SRK_CAPTURE_MENU.txt"

    if not firm.is_dir():
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not capture_marker.is_file():
        raise SarooRuntimeResidentInputProofIntegrationError(
            "source is not a validated SRK capture-menu tree; marker is missing"
        )
    if not makefile_path.is_file() or not main_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeResidentInputProofIntegrationError(
            "source capture-menu tree is incomplete; Makefile/main.c/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"output already exists; choose a new resident-input directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeResidentInputProofIntegrationError(
            "output must be outside the existing capture-menu tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    runtime_input_source = helpers / "srk_runtime_input.c"
    runtime_input_header = helpers / "srk_runtime_input.h"
    proof_source = helpers / "srk_runtime_resident_input_proof.c"
    proof_header = helpers / "srk_runtime_resident_input_proof.h"
    trampoline_source = helpers / "srk_runtime_resident_input_trampoline.S"
    required = (
        runtime_input_source,
        runtime_input_header,
        proof_source,
        proof_header,
        trampoline_source,
    )
    if any(not path.is_file() for path in required):
        raise SarooRuntimeResidentInputProofIntegrationError(
            f"SRK R9 helper sources are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    main_text = _read_text(main_path)
    game_text = _read_text(game_load_path)

    for marker in (
        _MAKEFILE_RUNTIME_INPUT_OBJECT,
        _MAKEFILE_PROOF_OBJECT,
        _MAKEFILE_TRAMPOLINE_OBJECT,
    ):
        if marker in makefile_text:
            raise SarooRuntimeResidentInputProofIntegrationError(
                "source tree already contains SRK R9 resident-input integration"
            )
    if _MAIN_PROOF_INCLUDE in main_text or _GAME_PROOF_INCLUDE in game_text:
        raise SarooRuntimeResidentInputProofIntegrationError(
            "source tree already contains SRK R9 resident-input integration"
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
            raise SarooRuntimeResidentInputProofIntegrationError(
                f"expected exactly one {label}; source tree may not match the validated capture-menu revision"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_CAPTURE_OBJECT,
        _MAKEFILE_CAPTURE_OBJECT
        + _MAKEFILE_RUNTIME_INPUT_OBJECT
        + _MAKEFILE_PROOF_OBJECT
        + _MAKEFILE_TRAMPOLINE_OBJECT,
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
        _GAME_INCLUDE_ANCHOR,
        _GAME_INCLUDE_ANCHOR + _GAME_PROOF_INCLUDE,
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

        _write_text(target_makefile, patched_makefile)
        _write_text(target_main, patched_main)
        _write_text(target_game, patched_game)

        copied: dict[Path, Path] = {}
        for helper in required:
            target = target_firm / helper.name
            shutil.copy2(helper, target)
            copied[helper] = target

        marker = output / "SRK_RUNTIME_RESIDENT_INPUT_PROOF.txt"
        _write_text(
            marker,
            "SRK SAROO R9 resident runtime-input proof\n"
            f"Source capture-menu tree: {source}\n"
            "The source capture-menu tree was not modified.\n"
            "Arm: SRK Arm Runtime Input in SAROO menu.\n"
            "Hook: context-safe BIOS HBLANK-IN trampoline at 0x0600090C.\n"
            "Install point: immediately after patch_game() once 1ST_READ is loaded.\n"
            "Input source: BIOS controller-1 memory snapshot at 0x06020232.\n"
            "Sampling: at most once every 20000 SS_TIMER ticks (20 ms).\n"
            "Activation: L+R for 50 rate-limited samples (approximately 1 second).\n"
            "Persistent evidence: /SAROO/SRK_RUNTIME_INPUT_PROOF.BIN (96 bytes).\n"
            "Slots: armed, installed, activated.\n"
            "Runtime direct SMPC polling: none. VDP dependency: none.\n"
            "Waiting path performs no SD I/O; activation performs one 32-byte update.\n"
            "After activation the original BIOS HBLANK-IN vector is restored.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeResidentInputProofIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        main_path=output / "Firm_Saturn" / "main.c",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        runtime_input_source_path=copied[runtime_input_source],
        runtime_input_header_path=copied[runtime_input_header],
        proof_source_path=copied[proof_source],
        proof_header_path=copied[proof_header],
        trampoline_source_path=copied[trampoline_source],
        marker_path=marker,
    )
