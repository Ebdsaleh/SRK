from inspect import signature
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_candidate_contract import (
    build_saturn_sbl_midi_calibration_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_midi_calibration_candidate_contract.py"
)


def test_public_contract_keeps_historical_gate4_signature_while_adding_soundfont():
    params = signature(build_saturn_sbl_midi_calibration_candidate).parameters
    assert "soundfont" in params
    assert "melodic_tone_bank" in params
    assert "drum_tone_bank" in params
    assert "sound_driver" in params


def test_explicit_old_tone_banks_route_to_historical_builder_only():
    text = SOURCE.read_text(encoding="utf-8")
    assert "from . import sbl_midi_calibration_candidate as _legacy_candidate" in text
    assert "from . import sbl_midi_calibration_consolidated as _candidate" in text
    assert "historical = melodic_tone_bank is not None or drum_tone_bank is not None" in text
    assert "_legacy_candidate.build_saturn_sbl_midi_calibration_candidate(" in text
    assert "soundfont=soundfont" in text
