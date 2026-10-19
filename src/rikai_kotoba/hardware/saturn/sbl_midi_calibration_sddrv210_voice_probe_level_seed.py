"""SDDRV210 voice probe R5: seed Direct-MIDI channel level controllers.

R4 physical evidence proved that SDDRV210 reaches a real keyed SCSP voice with
non-zero sample address and direct-send routing, but programs the live SCSP TL
to 0xFF.  The exact authored GMCxx.BIN banks were then audited off-card and no
program is authored with TL=0xFF (Program 16 is TL=0x19).

R5 preserves the R4/R3/R2/R1 telemetry and the exact tone banks.  It changes
only the Direct-MIDI setup sequence by explicitly seeding MIDI Channel Volume
(CC7) and Expression (CC11) to 127 before bank/program selection.  This is a
causal A/B probe of SDDRV's per-note level path; it does not write SCSP
registers directly and it does not introduce a dummy sequence.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210_voice_probe_keyed as _r4


SaturnSblMidiCalibrationCandidateError = _r4.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _r4.SaturnSblMidiCalibrationCandidateResult

LEVEL_SEED_REVISION = "R5_CC7_CC11_FULL"
CHANNEL_VOLUME_CONTROLLER = 7
EXPRESSION_CONTROLLER = 11
LEVEL_SEED_VALUE = 127


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_direct_midi_level_seed"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "voice_probe_level_seed": LEVEL_SEED_REVISION,
            "channel_volume_controller": CHANNEL_VOLUME_CONTROLLER,
            "channel_volume_value": LEVEL_SEED_VALUE,
            "expression_controller": EXPRESSION_CONTROLLER,
            "expression_value": LEVEL_SEED_VALUE,
            "level_seed_before_bank_program": True,
            "level_seed_every_program_selection": True,
            "level_seed_preserves_keyed_probe": True,
            "level_seed_scsp_direct_writes": False,
            "level_seed_dummy_sequence": False,
            "r4_physical_keyed_tl": "0x00FF",
            "r4_physical_keyed_mixer": "0xE000",
            "r4_authored_program16_tl": "0x19",
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _runtime(base: str) -> str:
    controller_anchor = "#define SRK_SBL_CAL_BANK_CONTROLLER 32u\n"
    if base.count(controller_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R5 controller-constant anchor changed"
        )
    controller_constants = (
        "#define SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER 7u\n"
        "#define SRK_SBL_CAL_EXPRESSION_CONTROLLER 11u\n"
        "#define SRK_SBL_CAL_LEVEL_SEED_VALUE 127u\n"
    )
    base = base.replace(
        controller_anchor,
        controller_anchor + controller_constants,
        1,
    )

    error_anchor = "#define SRK_SBL_CAL_ERR_MIX 11u\n"
    if base.count(error_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R5 error-code anchor changed"
        )
    base = base.replace(
        error_anchor,
        error_anchor + "#define SRK_SBL_CAL_ERR_LEVEL_SEED 12u\n",
        1,
    )

    bank_send = (
        " result=srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,"
        "SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_BANK_CONTROLLER,0u);\n"
    )
    if base.count(bank_send) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R5 bank-select anchor changed"
        )
    level_seed = (
        " result=srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,"
        "SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_CHANNEL_VOLUME_CONTROLLER,"
        "SRK_SBL_CAL_LEVEL_SEED_VALUE);\n"
        " if(result!=SND_RET_SET){srk_cal_state->error="
        "SRK_SBL_CAL_ERR_LEVEL_SEED;return 0;}\n"
        " result=srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,"
        "SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_EXPRESSION_CONTROLLER,"
        "SRK_SBL_CAL_LEVEL_SEED_VALUE);\n"
        " if(result!=SND_RET_SET){srk_cal_state->error="
        "SRK_SBL_CAL_ERR_LEVEL_SEED;return 0;}\n"
    )
    base = base.replace(bank_send, level_seed + bank_send, 1)

    if "SND_StartSeq" in base:
        raise SaturnSblMidiCalibrationCandidateError(
            "R5 Direct-MIDI level seed unexpectedly introduced SND_StartSeq"
        )
    return base


@contextmanager
def _contract():
    old_runtime = _r4._runtime
    old_manifest = _r4._telemetry_manifest

    def runtime(base: str) -> str:
        return _runtime(old_runtime(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _r4._runtime = runtime
    _r4._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _r4._runtime = old_runtime
        _r4._telemetry_manifest = old_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build R5 with CC7/CC11 level seeding and preserved R4 telemetry."""

    with _contract():
        return _r4.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
