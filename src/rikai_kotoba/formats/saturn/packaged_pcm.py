"""SRK-owned deterministic PCM payload format for Saturn diagnostics.

The first packaged-audio proof intentionally uses a tiny self-describing format
rather than WAV or a Sega SDK container.  This keeps packaging provenance and
future Saturn-side loading independent from any proprietary library while the
accepted SCSP backend continues to own hardware register encoding.
"""

from __future__ import annotations

from dataclasses import dataclass


PACKAGED_PCM_FILENAME = "SRKPCM.BIN"
PACKAGED_PCM_MAGIC = b"SRKP"
PACKAGED_PCM_VERSION = 1
PACKAGED_PCM_ENCODING_PCM16_BE = 1
PACKAGED_PCM_CHANNELS_MONO = 1
PACKAGED_PCM_HEADER_SIZE = 16
PACKAGED_PCM_SAMPLE_COUNT = 512
PACKAGED_PCM_LOOP_START = 0
PACKAGED_PCM_LOOP_END = PACKAGED_PCM_SAMPLE_COUNT - 1


class SaturnPackagedPCMError(ValueError):
    """Raised when an SRK packaged PCM payload is malformed."""


@dataclass(frozen=True)
class SaturnPackagedPCM:
    version: int
    encoding: int
    channels: int
    sample_count: int
    loop_start: int
    loop_end: int
    samples: tuple[int, ...]


# Thirty-two signed levels, each repeated sixteen times, produce exactly 512
# deterministic samples.  The first and final levels are zero so the initial
# file-backed loop proof has a bounded, repeatable endpoint without claiming a
# calibrated sample rate or acoustic transfer function.
_STAGE6_LEVELS = (
    0,
    4096,
    8192,
    12288,
    16384,
    12288,
    8192,
    4096,
    0,
    -4096,
    -8192,
    -12288,
    -16384,
    -12288,
    -8192,
    -4096,
    0,
    6144,
    18432,
    10240,
    24576,
    8192,
    4096,
    0,
    -4096,
    -10240,
    -24576,
    -8192,
    -18432,
    -6144,
    0,
    0,
)
_STAGE6_SAMPLES_PER_LEVEL = 16


def build_deterministic_packaged_pcm() -> bytes:
    """Return the immutable Stage-6A mono PCM payload bytes."""

    samples = tuple(
        level
        for level in _STAGE6_LEVELS
        for _ in range(_STAGE6_SAMPLES_PER_LEVEL)
    )
    if len(samples) != PACKAGED_PCM_SAMPLE_COUNT:
        raise AssertionError("deterministic PCM definition has the wrong sample count")

    header = bytearray(PACKAGED_PCM_HEADER_SIZE)
    header[0:4] = PACKAGED_PCM_MAGIC
    header[4] = PACKAGED_PCM_VERSION
    header[5] = PACKAGED_PCM_ENCODING_PCM16_BE
    header[6] = PACKAGED_PCM_CHANNELS_MONO
    header[7] = 0
    header[8:12] = PACKAGED_PCM_SAMPLE_COUNT.to_bytes(4, "big")
    header[12:14] = PACKAGED_PCM_LOOP_START.to_bytes(2, "big")
    header[14:16] = PACKAGED_PCM_LOOP_END.to_bytes(2, "big")

    body = bytearray()
    for sample in samples:
        body.extend(int(sample).to_bytes(2, "big", signed=True))
    return bytes(header + body)


def parse_packaged_pcm(data: bytes) -> SaturnPackagedPCM:
    """Parse and strictly validate one SRK packaged PCM payload."""

    if len(data) < PACKAGED_PCM_HEADER_SIZE:
        raise SaturnPackagedPCMError("packaged PCM is shorter than its 16-byte header")
    if data[0:4] != PACKAGED_PCM_MAGIC:
        raise SaturnPackagedPCMError("packaged PCM magic is not SRKP")

    version = data[4]
    encoding = data[5]
    channels = data[6]
    reserved = data[7]
    sample_count = int.from_bytes(data[8:12], "big")
    loop_start = int.from_bytes(data[12:14], "big")
    loop_end = int.from_bytes(data[14:16], "big")

    if version != PACKAGED_PCM_VERSION:
        raise SaturnPackagedPCMError(f"unsupported packaged PCM version: {version}")
    if encoding != PACKAGED_PCM_ENCODING_PCM16_BE:
        raise SaturnPackagedPCMError(f"unsupported packaged PCM encoding: {encoding}")
    if channels != PACKAGED_PCM_CHANNELS_MONO:
        raise SaturnPackagedPCMError(f"unsupported packaged PCM channel count: {channels}")
    if reserved != 0:
        raise SaturnPackagedPCMError("packaged PCM reserved byte must be zero")
    if sample_count == 0:
        raise SaturnPackagedPCMError("packaged PCM sample count must be positive")
    if loop_start >= sample_count or loop_end >= sample_count or loop_start > loop_end:
        raise SaturnPackagedPCMError("packaged PCM loop bounds are invalid")

    expected_size = PACKAGED_PCM_HEADER_SIZE + (sample_count * 2)
    if len(data) != expected_size:
        raise SaturnPackagedPCMError(
            f"packaged PCM byte size mismatch: expected {expected_size}, got {len(data)}"
        )

    samples = tuple(
        int.from_bytes(data[offset : offset + 2], "big", signed=True)
        for offset in range(PACKAGED_PCM_HEADER_SIZE, len(data), 2)
    )
    return SaturnPackagedPCM(
        version=version,
        encoding=encoding,
        channels=channels,
        sample_count=sample_count,
        loop_start=loop_start,
        loop_end=loop_end,
        samples=samples,
    )
