"""Prepare a separate SAROO tree with SRK's runtime-menu input hook.

This layer starts from the already generated, hardware-validated SRK capture-menu
shape and creates a new output tree.  It copies SRK's title-neutral runtime-input
helper into ``Firm_Saturn``, links it through the generated Makefile, and feeds
completed BIOS controller samples from SAROO's existing ``cdp_hook`` into the
L+R hold detector.

This tranche deliberately stops at an internal menu-request latch.  It performs
no SD writes, no RAM capture, no SMPC polling of its own, and no VDP changes.
Those later actions remain separate hardware-validation steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeMenuIntegrationError(RuntimeError):
    """Raised when the runtime-menu input-hook tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeMenuIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    game_load_path: Path
    runtime_source_path: Path
    runtime_header_path: Path
    marker_path: Path


_MAKEFILE_CAPTURE_OBJECT = "\t\tobj/srk_capture_helper.o  \\\n"
_MAKEFILE_RUNTIME_OBJECT = "\t\tobj/srk_runtime_input.o  \\\n"

_GAME_INCLUDE_ANCHOR = '#include "smpc.h"\n'
_GAME_RUNTIME_INCLUDE = '#include "srk_runtime_input.h"\n'

_GAME_STATE_ANCHOR = "static int (*cdp_boot_game)(void);\nstatic int sk0, sk1;\n"
_GAME_STATE_PATCH = (
    _GAME_STATE_ANCHOR
    + "static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;\n"
    + "static int srk_runtime_menu_requested = 0;\n"
)

_GAME_HOOK_ANCHOR = (
    "static void cdp_hook(void)\n"
    "{\n"
    "\tsk0 = *(u16*)0x06020232;\n"
    "\tsk1 = *(u16*)0x06020236;\n"
    "\torig_func();\n"
    "}\n"
)
_GAME_HOOK_PATCH = (
    "static void cdp_hook(void)\n"
    "{\n"
    "\tint srk_event;\n"
    "\tsk0 = *(u16*)0x06020232;\n"
    "\tsk1 = *(u16*)0x06020236;\n"
    "\tsrk_event = srk_runtime_input_sample(\n"
    "\t\t&srk_runtime_input_state,\n"
    "\t\t(unsigned int)sk0\n"
    "\t);\n"
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU)\n"
    "\t\tsrk_runtime_menu_requested = 1;\n"
    "\torig_func();\n"
    "}\n"
)

_GAME_PLAYER_ANCHOR = (
    "void my_cdplayer(void)\n"
    "{\n"
    "\tvoid (*go)(int);\n"
)
_GAME_PLAYER_PATCH = (
    _GAME_PLAYER_ANCHOR
    + "\n"
    + "\tsrk_runtime_input_reset(&srk_runtime_input_state);\n"
    + "\tsrk_runtime_menu_requested = 0;\n"
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
        raise SarooRuntimeMenuIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeMenuIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeMenuIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree is not the validated SRK/SAROO shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_menu_input_tree(
    capture_menu_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeMenuIntegrationResult:
    """Copy a capture-menu tree and add only the safe runtime input hook.

    The generated tree observes controller-1 data already captured by SAROO's
    BIOS key hook.  A completed L+R hold merely sets an internal request latch;
    there is intentionally no renderer, capture action, or file write yet.
    """

    source = _canonical(capture_menu_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    game_load_path = firm / "game_load.c"
    capture_marker = source / "SRK_CAPTURE_MENU.txt"

    if not firm.is_dir():
        raise SarooRuntimeMenuIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not capture_marker.is_file():
        raise SarooRuntimeMenuIntegrationError(
            "source is not a validated SRK capture-menu tree; marker is missing"
        )
    if not makefile_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeMenuIntegrationError(
            "source capture-menu tree is incomplete; Makefile/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeMenuIntegrationError(
            f"output already exists; choose a new runtime-menu directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeMenuIntegrationError(
            "output must be outside the existing capture-menu tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    runtime_source = helpers / "srk_runtime_input.c"
    runtime_header = helpers / "srk_runtime_input.h"
    if not runtime_source.is_file() or not runtime_header.is_file():
        raise SarooRuntimeMenuIntegrationError(
            f"SRK runtime-input helper sources are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_RUNTIME_OBJECT in makefile_text or _GAME_RUNTIME_INCLUDE in game_text:
        raise SarooRuntimeMenuIntegrationError(
            "source tree already contains SRK runtime-input integration"
        )

    # Validate all anchors before creating output, so an incompatible SAROO
    # revision cannot leave a misleading partially generated tree behind.
    if makefile_text.count(_MAKEFILE_CAPTURE_OBJECT) != 1:
        raise SarooRuntimeMenuIntegrationError(
            "capture-menu Makefile does not contain exactly one SRK capture-helper object"
        )
    for anchor, label in (
        (_GAME_INCLUDE_ANCHOR, "game_load include"),
        (_GAME_STATE_ANCHOR, "game_load controller state"),
        (_GAME_HOOK_ANCHOR, "game_load completed controller hook"),
        (_GAME_PLAYER_ANCHOR, "game_load player initialization"),
    ):
        if game_text.count(anchor) != 1:
            raise SarooRuntimeMenuIntegrationError(
                f"expected exactly one {label} anchor; "
                "SAROO revision may not match the validated integration"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_CAPTURE_OBJECT,
        _MAKEFILE_CAPTURE_OBJECT + _MAKEFILE_RUNTIME_OBJECT,
        1,
    )
    patched_game = _replace_once(
        game_text,
        _GAME_INCLUDE_ANCHOR,
        _GAME_INCLUDE_ANCHOR + _GAME_RUNTIME_INCLUDE,
        label="game_load include",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_STATE_ANCHOR,
        _GAME_STATE_PATCH,
        label="game_load controller state",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_HOOK_ANCHOR,
        _GAME_HOOK_PATCH,
        label="game_load completed controller hook",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_PLAYER_ANCHOR,
        _GAME_PLAYER_PATCH,
        label="game_load player initialization",
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_game = target_firm / "game_load.c"
        target_runtime_source = target_firm / runtime_source.name
        target_runtime_header = target_firm / runtime_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_game, patched_game)
        shutil.copy2(runtime_source, target_runtime_source)
        shutil.copy2(runtime_header, target_runtime_header)

        marker = output / "SRK_RUNTIME_MENU.txt"
        _write_text(
            marker,
            "SRK SAROO runtime-menu input-hook tranche\n"
            f"Source capture-menu tree: {source}\n"
            "The source capture-menu tree was not modified.\n"
            "Input source: SAROO completed BIOS controller sample (controller 1).\n"
            "Activation: hold Saturn L+R for 50 consecutive completed samples.\n"
            "Current action: set an internal runtime-menu request latch only.\n"
            "No runtime menu renderer is installed by this tranche.\n"
            "No SD writes, RAM captures, SMPC polling, or VDP changes are performed.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeMenuIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        runtime_source_path=output / "Firm_Saturn" / runtime_source.name,
        runtime_header_path=output / "Firm_Saturn" / runtime_header.name,
        marker_path=output / "SRK_RUNTIME_MENU.txt",
    )
