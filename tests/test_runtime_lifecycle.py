"""Tests for SRK's backend-neutral application lifecycle."""

import unittest

from rikai_kotoba.runtime.application import ApplicationSpec
from rikai_kotoba.runtime.lifecycle import (
    ApplicationRuntime,
    RuntimeState,
    ServiceRegistry,
)


class _Service:
    def __init__(self, name, calls, *, fail_start=False):
        self.name = name
        self.calls = calls
        self.fail_start = fail_start

    def start(self):
        self.calls.append((self.name, "start"))
        if self.fail_start:
            raise RuntimeError(f"{self.name} failed")

    def update(self, delta_seconds):
        self.calls.append((self.name, "update", delta_seconds))

    def stop(self):
        self.calls.append((self.name, "stop"))


class RuntimeLifecycleTests(unittest.TestCase):
    def test_application_spec_validates_geometry(self):
        spec = ApplicationSpec("SRK", width=1000, height=700, minimum_width=800)
        self.assertEqual(spec.title, "SRK")
        self.assertAlmostEqual(spec.frame_interval_seconds, 1.0 / 60.0)
        with self.assertRaises(ValueError):
            ApplicationSpec("SRK", width=600, minimum_width=700)

    def test_runtime_starts_updates_and_stops_in_deterministic_order(self):
        calls = []
        registry = ServiceRegistry()
        registry.register("first", _Service("first", calls))
        registry.register("second", _Service("second", calls))
        runtime = ApplicationRuntime(services=registry)

        runtime.start()
        runtime.update(0.25)
        runtime.stop()

        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertEqual(
            calls,
            [
                ("first", "start"),
                ("second", "start"),
                ("first", "update", 0.25),
                ("second", "update", 0.25),
                ("second", "stop"),
                ("first", "stop"),
            ],
        )

    def test_failed_start_rolls_back_already_started_services(self):
        calls = []
        registry = ServiceRegistry()
        registry.register("first", _Service("first", calls))
        registry.register("second", _Service("second", calls, fail_start=True))
        runtime = ApplicationRuntime(services=registry)

        with self.assertRaisesRegex(RuntimeError, "second failed"):
            runtime.start()

        self.assertEqual(runtime.state, RuntimeState.STOPPED)
        self.assertEqual(
            calls,
            [
                ("first", "start"),
                ("second", "start"),
                ("second", "stop"),
                ("first", "stop"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
