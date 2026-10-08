"""Prepare a bounded visible-canary SAROO tree from a runtime-video state tree.

This stage is deliberately narrower than the eventual text overlay.  It keeps
all title-owned VRAM/CRAM and VDP1 resources untouched.  On the already
validated L+R menu-open event SRK snapshots the VDP2 color-offset register set,
applies a short red color-offset pulse for three display frames, restores the
exact captured register values, and then returns to the normal title path.

The source generated tree is never modified in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil

from .firmware_integration import default_helper_root


class SarooRuntimeVideoCanaryIntegrationError(RuntimeError):
    """Raised when the runtime video-canary tree cannot be prepared safely."""


@dataclass(frozen=True)
class SarooRuntimeVideoCanaryIntegrationResult:
    source_root: Path
    output_root: Path
    firm_saturn_directory: Path
    game_load_path: Path
    video_source_path: Path
    video_header_path: Path
    marker_path: Path


_GAME_CAPTURE_ONLY_ANCHOR = (
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED)\n"
    "\t\t\tsrk_runtime_video_state_capture(&srk_runtime_video_state);\n"
)
_GAME_CANARY_PATCH = (
    "\t\tif(srk_menu_event==SRK_RUNTIME_MENU_EVENT_OPENED){\n"
    "\t\t\tif(srk_runtime_video_state_capture(&srk_runtime_video_state))\n"
    "\t\t\t\tsrk_runtime_video_canary_pulse(&srk_runtime_video_state);\n"
    "\t\t}\n"
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
        raise SarooRuntimeVideoCanaryIntegrationError(f"cannot read {path}: {exc}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise SarooRuntimeVideoCanaryIntegrationError(f"cannot write {path}: {exc}") from exc


def prepare_runtime_video_canary_tree(
    runtime_video_source_root: os.PathLike[str] | str,
    output_root: os.PathLike[str] | str,
    *,
    helper_root: os.PathLike[str] | str | None = None,
) -> SarooRuntimeVideoCanaryIntegrationResult:
    """Create a separate generated tree containing the bounded visible canary."""

    source = _canonical(runtime_video_source_root)
    output = _canonical(output_root)
    firm = source / "Firm_Saturn"
    game_load_path = firm / "game_load.c"
    video_marker = source / "SRK_RUNTIME_VIDEO_STATE.txt"

    if not firm.is_dir():
        raise SarooRuntimeVideoCanaryIntegrationError(
            f"generated Firm_Saturn directory not found beneath: {source}"
        )
    if not video_marker.is_file():
        raise SarooRuntimeVideoCanaryIntegrationError(
            "source is not a validated SRK runtime-video state tree; marker is missing"
        )
    if not game_load_path.is_file():
        raise SarooRuntimeVideoCanaryIntegrationError(
            "source runtime-video tree is incomplete; game_load.c is missing"
        )
    if output.exists():
        raise SarooRuntimeVideoCanaryIntegrationError(
            f"output already exists; choose a new runtime-video-canary directory: {output}"
        )
    if output == source or _inside(output, source):
        raise SarooRuntimeVideoCanaryIntegrationError(
            "output must be outside the existing runtime-video tree"
        )

    helpers = _canonical(helper_root) if helper_root is not None else default_helper_root()
    video_source = helpers / "srk_runtime_video_state.c"
    video_header = helpers / "srk_runtime_video_state.h"
    if not video_source.is_file() or not video_header.is_file():
        raise SarooRuntimeVideoCanaryIntegrationError(
            f"SRK runtime-video helper sources are unavailable beneath: {helpers}"
        )

    game_text = _read_text(game_load_path)
    if "srk_runtime_video_canary_pulse(&srk_runtime_video_state)" in game_text:
        raise SarooRuntimeVideoCanaryIntegrationError(
            "source tree already contains SRK runtime-video canary integration"
        )
    if game_text.count(_GAME_CAPTURE_ONLY_ANCHOR) != 1:
        raise SarooRuntimeVideoCanaryIntegrationError(
            "expected exactly one read-only runtime-video capture anchor; "
            "source tree may not match the validated R3 revision"
        )

    patched_game = game_text.replace(
        _GAME_CAPTURE_ONLY_ANCHOR,
        _GAME_CANARY_PATCH,
        1,
    )

    try:
        shutil.copytree(source, output)
        target_firm = output / "Firm_Saturn"
        target_game = target_firm / "game_load.c"
        target_video_source = target_firm / video_source.name
        target_video_header = target_firm / video_header.name

        _write_text(target_game, patched_game)
        shutil.copy2(video_source, target_video_source)
        shutil.copy2(video_header, target_video_header)

        marker = output / "SRK_RUNTIME_VIDEO_CANARY.txt"
        _write_text(
            marker,
            "SRK SAROO bounded runtime-video canary tranche\n"
            f"Source runtime-video tree: {source}\n"
            "The source runtime-video tree was not modified.\n"
            "Activation: hardware-validated L+R hold event.\n"
            "Visible action: red VDP2 color-offset pulse for three display frames.\n"
            "Restore: exact captured VDP2 color-offset register values before return.\n"
            "CLOFSL is never changed by the canary; both offset banks are programmed equally.\n"
            "VRAM writes: none. CRAM writes: none. VDP1 writes: none.\n"
            "No SD writes, RAM captures, or direct SMPC polling are performed.\n"
            "This is a visibility/restore canary, not the final SRK text menu.\n",
        )
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise

    return SarooRuntimeVideoCanaryIntegrationResult(
        source_root=source,
        output_root=output,
        firm_saturn_directory=output / "Firm_Saturn",
        game_load_path=output / "Firm_Saturn" / "game_load.c",
        video_source_path=output / "Firm_Saturn" / video_source.name,
        video_header_path=output / "Firm_Saturn" / video_header.name,
        marker_path=output / "SRK_RUNTIME_VIDEO_CANARY.txt",
    )
