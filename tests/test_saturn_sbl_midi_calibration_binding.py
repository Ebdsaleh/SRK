from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = (
    _ROOT
    / "integrations"
    / "saturn"
    / "standalone"
    / "srk_saturn_sbl_midi_calibration.c"
)
_HEADER = (
    _ROOT
    / "integrations"
    / "saturn"
    / "standalone"
    / "srk_saturn_sbl_midi_calibration.h"
)


def test_calibration_binding_uses_verified_sega_direct_midi_contract():
    source = _SOURCE.read_text(encoding="utf-8")
    header = _HEADER.read_text(encoding="utf-8")

    assert '#include "srk_saturn_sbl_direct_midi.h"' in source
    assert "#define SRK_SBL_CAL_NOTE_OFF 0u" in source
    assert "#define SRK_SBL_CAL_NOTE_ON 1u" in source
    assert "#define SRK_SBL_CAL_CONTROL_CHANGE 3u" in source
    assert "#define SRK_SBL_CAL_PROGRAM_CHANGE 4u" in source
    assert "#define SRK_SBL_CAL_BANK_CONTROLLER 32u" in source
    assert "#define SRK_SBL_CAL_MELODIC_BANK 0u" in source
    assert "#define SRK_SBL_CAL_PAN_CONTROLLER 10u" in source
    assert "result == SND_RET_SET" in source

    bank_select = source.index("SRK_SBL_CAL_BANK_CONTROLLER")
    program_change = source.index("SRK_SBL_CAL_PROGRAM_CHANGE", bank_select)
    assert bank_select < program_change

    assert "host->midi_select_program = srk_saturn_sbl_midi_select_program;" in source
    assert "host->midi_set_pan = srk_saturn_sbl_midi_set_pan;" in source
    assert "host->midi_note_on = srk_saturn_sbl_midi_note_on;" in source
    assert "host->midi_note_off = srk_saturn_sbl_midi_note_off;" in source
    assert "host->midi_persist_review = 0;" in source
    assert "void srk_saturn_sbl_midi_calibration_bind(SRK_DIAG_HOST *host);" in header

    combined = source + "\n" + header
    for forbidden in (
        "0x25A00000",
        "0x25B00000",
        "KYONB",
        "KYONEX",
        "DIPAN",
        "DISDL",
        "MC68EC000",
    ):
        assert forbidden not in combined
