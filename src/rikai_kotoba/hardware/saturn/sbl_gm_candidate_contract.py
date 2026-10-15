"""Sega-SBL contract corrections for the Space Spectre GM candidate.

The first real GeneralUser build reached the generated Saturn project and
exposed a compile-time collision with ``SEGA_GFS.H``.  Review against Sega's
SBL 6.01 sound-driver sources also proved that area-map entries are two
big-endian 32-bit bitfields, not the byte-oriented layout used by the first
candidate.

Sega's sample projects pass ``SND_INI_ARA_SZ`` as the raw map-file byte count
(e.g. 34-byte SMPSND6.MP -> 0x22 and 74-byte BOOTSND.MP -> 0x4A), so this layer
deliberately preserves the existing raw-byte value.  It does not reinterpret
the driver's historical ``CHG_LONG`` implementation.

Keep these corrections scoped around the existing candidate builder so the
reviewed R26-R28 baselines and generic SBL probes remain immutable.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import struct
from typing import Iterator

from . import sbl_gm_physical_candidate as _candidate


SaturnSblGmCandidateError = _candidate.SaturnSblGmCandidateError
SaturnSblGmCandidateResult = _candidate.SaturnSblGmCandidateResult


_AREA_END_MARK = 0x80000000
_AREA_KIND_TONE = 0
_AREA_ADDRESS_MASK = 0x000FFFFF
_AREA_SIZE_MASK = 0x000FFFFF


def build_sega_sbl_area_map(melodic_size: int, drum_size: int) -> tuple[bytes, int]:
    """Pack the two tone banks using Sega SBL's documented area-map bitfields."""

    drum_start = _candidate._align4(_candidate._TONE_START + melodic_size)
    if melodic_size <= 0 or drum_size <= 0:
        raise SaturnSblGmCandidateError("SBL tone-bank sizes must be positive")
    if melodic_size > _AREA_SIZE_MASK or drum_size > _AREA_SIZE_MASK:
        raise SaturnSblGmCandidateError("SBL tone-bank size exceeds 20-bit area-map field")
    if drum_start + drum_size > _candidate._SOUND_RAM_END:
        raise SaturnSblGmCandidateError(
            "GM instrument + drum banks do not fit Saturn Sound RAM B000h..7FFFFh: "
            f"melodic={melodic_size}, drum={drum_size}"
        )

    def entry(bank: int, start: int, size: int) -> bytes:
        if not (0 <= bank <= 0x0F):
            raise SaturnSblGmCandidateError(f"SBL tone-bank id is outside 4-bit field: {bank}")
        if start & ~_AREA_ADDRESS_MASK:
            raise SaturnSblGmCandidateError(
                f"SBL tone-bank start is outside 20-bit sound RAM: {start:#x}"
            )
        word0 = (
            ((_AREA_KIND_TONE & 0x07) << 28)
            | ((bank & 0x0F) << 24)
            | (start & _AREA_ADDRESS_MASK)
        )
        word1 = size & _AREA_SIZE_MASK
        return struct.pack(">II", word0, word1)

    # Sega map files terminate on the high bit of the next map word.  Four
    # bytes keeps the generated buffer longword-aligned while preserving that
    # exact end-marker semantic.
    payload = (
        entry(0, _candidate._TONE_START, melodic_size)
        + entry(1, drum_start, drum_size)
        + struct.pack(">I", _AREA_END_MARK)
    )
    if len(payload) != 20:
        raise SaturnSblGmCandidateError("two-bank SBL area map must be exactly 20 bytes")
    return payload, drum_start


_RUNTIME_REPLACEMENTS = (
    ("#define GFS_OPEN_MAX 2", "#define SRK_GFS_OPEN_MAX 2"),
    ("#define GFS_MAX_DIR 32", "#define SRK_GFS_MAX_DIR 32"),
    ("GFS_WORK_SIZE(GFS_OPEN_MAX)", "GFS_WORK_SIZE(SRK_GFS_OPEN_MAX)"),
    ("gfs_names[GFS_MAX_DIR]", "gfs_names[SRK_GFS_MAX_DIR]"),
    ("GFS_DIRTBL_NDIR(&gfs_table)=GFS_MAX_DIR", "GFS_DIRTBL_NDIR(&gfs_table)=SRK_GFS_MAX_DIR"),
    ("GFS_Init(GFS_OPEN_MAX,gfs_work,&gfs_table)", "GFS_Init(SRK_GFS_OPEN_MAX,gfs_work,&gfs_table)"),
)


def rewrite_sega_sbl_runtime_contract(source: str) -> str:
    """Namespace SRK's local GFS sizing without redefining Sega header macros."""

    result = source
    for old, new in _RUNTIME_REPLACEMENTS:
        count = result.count(old)
        if count != 1:
            raise SaturnSblGmCandidateError(
                f"SBL runtime contract anchor changed ({old!r}, count={count})"
            )
        result = result.replace(old, new, 1)

    # SEGA_GFS.H owns GFS_OPEN_MAX.  A local redefinition is a -Werror failure
    # with the recorded compiler and would also make the intended work size
    # ambiguous.  The SRK-local names must be the only local definitions.
    if "#define GFS_OPEN_MAX " in result or "#define GFS_MAX_DIR " in result:
        raise SaturnSblGmCandidateError("generated runtime still redefines Sega GFS macros")
    return result


@contextmanager
def _sega_sbl_candidate_contract() -> Iterator[None]:
    original_area_map = _candidate._area_map
    original_runtime = _candidate._runtime

    def runtime(profile, assets):
        return rewrite_sega_sbl_runtime_contract(original_runtime(profile, assets))

    _candidate._area_map = build_sega_sbl_area_map
    _candidate._runtime = runtime
    try:
        yield
    finally:
        _candidate._area_map = original_area_map
        _candidate._runtime = original_runtime


def _build_log_tail(output_directory: Path, limit: int = 6000) -> str:
    log_path = output_directory / "SRK_STANDALONE_BUILD_LOG.txt"
    if not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:].strip()


def build_saturn_sbl_gm_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    melodic_tone_bank=None,
    drum_tone_bank=None,
    sound_driver=None,
) -> SaturnSblGmCandidateResult:
    """Build with the reviewed Sega SBL map/GFS contract."""

    output = Path(output_directory).expanduser().resolve(strict=False)
    try:
        with _sega_sbl_candidate_contract():
            return _candidate.build_saturn_sbl_gm_candidate(
                baseline_project,
                saturn_root,
                output,
                melodic_tone_bank=melodic_tone_bank,
                drum_tone_bank=drum_tone_bank,
                sound_driver=sound_driver,
            )
    except SaturnSblGmCandidateError as exc:
        tail = _build_log_tail(output)
        if tail:
            raise SaturnSblGmCandidateError(
                f"{exc}\n--- standalone build log tail ---\n{tail}"
            ) from exc
        raise
