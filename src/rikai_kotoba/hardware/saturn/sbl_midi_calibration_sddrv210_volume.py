"""Current SDDRV Ver 2.10 diagnostic with explicit master-volume control.

This layer preserves the previously deployed telemetry-correct SDDRV210 candidate
as historical evidence and changes only the current non-historical build. Sega's
SDDRV Ver 2.10 HOST.ASM documents command 0x82 as SCSP Master Volume with
0 = off and 0x0F = maximum; the handler masks P1 with 0x0F before writing MVOL.

The current diagnostic therefore exposes that exact 0..15 value on the MIDI
screen and maps D-pad UP/DOWN to immediate SND_SetTlVl() changes.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210 as _sddrv210


SaturnSblMidiCalibrationCandidateError = _sddrv210.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _sddrv210.SaturnSblMidiCalibrationCandidateResult

MASTER_VOLUME_MIN = 0
MASTER_VOLUME_MAX = 15
MASTER_VOLUME_DEFAULT = 15


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_master_volume_control"] = True
    candidate["policy"] = policy
    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "master_volume_min": MASTER_VOLUME_MIN,
            "master_volume_max": MASTER_VOLUME_MAX,
            "master_volume_default": MASTER_VOLUME_DEFAULT,
            "master_volume_control": "DPAD_UP_DOWN",
            "master_volume_command": "SND_SetTlVl",
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _header(base: str) -> str:
    field_anchor = " unsigned long system_interface_work_pointer;\n"
    if base.count(field_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume header field anchor changed"
        )
    base = base.replace(
        field_anchor,
        field_anchor + " unsigned int master_volume;\n",
        1,
    )

    prototype_anchor = (
        "void srk_saturn_sbl_midi_calibration_runtime_poll("
        "SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);\n"
    )
    if base.count(prototype_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume header prototype anchor changed"
        )
    return base.replace(
        prototype_anchor,
        prototype_anchor
        + "int srk_saturn_sbl_midi_calibration_runtime_adjust_volume("
        + "SRK_SBL_MIDI_CAL_RUNTIME_STATE *state,int delta);\n",
        1,
    )


def _runtime(base: str) -> str:
    macro_anchor = (
        "#define SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED "
        "0x00000480UL\n"
    )
    if base.count(macro_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume macro anchor changed"
        )
    base = base.replace(
        macro_anchor,
        macro_anchor
        + f"#define SRK_SBL_CAL_MASTER_VOLUME_MIN {MASTER_VOLUME_MIN}u\n"
        + f"#define SRK_SBL_CAL_MASTER_VOLUME_MAX {MASTER_VOLUME_MAX}u\n"
        + f"#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT {MASTER_VOLUME_DEFAULT}u\n",
        1,
    )

    reset_anchor = (
        " s->system_information_pointer=0UL;s->host_interface_pointer=0UL;"
        "s->area_map_current_pointer=0UL;s->system_interface_work_pointer=0UL;\n"
    )
    if base.count(reset_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume reset anchor changed"
        )
    base = base.replace(
        reset_anchor,
        reset_anchor
        + " s->master_volume=SRK_SBL_CAL_MASTER_VOLUME_DEFAULT;\n",
        1,
    )

    fixed_volume = "result=SND_SetTlVl(15);"
    dynamic_volume = (
        "result=SND_SetTlVl((SndTlVl)srk_cal_state->master_volume);"
    )
    if base.count(fixed_volume) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 fixed master-volume anchor changed"
        )
    base = base.replace(fixed_volume, dynamic_volume, 1)

    poll_anchor = (
        "void srk_saturn_sbl_midi_calibration_runtime_poll("
        "SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){srk_cal_sample(state);}\n"
    )
    if base.count(poll_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume runtime-poll anchor changed"
        )
    adjust = f"""int srk_saturn_sbl_midi_calibration_runtime_adjust_volume(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state,int delta){{
 int next;SndRet result;if(!state||delta==0)return 0;
 next=(int)state->master_volume+delta;
 if(next<(int)SRK_SBL_CAL_MASTER_VOLUME_MIN)next=(int)SRK_SBL_CAL_MASTER_VOLUME_MIN;
 if(next>(int)SRK_SBL_CAL_MASTER_VOLUME_MAX)next=(int)SRK_SBL_CAL_MASTER_VOLUME_MAX;
 if((unsigned int)next==state->master_volume)return 1;
 state->master_volume=(unsigned int)next;
 if(!state->initialized)return 1;
 result=SND_SetTlVl((SndTlVl)state->master_volume);state->last_ret=(unsigned int)result;
 srk_cal_sample(state);
 if(result!=SND_RET_SET){{state->error=SRK_SBL_CAL_ERR_VOLUME;return 0;}}
 state->error=0u;return 1;
}}
"""
    return base.replace(poll_anchor, poll_anchor + adjust, 1)


def _main(base: str) -> str:
    render_tail = 'srk_cal_field(20,11,3,"0 /");srk_cal_num(n,(srk_u32)(srk_app.midi.program&7u));srk_cal_field(24,11,4,n);}\n'
    if base.count(render_tail) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume renderer anchor changed"
        )
    render_replacement = (
        'srk_cal_field(20,11,3,"0 /");'
        'srk_cal_num(n,(srk_u32)(srk_app.midi.program&7u));'
        'srk_cal_field(24,11,4,n);'
        'srk_cal_field(2,3,14,"Master volume:");'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.master_volume);'
        'srk_cal_field(17,3,2,n);'
        'srk_cal_field(20,3,4,"/ 15");'
        'srk_cal_field(2,24,22,"UP/DOWN Master volume");'
        '}\n'
    )
    base = base.replace(render_tail, render_replacement, 1)

    frame_anchor = (
        "static void srk_cal_frame(void){int active=srk_app.menu.active&&"
        "srk_app.menu.active_screen==SRK_DIAG_SCREEN_MIDI_TEST;"
        "if(active){srk_saturn_sbl_midi_calibration_runtime_poll("
        "&srk_midi_calibration_runtime);srk_cal_render();}"
        "else if(srk_midi_calibration_screen_was_active){"
        "srk_saturn_sbl_midi_calibration_runtime_stop("
        "&srk_midi_calibration_runtime);}"
        "srk_midi_calibration_screen_was_active=active;}\n"
    )
    if base.count(frame_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 volume frame anchor changed"
        )
    frame = (
        "static void srk_cal_frame(void){int active=srk_app.menu.active&&"
        "srk_app.menu.active_screen==SRK_DIAG_SCREEN_MIDI_TEST;"
        "if(active){"
        "if((srk_app.input.pressed&SRK_DIAG_BUTTON_UP)!=0u)"
        "(void)srk_saturn_sbl_midi_calibration_runtime_adjust_volume("
        "&srk_midi_calibration_runtime,1);"
        "if((srk_app.input.pressed&SRK_DIAG_BUTTON_DOWN)!=0u)"
        "(void)srk_saturn_sbl_midi_calibration_runtime_adjust_volume("
        "&srk_midi_calibration_runtime,-1);"
        "srk_saturn_sbl_midi_calibration_runtime_poll("
        "&srk_midi_calibration_runtime);srk_cal_render();}"
        "else if(srk_midi_calibration_screen_was_active){"
        "srk_saturn_sbl_midi_calibration_runtime_stop("
        "&srk_midi_calibration_runtime);}"
        "srk_midi_calibration_screen_was_active=active;}\n"
    )
    return base.replace(frame_anchor, frame, 1)


@contextmanager
def _contract():
    old_header = _sddrv210._header
    old_runtime = _sddrv210._runtime
    old_main = _sddrv210._main
    old_manifest = _sddrv210._telemetry_manifest

    def header(base: str) -> str:
        return _header(old_header(base))

    def runtime(base: str) -> str:
        return _runtime(old_runtime(base))

    def main(base: str) -> str:
        return _main(old_main(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _sddrv210._header = header
    _sddrv210._runtime = runtime
    _sddrv210._main = main
    _sddrv210._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _sddrv210._header = old_header
        _sddrv210._runtime = old_runtime
        _sddrv210._main = old_main
        _sddrv210._telemetry_manifest = old_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build current SDDRV210 candidate with live 0..15 master-volume control."""

    with _contract():
        return _sddrv210.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
