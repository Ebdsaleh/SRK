from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_gm_candidate_contract import (
    build_sega_sbl_area_map,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_pre_media import (
    EXPECTED_DRUM_SHA256,
    EXPECTED_MELODIC_SHA256,
    EXPECTED_SEGA_SND_SHA256,
    EXPECTED_SOUND_DRIVER_SHA256,
    _DEPLOY_BIN,
    _DEPLOY_CUE,
    _MAIN,
    _RUNTIME,
)


_ROOT = Path(__file__).resolve().parents[1]
_GATE = (
    _ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_midi_calibration_pre_media.py"
)


def test_calibration_gate_locks_eridu_validated_real_sega_assets() -> None:
    assert EXPECTED_SOUND_DRIVER_SHA256 == (
        "76754e5bae4217e48d6a3c53c181033ddaab050deabda638bc41bf2f7f4906e3"
    )
    assert EXPECTED_MELODIC_SHA256 == (
        "1b5821cd64037b6aef1e6836f3064069761d7a1fa1a7cbc166213d1caf07808b"
    )
    assert EXPECTED_DRUM_SHA256 == (
        "6b3b3dc9b69e480fd235266defa3e91d1837b906900378bd3b409256277b9534"
    )
    assert EXPECTED_SEGA_SND_SHA256 == (
        "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
    )


def test_calibration_gate_reconstructs_locked_two_bank_sound_ram_map() -> None:
    payload, drum_start = build_sega_sbl_area_map(321130, 111776)
    assert len(payload) == 20
    assert drum_start == 0x5966C
    assert sha256(payload).hexdigest() == (
        "a307131a1db37f5f272548e3eb9d13d95b35894e9aeb97fb40a44b055c9e1069"
    )


def test_calibration_gate_audits_runtime_main_and_deployable_contract() -> None:
    source = _GATE.read_text(encoding="utf-8")

    assert _RUNTIME == "src/srk_saturn_runtime.c"
    assert _MAIN == "src/srk_saturn_main.c"
    assert _DEPLOY_BIN == "build/SRK-Diagnostics/SRK-Diagnostics.bin"
    assert _DEPLOY_CUE == "build/SRK-Diagnostics/SRK-Diagnostics.cue"

    # Match the contract text itself rather than Python's choice of quote style.
    # The original version accidentally required double quotes even though the
    # gate stores these anchors in single-quoted string literals.
    for required in (
        "SND_Init(&ini);",
        "SND_ChgMap(0)",
        "SND_KD_TONE,0)",
        "SND_KD_TONE,1)",
        "#define SRK_SBL_CAL_BANK_CONTROLLER 32u",
        "#define SRK_SBL_CAL_PAN_CONTROLLER 10u",
        "host->midi_persist_review = 0;",
        "srk_host.present_audio_tone = 0;",
        "srk_host.stop_audio = 0;",
        "srk_host.read_audio_status = 0;",
        "cue-bin-mode1-2352",
        "verified_against_iso",
    ):
        assert required in source

    for forbidden_runtime_marker in (
        "0x25A00000",
        "0x25B00000",
        "SRK_AUDIO_SOUND_RAM",
        "SRK_AUDIO_SCSP_SLOT0",
    ):
        assert forbidden_runtime_marker in source


def test_calibration_pre_media_module_has_no_card_or_write_api() -> None:
    source = _GATE.read_text(encoding="utf-8")
    for forbidden in (
        "card_root",
        "destination_name",
        "shutil.copy",
        "write_bytes(",
        "write_text(",
        "unlink(",
        "mkdir(",
    ):
        assert forbidden not in source
