"""SAROO-assisted Sega Saturn runtime/debug tooling.

This package contains only title-neutral hardware-research primitives. Runtime
capture, memory dumps, patching, and correlation remain parameterized by caller-
supplied addresses/data rather than commercial-game-specific constants.
"""

from .build import (
    SarooBuildArtifact,
    SarooBuildError,
    SarooBuildResult,
    build_firm_saturn_tree,
)
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
from .firmware_integration import (
    SarooFirmwareIntegrationError,
    SarooFirmwareIntegrationResult,
    default_helper_root,
    prepare_firm_saturn_tree,
)
from .sd_exchange import (
    SAROO_SD_WRITE_CHUNK_SIZE,
    SarooSdWriteChunk,
    import_raw_sd_dump,
    plan_sd_write_chunks,
    total_planned_bytes,
)
from .toolchain import (
    SAROO_TOOL_REQUIREMENTS,
    SarooToolProbe,
    SarooToolRequirement,
    SarooToolchainError,
    SarooToolchainReport,
    inspect_saroo_toolchain,
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
    "SAROO_TOOL_REQUIREMENTS",
    "CaptureArtifact",
    "CaptureError",
    "CaptureIntegrityError",
    "CaptureStore",
    "CaptureVerification",
    "CapturedRegion",
    "MemoryRange",
    "SarooBuildArtifact",
    "SarooBuildError",
    "SarooBuildResult",
    "SarooCaptureCoordinator",
    "SarooFirmwareIntegrationError",
    "SarooFirmwareIntegrationResult",
    "SarooSdWriteChunk",
    "SarooToolProbe",
    "SarooToolRequirement",
    "SarooToolchainError",
    "SarooToolchainReport",
    "SarooTransport",
    "SarooTransportError",
    "SarooTransportStatus",
    "SarooTransportUnavailableError",
    "UnconfiguredSarooTransport",
    "build_firm_saturn_tree",
    "default_helper_root",
    "import_raw_sd_dump",
    "inspect_saroo_toolchain",
    "load_manifest",
    "plan_sd_write_chunks",
    "prepare_firm_saturn_tree",
    "total_planned_bytes",
    "verify_capture",
]
