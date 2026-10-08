"""Add SRK's renderer-independent runtime-menu state machine to a validated hook tree.

This stage intentionally starts from the already hardware-validated runtime-input
hook tree.  It creates a new output tree, links the title-neutral menu-state
helper, and feeds completed controller samples into that helper.  It still does
not render, capture memory, write the SD card, or issue SMPC commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeMenuStateIntegrationError(RuntimeError):
    """Raised when the runtime-menu state tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeMenuStateIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    game_load_path: Path
    state_source_path: Path
    state_header_path: Path
    marker_path: Path


_MAKEFILE_RUNTIME_INPUT_OBJECT = "\t\tobj/srk_runtime_input.o  \\\n"
_MAKEFILE_MENU_STATE_OBJECT = "\t\tobj/srk_runtime_menu_state.o  \\\n"

_GAME_INPUT_INCLUDE = '#include "srk_runtime_input.h"\n'
_GAME_STATE_INCLUDE = '#include "srk_runtime_menu_state.h"\n'

_GAME_STATE_ANCHOR = (
    "static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;\n"
    "static int srk_runtime_menu_requested = 0;\n"
)
_GAME_STATE_PATCH = (
    "static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;\n"
    "static SRK_RUNTIME_MENU_STATE srk_runtime_menu_state;\n"
)

_GAME_EVENT_ANCHOR = (
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU)\n"
    "\t\tsrk_runtime_menu_requested = 1;\n"
    "\torig_func();\n"
)
_GAME_EVENT_PATCH = (
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU)\n"
    "\t\tsrk_runtime_menu_request_open(&srk_runtime_menu_state);\n"
    "\tif(srk_runtime_menu_state.active)\n"
    "\t\tsrk_runtime_menu_state_sample(\n"
    "\t\t\t&srk_runtime_menu_state,\n"
    "\t\t\t(unsigned int)sk0\n"
    "\t\t);\n"
    "\torig_func();\n"
)

_GAME_RESET_ANCHOR = (
    "\tsrk_runtime_input_reset(&srk_runtime_input_state);\n"
    "\tsrk_runtime_menu_requested = 0;\n"
)
_GAME_RESET_PATCH = (
    "\tsrk_runtime_input_reset(&srk_runtime_input_state);\n"
    "\tsrk_runtime_menu_state_reset(&srk_runtime_menu_state);\n"
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
        raise SarooRuntimeMenuStateIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeMenuStateIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeMenuStateIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree is not the validated SRK runtime-hook shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_menu_state_tree(
    runtime_hook_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeMenuStateIntegrationResult:
    """Create a separate runtime-menu state tree from a validated hook tree."""

    source = _canonical(runtime_hook_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    game_load_path = firm / "game_load.c"
    runtime_marker = source / "SRK_RUNTIME_MENU.txt"

    if not firm.is_dir():
        raise SarooRuntimeMenuStateIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not runtime_marker.is_file():
        raise SarooRuntimeMenuStateIntegrationError(
            "source is not a validated SRK runtime-hook tree; marker is missing"
        )
    if not makefile_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeMenuStateIntegrationError(
            "source runtime-hook tree is incomplete; Makefile/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeMenuStateIntegrationError(
            f"output already exists; choose a new runtime-menu-state directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeMenuStateIntegrationError(
            "output must be outside the existing runtime-hook tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    state_source = helpers / "srk_runtime_menu_state.c"
    state_header = helpers / "srk_runtime_menu_state.h"
    if not state_source.is_file() or not state_header.is_file():
        raise SarooRuntimeMenuStateIntegrationError(
            f"SRK runtime-menu state helpers are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_MENU_STATE_OBJECT in makefile_text or _GAME_STATE_INCLUDE in game_text:
        raise SarooRuntimeMenuStateIntegrationError(
            "source tree already contains SRK runtime-menu state integration"
        )

    if makefile_text.count(_MAKEFILE_RUNTIME_INPUT_OBJECT) != 1:
        raise SarooRuntimeMenuStateIntegrationError(
            "runtime-hook Makefile does not contain exactly one runtime-input object"
        )
    for anchor, label in (
        (_GAME_INPUT_INCLUDE, "runtime-input include"),
        (_GAME_STATE_ANCHOR, "runtime-menu request state"),
        (_GAME_EVENT_ANCHOR, "runtime-menu request event"),
        (_GAME_RESET_ANCHOR, "runtime-menu reset"),
    ):
        if game_text.count(anchor) != 1:
            raise SarooRuntimeMenuStateIntegrationError(
                f"expected exactly one {label} anchor; "
                "source tree may not match the validated runtime-hook revision"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_RUNTIME_INPUT_OBJECT,
        _MAKEFILE_RUNTIME_INPUT_OBJECT + _MAKEFILE_MENU_STATE_OBJECT,
        1,
    )
    patched_game = _replace_once(
        game_text,
        _GAME_INPUT_INCLUDE,
        _GAME_INPUT_INCLUDE + _GAME_STATE_INCLUDE,
        label="runtime-input include",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_STATE_ANCHOR,
        _GAME_STATE_PATCH,
        label="runtime-menu request state",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_EVENT_ANCHOR,
        _GAME_EVENT_PATCH,
        label="runtime-menu request event",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_RESET_ANCHOR,
        _GAME_RESET_PATCH,
        label="runtime-menu reset",
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_game = target_firm / "game_load.c"
        target_state_source = target_firm / state_source.name
        target_state_header = target_firm / state_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_game, patched_game)
        shutil.copy2(state_source, target_state_source)
        shutil.copy2(state_header, target_state_header)

        marker = output / "SRK_RUNTIME_MENU_STATE.txt"
        _write_text(
            marker,
            "SRK SAROO runtime-menu state-machine tranche\n"
            f"Source runtime-hook tree: {source}\n"
            "The source runtime-hook tree was not modified.\n"
            "Activation still comes from the hardware-validated L+R hold detector.\n"
            "Menu state opens on that event and arms controls only after L+R release.\n"
            "Resume event: new A, B, or Start press after controls are armed.\n"
            "No renderer is installed by this tranche.\n"
            "No SD writes, RAM captures, direct SMPC polling, or VDP changes are performed.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeMenuStateIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        state_source_path=output / "Firm_Saturn" / state_source.name,
        state_header_path=output / "Firm_Saturn" / state_header.name,
        marker_path=output / "SRK_RUNTIME_MENU_STATE.txt",
    )
