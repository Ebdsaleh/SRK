"""Tests for the presentation-neutral SAROO application controller."""

from hashlib import sha256
from pathlib import Path
import threading
import time
import tempfile
import unittest

from rikai_kotoba.application.saroo_capture import SarooCaptureController
from rikai_kotoba.application.workers import BackgroundWorkerService
from rikai_kotoba.hardware.saturn.saroo import (
    CaptureStore,
    MemoryRange,
    SarooCaptureCoordinator,
    SarooTransportStatus,
)


class _FakeTransport:
    def __init__(self, payloads=None, *, available=True):
        self.payloads = dict(payloads or {})
        self.available = available
        self.closed = False

    def status(self):
        return SarooTransportStatus(
            "synthetic",
            self.available,
            "ready" if self.available else "offline",
        )

    def read_memory(self, memory_range):
        return self.payloads[memory_range.start_address]

    def close(self):
        self.closed = True


class SarooCaptureControllerTests(unittest.TestCase):
    @staticmethod
    def _drain_until(workers, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            workers.update(0.0)
            if predicate():
                return
            time.sleep(0.005)
        raise AssertionError("timed out waiting for SAROO controller event")

    def test_status_result_is_forwarded_on_application_thread(self):
        workers = BackgroundWorkerService(max_workers=1)
        main_thread = threading.get_ident()
        received = []
        threads = []
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(
                _FakeTransport(),
                CaptureStore(temporary),
            )
            controller = SarooCaptureController(coordinator, workers)
            controller.subscribe(
                lambda event: (received.append(event), threads.append(threading.get_ident()))
            )
            workers.start()
            try:
                controller.refresh_status()
                self._drain_until(
                    workers,
                    lambda: any(event.kind == "status" for event in received),
                )
            finally:
                workers.stop()

        status_events = [event for event in received if event.kind == "status"]
        self.assertEqual(len(status_events), 1)
        self.assertTrue(status_events[0].status.available)
        self.assertTrue(all(thread_id == main_thread for thread_id in threads))
        self.assertFalse(controller.is_busy)

    def test_capture_result_returns_published_artifact(self):
        memory_range = MemoryRange(0x06000000, 4, "high")
        workers = BackgroundWorkerService(max_workers=1)
        received = []
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(
                _FakeTransport({memory_range.start_address: b"DATA"}),
                CaptureStore(temporary),
            )
            controller = SarooCaptureController(coordinator, workers)
            controller.subscribe(received.append)
            workers.start()
            try:
                controller.capture("checkpoint", (memory_range,))
                self._drain_until(
                    workers,
                    lambda: any(event.kind == "captured" for event in received),
                )
            finally:
                workers.stop()

            captured = [event for event in received if event.kind == "captured"]
            self.assertEqual(len(captured), 1)
            self.assertTrue(captured[0].artifact.manifest_path.is_file())
            self.assertEqual(captured[0].artifact.region_paths[0].read_bytes(), b"DATA")

    def test_unavailable_capture_becomes_structured_error_event(self):
        workers = BackgroundWorkerService(max_workers=1)
        received = []
        with tempfile.TemporaryDirectory() as temporary:
            coordinator = SarooCaptureCoordinator(
                _FakeTransport(available=False),
                CaptureStore(temporary),
            )
            controller = SarooCaptureController(coordinator, workers)
            controller.subscribe(received.append)
            workers.start()
            try:
                controller.capture("checkpoint", (MemoryRange(0x06000000, 4),))
                self._drain_until(
                    workers,
                    lambda: any(event.kind == "error" for event in received),
                )
            finally:
                workers.stop()

        errors = [event for event in received if event.kind == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("unavailable", errors[0].message)
        self.assertFalse(controller.is_busy)

    def test_mounted_sd_game_capture_import_is_read_only_and_transport_independent(self):
        workers = BackgroundWorkerService(max_workers=1)
        received = []
        payload = bytearray(0x00100000)
        payload[0x20:0x24] = b"TEST"
        payload = bytes(payload)

        with tempfile.TemporaryDirectory() as card_temporary, tempfile.TemporaryDirectory() as store_temporary:
            card_root = Path(card_temporary)
            source = card_root / "SAROO" / "SRK_GAME_WRAMH.BIN"
            source.parent.mkdir(parents=True)
            source.write_bytes(payload)
            original = source.read_bytes()

            coordinator = SarooCaptureCoordinator(
                _FakeTransport(available=False),
                CaptureStore(store_temporary),
            )
            controller = SarooCaptureController(coordinator, workers)
            controller.subscribe(received.append)
            workers.start()
            try:
                controller.import_mounted_sd_capture(
                    card_root,
                    "zone-b",
                    session_label="real-hardware",
                    game_wramh=True,
                )
                self._drain_until(
                    workers,
                    lambda: any(event.kind == "imported" for event in received),
                )
            finally:
                workers.stop()

            imported = [event for event in received if event.kind == "imported"]
            self.assertEqual(len(imported), 1)
            result = imported[0].ingest_result
            self.assertIsNotNone(result)
            self.assertEqual(len(result.summaries), 1)
            self.assertEqual(result.summaries[0].sha256, sha256(payload).hexdigest())
            self.assertEqual(result.summaries[0].nonzero_bytes, 4)
            self.assertTrue(result.artifact.manifest_path.is_file())
            self.assertEqual(result.artifact.region_paths[0].read_bytes(), payload)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(controller.is_busy)


if __name__ == "__main__":
    unittest.main()
