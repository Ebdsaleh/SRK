"""SDDRV210 voice probe R4: latch the SCSP state while KYONB is actually set.

Physical R3 evidence proved that Direct MIDI reaches a real SCSP key-on:
  * SDDRV slot-work changed;
  * an allocated management-2 record/layer was observed;
  * SCSP hardware changed;
  * K > 0 and KL YES proved KYONB occurred.

R3's KX/SA/TL/MX fields, however, captured the *first* SCSP change, which may
precede the final keyed register state.  R4 preserves R3 and adds a keyed-state
snapshot that is refreshed while KYONB remains asserted and then retained after
Note Off.  This lets physical evidence compare the MIDI voice's actual keyed
control/TL/mixer state against the already audible raw-SCSP reference without
writing any SCSP register from the diagnostic.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210_voice_probe_redteam as _r3


SaturnSblMidiCalibrationCandidateError = _r3.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _r3.SaturnSblMidiCalibrationCandidateResult

KEYED_SNAPSHOT_REVISION = "R4_KEYED"


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_voice_probe_keyed_snapshot"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "voice_probe_keyed_snapshot": KEYED_SNAPSHOT_REVISION,
            "keyed_snapshot_requires_kyonb": True,
            "keyed_snapshot_refreshes_while_held": True,
            "keyed_snapshot_persists_after_note_off": True,
            "keyed_snapshot_is_read_only": True,
            "raw_scsp_reference_stopped_control": "0x0020",
            "raw_scsp_reference_stopped_mixer": "0x0000",
            "raw_scsp_reference_audible_control": "0x0820",
            "raw_scsp_reference_audible_mixer_volume4_center": "0x8000",
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _header(base: str) -> str:
    anchor = " unsigned int probe_latch_active;\n"
    if base.count(anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 keyed-snapshot header anchor changed"
        )
    fields = """ unsigned int keyed_scsp_slot;
 unsigned int keyed_scsp_control;
 unsigned int keyed_scsp_sample_address_low;
 unsigned int keyed_scsp_total_level;
 unsigned int keyed_scsp_mixer;
 unsigned int latched_keyed_scsp_slot;
 unsigned int latched_keyed_scsp_control;
 unsigned int latched_keyed_scsp_sample_address_low;
 unsigned int latched_keyed_scsp_total_level;
 unsigned int latched_keyed_scsp_mixer;
 unsigned int keyed_mixer_nonzero_latched;
 unsigned int keyed_tl_not_ff_latched;
"""
    return base.replace(anchor, anchor + fields, 1)


def _runtime(base: str) -> str:
    current_reset_anchor = (
        " s->management_match_count=0u;s->slot_changed_count=0u;"
        "s->scsp_changed_count=0u;s->scsp_keyed_count=0u;\n"
    )
    if base.count(current_reset_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 current keyed-state reset anchor changed"
        )
    base = base.replace(
        current_reset_anchor,
        current_reset_anchor
        + " s->keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE;s->keyed_scsp_control=0u;"
        + "s->keyed_scsp_sample_address_low=0u;s->keyed_scsp_total_level=0u;"
        + "s->keyed_scsp_mixer=0u;\n",
        1,
    )

    capture_anchor = (
        " s->slot_changed_latched=0u;s->scsp_changed_latched=0u;"
        "s->scsp_key_latched=0u;\n"
    )
    if base.count(capture_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 Note-On capture reset anchor changed"
        )
    base = base.replace(
        capture_anchor,
        capture_anchor
        + " s->latched_keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE;"
        + "s->latched_keyed_scsp_control=0u;"
        + "s->latched_keyed_scsp_sample_address_low=0u;"
        + "s->latched_keyed_scsp_total_level=0u;"
        + "s->latched_keyed_scsp_mixer=0u;"
        + "s->keyed_mixer_nonzero_latched=0u;"
        + "s->keyed_tl_not_ff_latched=0u;\n",
        1,
    )

    old_key = (
        "  if((srk_cal_probe_reg16(r+0x00UL)&SRK_SBL_CAL_SCSP_KYONB_MASK)!=0u)"
        "{s->scsp_keyed_count++;if(srk_cal_probe_latch_active)"
        "s->scsp_key_latched=1u;}\n"
    )
    if base.count(old_key) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 KYONB sampling anchor changed"
        )
    new_key = """  if((srk_cal_probe_reg16(r+0x00UL)&SRK_SBL_CAL_SCSP_KYONB_MASK)!=0u){
   s->scsp_keyed_count++;
   if(s->keyed_scsp_slot==SRK_SBL_CAL_SLOT_NONE){
    s->keyed_scsp_slot=i;
    s->keyed_scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL);
    s->keyed_scsp_sample_address_low=(unsigned int)srk_cal_probe_reg16(r+0x02UL);
    s->keyed_scsp_total_level=(unsigned int)srk_cal_probe_reg16(r+0x0CUL);
    s->keyed_scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL);
   }
   if(srk_cal_probe_latch_active){
    s->scsp_key_latched=1u;
    s->latched_keyed_scsp_slot=i;
    s->latched_keyed_scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL);
    s->latched_keyed_scsp_sample_address_low=(unsigned int)srk_cal_probe_reg16(r+0x02UL);
    s->latched_keyed_scsp_total_level=(unsigned int)srk_cal_probe_reg16(r+0x0CUL);
    s->latched_keyed_scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL);
    if(s->latched_keyed_scsp_mixer!=0u)s->keyed_mixer_nonzero_latched=1u;
    if((s->latched_keyed_scsp_total_level&0x00FFu)!=0x00FFu ||
       (s->latched_keyed_scsp_total_level&0x0100u)!=0u)
     s->keyed_tl_not_ff_latched=1u;
   }
  }
