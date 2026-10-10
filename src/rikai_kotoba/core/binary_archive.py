"""Read-only binary/archive inspection primitives used by SRK Mjolnir.

The inspector deliberately starts from raw bytes instead of delegating format
identification to a compiler/linker backend.  Its first container decoder is the
classic Unix ``ar`` format used by many static libraries.  Unknown member
formats remain unknown; the report preserves offsets, sizes, hashes, and byte
prefixes so later research can be evidence-driven rather than guessed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO


AR_MAGIC = b"!<arch>\n"
AR_HEADER_SIZE = 60
_HASH_CHUNK = 1024 * 1024
_SIGNATURE_PREFIX = 32
_GNU_STRING_TABLE_LIMIT = 8 * 1024 * 1024


class BinaryArchiveError(RuntimeError):
    """Raised when a recognized binary container is structurally malformed."""


@dataclass(frozen=True)
class BinarySignature:
    kind: str
    detail: str
    prefix_hex: str
    prefix_ascii: str


@dataclass(frozen=True)
class ArchiveMember:
    index: int
    name: str
    raw_name: str
    header_offset: int
    data_offset: int
    stored_size: int
    size: int
    sha256: str
    signature: BinarySignature
    metadata: bool


@dataclass(frozen=True)
class BinaryInspectionReport:
    path: Path
    size: int
    sha256: str
    container_kind: str
    signature: BinarySignature
    members: tuple[ArchiveMember, ...]


def _printable_prefix(data: bytes) -> str:
    return "".join(chr(value) if 32 <= value <= 126 else "." for value in data)


def _prefix_hex(data: bytes) -> str:
    return " ".join(f"{value:02X}" for value in data)


def _signature(data: bytes) -> BinarySignature:
    prefix = data[:_SIGNATURE_PREFIX]
    prefix_hex = _prefix_hex(prefix[:16])
    prefix_ascii = _printable_prefix(prefix[:16])

    if prefix.startswith(AR_MAGIC):
        return BinarySignature(
            kind="unix-ar",
            detail="classic Unix ar archive",
            prefix_hex=prefix_hex,
            prefix_ascii=prefix_ascii,
        )

    if len(prefix) >= 20 and prefix[:4] == b"\x7fELF":
        elf_class = {1: "ELF32", 2: "ELF64"}.get(prefix[4], f"class-{prefix[4]}")
        byte_order = {1: "little", 2: "big"}.get(prefix[5])
        if byte_order is None:
            detail = f"{elf_class} unknown-endian"
        else:
            endian = "little" if byte_order == "little" else "big"
            object_type = int.from_bytes(prefix[16:18], endian)
            machine = int.from_bytes(prefix[18:20], endian)
            type_name = {0: "NONE", 1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}.get(
                object_type,
                str(object_type),
            )
            machine_name = {
                3: "x86",
                40: "ARM",
                42: "SH",
                62: "x86-64",
                183: "AArch64",
            }.get(machine, "unknown")
            detail = (
                f"{elf_class} {byte_order}-endian {type_name} "
                f"machine={machine_name}({machine})"
            )
        return BinarySignature(
            kind="elf",
            detail=detail,
            prefix_hex=prefix_hex,
            prefix_ascii=prefix_ascii,
        )

    if prefix.startswith(b"MZ"):
        return BinarySignature(
            kind="mz",
            detail="DOS/PE-style MZ header",
            prefix_hex=prefix_hex,
            prefix_ascii=prefix_ascii,
        )

    return BinarySignature(
        kind="unknown",
        detail="unrecognized raw byte signature",
        prefix_hex=prefix_hex,
        prefix_ascii=prefix_ascii,
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _read_prefix(path: Path, size: int = _SIGNATURE_PREFIX) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def _hash_region(handle: BinaryIO, offset: int, size: int) -> tuple[str, bytes]:
    digest = hashlib.sha256()
    prefix = bytearray()
    remaining = size
    handle.seek(offset)
    while remaining:
        chunk = handle.read(min(_HASH_CHUNK, remaining))
        if not chunk:
            raise BinaryArchiveError(
                f"unexpected end of file while reading archive member at 0x{offset:X}"
            )
        if len(prefix) < _SIGNATURE_PREFIX:
            wanted = _SIGNATURE_PREFIX - len(prefix)
            prefix.extend(chunk[:wanted])
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest(), bytes(prefix)


def _ascii_field(field: bytes, label: str, offset: int) -> str:
    try:
        return field.decode("ascii")
    except UnicodeDecodeError as exc:
        raise BinaryArchiveError(
            f"non-ASCII {label} field in ar header at 0x{offset:X}"
        ) from exc


def _decimal_field(field: bytes, label: str, offset: int) -> int:
    text = _ascii_field(field, label, offset).strip()
    if not text or not text.isdigit():
        raise BinaryArchiveError(
            f"invalid {label} field in ar header at 0x{offset:X}: {text!r}"
        )
    return int(text, 10)


def _gnu_name(string_table: bytes | None, raw_name: str) -> str:
    if string_table is None:
        return f"<unresolved GNU name {raw_name}>"
    try:
        start = int(raw_name[1:], 10)
    except ValueError:
        return f"<invalid GNU name {raw_name}>"
    if start < 0 or start >= len(string_table):
        return f"<GNU name offset {start} out of range>"
    end = string_table.find(b"/\n", start)
    if end < 0:
        end = string_table.find(b"\x00", start)
    if end < 0:
        end = len(string_table)
    return string_table[start:end].decode("utf-8", errors="replace")


def _normalize_standard_name(raw_name: str, string_table: bytes | None) -> str:
    if raw_name == "/":
        return "/ (symbol table)"
    if raw_name == "//":
        return "// (GNU string table)"
    if raw_name == "/SYM64/":
        return "/SYM64/ (64-bit symbol table)"
    if raw_name.startswith("/") and raw_name[1:].isdigit():
        return _gnu_name(string_table, raw_name)
    if raw_name.endswith("/"):
        return raw_name[:-1]
    return raw_name


def _inspect_ar(path: Path, size: int) -> tuple[ArchiveMember, ...]:
    records: list[dict[str, object]] = []
    string_table: bytes | None = None

    with path.open("rb") as handle:
        magic = handle.read(len(AR_MAGIC))
        if magic != AR_MAGIC:
            raise BinaryArchiveError("not a classic Unix ar archive")

        offset = len(AR_MAGIC)
        index = 0
        while offset < size:
            if size - offset < AR_HEADER_SIZE:
                raise BinaryArchiveError(
                    f"truncated ar member header at 0x{offset:X}"
                )
            handle.seek(offset)
            header = handle.read(AR_HEADER_SIZE)
            if header[58:60] != b"`\n":
                raise BinaryArchiveError(
                    f"invalid ar member trailer at 0x{offset:X}"
                )

            raw_name = _ascii_field(header[0:16], "name", offset).rstrip()
            stored_size = _decimal_field(header[48:58], "size", offset)
            stored_data_offset = offset + AR_HEADER_SIZE
            stored_end = stored_data_offset + stored_size
            if stored_end > size:
                raise BinaryArchiveError(
                    f"ar member at 0x{offset:X} extends beyond end of file"
                )

            data_offset = stored_data_offset
            logical_size = stored_size
            bsd_name: str | None = None
            if raw_name.startswith("#1/"):
                try:
                    name_size = int(raw_name[3:], 10)
                except ValueError as exc:
                    raise BinaryArchiveError(
                        f"invalid BSD long-name length at 0x{offset:X}"
                    ) from exc
                if name_size < 0 or name_size > stored_size:
                    raise BinaryArchiveError(
                        f"BSD long-name length exceeds member at 0x{offset:X}"
                    )
                handle.seek(stored_data_offset)
                name_bytes = handle.read(name_size)
                if len(name_bytes) != name_size:
                    raise BinaryArchiveError(
                        f"truncated BSD long name at 0x{offset:X}"
                    )
                bsd_name = name_bytes.rstrip(b"\x00").decode(
                    "utf-8",
                    errors="replace",
                )
                data_offset += name_size
                logical_size -= name_size

            if raw_name == "//":
                if stored_size > _GNU_STRING_TABLE_LIMIT:
                    raise BinaryArchiveError(
                        "GNU ar string table exceeds the bounded inspection limit"
                    )
                handle.seek(stored_data_offset)
                string_table = handle.read(stored_size)
                if len(string_table) != stored_size:
                    raise BinaryArchiveError("truncated GNU ar string table")

            digest, prefix = _hash_region(handle, data_offset, logical_size)
            records.append(
                {
                    "index": index,
                    "raw_name": raw_name,
                    "bsd_name": bsd_name,
                    "header_offset": offset,
                    "data_offset": data_offset,
                    "stored_size": stored_size,
                    "size": logical_size,
                    "sha256": digest,
                    "prefix": prefix,
                }
            )

            offset = stored_end + (stored_size & 1)
            index += 1

    members: list[ArchiveMember] = []
    for record in records:
        raw_name = str(record["raw_name"])
        bsd_name = record["bsd_name"]
        name = (
            str(bsd_name)
            if bsd_name is not None
            else _normalize_standard_name(raw_name, string_table)
        )
        metadata = raw_name in {"/", "//", "/SYM64/"}
        prefix = bytes(record["prefix"])
        signature = (
            BinarySignature(
                kind="archive-metadata",
                detail="archive symbol/name metadata member",
                prefix_hex=_prefix_hex(prefix[:16]),
                prefix_ascii=_printable_prefix(prefix[:16]),
            )
            if metadata
            else _signature(prefix)
        )
        members.append(
            ArchiveMember(
                index=int(record["index"]),
                name=name,
                raw_name=raw_name,
                header_offset=int(record["header_offset"]),
                data_offset=int(record["data_offset"]),
                stored_size=int(record["stored_size"]),
                size=int(record["size"]),
                sha256=str(record["sha256"]),
                signature=signature,
                metadata=metadata,
            )
        )
    return tuple(members)


def inspect_binary(path: os.PathLike[str] | str) -> BinaryInspectionReport:
    """Inspect one binary file without modifying it or invoking external tools."""

    source = Path(path).expanduser().resolve(strict=False)
    if not source.is_file():
        raise BinaryArchiveError(f"binary inspection source is not a file: {source}")

    size = source.stat().st_size
    prefix = _read_prefix(source)
    signature = _signature(prefix)
    members: tuple[ArchiveMember, ...] = ()
    container_kind = signature.kind
    if prefix.startswith(AR_MAGIC):
        members = _inspect_ar(source, size)
        container_kind = "unix-ar"
    elif signature.kind not in {"elf", "mz"}:
        container_kind = "raw/unknown"

    return BinaryInspectionReport(
        path=source,
        size=size,
        sha256=_sha256_path(source),
        container_kind=container_kind,
        signature=signature,
        members=members,
    )
