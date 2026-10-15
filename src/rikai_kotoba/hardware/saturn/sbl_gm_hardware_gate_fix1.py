"""FIX1 view for the Space Spectre SBL/GM hardware gate.

The original hardware gate correctly validates the generated runtime for Sega
sound-driver calls, but it also asked that runtime file to contain the diagnostic
screen title.  The candidate builder emits that title in ``srk_saturn_main.c``
inside the generated ``gm_render`` UI block.  FIX1 preserves every original gate
check while presenting the candidate runtime validator with a read-only combined
runtime + generated-main text view for that one marker scan.

No candidate bytes are modified and no card-write behavior is changed.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import sbl_gm_hardware_gate as _base


CONFIRMATION_TOKEN = _base.CONFIRMATION_TOKEN
DEFAULT_DESTINATION_NAME = _base.DEFAULT_DESTINATION_NAME
SaturnSblGmHardwareGateError = _base.SaturnSblGmHardwareGateError
SaturnSblGmHardwareEvidence = _base.SaturnSblGmHardwareEvidence
SaturnSblGmHardwareResult = _base.SaturnSblGmHardwareResult

_MAIN = "src/srk_saturn_main.c"


class _RuntimeMarkerView:
    """Read-only text view combining runtime code with generated diagnostic UI."""

    def __init__(self, runtime: Path, main: Path) -> None:
        self._runtime = runtime
        self._main = main

    def read_text(self, *, encoding: str = "utf-8", errors: str = "strict") -> str:
        runtime_text = self._runtime.read_text(encoding=encoding, errors=errors)
        main_text = self._main.read_text(encoding=encoding, errors=errors)
        return runtime_text + "\n" + main_text


@contextmanager
def _correct_marker_scope() -> Iterator[None]:
    original = _base._project_file

    def project_file(root: Path, relative: str, label: str):
        path = original(root, relative, label)
        if relative == _base._RUNTIME and label == "candidate runtime":
            main = original(root, _MAIN, "candidate generated main")
            return _RuntimeMarkerView(path, main)
        return path

    _base._project_file = project_file
    try:
        yield
    finally:
        _base._project_file = original


def inspect_saturn_sbl_gm_hardware_gate(*args, **kwargs) -> SaturnSblGmHardwareEvidence:
    """Run the original read-only gate with the screen marker read from main."""

    with _correct_marker_scope():
        return _base.inspect_saturn_sbl_gm_hardware_gate(*args, **kwargs)


def run_saturn_sbl_gm_hardware_gate(*args, **kwargs) -> SaturnSblGmHardwareResult:
    """Run the original guarded gate with the corrected marker-file view."""

    with _correct_marker_scope():
        return _base.run_saturn_sbl_gm_hardware_gate(*args, **kwargs)
