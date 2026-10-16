from rikai_kotoba.tools.saturn_sbl_midi_calibration_gate4_candidate import build_parser


def test_gate4_cli_requires_explicit_real_sound_assets_and_stays_off_card() -> None:
    parser = build_parser()
    actions = {action.dest: action for action in parser._actions}

    for required in (
        "baseline_project",
        "saturn_root",
        "output",
        "melodic_tone_bank",
        "drum_tone_bank",
        "sound_driver",
    ):
        assert required in actions
        assert actions[required].required

    for forbidden in (
        "card_root",
        "apply",
        "confirm",
        "destination",
        "destination_name",
        "category",
        "erase",
        "format",
    ):
        assert forbidden not in actions
