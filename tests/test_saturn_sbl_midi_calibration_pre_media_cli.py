from rikai_kotoba.tools.saturn_sbl_midi_calibration_pre_media import _parser


def test_calibration_pre_media_cli_has_no_media_or_mutation_surface() -> None:
    parser = _parser()
    destinations = {action.dest for action in parser._actions}

    assert "project" in destinations
    for forbidden in (
        "card_root",
        "destination",
        "destination_name",
        "apply",
        "confirm",
        "deploy",
        "output",
    ):
        assert forbidden not in destinations
