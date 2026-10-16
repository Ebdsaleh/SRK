from hashlib import sha256
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_candidate import (
    _GATE4_MAP_BYTES,
    _gate4_header,
    build_gate4_external_area_map,
)


_ROOT = Path(__file__).resolve().parents[1]
_BINDING = (
    _ROOT
    / "integrations"
    / "saturn"
    / "standalone"
    / "srk_saturn_sbl_midi_calibration.c"
)


def test_gate4_uses_external_mp_map_proven_by_native_sequence_path() -> None:
    payload, drum_start = build_gate4_external_area_map(321130, 111776)

    assert _GATE4_MAP_BYTES == 18
    assert len(payload) == 18
    assert drum_start == 0x5966C
    assert payload.hex() == "0000b0000004e66a0105966c0001b4a0ffff"
    assert sha256(payload).hexdigest() == (
        "b4a249b0d9df4985ad6f3357cd978e017b41bbf82d0d6603f378d968c6b67001"
    )
    assert payload.endswith(b"\xff\xff")
    assert not payload.endswith(b"\x80\x00\x00\x00")


def test_gate4_runtime_header_declares_external_mp_contract() -> None:
    header = _gate4_header(25488, 321130, 111776)

    assert "SRK_SBL_CAL_DRIVER_BYTES 25488UL" in header
    assert "SRK_SBL_CAL_MAP_BYTES 18UL" in header
    assert "SRK_SBL_CAL_TONE_BYTES 321130UL" in header
    assert "SRK_SBL_CAL_DRUM_BYTES 111776UL" in header
    assert "SRK_SBL_CAL_GATE4_EXTERNAL_MP 1u" in header


def test_gate4_keeps_concrete_direct_midi_callbacks_not_stubs() -> None:
    source = _BINDING.read_text(encoding="utf-8")

    assert "return result == SND_RET_SET;" in source
    assert "srk_saturn_sbl_direct_midi(" in source
    assert "SRK_SBL_CAL_BANK_CONTROLLER" in source
    assert "SRK_SBL_CAL_PROGRAM_CHANGE" in source
    assert "SRK_SBL_CAL_NOTE_ON" in source
    assert "host->midi_select_program = srk_saturn_sbl_midi_select_program;" in source
    assert "host->midi_set_pan = srk_saturn_sbl_midi_set_pan;" in source
    assert "host->midi_note_on = srk_saturn_sbl_midi_note_on;" in source
    assert "host->midi_note_off = srk_saturn_sbl_midi_note_off;" in source
