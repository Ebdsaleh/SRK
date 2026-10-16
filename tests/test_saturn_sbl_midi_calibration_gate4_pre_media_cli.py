from rikai_kotoba.tools.saturn_sbl_midi_calibration_gate4_pre_media import build_parser


def test_gate4_pre_media_cli_is_project_only_and_read_only() -> None:
    parser = build_parser()
    actions = {action.dest: action for action in parser._actions}

    assert "project" in actions
    assert actions["project"].required

    for forbidden in (
        "card_root",
        "destination",
        "destination_name",
        "category",
        "apply",
        "confirm",
        "deploy",
        "erase",
        "format",
        "output",
    ):
        assert forbidden not in actions
