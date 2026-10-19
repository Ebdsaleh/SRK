"""SDDRV210 voice probe R3: REDTEAM-hardened independent evidence.

R2 corrected SH-2 access to 68000 Sound RAM by using aligned 16-bit reads.
R3 keeps that correction and removes the remaining single-assumption failure
mode from R1: voice allocation is no longer inferred only from flag2 bit 0x08.

The R3 probe:
* validates the known BANK_init 0x007F channel-volume invariant;
* exposes the aligned word containing the odd-byte management status;
* uses stable double-sampled 32-bit reads for bank/layer pointers;
* scans every SDDRV slot record for management #2 independently of flags;
* snapshots all SDDRV slot-work words and all SCSP slot words before Note On;
* latches any slot-work or SCSP change seen until the next Note On;
* independently latches any observed SCSP KYONB state;
* preserves raw flag bytes instead of using them as a prerequisite for display.

It remains strictly observational: no Sound-RAM or SCSP writes are introduced.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210_voice_probe_wordbus as _r2


SaturnSblMidiCalibrationCandidateError = _r2.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _r2.SaturnSblMidiCalibrationCandidateResult

HARDENING_REVISION = "R3_REDTEAM"
SCSP_KYONB_MASK = 0x0800


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_voice_probe_redteam_hardened"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "voice_probe_hardening": HARDENING_REVISION,
            "allocation_flag_is_not_gate": True,
            "management_scan_independent": True,
            "slot_work_change_latched": True,
            "scsp_scan_independent": True,
            "scsp_change_latched": True,
            "scsp_kyonb_mask": f"0x{SCSP_KYONB_MASK:04X}",
            "scsp_kyonb_latched": True,
            "u32_double_sample_stability": True,
            "status_aligned_word_exposed": True,
            "note_interval_latching": True,
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _header(base: str) -> str:
    anchor = " unsigned int scsp_mixer;\n"
    if base.count(anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 voice-probe header anchor changed"
        )
    fields = """ unsigned int probe_bus_sane;
 unsigned int direct_midi_status_word;
 unsigned int bank_read_stable;
 unsigned int layer_read_stable;
 unsigned int management_match_count;
 unsigned int slot_changed_count;
 unsigned int slot_changed_latched;
 unsigned int scsp_changed_count;
 unsigned int scsp_changed_latched;
 unsigned int scsp_keyed_count;
 unsigned int scsp_key_latched;
 unsigned int latched_slot_work_index;
 unsigned int latched_scsp_slot;
 unsigned int latched_slot_flag1;
 unsigned int latched_slot_flag2;
 unsigned int latched_slot_midi;
 unsigned int latched_slot_note;
 unsigned int latched_slot_velocity;
 unsigned int latched_slot_management;
 unsigned long latched_slot_layer_address;
 unsigned int latched_scsp_control;
 unsigned int latched_scsp_sample_address_low;
 unsigned int latched_scsp_total_level;
 unsigned int latched_scsp_mixer;
 unsigned int probe_latch_active;
