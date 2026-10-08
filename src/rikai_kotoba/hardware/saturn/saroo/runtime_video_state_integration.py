"""Add SRK's read-only VDP2 preservation snapshot to a runtime-menu state tree.

This stage starts from the generated runtime-menu state-machine tree and creates
another separate output tree.  It links the title-neutral video-state helper and
captures only the VDP2 color-offset registers when the menu lifecycle opens.

The generated firmware still performs no visible rendering and writes no VDP,
VRAM, CRAM, SD-card, or capture state.  This is an intentionally read-only
hardware checkpoint before any visible canary or overlay is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeVideoStateIntegrationError(RuntimeError):
    """Raised when the runtime video-state tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeVideoStateIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    makefile_path: Path
    game_load_path: Path
    video_source_path: Path
    video_header_path: Path
    marker_path: Path


_MAKEFILE_MENU_STATE_OBJECT = "\t\tobj/srk_runtime_menu_state.o  \\\n"
_MAKEFILE_VIDEO_STATE_OBJECT = "\t\tobj/srk_runtime_video_state.o  \\\n"

_GAME_MENU_STATE_INCLUDE = '#include "srk_runtime_menu_state.h"\n'
_GAME_VIDEO_STATE_INCLUDE = '#include "srk_runtime_video_state.h"\n'

_GAME_STATE_ANCHOR = (
    "static SRK_RUNTIME_INPUT_STATE srk_runtime_input_state;\n"
    "static SRK_RUNTIME_MENU_STATE srk_runtime_menu_state;\n"
)
_GAME_STATE_PATCH = (
    _GAME_STATE_ANCHOR
    + "static SRK_RUNTIME_VIDEO_STATE srk_runtime_video_state;\n"
)

_GAME_EVENT_DECL_ANCHOR = "\tint srk_event;\n"
_GAME_EVENT_DECL_PATCH = (
    "\tint srk_event;\n"
    "\tint srk_menu_event;\n"
)

_GAME_EVENT_ANCHOR = (
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU)\n"
    "\t\tsrk_runtime_menu_request_open(&srk_runtime_menu_state);\n"
    "\tif(srk_runtime_menu_state.active)\n"
    "\t\tsrk_runtime_menu_state_sample(\n"
    "\t\t\t&srk_runtime_menu_state,\n"
    "\t\t\t(unsigned int)sk0\n"
    "\t\t);\n"
    "\torig_func();\n"
)
_GAME_EVENT_PATCH = (
    "\tsrk_menu_event = SRK_RUNTIME_MENU_EVENT_NONE;\n"
    "\tif(srk_event==SRK_RUNTIME_INPUT_OPEN_MENU){\n"
    "\t\tsrk_menu_event = srk_runtime_menu_request_open(&srk_runtime_menu_state);\n"
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED)\n"
    "\t\t\tsrk_runtime_video_state_capture(&srk_runtime_video_state);\n"
    "\t}\n"
    "\tif(srk_runtime_menu_state.active){\n"
    "\t\tsrk_menu_event = srk_runtime_menu_state_sample(\n"
    "\t\t\t&srk_runtime_menu_state,\n"
    "\t\t\t(unsigned int)sk0\n"
    "\t\t);\n"
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_RESUMED)\n"
    "\t\t\tsrk_runtime_video_state_reset(&srk_runtime_video_state);\n"
    "\t}\n"
    "\torig_func();\n"
)

