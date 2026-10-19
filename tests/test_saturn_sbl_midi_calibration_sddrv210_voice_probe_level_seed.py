from __future__ import annotations

from pathlib import Path

import pytest

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_volume as volume
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe as r1
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_wordbus as r2
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_redteam as r3
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_keyed as r4
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_level_seed import (
    CHANNEL_VOLUME_CONTROLLER,
    EXPRESSION_CONTROLLER,
    LEVEL_SEED_REVISION,
    LEVEL_SEED_VALUE,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_level_seed_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    SaturnSblMidiCalibrationSddrv210LevelSeedGuardedDeploymentError,
    _require_final_hash_lock,
)


ROOT = Path(__file__).resolve().parents[1]


def _families() -> SaturnGmCalibrationFamilyBanks:
    banks = []
    for family in range(16):
        banks.append(
            SaturnGmCalibrationFamilyBank(
                family=family,
                filename=f"GMC{family:02d}.BIN",
                programs=tuple(range(family * 8, family * 8 + 8)),
                payload=bytes(100 + family),
                sha256=f"{family:064x}",
                voices=(),
                velocity_amounts=(0,),
            )
        )
    return SaturnGmCalibrationFamilyBanks(
        source_path=Path("GeneralUser-GS.sf2"),
        source_sha256="0" * 64,
        banks=tuple(banks),
    )


def _r4_runtime() -> str:
    families = _families()
    return r4._runtime(
        r3._runtime(
            r2._runtime(
                r1._runtime(
                    volume._runtime(
                        sddrv210._runtime(legacy._runtime(families))
                    )
                )
            )
        )
    )


def _r5_runtime() -> str:
    return _runtime(_r4_runtime())


def test_level_seed_adds_cc7_cc11_full_before_bank_and_program():
    runtime = _r5_runtime()
    assert CHANNEL_VOLUME_CONTROLLER == 7
    assert EXPRESSION_CONTROLLER == 11
    assert LEVEL_SEED_VALUE == 127
    assert "#define SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER 7u" in runtime
    assert "#define SRK_SBL_CAL_EXPRESSION_CONTROLLER 11u" in runtime
    assert "#define SRK_SBL_CAL_LEVEL_SEED_VALUE 127u" in runtime
    assert "#define SRK_SBL_CAL_ERR_LEVEL_SEED 12u" in runtime

    start = runtime.index(
        "static int srk_cal_select_program(void *context,unsigned int program){"
    )
    end = runtime.index("static int srk_cal_set_pan(", start)
    select = runtime[start:end]
    move = select.index("SND_MoveData((Uint16 *)srk_cal_family")
    mix = select.index("SND_ChgMix(0,0)")
    master = select.index("SND_SetTlVl(")
    cc7 = select.index(
        "SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE"
    )
    cc11 = select.index(
        "SRK_SBL_CAL_EXPRESSION_CONTROLLER,SRK_SBL_CAL_LEVEL_SEED_VALUE"
    )
    cc32 = select.index("SRK_SBL_CAL_BANK_CONTROLLER,0u")
    program = select.index(
        "SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u"
    )
    assert move < mix < master < cc7 < cc11 < cc32 < program


def test_level_seed_is_reapplied_for_every_program_selection():
    runtime = _r5_runtime()
    start = runtime.index(
        "static int srk_cal_select_program(void *context,unsigned int program){"
    )
    end = runtime.index("static int srk_cal_set_pan(", start)
    select = runtime[start:end]
    family_end = select.index(" srk_cal_state->current_family=family;")
    cc7 = select.index("SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER")
    cc11 = select.index("SRK_SBL_CAL_EXPRESSION_CONTROLLER")
    assert family_end < cc7 < cc11


def test_level_seed_preserves_r4_keyed_telemetry_and_no_dummy_sequence():
    runtime = _r5_runtime()
    assert "latched_keyed_scsp_total_level" in runtime
    assert "latched_keyed_scsp_mixer" in runtime
    assert "SRK_SBL_CAL_SCSP_KYONB_MASK" in runtime
    assert "SND_StartSeq" not in runtime

    # R5 itself must not bypass SDDRV by writing SCSP registers.
    source = (
        ROOT
        / "src"
        / "rikai_kotoba"
        / "hardware"
        / "saturn"
        / "sbl_midi_calibration_sddrv210_voice_probe_level_seed.py"
    ).read_text(encoding="utf-8")
    assert "0x25B00000" not in source
    assert "volatile Uint16" not in source


def test_level_seed_manifest_records_causal_ab_probe():
    document = _telemetry_manifest(
        r4._telemetry_manifest(
            r3._telemetry_manifest(
                r2._telemetry_manifest(
                    r1._telemetry_manifest(
                        volume._telemetry_manifest(
                            sddrv210._telemetry_manifest(
                                {"policy": {}, "sbl_midi_calibration": {"telemetry": {}}}
                            )
                        )
                    )
                )
            )
        )
    )
    assert document["policy"]["sddrv210_direct_midi_level_seed"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["voice_probe_level_seed"] == LEVEL_SEED_REVISION
    assert telemetry["channel_volume_controller"] == 7
    assert telemetry["channel_volume_value"] == 127
    assert telemetry["expression_controller"] == 11
    assert telemetry["expression_value"] == 127
    assert telemetry["level_seed_before_bank_program"] is True
    assert telemetry["level_seed_every_program_selection"] is True
    assert telemetry["level_seed_preserves_keyed_probe"] is True
    assert telemetry["level_seed_scsp_direct_writes"] is False
    assert telemetry["level_seed_dummy_sequence"] is False
    assert telemetry["r4_physical_keyed_tl"] == "0x00FF"
    assert telemetry["r4_physical_keyed_mixer"] == "0xE000"
    assert telemetry["r4_authored_program16_tl"] == "0x19"


def test_current_candidate_routes_level_seed_over_preserved_r4():
    source_root = ROOT / "src" / "rikai_kotoba" / "hardware" / "saturn"
    contract = (
        source_root / "sbl_midi_calibration_candidate_contract.py"
    ).read_text(encoding="utf-8")
    level_seed = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_level_seed.py"
    ).read_text(encoding="utf-8")

    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_level_seed "
        "as _sddrv210_probe"
        in contract
    )
    assert (
        "return _sddrv210_probe.build_saturn_sbl_midi_calibration_candidate("
        in contract
    )
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_keyed as _r4"
        in level_seed
    )


def test_level_seed_guard_is_separate_and_fails_closed_before_r5_hash_lock():
    assert DESTINATION_NAME == "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-LEVEL-SEED-R5"
    assert CONFIRMATION_TOKEN == "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-LEVEL-SEED-R5"
    assert EXPECTED_MANIFEST_SHA256 is None
    assert EXPECTED_BUILD_REPORT_SHA256 is None
    assert EXPECTED_BIN_SHA256 is None
    assert EXPECTED_CUE_SHA256 is None

    with pytest.raises(
        SaturnSblMidiCalibrationSddrv210LevelSeedGuardedDeploymentError,
        match="intentionally blocked",
    ):
        _require_final_hash_lock()