"""
    return base.replace(anchor, anchor + fields, 1)


def _runtime(base: str) -> str:
    helper_anchor = (
        "static Uint16 srk_cal_probe_reg16(Uint32 address)"
        "{return *(volatile Uint16 *)address;}\n"
    )
    if base.count(helper_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 voice-probe word-reader anchor changed"
        )

    helpers = helper_anchor + """static Uint32 srk_cal_probe_u32_stable(Uint32 address,unsigned int *ok){
 unsigned int i;Uint16 a,b,c,d;if(ok)*ok=0u;
 for(i=0u;i<4u;i++){a=srk_cal_probe_u16(address);b=srk_cal_probe_u16(address+2UL);c=srk_cal_probe_u16(address);d=srk_cal_probe_u16(address+2UL);if(a==c&&b==d){if(ok)*ok=1u;return ((Uint32)a<<16)|(Uint32)b;}}
 return ((Uint32)c<<16)|(Uint32)d;
}
#define SRK_SBL_CAL_SLOT_WORK_WORDS 32u
#define SRK_SBL_CAL_SCSP_SLOT_WORDS 16u
#define SRK_SBL_CAL_SCSP_KYONB_MASK 0x0800u
static Uint16 srk_cal_probe_slot_baseline[SRK_SBL_CAL_SLOT_COUNT][SRK_SBL_CAL_SLOT_WORK_WORDS];
static Uint16 srk_cal_probe_scsp_baseline[SRK_SBL_CAL_SLOT_COUNT][SRK_SBL_CAL_SCSP_SLOT_WORDS];
static unsigned int srk_cal_probe_latch_active;
static void srk_cal_probe_capture_baseline(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){
 unsigned int i,j;Uint32 w,r;if(!s)return;
 for(i=0u;i<SRK_SBL_CAL_SLOT_COUNT;i++){
  w=SRK_SBL_CAL_SLOT_WORK_ADDRESS+(Uint32)i*SRK_SBL_CAL_SLOT_WORK_STRIDE;
  r=SRK_SBL_CAL_SCSP_SLOT_ADDRESS+(Uint32)i*SRK_SBL_CAL_SCSP_SLOT_STRIDE;
  for(j=0u;j<SRK_SBL_CAL_SLOT_WORK_WORDS;j++)srk_cal_probe_slot_baseline[i][j]=srk_cal_probe_u16(w+(Uint32)j*2UL);
  for(j=0u;j<SRK_SBL_CAL_SCSP_SLOT_WORDS;j++)srk_cal_probe_scsp_baseline[i][j]=srk_cal_probe_reg16(r+(Uint32)j*2UL);
 }
 s->slot_changed_latched=0u;s->scsp_changed_latched=0u;s->scsp_key_latched=0u;
 s->latched_slot_work_index=SRK_SBL_CAL_SLOT_NONE;s->latched_scsp_slot=SRK_SBL_CAL_SLOT_NONE;
 s->latched_slot_flag1=0u;s->latched_slot_flag2=0u;s->latched_slot_midi=0u;s->latched_slot_note=0u;s->latched_slot_velocity=0u;s->latched_slot_management=0u;s->latched_slot_layer_address=0UL;
 s->latched_scsp_control=0u;s->latched_scsp_sample_address_low=0u;s->latched_scsp_total_level=0u;s->latched_scsp_mixer=0u;
 srk_cal_probe_latch_active=1u;s->probe_latch_active=1u;
}
static void srk_cal_probe_latch_stop(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){srk_cal_probe_latch_active=0u;if(s)s->probe_latch_active=0u;}
"""
    base = base.replace(helper_anchor, helpers, 1)

    start = "static void srk_cal_probe_voice(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){\n"
    end = "}\nstatic void srk_cal_sample(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){\n"
    si = base.find(start)
    ei = base.find(end, si)
    if si < 0 or ei < 0:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 voice-probe sampling body anchor changed"
        )
    ei += 2

    hardened = """static void srk_cal_probe_voice(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){
 unsigned int i,j,changed,stable;Uint32 w,r,layer;if(!s)return;
 s->direct_midi_status_word=(unsigned int)srk_cal_probe_word16(SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS);
 s->direct_midi_status=(unsigned int)srk_cal_probe_u8(SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS);
 s->driver_program=(unsigned int)srk_cal_probe_u8(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x00UL);
 s->driver_bank_address=(unsigned long)srk_cal_probe_u32_stable(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x04UL,&stable);
 s->bank_read_stable=stable;
 s->midi_master_volume=(unsigned int)srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x10UL);
 s->midi_volume=(unsigned int)srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x12UL);
 s->midi_expression=(unsigned int)srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x14UL);
 s->noteon_master_volume=(unsigned int)srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x18UL);
 s->total_volume=(unsigned int)srk_cal_probe_u16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x1AUL);
 s->probe_bus_sane=(s->midi_master_volume==0x007Fu&&s->midi_volume==0x007Fu&&s->midi_expression==0x007Fu)?1u:0u;
 s->management_match_count=0u;s->slot_changed_count=0u;s->scsp_changed_count=0u;s->scsp_keyed_count=0u;
 s->active_slot_count=0u;s->active_slot_work_index=SRK_SBL_CAL_SLOT_NONE;s->active_scsp_slot=SRK_SBL_CAL_SLOT_NONE;
 s->slot_flag1=0u;s->slot_flag2=0u;s->slot_midi=0u;s->slot_note=0u;s->slot_velocity=0u;s->slot_direct_pan=0u;s->slot_management=0u;s->slot_layer_address=0UL;s->layer_read_stable=1u;
 s->scsp_control=0u;s->scsp_sample_address_low=0u;s->scsp_loop_start=0u;s->scsp_loop_end=0u;s->scsp_total_level=0u;s->scsp_mixer=0u;
 for(i=0u;i<SRK_SBL_CAL_SLOT_COUNT;i++){
  w=SRK_SBL_CAL_SLOT_WORK_ADDRESS+(Uint32)i*SRK_SBL_CAL_SLOT_WORK_STRIDE;
  r=SRK_SBL_CAL_SCSP_SLOT_ADDRESS+(Uint32)i*SRK_SBL_CAL_SCSP_SLOT_STRIDE;
  changed=0u;
  if(srk_cal_probe_u16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET){
   s->management_match_count++;s->active_slot_count++;
   if(s->active_slot_work_index==SRK_SBL_CAL_SLOT_NONE){
    s->active_slot_work_index=i;s->slot_flag1=(unsigned int)srk_cal_probe_u8(w+0x00UL);s->slot_flag2=(unsigned int)srk_cal_probe_u8(w+0x05UL);
    s->slot_midi=(unsigned int)srk_cal_probe_u8(w+0x01UL);s->slot_note=(unsigned int)srk_cal_probe_u8(w+0x02UL);s->slot_velocity=(unsigned int)srk_cal_probe_u8(w+0x03UL);s->slot_direct_pan=(unsigned int)srk_cal_probe_u8(w+0x04UL);s->slot_management=(unsigned int)srk_cal_probe_u16(w+0x06UL);
    layer=srk_cal_probe_u32_stable(w+0x08UL,&stable);s->slot_layer_address=(unsigned long)layer;s->layer_read_stable=stable;
   }
  }
  if(srk_cal_probe_latch_active){
   for(j=0u;j<SRK_SBL_CAL_SLOT_WORK_WORDS;j++)if(srk_cal_probe_u16(w+(Uint32)j*2UL)!=srk_cal_probe_slot_baseline[i][j]){changed=1u;break;}
   if(changed){
    s->slot_changed_count++;
    if(!s->slot_changed_latched){
     s->slot_changed_latched=1u;s->latched_slot_work_index=i;
     s->latched_slot_flag1=(unsigned int)srk_cal_probe_u8(w+0x00UL);s->latched_slot_flag2=(unsigned int)srk_cal_probe_u8(w+0x05UL);
     s->latched_slot_midi=(unsigned int)srk_cal_probe_u8(w+0x01UL);s->latched_slot_note=(unsigned int)srk_cal_probe_u8(w+0x02UL);s->latched_slot_velocity=(unsigned int)srk_cal_probe_u8(w+0x03UL);s->latched_slot_management=(unsigned int)srk_cal_probe_u16(w+0x06UL);
     s->latched_slot_layer_address=(unsigned long)srk_cal_probe_u32_stable(w+0x08UL,&stable);
    }
   }
  }
  changed=0u;
  if((srk_cal_probe_reg16(r+0x00UL)&SRK_SBL_CAL_SCSP_KYONB_MASK)!=0u){s->scsp_keyed_count++;if(srk_cal_probe_latch_active)s->scsp_key_latched=1u;}
  if(srk_cal_probe_latch_active){
   for(j=0u;j<SRK_SBL_CAL_SCSP_SLOT_WORDS;j++)if(srk_cal_probe_reg16(r+(Uint32)j*2UL)!=srk_cal_probe_scsp_baseline[i][j]){changed=1u;break;}
   if(changed){
    s->scsp_changed_count++;
    if(!s->scsp_changed_latched){
     s->scsp_changed_latched=1u;s->latched_scsp_slot=i;
     s->latched_scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL);s->latched_scsp_sample_address_low=(unsigned int)srk_cal_probe_reg16(r+0x02UL);
     s->latched_scsp_total_level=(unsigned int)srk_cal_probe_reg16(r+0x0CUL);s->latched_scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL);
    }
   }
  }
 }
 if(s->latched_scsp_slot!=SRK_SBL_CAL_SLOT_NONE){
  r=SRK_SBL_CAL_SCSP_SLOT_ADDRESS+(Uint32)s->latched_scsp_slot*SRK_SBL_CAL_SCSP_SLOT_STRIDE;s->active_scsp_slot=s->latched_scsp_slot;
  s->scsp_control=s->latched_scsp_control;s->scsp_sample_address_low=s->latched_scsp_sample_address_low;s->scsp_total_level=s->latched_scsp_total_level;s->scsp_mixer=s->latched_scsp_mixer;
  s->scsp_loop_start=(unsigned int)srk_cal_probe_reg16(r+0x04UL);s->scsp_loop_end=(unsigned int)srk_cal_probe_reg16(r+0x06UL);
 }
}
"""
    base = base[:si] + hardened + base[ei:]

    note_on_anchor = (
        " result=srk_cal_send(SRK_SBL_CAL_NOTE_ON,(Uint8)channel,(Uint8)note,(Uint8)velocity);\n"
    )
    if base.count(note_on_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 Note-On latch anchor changed"
        )
    base = base.replace(
        note_on_anchor,
        " srk_cal_probe_capture_baseline(srk_cal_state);\n" + note_on_anchor,
        1,
    )

    note_on_fail = (
        " if(result!=SND_RET_SET){srk_cal_state->error=SRK_SBL_CAL_ERR_NOTE_ON;return 0;}return 1;\n"
    )
    if base.count(note_on_fail) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 Note-On result anchor changed"
        )
    base = base.replace(
        note_on_fail,
        " if(result!=SND_RET_SET){srk_cal_probe_latch_stop(srk_cal_state);srk_cal_state->error=SRK_SBL_CAL_ERR_NOTE_ON;return 0;}return 1;\n",
        1,
    )

    note_off_anchor = (
        " result=srk_cal_send(SRK_SBL_CAL_NOTE_OFF,(Uint8)channel,(Uint8)note,(Uint8)velocity);\n"
    )
    if base.count(note_off_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 Note-Off latch anchor changed"
        )
    base = base.replace(
        note_off_anchor,
        note_off_anchor + " srk_cal_probe_latch_stop(srk_cal_state);\n",
        1,
    )

    reset_anchor = (
        " s->scsp_control=0u;s->scsp_sample_address_low=0u;s->scsp_loop_start=0u;s->scsp_loop_end=0u;s->scsp_total_level=0u;s->scsp_mixer=0u;\n"
    )
    if base.count(reset_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 reset anchor changed"
        )
    reset = """ s->probe_bus_sane=0u;s->direct_midi_status_word=0u;s->bank_read_stable=0u;s->layer_read_stable=0u;
 s->management_match_count=0u;s->slot_changed_count=0u;s->slot_changed_latched=0u;s->scsp_changed_count=0u;s->scsp_changed_latched=0u;s->scsp_keyed_count=0u;s->scsp_key_latched=0u;
 s->latched_slot_work_index=SRK_SBL_CAL_SLOT_NONE;s->latched_scsp_slot=SRK_SBL_CAL_SLOT_NONE;s->latched_slot_flag1=0u;s->latched_slot_flag2=0u;s->latched_slot_midi=0u;s->latched_slot_note=0u;s->latched_slot_velocity=0u;s->latched_slot_management=0u;s->latched_slot_layer_address=0UL;
 s->latched_scsp_control=0u;s->latched_scsp_sample_address_low=0u;s->latched_scsp_total_level=0u;s->latched_scsp_mixer=0u;s->probe_latch_active=0u;srk_cal_probe_latch_active=0u;