"""
    base = base.replace(old_key, new_key, 1)

    reset_start = (
        "void srk_saturn_sbl_midi_calibration_runtime_reset("
        "SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){\n"
    )
    reset_end = "}\nstatic unsigned int srk_cal_begin(void *context){\n"
    rsi = base.find(reset_start)
    rei = base.find(reset_end, rsi)
    if rsi < 0 or rei < 0:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 runtime-reset function anchor changed"
        )
    reset_body = base[rsi:rei]
    if "s->keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE;" in reset_body:
        raise SaturnSblMidiCalibrationCandidateError(
            "R4 runtime-reset fields already injected"
        )
    reset = """ s->keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE;s->keyed_scsp_control=0u;s->keyed_scsp_sample_address_low=0u;s->keyed_scsp_total_level=0u;s->keyed_scsp_mixer=0u;
 s->latched_keyed_scsp_slot=SRK_SBL_CAL_SLOT_NONE;s->latched_keyed_scsp_control=0u;s->latched_keyed_scsp_sample_address_low=0u;s->latched_keyed_scsp_total_level=0u;s->latched_keyed_scsp_mixer=0u;
 s->keyed_mixer_nonzero_latched=0u;s->keyed_tl_not_ff_latched=0u;
"""
    return base[:rei] + reset + base[rei:]


def _main(base: str) -> str:
    replacements = {
        'srk_cal_field(18,22,3,"HW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_scsp_slot);':
        'srk_cal_field(18,22,3,"KS:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_keyed_scsp_slot);',
        "srk_midi_calibration_runtime.latched_scsp_control":
        "srk_midi_calibration_runtime.latched_keyed_scsp_control",
        "srk_midi_calibration_runtime.latched_scsp_sample_address_low":
        "srk_midi_calibration_runtime.latched_keyed_scsp_sample_address_low",
        "srk_midi_calibration_runtime.latched_scsp_total_level":
        "srk_midi_calibration_runtime.latched_keyed_scsp_total_level",
        "srk_midi_calibration_runtime.latched_scsp_mixer":
        "srk_midi_calibration_runtime.latched_keyed_scsp_mixer",
    }
    for old, new in replacements.items():
        if base.count(old) != 1:
            raise SaturnSblMidiCalibrationCandidateError(
                "R4 keyed HUD anchor changed: " + old[:40]
            )
        base = base.replace(old, new, 1)
    return base


@contextmanager
def _contract():
    old_header = _r3._header
    old_runtime = _r3._runtime
    old_main = _r3._main
    old_manifest = _r3._telemetry_manifest

    def header(base: str) -> str:
        return _header(old_header(base))

    def runtime(base: str) -> str:
        return _runtime(old_runtime(base))

    def main(base: str) -> str:
        return _main(old_main(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _r3._header = header
    _r3._runtime = runtime
    _r3._main = main
    _r3._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _r3._header = old_header
        _r3._runtime = old_runtime
        _r3._main = old_main
        _r3._telemetry_manifest = old_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build R4 keyed-state telemetry without changing SDDRV or SCSP state."""

    with _contract():
        return _r3.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
