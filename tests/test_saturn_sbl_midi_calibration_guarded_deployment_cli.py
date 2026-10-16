from __future__ import annotations

from rikai_kotoba.tools.saturn_sbl_midi_calibration_guarded_deployment import (
    _parser,
)


def test_guarded_calibration_cli_exposes_only_two_phase_fixed_destination_surface() -> None:
    parser = _parser()
    destinations = {action.dest for action in parser._actions}
    assert {
        "project",
        "card_root",
        "guard_manifest",
        "apply",
        "expected_guard_manifest_sha256",
        "confirm",
    }.issubset(destinations)
    for forbidden in (
        "name",
        "destination",
        "destination_name",
        "category",
        "expected_bin_sha256",
        "expected_cue_sha256",
        "expected_candidate_manifest_sha256",
        "expected_candidate_report_sha256",
        "format",
        "erase",
    ):
        assert forbidden not in destinations
