"""Off-card inventory guard for mounted SAROO SD cards.

The guard records the complete directory/file topology and every file size while
hashing small/control files.  This makes it possible to prove that a controlled
firmware operation did not add, remove, truncate, or silently alter unrelated
small files without reading tens of gigabytes of game data on every check.

Inventory manifests are always written outside the mounted card.  Creating or
verifying an inventory never modifies the card.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Iterable


SAROO_CARD_INVENTORY_SCHEMA = "srk.saroo.card-inventory"
SAROO_CARD_INVENTORY_VERSION = 1
SAROO_CARD_INVENTORY_HASH_MAX_BYTES = 1024 * 1024
_ALWAYS_HASH = {"saroo/ssfirm.bin", "saroo/mcuapp.bin", "saroo/saroocfg.txt"}


class SarooCardInventoryError(RuntimeError):
    """Raised when a safe card inventory cannot be created or verified."""


@dataclass(frozen=True)
class SarooCardInventoryEntry:
    relative_path: str
    kind: str
    size: int | None
    sha256: str | None


@dataclass(frozen=True)
class SarooCardInventoryResult:
    card_root: Path
    manifest_path: Path
    file_count: int
    directory_count: int
    total_file_bytes: int
    hashed_file_count: int
    manifest_sha256: str


@dataclass(frozen=True)
class SarooCardInventoryVerification:
    card_root: Path
    manifest_path: Path
    valid: bool
    differences: tuple[str, ...]
    file_count: int
    directory_count: int
    total_file_bytes: int
    hashed_file_count: int

    def require_valid(self) -> None:
        if not self.valid:
            detail = "; ".join(self.differences[:5])
            if len(self.differences) > 5:
                detail += f"; ... {len(self.differences) - 5} more"
            raise SarooCardInventoryError(f"SAROO card inventory verification failed: {detail}")


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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
        raise SarooCardInventoryError(f"cannot hash card file {path}: {exc}") from exc
    return digest.hexdigest()


def _walk_entries(
    card_root: Path,
    *,
    hash_max_bytes: int,
) -> tuple[SarooCardInventoryEntry, ...]:
    if hash_max_bytes < 0:
        raise SarooCardInventoryError("hash_max_bytes must not be negative")

    entries: list[SarooCardInventoryEntry] = []

    def visit(directory: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise SarooCardInventoryError(f"cannot enumerate card directory {directory}: {exc}") from exc

        for child in children:
            try:
                if child.is_symlink():
                    raise SarooCardInventoryError(
                        f"symbolic links are not supported in a SAROO card inventory: {child}"
                    )
                relative = child.relative_to(card_root).as_posix()
                if child.is_dir():
                    entries.append(
                        SarooCardInventoryEntry(
                            relative_path=relative,
                            kind="directory",
                            size=None,
                            sha256=None,
                        )
                    )
                    visit(child)
                elif child.is_file():
                    size = child.stat().st_size
                    should_hash = (
                        size <= hash_max_bytes
                        or relative.casefold() in _ALWAYS_HASH
                    )
                    entries.append(
                        SarooCardInventoryEntry(
                            relative_path=relative,
                            kind="file",
                            size=size,
                            sha256=_hash_file(child) if should_hash else None,
                        )
                    )
                else:
                    raise SarooCardInventoryError(
                        f"unsupported filesystem entry on SAROO card: {child}"
                    )
            except OSError as exc:
                raise SarooCardInventoryError(f"cannot inspect card entry {child}: {exc}") from exc

    visit(card_root)
    entries.sort(key=lambda entry: entry.relative_path.casefold())
    return tuple(entries)


def _summary(entries: Iterable[SarooCardInventoryEntry]) -> tuple[int, int, int, int]:
    file_count = 0
    directory_count = 0
    total_file_bytes = 0
    hashed_file_count = 0
    for entry in entries:
        if entry.kind == "file":
            file_count += 1
            total_file_bytes += int(entry.size or 0)
            if entry.sha256 is not None:
                hashed_file_count += 1
        elif entry.kind == "directory":
            directory_count += 1
    return file_count, directory_count, total_file_bytes, hashed_file_count


def _manifest_payload(
    card_root: Path,
    entries: tuple[SarooCardInventoryEntry, ...],
    *,
    hash_max_bytes: int,
    generated_utc: str,
) -> dict[str, object]:
    file_count, directory_count, total_file_bytes, hashed_file_count = _summary(entries)
    return {
        "schema": SAROO_CARD_INVENTORY_SCHEMA,
        "schema_version": SAROO_CARD_INVENTORY_VERSION,
        "generated_utc": generated_utc,
        "card_root_at_capture": str(card_root),
        "hash_max_bytes": hash_max_bytes,
        "file_count": file_count,
        "directory_count": directory_count,
        "total_file_bytes": total_file_bytes,
        "hashed_file_count": hashed_file_count,
        "entries": [
            {
                "path": entry.relative_path,
                "kind": entry.kind,
                "size": entry.size,
                "sha256": entry.sha256,
            }
            for entry in entries
        ],
    }


def _payload_bytes(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def create_saroo_card_inventory(
    card_root: os.PathLike[str] | str,
    manifest_path: os.PathLike[str] | str,
    *,
    hash_max_bytes: int = SAROO_CARD_INVENTORY_HASH_MAX_BYTES,
) -> SarooCardInventoryResult:
    """Create one off-card manifest without modifying the mounted card."""

    card = _canonical(card_root)
    manifest = _canonical(manifest_path)
    if not card.is_dir():
        raise SarooCardInventoryError(f"SAROO card root is not a directory: {card}")
    if _inside(manifest, card):
        raise SarooCardInventoryError("inventory manifest must be stored outside the SAROO card")
    if manifest.exists():
        raise SarooCardInventoryError(f"inventory manifest already exists: {manifest}")

    entries = _walk_entries(card, hash_max_bytes=hash_max_bytes)
    generated_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _manifest_payload(
        card,
        entries,
        hash_max_bytes=hash_max_bytes,
        generated_utc=generated_utc,
    )
    manifest_digest = sha256(_payload_bytes(payload)).hexdigest()
    document = dict(payload)
    document["manifest_sha256"] = manifest_digest

    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_name(manifest.name + ".srk-partial")
    if temporary.exists():
        raise SarooCardInventoryError(f"stale inventory temporary file exists: {temporary}")
    try:
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            temporary.rename(manifest)
        except OSError as exc:
            raise SarooCardInventoryError(f"cannot publish off-card inventory manifest: {exc}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    file_count, directory_count, total_file_bytes, hashed_file_count = _summary(entries)
    return SarooCardInventoryResult(
        card_root=card,
        manifest_path=manifest,
        file_count=file_count,
        directory_count=directory_count,
        total_file_bytes=total_file_bytes,
        hashed_file_count=hashed_file_count,
        manifest_sha256=manifest_digest,
    )


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise SarooCardInventoryError(f"cannot read inventory manifest {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise SarooCardInventoryError("inventory manifest root must be an object")
    expected_digest = document.get("manifest_sha256")
    if not isinstance(expected_digest, str):
        raise SarooCardInventoryError("inventory manifest is missing manifest_sha256")
    payload = dict(document)
    payload.pop("manifest_sha256", None)
    actual_digest = sha256(_payload_bytes(payload)).hexdigest()
    if actual_digest != expected_digest:
        raise SarooCardInventoryError("inventory manifest SHA-256 verification failed")
    if payload.get("schema") != SAROO_CARD_INVENTORY_SCHEMA:
        raise SarooCardInventoryError("unsupported SAROO card inventory schema")
    if payload.get("schema_version") != SAROO_CARD_INVENTORY_VERSION:
        raise SarooCardInventoryError("unsupported SAROO card inventory schema version")
    return document


def verify_saroo_card_inventory(
    card_root: os.PathLike[str] | str,
    manifest_path: os.PathLike[str] | str,
    *,
    allowed_changed_paths: Iterable[str] = (),
) -> SarooCardInventoryVerification:
    """Compare a mounted card with an off-card baseline inventory.

    ``allowed_changed_paths`` is intended for a later controlled operation where
    exactly one reviewed path, such as ``SAROO/ssfirm.bin``, may differ.  All
    other paths, file sizes, and recorded small-file hashes must still match.
    """

    card = _canonical(card_root)
    manifest = _canonical(manifest_path)
    if _inside(manifest, card):
        raise SarooCardInventoryError("inventory manifest must be outside the SAROO card")
    document = _load_manifest(manifest)

    hash_max_bytes = document.get("hash_max_bytes")
    if not isinstance(hash_max_bytes, int) or hash_max_bytes < 0:
        raise SarooCardInventoryError("inventory manifest has invalid hash_max_bytes")

    current = _walk_entries(card, hash_max_bytes=hash_max_bytes)
    file_count, directory_count, total_file_bytes, hashed_file_count = _summary(current)

    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise SarooCardInventoryError("inventory manifest entries must be a list")

    def normalized_allowed() -> set[str]:
        return {
            str(path).replace("\\", "/").strip("/").casefold()
            for path in allowed_changed_paths
            if str(path).strip()
        }

    allowed = normalized_allowed()
    baseline: dict[str, tuple[str, int | None, str | None]] = {}
    for item in raw_entries:
        if not isinstance(item, dict):
            raise SarooCardInventoryError("inventory manifest contains an invalid entry")
        path = item.get("path")
        kind = item.get("kind")
        size = item.get("size")
        digest = item.get("sha256")
        if not isinstance(path, str) or kind not in ("file", "directory"):
            raise SarooCardInventoryError("inventory manifest contains malformed path/kind data")
        baseline[path.casefold()] = (kind, size if isinstance(size, int) else None, digest if isinstance(digest, str) else None)

    current_map = {
        entry.relative_path.casefold(): (entry.kind, entry.size, entry.sha256)
        for entry in current
    }

    differences: list[str] = []
    all_paths = sorted(set(baseline) | set(current_map))
    for key in all_paths:
        if key in allowed:
            continue
        before = baseline.get(key)
        after = current_map.get(key)
        if before is None:
            differences.append(f"added: {key}")
            continue
        if after is None:
            differences.append(f"missing: {key}")
            continue
        if before[0] != after[0]:
            differences.append(f"type changed: {key}")
            continue
        if before[1] != after[1]:
            differences.append(f"size changed: {key} ({before[1]} -> {after[1]})")
            continue
        if before[2] is not None and before[2] != after[2]:
            differences.append(f"content hash changed: {key}")

    return SarooCardInventoryVerification(
        card_root=card,
        manifest_path=manifest,
        valid=not differences,
        differences=tuple(differences),
        file_count=file_count,
        directory_count=directory_count,
        total_file_bytes=total_file_bytes,
        hashed_file_count=hashed_file_count,
    )
