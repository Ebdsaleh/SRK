"""Prepare a separate SAROO tree with SRK's first modal red runtime shell.

This stage starts from the bounded R4 canary tree.  It keeps the running title's
main path inside SAROO's existing BIOS controller hook while SRK owns a solid-red
VDP2 color-offset surface.  The original BIOS controller routine is invoked once
per display frame so the already validated release-gated L+R detector can close
the modal state.  Exact captured color-offset registers are restored before the
hook returns.

A 600-display-frame fail-safe restores the title even if the dismissal gesture
is not observed.  The source generated tree is never modified in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeModalRedIntegrationError(RuntimeError):
    """Raised when the modal-red runtime tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeModalRedIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    game_load_path: Path
    modal_source_path: Path
    modal_header_path: Path
    canary_source_path: Path
    canary_header_path: Path
    marker_path: Path


_MAKEFILE_CANARY_OBJECT = "\t\tobj/srk_runtime_video_canary.o  \\\n"
_MAKEFILE_MODAL_OBJECT = "\t\tobj/srk_runtime_modal_red.o  \\\n"
_GAME_CANARY_INCLUDE = '#include "srk_runtime_video_canary.h"\n'
_GAME_MODAL_INCLUDE = '#include "srk_runtime_modal_red.h"\n'

_GAME_R4_OPEN_ANCHOR = (
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU){\n"
    "\t\tsrk_menu_event = srk_runtime_menu_request_open(&srk_runtime_menu_state);\n"
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED){\n"
    "\t\t\tif(srk_runtime_video_state_capture(&srk_runtime_video_state))\n"
    "\t\t\t\tsrk_runtime_video_canary_pulse(&srk_runtime_video_state);\n"
    "\t\t}\n"
    "\t}\n"
)
_GAME_MODAL_OPEN_PATCH = (
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU){\n"
    "\t\tsrk_menu_event = srk_runtime_menu_request_open(&srk_runtime_menu_state);\n"
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED){\n"
    "\t\t\tif(srk_runtime_video_state_capture(&srk_runtime_video_state)){\n"
    "\t\t\t\tsrk_runtime_modal_red_run(\n"
    "\t\t\t\t\t&srk_runtime_input_state,\n"
    "\t\t\t\t\t&srk_runtime_menu_state,\n"
    "\t\t\t\t\t&srk_runtime_video_state,\n"
    "\t\t\t\t\torig_func,\n"
    "\t\t\t\t\t(volatile unsigned short*)0x06020232\n"
    "\t\t\t\t);\n"
    "\t\t\t\tsrk_runtime_video_state_reset(&srk_runtime_video_state);\n"
    "\t\t\t\treturn;\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t}\n"
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
        raise SarooRuntimeModalRedIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeModalRedIntegrationError(f"cannot write {path}: {exc}") from exc


def prepare_runtime_modal_red_tree(
    runtime_canary_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeModalRedIntegrationResult:
    """Create a separate R5 modal-red tree from the validated R4 canary tree."""

    source = _canonical(runtime_canary_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    game_load_path = firm / "game_load.c"
    canary_marker = source / "SRK_RUNTIME_VIDEO_CANARY.txt"

    if not firm.is_dir():
        raise SarooRuntimeModalRedIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not canary_marker.is_file():
        raise SarooRuntimeModalRedIntegrationError(
            "source is not a validated SRK runtime-video canary tree; marker is missing"
        )
    if not makefile_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeModalRedIntegrationError(
            "source runtime-canary tree is incomplete; Makefile/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeModalRedIntegrationError(
            f"output already exists; choose a new runtime-modal directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeModalRedIntegrationError(
            "output must be outside the existing runtime-canary tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    modal_source = helpers / "srk_runtime_modal_red.c"
    modal_header = helpers / "srk_runtime_modal_red.h"
    canary_source = helpers / "srk_runtime_video_canary.c"
    canary_header = helpers / "srk_runtime_video_canary.h"
    for helper in (modal_source, modal_header, canary_source, canary_header):
        if not helper.is_file():
            raise SarooRuntimeModalRedIntegrationError(
                f"required SRK runtime helper is unavailable: {helper}"
            )

    makefile_text = _read_text(makefile_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_MODAL_OBJECT in makefile_text or _GAME_MODAL_INCLUDE in game_text:
        raise SarooRuntimeModalRedIntegrationError(
            "source tree already contains SRK modal-red integration"
        )
    if makefile_text.count(_MAKEFILE_CANARY_OBJECT) != 1:
        raise SarooRuntimeModalRedIntegrationError(
            "runtime-canary Makefile does not contain exactly one canary object"
        )
    if game_text.count(_GAME_CANARY_INCLUDE) != 1:
        raise SarooRuntimeModalRedIntegrationError(
            "runtime-canary game_load.c does not contain exactly one canary include"
        )
    if game_text.count(_GAME_R4_OPEN_ANCHOR) != 1:
        raise SarooRuntimeModalRedIntegrationError(
            "expected exactly one bounded R4 canary-open block; "
            "source tree may not match the validated R4 revision"
        )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_CANARY_OBJECT,
        _MAKEFILE_CANARY_OBJECT + _MAKEFILE_MODAL_OBJECT,
        1,
    )
    patched_game = game_text.replace(
        _GAME_CANARY_INCLUDE,
        _GAME_CANARY_INCLUDE + _GAME_MODAL_INCLUDE,
        1,
    )
    patched_game = patched_game.replace(
        _GAME_R4_OPEN_ANCHOR,
        _GAME_MODAL_OPEN_PATCH,
        1,
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_game = target_firm / "game_load.c"
        target_modal_source = target_firm / modal_source.name
        target_modal_header = target_firm / modal_header.name
        target_canary_source = target_firm / canary_source.name
        target_canary_header = target_firm / canary_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_game, patched_game)
        shutil.copy2(modal_source, target_modal_source)
        shutil.copy2(modal_header, target_modal_header)
        shutil.copy2(canary_source, target_canary_source)
        shutil.copy2(canary_header, target_canary_header)

        marker = output / "SRK_RUNTIME_MODAL_RED.txt"
        _write_text(
            marker,
            "SRK SAROO modal red-shell tranche\n"
            f"Source runtime-canary tree: {source}\n"
            "The source runtime-canary tree was not modified.\n"
            "Open: hardware-validated L+R hold event.\n"
            "Display: solid-red VDP2 color-offset takeover; no VRAM/CRAM/VDP1 writes.\n"
            "Title path: remains blocked inside the existing BIOS controller hook.\n"
            "Input while modal: original BIOS controller routine once per display frame.\n"
            "Dismiss: release L+R fully, then hold L+R for 50 fresh samples.\n"
            "Fail-safe: automatic restore after 600 display frames.\n"
            "Restore: exact captured VDP2 color-offset register values before return.\n"
            "No SD writes, RAM captures, or direct SMPC polling are performed.\n"
            "This is a modal lifecycle proof, not the final text menu.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeModalRedIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        modal_source_path=output / "Firm_Saturn" / modal_source.name,
        modal_header_path=output / "Firm_Saturn" / modal_header.name,
        canary_source_path=output / "Firm_Saturn" / canary_source.name,
        canary_header_path=output / "Firm_Saturn" / canary_header.name,
        marker_path=output / "SRK_RUNTIME_MODAL_RED.txt",
    )
