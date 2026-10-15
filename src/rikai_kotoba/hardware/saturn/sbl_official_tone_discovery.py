"""Read-only discovery for Sega/InVision Saturn tone-bank assets.

This scanner never copies, edits, deletes, or deploys anything.  It walks an
existing Saturn development tree and identifies files that look like Sega
SCSPBIN tone banks using the header/voice-offset structure consumed by SDDRV.

It is intentionally provenance-first: paths, sizes and hashes are reported so a
candidate can be reviewed against the original SDK/DTS media before SRK uses it.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import os


@dataclass(frozen=True)
class SaturnToneBankCandidate:
    path: Path
    size: int
    sha256: str
    voice_count: int | None
    mixer_offset: int | None
    velocity_offset: int | None
    peg_offset: int | None
    plfo_offset: int | None
    score: int
    reasons: tuple[str, ...]

    @property
    def structurally_valid(self) -> bool:
        return self.voice_count is not None


_NAME_HINTS = (
    "tone",
    "tonebank",
    "tone bank",
    "general",
    "midi",
    "gm",
    "invision",
    "choice",
)
_PATH_HINTS = (
    "tone banks",
    "tonebank",
    "tone_bank",
    "invision",
    "sound",
    "dts",
)
_BINARY_SUFFIXES = {".bin", ".ton", ".tone", ".dat"}
_MAX_READ_BYTES = 64 * 1024 * 1024


def _sha_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_scspbin_header(path: Path) -> tuple[int, int, int, int, int] | None:
    size = path.stat().st_size
    if size < 10 or size > _MAX_READ_BYTES:
        return None
    with path.open("rb") as handle:
        header = handle.read(min(size, 4096))
    if len(header) < 10:
        return None

    mixer = int.from_bytes(header[0:2], "big")
    velocity = int.from_bytes(header[2:4], "big")
    peg = int.from_bytes(header[4:6], "big")
    plfo = int.from_bytes(header[6:8], "big")

    if mixer < 10 or (mixer - 8) % 2:
        return None
    voice_count = (mixer - 8) // 2
    if not 1 <= voice_count <= 128:
        return None
    if not (mixer <= velocity <= peg <= plfo <= size):
        return None
    table_end = 8 + voice_count * 2
    if table_end > len(header):
        return None

    previous = -1
    for index in range(voice_count):
        off = int.from_bytes(header[8 + 2 * index : 10 + 2 * index], "big")
        if off < plfo or off >= size or off < previous:
            return None
        previous = off
    return voice_count, mixer, velocity, peg, plfo


def _candidate_score(path: Path, parsed: tuple[int, int, int, int, int] | None) -> tuple[int, tuple[str, ...]]:
    score = 0
    reasons: list[str] = []
    lower_name = path.name.casefold()
    lower_path = str(path.parent).casefold()

    for hint in _NAME_HINTS:
        if hint in lower_name:
            score += 3
            reasons.append(f"name:{hint}")
    for hint in _PATH_HINTS:
        if hint in lower_path:
            score += 1
            reasons.append(f"path:{hint}")
    if path.suffix.casefold() in _BINARY_SUFFIXES:
        score += 1
        reasons.append(f"suffix:{path.suffix.casefold()}")
    if parsed is not None:
        score += 8
        reasons.append("scspbin")
        if parsed[0] == 128:
            score += 12
            reasons.append("128-voices")
    return score, tuple(dict.fromkeys(reasons))


def discover_official_tone_candidates(saturn_root: os.PathLike[str] | str) -> tuple[SaturnToneBankCandidate, ...]:
    """Recursively inspect a Saturn development tree without modifying it."""

    root = Path(saturn_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise ValueError(f"Saturn root is not a directory: {root}")

    results: list[SaturnToneBankCandidate] = []
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
            size = path.stat().st_size
        except OSError:
            continue

        lower_name = path.name.casefold()
        lower_parent = str(path.parent).casefold()
        hinted = (
            path.suffix.casefold() in _BINARY_SUFFIXES
            or any(h in lower_name for h in _NAME_HINTS)
            or any(h in lower_parent for h in _PATH_HINTS)
        )
        if not hinted or size < 10 or size > _MAX_READ_BYTES:
            continue

        try:
            parsed = _parse_scspbin_header(path)
            score, reasons = _candidate_score(path, parsed)
            if parsed is None and score < 3:
                continue
            digest = _sha_file(path)
        except OSError:
            continue

        if parsed is None:
            voice_count = mixer = velocity = peg = plfo = None
        else:
            voice_count, mixer, velocity, peg, plfo = parsed
        results.append(
            SaturnToneBankCandidate(
                path=path,
                size=size,
                sha256=digest,
                voice_count=voice_count,
                mixer_offset=mixer,
                velocity_offset=velocity,
                peg_offset=peg,
                plfo_offset=plfo,
                score=score,
                reasons=reasons,
            )
        )

    results.sort(
        key=lambda item: (
            -item.score,
            0 if item.voice_count == 128 else 1,
            str(item.path).casefold(),
        )
    )
    return tuple(results)
