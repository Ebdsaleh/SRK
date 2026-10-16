from pathlib import Path

from rikai_kotoba.tools.saturn_sbl_midi_calibration_candidate import build_parser


_ROOT = Path(__file__).resolve().parents[1]
_CLI = _ROOT / "src" / "rikai_kotoba" / "tools" / "saturn_sbl_midi_calibration_candidate.py"


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
    assert args.soundfont is None
    assert args.sound_driver is None


def test_calibration_candidate_cli_uses_current_consolidated_contract_wrapper():
    source = _CLI.read_text(encoding="utf-8")
    assert "sbl_midi_calibration_candidate_contract import" in source
    assert "--soundfont" in source
    assert "--melodic-tone-bank" not in source
    assert "--drum-tone-bank" not in source
    assert "16 REAL FAMILY BANKS / NO PLACEHOLDERS" in source
    assert "DEFERRED TO MIDI SCREEN ENTRY / RELEASE ON EXIT" in source
    assert "COMMAND HISTORY + DRIVER/CPU ERROR STATUS" in source
    assert "RETAINED / REINITIALIZED AFTER SBL" in source
