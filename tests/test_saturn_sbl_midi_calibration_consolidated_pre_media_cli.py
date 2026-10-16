from rikai_kotoba.tools.saturn_sbl_midi_calibration_consolidated_pre_media import build_parser


def test_consolidated_pre_media_cli_is_project_only_and_read_only():
    parser = build_parser()
    args = parser.parse_args(["--project", "CONSOLIDATED"])
    assert str(args.project) == "CONSOLIDATED"

    options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--project" in options
    for forbidden in (
        "--card-root",
        "--destination",
        "--destination-name",
        "--apply",
        "--confirm",
        "--expected-bin-sha256",
        "--expected-cue-sha256",
        "--format",
        "--erase",
        "--deploy",
    ):
        assert forbidden not in options
