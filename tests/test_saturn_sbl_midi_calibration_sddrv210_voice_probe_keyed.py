from pathlib import Path

from rikai_kotoba.hardware.saturn import sbl_midi_calibration_consolidated as legacy
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210 as sddrv210
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_volume as volume
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe as r1
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_wordbus as r2
from rikai_kotoba.hardware.saturn import sbl_midi_calibration_sddrv210_voice_probe_redteam as r3
from rikai_kotoba.hardware.saturn.sbl_gm_calibration_family_banks import (
    SaturnGmCalibrationFamilyBank,
    SaturnGmCalibrationFamilyBanks,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_keyed import (
    KEYED_SNAPSHOT_REVISION,
    _header,
    _main,
    _runtime,
    _telemetry_manifest,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_keyed_pre_media import (
    FINAL_BUILD_REPORT_SHA256,
    FINAL_DEPLOYABLE_BIN_SHA256,
    FINAL_DEPLOYABLE_CUE_SHA256,
    FINAL_MANIFEST_SHA256,
)
from rikai_kotoba.hardware.saturn.sbl_midi_calibration_sddrv210_voice_probe_keyed_guarded_deployment import (
    CONFIRMATION_TOKEN,
    DESTINATION_NAME,
    EXPECTED_BIN_SHA256,
    EXPECTED_BUILD_REPORT_SHA256,
    EXPECTED_CUE_SHA256,
    EXPECTED_MANIFEST_SHA256,
    _require_final_hash_lock,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "integrations" / "saturn" / "standalone" / "srk_saturn_main.c"
PRE_MEDIA = (
    ROOT
    / "src"
    / "rikai_kotoba"
    / "hardware"
    / "saturn"
    / "sbl_midi_calibration_sddrv210_voice_probe_keyed_pre_media.py"
)


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


def _generated():
    families = _families()
    base_header = r3._header(
        r1._header(
            volume._header(
                sddrv210._header(legacy._header(26610, 10, families.max_bank_bytes))
            )
        )
    )
    base_runtime = r3._runtime(
        r2._runtime(
            r1._runtime(
                volume._runtime(
                    sddrv210._runtime(legacy._runtime(families))
                )
            )
        )
    )
    base_main = r3._main(
        r1._main(
            volume._main(
                sddrv210._main(
                    legacy._main(MAIN.read_text(encoding="utf-8"))
                )
            )
        )
    )
    return _header(base_header), _runtime(base_runtime), _main(base_main)


def test_keyed_probe_samples_registers_only_inside_kyonb_branch():
    header, runtime, _ = _generated()

    for field in (
        "keyed_scsp_slot",
        "keyed_scsp_control",
        "keyed_scsp_sample_address_low",
        "keyed_scsp_total_level",
        "keyed_scsp_mixer",
        "latched_keyed_scsp_slot",
        "latched_keyed_scsp_control",
        "latched_keyed_scsp_total_level",
        "latched_keyed_scsp_mixer",
    ):
        assert field in header

    keyed = runtime.index(
        "if((srk_cal_probe_reg16(r+0x00UL)&SRK_SBL_CAL_SCSP_KYONB_MASK)!=0u)"
    )
    latched_control = runtime.index(
        "s->latched_keyed_scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL)",
        keyed,
    )
    latched_mixer = runtime.index(
        "s->latched_keyed_scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL)",
        keyed,
    )
    assert keyed < latched_control < latched_mixer


def test_keyed_probe_refreshes_snapshot_while_note_is_held():
    _, runtime, _ = _generated()

    # The latched keyed snapshot is deliberately assigned on every observed
    # KYONB frame rather than protected by a one-shot "if not latched" gate.
    assert "if(!s->scsp_key_latched)" not in runtime
    assert "s->scsp_key_latched=1u;" in runtime
    assert "s->latched_keyed_scsp_slot=i;" in runtime
    assert "s->keyed_mixer_nonzero_latched=1u" in runtime
    assert "s->keyed_tl_not_ff_latched=1u" in runtime


def test_keyed_probe_hud_reports_keyed_snapshot_not_first_change_snapshot():
    _, _, main = _generated()

    assert '"KS:"' in main
    assert "latched_keyed_scsp_slot" in main
    assert "latched_keyed_scsp_control" in main
    assert "latched_keyed_scsp_sample_address_low" in main
    assert "latched_keyed_scsp_total_level" in main
    assert "latched_keyed_scsp_mixer" in main

    # R3 historical first-change storage still exists in the runtime contract,
    # but the physical comparison row no longer displays it as keyed state.
    assert "srk_midi_calibration_runtime.latched_scsp_control" not in main
    assert "srk_midi_calibration_runtime.latched_scsp_mixer" not in main


def test_keyed_manifest_records_physical_raw_scsp_reference_without_writing_it():
    document = _telemetry_manifest(
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

    assert document["policy"]["sddrv210_voice_probe_keyed_snapshot"] is True
    telemetry = document["sbl_midi_calibration"]["telemetry"]
    assert telemetry["voice_probe_keyed_snapshot"] == KEYED_SNAPSHOT_REVISION
    assert telemetry["keyed_snapshot_requires_kyonb"] is True
    assert telemetry["keyed_snapshot_refreshes_while_held"] is True
    assert telemetry["keyed_snapshot_persists_after_note_off"] is True
    assert telemetry["keyed_snapshot_is_read_only"] is True
    assert telemetry["raw_scsp_reference_stopped_control"] == "0x0020"
    assert telemetry["raw_scsp_reference_stopped_mixer"] == "0x0000"
    assert telemetry["raw_scsp_reference_audible_control"] == "0x0820"
    assert telemetry["raw_scsp_reference_audible_mixer_volume4_center"] == "0x8000"


def test_keyed_probe_remains_preserved_behind_current_level_seed_probe():
    source_root = ROOT / "src" / "rikai_kotoba" / "hardware" / "saturn"
    contract = (
        source_root / "sbl_midi_calibration_candidate_contract.py"
    ).read_text(encoding="utf-8")
    level_seed = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_level_seed.py"
    ).read_text(encoding="utf-8")
    keyed = (
        source_root / "sbl_midi_calibration_sddrv210_voice_probe_keyed.py"
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
    assert (
        "from . import sbl_midi_calibration_sddrv210_voice_probe_redteam as _r3"
        in keyed
    )


def test_keyed_guard_is_separate_and_locks_exact_r4_build():
    assert DESTINATION_NAME == (
        "SRK-Diagnostics-SBL-MIDI-CAL-SDDRV210-VOICE-PROBE-KEYED"
    )
    assert CONFIRMATION_TOKEN == (
        "DEPLOY-SBL-MIDI-CALIBRATION-SDDRV210-VOICE-PROBE-KEYED"
    )
    assert FINAL_MANIFEST_SHA256 == (
        "0c0c6d2d83e2b12b7e841f06641c1fe8798168ef056f46bf527df6683a75a71d"
    )
    assert FINAL_BUILD_REPORT_SHA256 == (
        "ec98c3cd50641682fd37408ba74608cbf6749a81f918d93f7853b834a9a9c232"
    )
    assert FINAL_DEPLOYABLE_BIN_SHA256 == (
        "7101e91c555e8bab28f6fd6b3b7cf73906738cf503919c8647e8986c3d5cd7b7"
    )
    assert FINAL_DEPLOYABLE_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )
    assert EXPECTED_MANIFEST_SHA256 == FINAL_MANIFEST_SHA256
    assert EXPECTED_BUILD_REPORT_SHA256 == FINAL_BUILD_REPORT_SHA256
    assert EXPECTED_BIN_SHA256 == FINAL_DEPLOYABLE_BIN_SHA256
    assert EXPECTED_CUE_SHA256 == FINAL_DEPLOYABLE_CUE_SHA256
    assert _require_final_hash_lock() == (
        FINAL_MANIFEST_SHA256,
        FINAL_BUILD_REPORT_SHA256,
        FINAL_DEPLOYABLE_BIN_SHA256,
        FINAL_DEPLOYABLE_CUE_SHA256,
    )


def test_keyed_pre_media_checks_struct_fields_in_generated_header():
    source = PRE_MEDIA.read_text(encoding="utf-8")
    assert '_RUNTIME_HEADER = "src/srk_saturn_sbl_midi_calibration_runtime.h"' in source

    header_start = source.index("runtime_header = ")
    runtime_start = source.index("runtime = ", header_start)
    header_audit = source[header_start:runtime_start]
    runtime_audit = source[runtime_start:]

    assert '"unsigned int keyed_scsp_slot;"' in header_audit
    assert '"unsigned int latched_keyed_scsp_slot;"' in header_audit
    assert '"unsigned int keyed_scsp_slot"' not in runtime_audit
    assert '"unsigned int latched_keyed_scsp_slot"' not in runtime_audit
    assert '"s->keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE"' in runtime_audit
    assert '"s->latched_keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE"' in runtime_audit
