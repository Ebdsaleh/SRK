"""CLI output regression for the R19 whole-card guarded deployment."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

from rikai_kotoba.tools.saturn_midi_68k_silent_batch_physical_candidate_guarded_deployment import (
    _print_pre_media,
)


def test_guarded_cli_prints_pre_media_image_anchor_and_index_27_contract():
    result = SimpleNamespace(
        manifest_sha256="1" * 64,
        report_sha256="2" * 64,
        image_sha256="3" * 64,
        deployable_bin_sha256="4" * 64,
        deployable_cue_sha256="5" * 64,
    )
    output = StringIO()
    with redirect_stdout(output):
        _print_pre_media(result)

    text = output.getvalue()
    assert "Batch image SHA-256      : " + ("3" * 64) in text
    assert "ACKNOWLEDGED / sequence 1 / index 27 / error 0" in text
    assert "MIDI-driven SCSP note    : NO" in text
