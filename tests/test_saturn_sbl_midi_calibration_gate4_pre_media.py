from hashlib import sha256
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_candidate import (
    build_gate4_external_area_map,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_gate4_pre_media import (
    _EXPECTED_MAP_SHA256,
)


_ROOT = Path(__file__).resolve().parents[1]
_GATE = (
    _ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_midi_calibration_gate4_pre_media.py"
)


def test_gate4_pre_media_pins_external_mp_map() -> None:
    payload, drum_start = build_gate4_external_area_map(321130, 111776)

    assert drum_start == 0x5966C
    assert len(payload) == 18
    assert payload[-2:] == b"\xff\xff"
    assert sha256(payload).hexdigest() == _EXPECTED_MAP_SHA256
    assert _EXPECTED_MAP_SHA256 == (
        "b4a249b0d9df4985ad6f3357cd978e017b41bbf82d0d6603f378d968c6b67001"
    )


def test_gate4_pre_media_requires_init_volume_direct_midi_and_raw_scsp_isolation() -> None:
    source = _GATE.read_text(encoding="utf-8")

    for required in (
        "SND_Init(&ini);",
        "SND_ChgMap(0)",
        "SND_ChgMix(0,0)",
        "SND_SetTlVl(15)",
        "SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2)",
        "host->midi_select_program = srk_saturn_sbl_midi_select_program;",
        "host->midi_note_on = srk_saturn_sbl_midi_note_on;",
        "srk_host.present_audio_tone = 0;",
        "SRK_SBL_CAL_MAP_BYTES 18UL",
        "SRK_SBL_CAL_GATE4_EXTERNAL_MP 1u",
    ):
        assert required in source


def test_gate4_pre_media_has_no_card_or_write_surface() -> None:
    source = _GATE.read_text(encoding="utf-8")

    for forbidden in (
        "card_root",
        "destination_name",
        "shutil.copy",
        "write_bytes(",
        "write_text(",
        "unlink(",
        "mkdir(",
        "rmtree(",
    ):
        assert forbidden not in source
