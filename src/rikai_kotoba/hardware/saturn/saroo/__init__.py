"""SAROO-assisted Sega Saturn runtime/debug tooling.

This package contains only title-neutral hardware-research primitives. Runtime
capture, memory dumps, patching, and correlation remain parameterized by caller-
supplied addresses/data rather than commercial-game-specific constants.
"""

from .capture import (
    CAPTURE_SCHEMA,
    CAPTURE_SCHEMA_VERSION,
    CaptureArtifact,
    CaptureError,
    CaptureIntegrityError,
    CaptureStore,
    CaptureVerification,
    CapturedRegion,
    MemoryRange,
    load_manifest,
    verify_capture,
)
from .sd_exchange import (
    SAROO_SD_WRITE_CHUNK_SIZE,
    SarooSdWriteChunk,
    import_raw_sd_dump,
    plan_sd_write_chunks,
    total_planned_bytes,
)
from .transport import (
    SarooCaptureCoordinator,
    SarooTransport,
    SarooTransportError,
    SarooTransportStatus,
    SarooTransportUnavailableError,
    UnconfiguredSarooTransport,
)

__all__ = [
    "CAPTURE_SCHEMA",
    "CAPTURE_SCHEMA_VERSION",
    "SAROO_SD_WRITE_CHUNK_SIZE",
    "CaptureArtifact",
    "CaptureError",
    "CaptureIntegrityError",
    "CaptureStore",
    "CaptureVerification",
    "CapturedRegion",
    "MemoryRange",
    "SarooCaptureCoordinator",
    "SarooSdWriteChunk",
    "SarooTransport",
    "SarooTransportError",
    "SarooTransportStatus",
    "SarooTransportUnavailableError",
    "UnconfiguredSarooTransport",
    "import_raw_sd_dump",
    "load_manifest",
    "plan_sd_write_chunks",
    "total_planned_bytes",
    "verify_capture",
]
