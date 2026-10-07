"""Tests for the reusable Salix runtime package extracted inside SRK."""

from pathlib import Path
import tempfile
import unittest

from salix.runtime.application import ApplicationSpec
from salix.runtime.diagnostics import ExceptionReporter
from salix.runtime.lifecycle import ApplicationRuntime, RuntimeState, ServiceRegistry
from salix.runtime.paths import RuntimePathSpec, RuntimePaths
from salix.runtime.presentation import PresentationBackend, PresentationCapability
from salix.runtime.scenes import SceneRegistry


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


class _SceneHost:
    def __init__(self):
        self.visible = set()

    def exists(self, container):
        return container in {"a", "b"}

    def show(self, container):
        self.visible.add(container)

    def hide(self, container):
        self.visible.discard(container)


class SalixRuntimeTests(unittest.TestCase):
    def test_application_spec_validates_geometry(self):
        spec = ApplicationSpec("SRK", width=1000, height=700, minimum_width=800)
        self.assertEqual(spec.title, "SRK")
        self.assertAlmostEqual(spec.frame_interval_seconds, 1.0 / 60.0)
        with self.assertRaises(ValueError):
            ApplicationSpec("SRK", width=600, minimum_width=700)

    def test_runtime_order_and_failed_start_rollback(self):
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

        rollback_calls = []
        rollback = ServiceRegistry()
        rollback.register("first", _Service("first", rollback_calls))
        rollback.register(
            "second", _Service("second", rollback_calls, fail_start=True)
        )
        failing_runtime = ApplicationRuntime(services=rollback)
        with self.assertRaisesRegex(RuntimeError, "second failed"):
            failing_runtime.start()
        self.assertEqual(failing_runtime.state, RuntimeState.STOPPED)
        self.assertEqual(
            rollback_calls,
            [
                ("first", "start"),
                ("second", "start"),
                ("second", "stop"),
                ("first", "stop"),
            ],
        )

    def test_presentation_capabilities_are_explicit(self):
        backend = PresentationBackend(
            "test",
            component_renderer=object(),
            scene_host=object(),
        )
        self.assertTrue(backend.supports(PresentationCapability.COMPONENTS))
        self.assertTrue(backend.supports("scenes"))
        self.assertFalse(backend.supports("live_tables"))
        with self.assertRaises(RuntimeError):
            backend.require(PresentationCapability.LIVE_TABLES)

    def test_scene_registry_delegates_visibility(self):
        host = _SceneHost()
        scenes = SceneRegistry(host)
        a = object()
        b = object()
        scenes.register("a", a, container="a")
        scenes.register("b", b, container="b")
        self.assertTrue(scenes.activate("a"))
        self.assertEqual(host.visible, {"a"})
        self.assertIs(scenes.active_scene(), a)
        self.assertTrue(scenes.activate("b"))
        self.assertEqual(host.visible, {"b"})
        self.assertIs(scenes.active_scene(), b)

    def test_runtime_paths_are_application_named_and_repo_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = RuntimePaths(
                RuntimePathSpec(app_name="Example"),
                bundle_directory=root / "bundle",
                application_directory=root / "app",
                environ={"XDG_STATE_HOME": str(root / "state")},
                os_name="posix",
                platform="linux",
                home=root / "home",
            )
            self.assertEqual(paths.state_directory(), root / "state" / "Example")
            self.assertEqual(
                paths.default_download_directory(),
                root / "home" / "Downloads" / "Example",
            )

    def test_exception_reporter_throttles_identical_failure(self):
        emitted = []
        values = iter((10.0, 11.0, 20.0))
        reporter = ExceptionReporter(
            throttle_seconds=5.0,
            clock=lambda: next(values),
            output=emitted.append,
        )
        error = ValueError("synthetic")
        self.assertTrue(reporter.report("test", error))
        self.assertFalse(reporter.report("test", error))
        self.assertTrue(reporter.report("test", error))
        self.assertEqual(len(emitted), 2)


if __name__ == "__main__":
    unittest.main()
