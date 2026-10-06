"""Tests for the toolkit-neutral disc workspace controller."""

import threading
import time
import unittest

from rikai_kotoba.application.controller import DiscWorkspaceController
from rikai_kotoba.application.disc_workspace import DiscWorkspaceSnapshot
from rikai_kotoba.runtime.workers import BackgroundWorkerService


class _FakeDiscService:
    def open_source(self, path):
        return DiscWorkspaceSnapshot(
            source_path=path,
            source_kind="synthetic",
            base_name="sample",
            entries=(),
        )

    def close_source(self):
        pass


class DiscWorkspaceControllerTests(unittest.TestCase):
    def test_completed_worker_job_is_forwarded_on_main_thread(self):
        workers = BackgroundWorkerService(max_workers=1)
        controller = DiscWorkspaceController(_FakeDiscService(), workers)
        events = []
        handler_threads = []
        main_thread = threading.get_ident()

        def handler(event):
            events.append(event)
            handler_threads.append(threading.get_ident())

        controller.subscribe(handler)
        workers.start()
        try:
            controller.open_source("sample.iso")
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                workers.update(0.0)
                if any(event.kind == "opened" for event in events):
                    break
                time.sleep(0.005)
            else:
                self.fail("timed out waiting for opened event")
        finally:
            workers.stop()

        self.assertEqual(events[0].kind, "opening")
        opened = [event for event in events if event.kind == "opened"]
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].snapshot.base_name, "sample")
        self.assertTrue(all(thread_id == main_thread for thread_id in handler_threads))
        self.assertFalse(controller.is_busy)

    def test_empty_path_is_rejected_before_worker_submission(self):
        workers = BackgroundWorkerService(max_workers=1)
        controller = DiscWorkspaceController(_FakeDiscService(), workers)
        workers.start()
        try:
            with self.assertRaises(ValueError):
                controller.open_source("   ")
        finally:
            workers.stop()


if __name__ == "__main__":
    unittest.main()
