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
    "CaptureArtifact",
    "CaptureError",
    "CaptureIntegrityError",
    "CaptureStore",
    "CaptureVerification",
    "CapturedRegion",
    "MemoryRange",
    "SarooCaptureCoordinator",
    "SarooTransport",
    "SarooTransportError",
    "SarooTransportStatus",
    "SarooTransportUnavailableError",
    "UnconfiguredSarooTransport",
    "load_manifest",
    "verify_capture",
]
