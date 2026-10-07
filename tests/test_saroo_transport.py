"""Synthetic tests for the title-neutral SAROO transport boundary."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from rikai_kotoba.hardware.saturn.saroo.capture import (
    CaptureStore,
    MemoryRange,
    verify_capture,
)
from rikai_kotoba.hardware.saturn.saroo.transport import (
    SarooCaptureCoordinator,
    SarooTransportError,
    SarooTransportStatus,
    SarooTransportUnavailableError,
    UnconfiguredSarooTransport,
)


class _FakeTransport:
    def __init__(self, payloads=None, *, available=True):
        self.payloads = dict(payloads or {})
        self.available = available
        self.closed = False
        self.requests = []

    def status(self):
        return SarooTransportStatus(
            name="synthetic",
            available=self.available,
            detail="ready" if self.available else "not connected",
        )

    def read_memory(self, memory_range):
        self.requests.append(memory_range)
        return self.payloads[memory_range.start_address]

    def close(self):
        self.closed = True


class SarooTransportTests(unittest.TestCase):
    def test_unconfigured_transport_reports_explicit_unavailable_state(self):
        transport = UnconfiguredSarooTransport()
        status = transport.status()
        self.assertFalse(status.available)
        self.assertEqual(status.name, "unconfigured")
        with self.assertRaises(SarooTransportUnavailableError):
            transport.read_memory(MemoryRange(0x06000000, 4))

    def test_capture_coordinator_reads_ranges_and_publishes_artifact(self):
        timestamp = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
        low = MemoryRange(0x06000000, 4, "low")
        high = MemoryRange(0x06100000, 4, "high")
        transport = _FakeTransport(
            {
                low.start_address: b"LOW!",
                high.start_address: b"HIGH",
            }
        )

        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(
                transport,
                CaptureStore(Path(temporary) / "Dumps" / "SAROO"),
            )
            artifact = coordinator.capture(
                "checkpoint",
                (low, high),
                captured_at=timestamp,
                session_label="synthetic",
            )

            self.assertEqual(transport.requests, [low, high])
            self.assertEqual(tuple(path.read_bytes() for path in artifact.region_paths), (b"LOW!", b"HIGH"))
            self.assertTrue(verify_capture(artifact.directory).valid)

    def test_unavailable_transport_is_rejected_before_any_read(self):
        transport = _FakeTransport(available=False)
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(transport, CaptureStore(temporary))
            with self.assertRaisesRegex(SarooTransportUnavailableError, "not connected"):
                coordinator.capture("checkpoint", (MemoryRange(0x06000000, 4),))
        self.assertEqual(transport.requests, [])

    def test_short_transport_read_is_not_accepted_as_valid_capture(self):
        memory_range = MemoryRange(0x06000000, 4, "sample")
        transport = _FakeTransport({memory_range.start_address: b"BAD"})
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(transport, CaptureStore(temporary))
            with self.assertRaisesRegex(SarooTransportError, "captured byte count"):
                coordinator.capture("checkpoint", (memory_range,))

    def test_close_delegates_to_transport(self):
        transport = _FakeTransport()
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(transport, CaptureStore(temporary))
            coordinator.close()
        self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
