"""Desktop entry point for the SRK application built on Salix + Dear PyGui."""

from __future__ import annotations

import argparse
import os
from typing import Sequence

from rikai_kotoba import __version__
from rikai_kotoba.application.controller import DiscWorkspaceController
from rikai_kotoba.application.disc_workspace import DiscWorkspaceService
from rikai_kotoba.application.paths import state_directory
from rikai_kotoba.application.workers import BackgroundWorkerService
from salix.runtime.application import ApplicationSpec
from salix.runtime.diagnostics import ExceptionReporter
from salix.runtime.lifecycle import ApplicationRuntime, CallbackService


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="SRK (Salix Rikai Kotoba) Dear PyGui desktop application"
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Optional CUE/BIN/ISO/IMG/RAW source to open after launch",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Workspace root for generated artifacts; defaults to the current directory",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"SRK {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    source = os.path.abspath(args.source) if args.source else None
    output_dir = os.path.abspath(args.output_dir or os.getcwd())

    reporter = ExceptionReporter(
        log_path=state_directory() / "ui_errors.log",
        prefix="[SRK UI Error]",
    )
    runtime = ApplicationRuntime(
        error_handler=lambda context, exc: reporter.report(context, exc)
    )

    workers = BackgroundWorkerService(max_workers=2)
    runtime.services.register("SRK background workers", workers)

    disc_service = DiscWorkspaceService()
    disc_controller = DiscWorkspaceController(disc_service, workers)

    try:
        from salix.engine.application_hosts import DearPyGuiApplicationHost
        from rikai_kotoba.views.main_viewport import MainViewport
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("dearpygui"):
            print(
                "Dear PyGui is not installed. Reinstall SRK desktop dependencies with:\n"
                "    python -m pip install -e ."
            )
            return 2
        raise

    spec = ApplicationSpec(
        name="SRK",
        title="SRK - Salix Rikai Kotoba",
        width=1180,
        height=760,
        minimum_width=1000,
        minimum_height=640,
        target_fps=60,
    )
    host = DearPyGuiApplicationHost(spec, runtime=runtime)
    viewport = MainViewport(
        host,
        disc_controller,
        workers,
        reporter,
        initial_source=source,
        output_dir=output_dir,
    )
    runtime.services.register(
        "SRK active view",
        CallbackService(
            on_update=viewport.update,
            on_stop=viewport.dispose,
        ),
    )
    return host.run()


if __name__ == "__main__":
    raise SystemExit(main())
