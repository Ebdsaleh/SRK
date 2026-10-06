"""Tests for SRK's worker-to-main-thread event bridge."""

import threading
import time
import unittest

from rikai_kotoba.runtime.workers import (
    BackgroundWorkerService,
    WorkerEventKind,
)


class BackgroundWorkerTests(unittest.TestCase):
    @staticmethod
    def _drain_until(workers, predicate, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            workers.update(0.0)
            if predicate():
                return
            time.sleep(0.005)
        raise AssertionError("timed out waiting for worker event")

    def test_worker_result_is_dispatched_on_update_calling_thread(self):
        workers = BackgroundWorkerService(max_workers=1)
        events = []
        main_thread = threading.get_ident()
        worker_thread = []
        handler_threads = []

        def task():
            worker_thread.append(threading.get_ident())
            return "done"

        def handler(event):
            events.append(event)
            handler_threads.append(threading.get_ident())

        workers.subscribe(handler)
        workers.start()
        try:
            workers.submit("test.job", task)
            self._drain_until(
                workers,
                lambda: any(e.kind is WorkerEventKind.COMPLETED for e in events),
            )
        finally:
            workers.stop()

        completed = [e for e in events if e.kind is WorkerEventKind.COMPLETED]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].payload, "done")
        self.assertNotEqual(worker_thread[0], main_thread)
        self.assertTrue(handler_threads)
        self.assertTrue(all(thread_id == main_thread for thread_id in handler_threads))

    def test_worker_failure_becomes_structured_failed_event(self):
        workers = BackgroundWorkerService(max_workers=1)
        events = []
        workers.subscribe(events.append)
        workers.start()
        try:
            def fail():
                raise ValueError("synthetic failure")

            workers.submit("test.failure", fail)
            self._drain_until(
                workers,
                lambda: any(e.kind is WorkerEventKind.FAILED for e in events),
            )
        finally:
            workers.stop()

        failed = [e for e in events if e.kind is WorkerEventKind.FAILED]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].error_type, "ValueError")
        self.assertEqual(failed[0].error_message, "synthetic failure")
        self.assertIn("ValueError", failed[0].traceback_text or "")

    def test_submit_requires_running_service(self):
        workers = BackgroundWorkerService(max_workers=1)
        with self.assertRaises(RuntimeError):
            workers.submit("test", lambda: None)


if __name__ == "__main__":
    unittest.main()
