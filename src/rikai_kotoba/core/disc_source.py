"""Generic discovery and opening of read-only optical-disc sources.

This module is intentionally platform- and game-agnostic.  It centralizes the
small amount of filesystem logic needed to choose between a standalone image
(``DiscImage``) and a CUE-backed multi-track disc (``CueDisc``).
"""

from __future__ import annotations

import os
from typing import List

from rikai_kotoba.core.cue_disc import CueDisc, parse_cue
from rikai_kotoba.core.disc_image import DiscImage


CUE_EXTENSION = ".cue"
STANDALONE_IMAGE_EXTENSIONS = (".bin", ".img", ".iso", ".raw")
SUPPORTED_DISC_EXTENSIONS = (CUE_EXTENSION,) + STANDALONE_IMAGE_EXTENSIONS


class UnsupportedDiscSourceError(ValueError):
    """Raised when a path has no SRK-supported disc-image extension."""


def _canonical(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(path))))


def is_supported_disc_path(path: os.PathLike[str] | str) -> bool:
    """Return whether ``path`` has an extension SRK can currently open."""

    return os.path.splitext(os.fspath(path))[1].lower() in SUPPORTED_DISC_EXTENSIONS


def open_disc_source(path: os.PathLike[str] | str) -> object:
    """Open one supported disc source read-only.

    CUE sheets become ``CueDisc`` instances so all referenced tracks participate
    in one logical LBA space. Standalone BIN/IMG/ISO/RAW files become
    ``DiscImage`` instances and have their supported sector geometry detected.
    """

    source_path = os.path.abspath(os.fspath(path))
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Disc image not found: {source_path}")

    suffix = os.path.splitext(source_path)[1].lower()
    if suffix == CUE_EXTENSION:
        return CueDisc(source_path)
    if suffix in STANDALONE_IMAGE_EXTENSIONS:
        return DiscImage(source_path)

    raise UnsupportedDiscSourceError(
        "Unsupported disc source extension "
        f"'{suffix or '<none>'}': {source_path}. "
        f"Supported extensions: {', '.join(SUPPORTED_DISC_EXTENSIONS)}"
    )


def discover_disc_candidates(
    root: os.PathLike[str] | str,
    *,
    recursive: bool = True,
) -> List[str]:
    """Find supported disc sources beneath ``root``.

    If a CUE sheet references track files that also appear in the scan, those
    physical track files are suppressed from the returned list. The CUE is the
    meaningful whole-disc object and should be preferred by callers.

    Passing a supported file returns that file as a single candidate. Missing
    paths and unsupported files produce an empty list.
    """

    search_root = os.path.abspath(os.fspath(root))

    if os.path.isfile(search_root):
        return [search_root] if is_supported_disc_path(search_root) else []
    if not os.path.isdir(search_root):
        return []

    cues: List[str] = []
    standalones: List[str] = []

    if recursive:
        iterator = os.walk(search_root)
    else:
        try:
            names = os.listdir(search_root)
        except OSError:
            return []
        iterator = [(search_root, [], names)]

    for current_root, _dirs, files in iterator:
        for name in files:
            path = os.path.join(current_root, name)
            suffix = os.path.splitext(name)[1].lower()
            if suffix == CUE_EXTENSION:
                cues.append(path)
            elif suffix in STANDALONE_IMAGE_EXTENSIONS:
                standalones.append(path)

    cues.sort(key=str.casefold)
    standalones.sort(key=str.casefold)

    referenced_tracks = set()
    for cue_path in cues:
        try:
            tracks = parse_cue(cue_path)
        except Exception:
            # A malformed CUE is still surfaced as a candidate so opening it can
            # report the precise parsing error. Its track files are not hidden.
            continue

        cue_dir = os.path.dirname(cue_path)
        for track in tracks:
            target = track.file_name
            if not os.path.isabs(target):
                target = os.path.join(cue_dir, target)
            referenced_tracks.add(_canonical(target))

    return cues + [
        path for path in standalones if _canonical(path) not in referenced_tracks
    ]
