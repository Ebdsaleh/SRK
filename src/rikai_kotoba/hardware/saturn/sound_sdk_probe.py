"""Read-only evidence probe for the user's installed Sega Saturn sound SDK.

The purpose of this probe is to answer one concrete integration question without
inventing API names: what sequence, tone-bank, PCM and CD-DA interfaces are
actually present in the installed SBL/SGL trees, and which local Sega samples
exercise them?

The probe never executes SDK programs, never links or copies proprietary Sega
artifacts, and never writes beneath the supplied Saturn root.  It only reads
small text/source/header/config files and reports exact paths plus matching
lines.  Binary libraries are reported by path/size/SHA-256 only.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os
import re
from typing import Iterable


class SaturnSoundSdkProbeError(RuntimeError):
    """Raised when the installed Saturn SDK cannot be inspected safely."""


@dataclass(frozen=True)
class SaturnSoundSdkTextMatch:
    path: Path
    line_number: int
    line: str


@dataclass(frozen=True)
class SaturnSoundSdkArtifact:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class SaturnSoundSdkProbeResult:
    saturn_root: Path
    text_files_read: int
    oversize_skipped: int
    snd_headers: tuple[Path, ...]
    snd_libraries: tuple[SaturnSoundSdkArtifact, ...]
    sound_samples: tuple[Path, ...]
    sequence_matches: tuple[SaturnSoundSdkTextMatch, ...]
    pcm_matches: tuple[SaturnSoundSdkTextMatch, ...]
    cdda_matches: tuple[SaturnSoundSdkTextMatch, ...]
    bank_matches: tuple[SaturnSoundSdkTextMatch, ...]


_TEXT_SUFFIXES = {
    ".c", ".h", ".s", ".asm", ".inc", ".cfg", ".mak", ".mk", ".txt",
    ".htm", ".html", ".md",
}
_MAX_TEXT_BYTES = 2 * 1024 * 1024

# These are deliberately broad vocabulary groups.  The probe reports evidence;
# callers decide which exact API is appropriate after seeing installed headers
# and samples.
_SEQUENCE_RE = re.compile(
    r"\b(?:SND|sl)[A-Za-z0-9_]*(?:Seq|Sequence|Midi|MIDI|Bgm|BGM)[A-Za-z0-9_]*\b"
)
_PCM_RE = re.compile(
    r"\b(?:SND|PCM|sl)[A-Za-z0-9_]*(?:Pcm|PCM|Sound|Voice)[A-Za-z0-9_]*\b"
)
_CDDA_RE = re.compile(
    r"\b(?:CDC|CD|sl|SND)[A-Za-z0-9_]*(?:Cdda|CDDA|Cd|CD|Play|Ply|Pause|Stop)[A-Za-z0-9_]*\b"
)
_BANK_RE = re.compile(
    r"\b(?:SND|sl)[A-Za-z0-9_]*(?:Bank|Tone|Map|Program|Patch|Drum)[A-Za-z0-9_]*\b"
)


def _canonical(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> SaturnSoundSdkArtifact:
    return SaturnSoundSdkArtifact(
        path=path.resolve(),
        size=path.stat().st_size,
        sha256=_sha256_file(path),
    )


def _looks_like_sound_sample(path: Path) -> bool:
    parts = [part.casefold() for part in path.parts]
    joined = "/".join(parts)
    return (
        "/segasmp/snd/" in joined
        or "smpsnd" in joined
        or "soundplayer" in joined
        or "cdda" in path.name.casefold()
    )


def _header_is_sound(path: Path) -> bool:
    name = path.name.casefold()
    return (
        name in {"sega_snd.h", "sega_pcm.h", "sega_cdc.h", "sgl.h"}
        or "snd" in name
        or "sound" in name
        or "pcm" in name
    )


def _library_is_sound(path: Path) -> bool:
    name = path.name.casefold()
    return name in {
        "sega_snd.a", "sega_snd.lib", "sega_pcm.a", "sega_pcm.lib",
        "sega_cdc.a", "sega_cdc.lib",
    }


def _append_matches(
    destination: list[SaturnSoundSdkTextMatch],
    path: Path,
    lines: Iterable[str],
    pattern: re.Pattern[str],
) -> None:
    for line_number, line in enumerate(lines, 1):
        if pattern.search(line):
            destination.append(
                SaturnSoundSdkTextMatch(
                    path=path.resolve(),
                    line_number=line_number,
                    line=line.strip(),
                )
            )


def inspect_saturn_sound_sdk(
    saturn_root: os.PathLike[str] | str,
    *,
    match_limit: int = 240,
) -> SaturnSoundSdkProbeResult:
    """Inspect installed Saturn sound SDK evidence without modifying it."""

    root = _canonical(saturn_root)
    if not root.is_dir():
        raise SaturnSoundSdkProbeError(f"Saturn root is not a directory: {root}")
    if match_limit < 1:
        raise SaturnSoundSdkProbeError("match_limit must be positive")

    text_files_read = 0
    oversize_skipped = 0
    snd_headers: list[Path] = []
    snd_libraries: list[SaturnSoundSdkArtifact] = []
    sound_samples: set[Path] = set()
    sequence_matches: list[SaturnSoundSdkTextMatch] = []
    pcm_matches: list[SaturnSoundSdkTextMatch] = []
    cdda_matches: list[SaturnSoundSdkTextMatch] = []
    bank_matches: list[SaturnSoundSdkTextMatch] = []

    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        try:
            if not path.is_file():
                continue
        except OSError:
            continue

        if _library_is_sound(path):
            snd_libraries.append(_artifact(path))
            continue

        if path.suffix.casefold() not in _TEXT_SUFFIXES:
            continue

        try:
            if path.stat().st_size > _MAX_TEXT_BYTES:
                oversize_skipped += 1
                continue
            raw = path.read_bytes()
        except OSError:
            continue

        text_files_read += 1
        text = raw.decode("latin-1", errors="replace")
        lines = text.splitlines()

        if path.suffix.casefold() == ".h" and _header_is_sound(path):
            snd_headers.append(path.resolve())
        if _looks_like_sound_sample(path):
            sound_samples.add(path.parent.resolve())

        if len(sequence_matches) < match_limit:
            _append_matches(sequence_matches, path, lines, _SEQUENCE_RE)
            del sequence_matches[match_limit:]
        if len(pcm_matches) < match_limit:
            _append_matches(pcm_matches, path, lines, _PCM_RE)
            del pcm_matches[match_limit:]
        if len(cdda_matches) < match_limit:
            _append_matches(cdda_matches, path, lines, _CDDA_RE)
            del cdda_matches[match_limit:]
        if len(bank_matches) < match_limit:
            _append_matches(bank_matches, path, lines, _BANK_RE)
            del bank_matches[match_limit:]

    return SaturnSoundSdkProbeResult(
        saturn_root=root,
        text_files_read=text_files_read,
        oversize_skipped=oversize_skipped,
        snd_headers=tuple(sorted(set(snd_headers), key=lambda p: str(p).casefold())),
        snd_libraries=tuple(sorted(snd_libraries, key=lambda a: str(a.path).casefold())),
        sound_samples=tuple(sorted(sound_samples, key=lambda p: str(p).casefold())),
        sequence_matches=tuple(sequence_matches),
        pcm_matches=tuple(pcm_matches),
        cdda_matches=tuple(cdda_matches),
        bank_matches=tuple(bank_matches),
    )
