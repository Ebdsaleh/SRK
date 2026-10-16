from rikai_kotoba.tools.saturn_sbl_midi_calibration_candidate import build_parser


def test_calibration_candidate_cli_requires_off_card_build_inputs():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--baseline-project",
            "baseline",
            "--saturn-root",
            "Saturn-Dev",
            "--output",
            "candidate",
        ]
    )

    assert str(args.baseline_project) == "baseline"
    assert str(args.saturn_root) == "Saturn-Dev"
    assert str(args.output) == "candidate"
    assert args.melodic_tone_bank is None
    assert args.drum_tone_bank is None
    assert args.sound_driver is None
