"""Read-only inspection of SAROO SD-card firmware layouts.

SAROO firmware distributions have used more than one Saturn-side firmware
location over time.  SRK must identify the layout that is actually present on a
mounted card before any later staging/deployment workflow can make a safe
recommendation.

This module is intentionally read-only.  It performs bounded directory lookups,
hashes recognised Saturn firmware files, and never creates, removes, renames,
or modifies anything beneath the supplied root.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os


SAROO_SD_LAYOUT_MODERN = "modern"
SAROO_SD_LAYOUT_LEGACY = "legacy"
SAROO_SD_LAYOUT_MIXED = "mixed"
SAROO_SD_LAYOUT_UNRECOGNIZED = "unrecognized"


class SarooSdLayoutError(RuntimeError):
    """Raised when a SAROO SD-card root cannot be inspected safely."""


@dataclass(frozen=True)
class SarooSdFileInfo:
    """One recognised Saturn firmware file already present on the card."""

    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class SarooSdLayoutReport:
    """Read-only description of a mounted SAROO SD-card layout."""

    root: Path
    layout: str
    firmware_files: tuple[SarooSdFileInfo, ...]
    saroo_directory_present: bool
    mcuapp_present: bool
    config_present: bool
    iso_directory_present: bool
    update_directory_present: bool
    warnings: tuple[str, ...]

    @property
    def recognized(self) -> bool:
        """Whether exactly one known Saturn-firmware layout was identified."""

        return self.layout in (SAROO_SD_LAYOUT_MODERN, SAROO_SD_LAYOUT_LEGACY)


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _hash_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise SarooSdLayoutError(f"cannot read firmware file {path}: {exc}") from exc
    return digest.hexdigest()


def _find_casefold_child(parent: Path, name: str) -> Path | None:
    """Find one direct child using FAT/Windows-style case-insensitive matching."""

    if not parent.is_dir():
        return None

    direct = parent / name
    if direct.exists():
        return direct

    wanted = name.casefold()
    try:
        matches = [child for child in parent.iterdir() if child.name.casefold() == wanted]
    except OSError as exc:
        raise SarooSdLayoutError(f"cannot inspect directory {parent}: {exc}") from exc

    if len(matches) > 1:
        raise SarooSdLayoutError(
            f"ambiguous case-insensitive entries named {name!r} beneath: {parent}"
        )
    return matches[0] if matches else None


def _file_info(root: Path, path: Path) -> SarooSdFileInfo:
    try:
        stat = path.stat()
    except OSError as exc:
        raise SarooSdLayoutError(f"cannot stat firmware file {path}: {exc}") from exc
    if not path.is_file():
        raise SarooSdLayoutError(f"expected a firmware file but found another entry: {path}")
    return SarooSdFileInfo(
        relative_path=path.relative_to(root).as_posix(),
        size=stat.st_size,
        sha256=_hash_file(path),
    )


def inspect_saroo_sd_layout(
    root: os.PathLike[str] | str,
) -> SarooSdLayoutReport:
    """Inspect a mounted SAROO SD-card root without modifying it.

    Recognised Saturn-side firmware locations are:

    * modern: ``SAROO/ssfirm.bin``
    * legacy: ``ramimage.bin`` at the card root

    If both are present SRK reports ``mixed`` rather than guessing which file
    the cartridge currently boots.  If neither is present the result is
    ``unrecognized``.  Companion-file presence is reported as evidence only and
    is never treated as permission to write to the card.
    """

    card_root = _canonical(root)
    if not card_root.is_dir():
        raise SarooSdLayoutError(f"SAROO SD-card root is not a directory: {card_root}")

    saroo_entry = _find_casefold_child(card_root, "SAROO")
    saroo_dir = saroo_entry if saroo_entry is not None and saroo_entry.is_dir() else None

    modern_path = (
        _find_casefold_child(saroo_dir, "ssfirm.bin") if saroo_dir is not None else None
    )
    if modern_path is not None and not modern_path.is_file():
        modern_path = None

    legacy_path = _find_casefold_child(card_root, "ramimage.bin")
    if legacy_path is not None and not legacy_path.is_file():
        legacy_path = None

    firmware_paths = [path for path in (modern_path, legacy_path) if path is not None]
    firmware_files = tuple(_file_info(card_root, path) for path in firmware_paths)

    if modern_path is not None and legacy_path is not None:
        layout = SAROO_SD_LAYOUT_MIXED
    elif modern_path is not None:
        layout = SAROO_SD_LAYOUT_MODERN
    elif legacy_path is not None:
        layout = SAROO_SD_LAYOUT_LEGACY
    else:
        layout = SAROO_SD_LAYOUT_UNRECOGNIZED

    mcuapp = _find_casefold_child(saroo_dir, "mcuapp.bin") if saroo_dir else None
    config = _find_casefold_child(saroo_dir, "saroocfg.txt") if saroo_dir else None
    iso_dir = _find_casefold_child(saroo_dir, "ISO") if saroo_dir else None
    update_dir = _find_casefold_child(saroo_dir, "update") if saroo_dir else None

    warnings: list[str] = []
    if layout == SAROO_SD_LAYOUT_MIXED:
        warnings.append(
            "Both SAROO/ssfirm.bin and root ramimage.bin are present; "
            "do not replace either until the active cartridge layout is confirmed."
        )
    elif layout == SAROO_SD_LAYOUT_UNRECOGNIZED:
        warnings.append(
            "No recognised Saturn firmware file was found; do not stage firmware "
            "to this card based on filename assumptions."
        )

    for info in firmware_files:
        if info.size == 0:
            warnings.append(f"Recognised firmware file is empty: {info.relative_path}")

    return SarooSdLayoutReport(
        root=card_root,
        layout=layout,
        firmware_files=firmware_files,
        saroo_directory_present=saroo_dir is not None,
        mcuapp_present=mcuapp is not None and mcuapp.is_file(),
        config_present=config is not None and config.is_file(),
        iso_directory_present=iso_dir is not None and iso_dir.is_dir(),
        update_directory_present=update_dir is not None and update_dir.is_dir(),
        warnings=tuple(warnings),
    )
