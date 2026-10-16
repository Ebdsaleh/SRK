from rikai_kotoba.tools.saturn_sbl_midi_calibration_consolidated_guarded_deployment import (
    build_parser,
)


def test_consolidated_guarded_cli_has_only_fixed_evidence_and_destination_surface() -> None:
    parser = build_parser()
    actions = {action.dest: action for action in parser._actions}

    for required in ("project", "card_root", "guard_manifest"):
        assert required in actions
        assert actions[required].required

    for optional in ("apply", "expected_guard_manifest_sha256", "confirm"):
        assert optional in actions

    for forbidden in (
        "name",
        "destination",
        "destination_name",
        "category",
        "expected_bin_sha256",
        "expected_cue_sha256",
        "expected_manifest_sha256",
        "expected_build_report_sha256",
        "expected_area_map_sha256",
        "format",
        "erase",
    ):
        assert forbidden not in actions