_GAME_RESET_ANCHOR = (
    "\tsrk_runtime_input_reset(&srk_runtime_input_state);\n"
    "\tsrk_runtime_menu_state_reset(&srk_runtime_menu_state);\n"
)
_GAME_RESET_PATCH = (
    _GAME_RESET_ANCHOR
    + "\tsrk_runtime_video_state_reset(&srk_runtime_video_state);\n"
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
        raise SarooRuntimeVideoStateIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeVideoStateIntegrationError(f"cannot write {path}: {exc}") from exc


def _replace_once(text: str, anchor: str, replacement: str, *, label: str) -> str:
    count = text.count(anchor)
    if count != 1:
        raise SarooRuntimeVideoStateIntegrationError(
            f"expected exactly one {label} anchor, found {count}; "
            "source tree is not the validated SRK runtime-state shape"
        )
    return text.replace(anchor, replacement, 1)


def prepare_runtime_video_state_tree(
    runtime_state_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeVideoStateIntegrationResult:
    """Create a separate tree with read-only runtime VDP2 state capture."""

    source = _canonical(runtime_state_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    makefile_path = firm / "Makefile"
    game_load_path = firm / "game_load.c"
    state_marker = source / "SRK_RUNTIME_MENU_STATE.txt"

    if not firm.is_dir():
        raise SarooRuntimeVideoStateIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not state_marker.is_file():
        raise SarooRuntimeVideoStateIntegrationError(
            "source is not a validated SRK runtime-menu state tree; marker is missing"
        )
    if not makefile_path.is_file() or not game_load_path.is_file():
        raise SarooRuntimeVideoStateIntegrationError(
            "source runtime-state tree is incomplete; Makefile/game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeVideoStateIntegrationError(
            f"output already exists; choose a new runtime-video-state directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeVideoStateIntegrationError(
            "output must be outside the existing runtime-state tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    video_source = helpers / "srk_runtime_video_state.c"
    video_header = helpers / "srk_runtime_video_state.h"
    if not video_source.is_file() or not video_header.is_file():
        raise SarooRuntimeVideoStateIntegrationError(
            f"SRK runtime-video state helpers are unavailable beneath: {helpers}"
        )

    makefile_text = _read_text(makefile_path)
    game_text = _read_text(game_load_path)

    if _MAKEFILE_VIDEO_STATE_OBJECT in makefile_text or _GAME_VIDEO_STATE_INCLUDE in game_text:
        raise SarooRuntimeVideoStateIntegrationError(
            "source tree already contains SRK runtime-video state integration"
        )

    if makefile_text.count(_MAKEFILE_MENU_STATE_OBJECT) != 1:
        raise SarooRuntimeVideoStateIntegrationError(
            "runtime-state Makefile does not contain exactly one menu-state object"
        )
    for anchor, label in (
        (_GAME_MENU_STATE_INCLUDE, "menu-state include"),
        (_GAME_STATE_ANCHOR, "runtime state declarations"),
        (_GAME_EVENT_DECL_ANCHOR, "runtime event declaration"),
        (_GAME_EVENT_ANCHOR, "runtime menu lifecycle event block"),
        (_GAME_RESET_ANCHOR, "runtime reset block"),
    ):
        if game_text.count(anchor) != 1:
            raise SarooRuntimeVideoStateIntegrationError(
                f"expected exactly one {label} anchor; "
                "source tree may not match the validated runtime-state revision"
            )

    patched_makefile = makefile_text.replace(
        _MAKEFILE_MENU_STATE_OBJECT,
        _MAKEFILE_MENU_STATE_OBJECT + _MAKEFILE_VIDEO_STATE_OBJECT,
        1,
    )
    patched_game = _replace_once(
        game_text,
        _GAME_MENU_STATE_INCLUDE,
        _GAME_MENU_STATE_INCLUDE + _GAME_VIDEO_STATE_INCLUDE,
        label="menu-state include",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_STATE_ANCHOR,
        _GAME_STATE_PATCH,
        label="runtime state declarations",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_EVENT_DECL_ANCHOR,
        _GAME_EVENT_DECL_PATCH,
        label="runtime event declaration",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_EVENT_ANCHOR,
        _GAME_EVENT_PATCH,
        label="runtime menu lifecycle event block",
    )
    patched_game = _replace_once(
        patched_game,
        _GAME_RESET_ANCHOR,
        _GAME_RESET_PATCH,
        label="runtime reset block",
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_makefile = target_firm / "Makefile"
        target_game = target_firm / "game_load.c"
        target_video_source = target_firm / video_source.name
        target_video_header = target_firm / video_header.name

        _write_text(target_makefile, patched_makefile)
        _write_text(target_game, patched_game)
        shutil.copy2(video_source, target_video_source)
        shutil.copy2(video_header, target_video_header)

        marker = output / "SRK_RUNTIME_VIDEO_STATE.txt"
        _write_text(
            marker,
            "SRK SAROO runtime-video read-only state tranche\n"
            f"Source runtime-state tree: {source}\n"
            "The source runtime-state tree was not modified.\n"
            "On menu-open, SRK snapshots only VDP2 color-offset registers.\n"
            "On Resume, that in-memory snapshot is discarded without hardware writes.\n"
            "Current renderer: none.\n"
            "VDP writes: none. VRAM/CRAM writes: none.\n"
            "No SD writes, RAM captures, or direct SMPC polling are performed.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeVideoStateIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        makefile_path=output / "Firm_Saturn" / "Makefile",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        video_source_path=output / "Firm_Saturn" / video_source.name,
        video_header_path=output / "Firm_Saturn" / video_header.name,
        marker_path=output / "SRK_RUNTIME_VIDEO_STATE.txt",
    )
