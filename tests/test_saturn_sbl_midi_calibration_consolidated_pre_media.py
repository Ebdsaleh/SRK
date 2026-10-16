from pathlib import Path

from rikai_kotoba.hardware.saturn.sbl_midi_calibration_consolidated_pre_media import (
    EXPECTED_AREA_MAP_SHA256,
    EXPECTED_ARTIFACTS,
    EXPECTED_FAMILIES,
    EXPECTED_FAMILY_COUNT,
    EXPECTED_MAX_FAMILY_BYTES,
    EXPECTED_PROGRAM_COUNT,
    EXPECTED_SEGA_SND_SHA256,
    EXPECTED_SOUND_DRIVER_SHA256,
    EXPECTED_SOUNDFONT_SHA256,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_midi_calibration_consolidated_pre_media.py"
)


def test_pre_media_locks_exact_eridu_consolidated_assets():
    assert EXPECTED_SOUND_DRIVER_SHA256 == (
        "76754e5bae4217e48d6a3c53c181033ddaab050deabda638bc41bf2f7f4906e3"
    )
    assert EXPECTED_SOUNDFONT_SHA256 == (
        "9575028c7a1f589f5770fccc8cff2734566af40cd26ed836944e9a5152688cfe"
    )
    assert EXPECTED_SEGA_SND_SHA256 == (
        "7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407"
    )
    assert EXPECTED_AREA_MAP_SHA256 == (
        "40530e1a0f1b147a6f87aaaa00de7593b82fbec806f291bcddc2b09d865a4605"
    )
    assert EXPECTED_MAX_FAMILY_BYTES == 185568
    assert EXPECTED_PROGRAM_COUNT == 128
    assert EXPECTED_FAMILY_COUNT == 16


def test_pre_media_locks_all_16_real_family_banks_without_gaps():
    assert len(EXPECTED_FAMILIES) == 16
    covered = []
    for family, filename, programs, size, sha256 in EXPECTED_FAMILIES:
        assert filename == f"GMC{family:02d}.BIN"
        assert len(programs) == 8
        assert tuple(programs) == tuple(range(family * 8, family * 8 + 8))
        assert size > 0
        assert len(sha256) == 64
        covered.extend(programs)
    assert tuple(covered) == tuple(range(128))


def test_pre_media_locks_final_and_intermediate_build_artifacts():
    assert EXPECTED_ARTIFACTS["build/srk_diag.bin"] == (
        84352,
        "5ae8a318639baef20efc1db74d203d479b615db314f3bb7ae6161ee01af5041c",
    )
    assert EXPECTED_ARTIFACTS["build/srk_diag.iso"] == (
        2097152,
        "6a009f8344cc628e39963da0e75ef155ccd8733837dc90d3d0a85dbf1ac62e43",
    )
    assert EXPECTED_ARTIFACTS["build/srk_diag.map"] == (
        69467,
        "1eb95b96b2e4bf5a45c9a52aefa25dbba460001552bcddc51aff2f782dfc2b69",
    )
    assert EXPECTED_ARTIFACTS["build/SRK-Diagnostics/SRK-Diagnostics.bin"] == (
        2408448,
        "3c03f4c49dd70e7f142faaa3b1fc69b1e1735eb13b5524beed0b46a4d3bfaff6",
    )
    assert EXPECTED_ARTIFACTS["build/SRK-Diagnostics/SRK-Diagnostics.cue"] == (
        81,
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950",
    )


def test_pre_media_requires_consolidated_lifecycle_telemetry_and_raw_scsp_contract():
    text = SOURCE.read_text(encoding="utf-8")
    for required in (
        '"sbl_midi_calibration_consolidated": True',
        '"raw_scsp_audio_callbacks_disabled": False',
        '"screen_owned_sbl_lifecycle": True',
        '"silent_placeholder_gm_voices": False',
        '"command_history_proves_driver_execution": True',
        "0x25A00416",
        "0x25A0041A",
        "0x25A00420",
        "family=program/SRK_SBL_CAL_FAMILY_SIZE",
        "voice=program%SRK_SBL_CAL_FAMILY_SIZE",
        "history!=s->history_baseline",
        "srk_saturn_audio_bind(srk_cal_host,host_state);",
    ):
        assert required in text
    assert 'if "SND_ChgMix" in runtime:' in text
    assert "srk_host.present_audio_tone = 0;" in text
    assert "srk_host.stop_audio = 0;" in text
    assert "srk_host.read_audio_status = 0;" in text


def test_pre_media_has_no_card_destination_or_write_surface():
    text = SOURCE.read_text(encoding="utf-8")
    for forbidden in (
        "card_root",
        "destination_name",
        "DEPLOY-",
        "shutil.copy",
        "write_bytes(",
        "write_text(",
        "unlink(",
        "rmtree(",
        "format(",
        "diskpart",
        "mkfs",
    ):
        assert forbidden not in text