"""
    return base.replace(reset_anchor, reset_anchor + reset, 1)


def _main(base: str) -> str:
    start = 'srk_cal_field(2,20,5,"M2 S:");'
    end = 'srk_cal_field(29,24,4,h4);'
    si = base.find(start)
    ei = base.find(end, si)
    if si < 0 or ei < 0:
        raise SaturnSblMidiCalibrationCandidateError(
            "R3 HUD anchor changed"
        )
    ei += len(end)

    hud = (
        'srk_cal_field(2,20,4,"BUS:");srk_cal_field(6,20,3,srk_midi_calibration_runtime.probe_bus_sane?"OK":"BAD");'
        'srk_cal_field(10,20,3,"M2:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.direct_midi_status_word);srk_cal_field(13,20,6,h16);'
        'srk_cal_field(20,20,2,"P:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.driver_program);srk_cal_field(22,20,3,n);'
        'srk_cal_field(26,20,3,"B:");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.driver_bank_address);srk_cal_field(29,20,10,h32);'
        'srk_cal_field(2,21,2,"V:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_master_volume);srk_cal_field(4,21,3,n);'
        'srk_cal_field(8,21,1,"/");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_volume);srk_cal_field(9,21,3,n);'
        'srk_cal_field(13,21,1,"/");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_expression);srk_cal_field(14,21,3,n);'
        'srk_cal_field(18,21,3,"MG:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.management_match_count);srk_cal_field(21,21,2,n);'
        'srk_cal_field(24,21,3,"SW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.slot_changed_count);srk_cal_field(27,21,2,n);'
        'srk_cal_field(30,21,3,"HW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.scsp_changed_count);srk_cal_field(33,21,2,n);'
        'srk_cal_field(36,21,2,"K:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.scsp_keyed_count);srk_cal_field(38,21,2,n);'
        'srk_cal_field(2,22,3,"LAT");srk_cal_field(6,22,2,srk_midi_calibration_runtime.probe_latch_active?"ON":"--");'
        'srk_cal_field(9,22,3,"SW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_slot_work_index);srk_cal_field(12,22,5,n);'
        'srk_cal_field(18,22,3,"HW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_scsp_slot);srk_cal_field(21,22,5,n);'
        'srk_cal_field(27,22,3,"F1:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_slot_flag1);srk_cal_field(30,22,4,h16);'
        'srk_cal_field(35,22,3,"F2:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_slot_flag2);srk_cal_field(38,22,2,h16+4);'
        'srk_cal_field(2,23,2,"M:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_slot_management);srk_cal_field(4,23,6,h16);'
        'srk_cal_field(11,23,3,"Ch:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_slot_midi);srk_cal_field(14,23,2,n);'
        'srk_cal_field(17,23,2,"N:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_slot_note);srk_cal_field(19,23,3,n);'
        'srk_cal_field(23,23,2,"V:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.latched_slot_velocity);srk_cal_field(25,23,3,n);'
        'srk_cal_field(29,23,3,"LY:");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.latched_slot_layer_address);srk_cal_field(32,23,8,h32+2);'
        'srk_cal_field(2,24,3,"KX:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_scsp_control);srk_cal_field(5,24,4,h16+2);'
        'srk_cal_field(10,24,3,"SA:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_scsp_sample_address_low);srk_cal_field(13,24,4,h16+2);'
        'srk_cal_field(18,24,3,"TL:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_scsp_total_level);srk_cal_field(21,24,4,h16+2);'
        'srk_cal_field(26,24,3,"MX:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.latched_scsp_mixer);srk_cal_field(29,24,4,h16+2);'
        'srk_cal_field(34,24,2,"KL");srk_cal_field(36,24,3,srk_midi_calibration_runtime.scsp_key_latched?"YES":"NO");'
    )
    return base[:si] + hud + base[ei:]


@contextmanager
def _contract():
    old_header = _r2._probe._header
    old_main = _r2._probe._main
    old_r2_runtime = _r2._runtime
    old_r2_manifest = _r2._telemetry_manifest

    def header(base: str) -> str:
        return _header(old_header(base))

    def main(base: str) -> str:
        return _main(old_main(base))

    def runtime(base: str) -> str:
        return _runtime(old_r2_runtime(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_r2_manifest(document))

    _r2._probe._header = header
    _r2._probe._main = main
    _r2._runtime = runtime
    _r2._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _r2._probe._header = old_header
        _r2._probe._main = old_main
        _r2._runtime = old_r2_runtime
        _r2._telemetry_manifest = old_r2_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build the REDTEAM-hardened R3 read-only voice probe."""

    with _contract():
        return _r2.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
