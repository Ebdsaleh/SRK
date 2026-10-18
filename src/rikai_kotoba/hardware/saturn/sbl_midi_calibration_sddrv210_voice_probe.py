"""SDDRV Ver 2.10 Direct-MIDI voice-allocation probe.

Physical Saturn validation proved that SDDRV 2.10 consumes SRK's host commands
with a valid interface table, advancing command history and no global driver/68K
error.  This layer therefore observes the next boundary instead of changing the
audio path: management #2/channel 0 work, the management #2 host-status byte,
SDDRV slot_work allocation, and the corresponding raw SCSP slot registers.

Addresses are derived directly from the supplied SDDRV 2.10 SCSP.LIB:
  bs_HIFWK=0x0700, OF_HI_STAT3=0x84
  bs_PWKTP=0x7000, management #2=0x0400
  slot_work=0x1000 relative to bs_PWKTP
  slot_wk_unit=0x40, SCSP_slot_unit=0x20
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210_volume as _volume


SaturnSblMidiCalibrationCandidateError = _volume.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _volume.SaturnSblMidiCalibrationCandidateResult

PROBE_MASTER_VOLUME_DEFAULT = 5
DIRECT_MIDI_STATUS_ADDRESS = 0x25A00785
MANAGEMENT2_CHANNEL0_ADDRESS = 0x25A07400
SLOT_WORK_ADDRESS = 0x25A08000
SLOT_WORK_STRIDE = 0x40
SLOT_COUNT = 32
SCSP_SLOT_ADDRESS = 0x25B00000
SCSP_SLOT_STRIDE = 0x20
MANAGEMENT2_OFFSET = 0x0400


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_voice_allocation_probe"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "master_volume_default": PROBE_MASTER_VOLUME_DEFAULT,
            "direct_midi_management": 2,
            "direct_midi_channel": 0,
            "direct_midi_status_address": f"0x{DIRECT_MIDI_STATUS_ADDRESS:08X}",
            "management2_channel0_address": f"0x{MANAGEMENT2_CHANNEL0_ADDRESS:08X}",
            "slot_work_address": f"0x{SLOT_WORK_ADDRESS:08X}",
            "slot_work_stride_bytes": SLOT_WORK_STRIDE,
            "slot_count": SLOT_COUNT,
            "scsp_slot_address": f"0x{SCSP_SLOT_ADDRESS:08X}",
            "scsp_slot_stride_bytes": SCSP_SLOT_STRIDE,
            "management2_offset": f"0x{MANAGEMENT2_OFFSET:04X}",
            "slot_note_on_flag_mask": "0x08",
            "slot_key_on_flag_mask": "0x02",
            "voice_probe_is_read_only": True,
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _header(base: str) -> str:
    anchor = " unsigned int master_volume;\n"
    if base.count(anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe header anchor changed"
        )
    fields = """ unsigned int direct_midi_status;
 unsigned int driver_program;
 unsigned long driver_bank_address;
 unsigned int midi_master_volume;
 unsigned int midi_volume;
 unsigned int midi_expression;
 unsigned int noteon_master_volume;
 unsigned int total_volume;
 unsigned int active_slot_count;
 unsigned int active_slot_work_index;
 unsigned int active_scsp_slot;
 unsigned int slot_flag1;
 unsigned int slot_flag2;
 unsigned int slot_midi;
 unsigned int slot_note;
 unsigned int slot_velocity;
 unsigned int slot_direct_pan;
 unsigned int slot_management;
 unsigned long slot_layer_address;
 unsigned int scsp_control;
 unsigned int scsp_sample_address_low;
 unsigned int scsp_loop_start;
 unsigned int scsp_loop_end;
 unsigned int scsp_total_level;
 unsigned int scsp_mixer;
"""
    return base.replace(anchor, anchor + fields, 1)


def _runtime(base: str) -> str:
    default_anchor = "#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT 15u\n"
    if base.count(default_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe master-volume anchor changed"
        )
    base = base.replace(
        default_anchor,
        f"#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT {PROBE_MASTER_VOLUME_DEFAULT}u\n",
        1,
    )

    macro_anchor = (
        f"#define SRK_SBL_CAL_MASTER_VOLUME_DEFAULT "
        f"{PROBE_MASTER_VOLUME_DEFAULT}u\n"
    )
    macros = f"""#define SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS 0x{DIRECT_MIDI_STATUS_ADDRESS:08X}UL
#define SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS 0x{MANAGEMENT2_CHANNEL0_ADDRESS:08X}UL
#define SRK_SBL_CAL_SLOT_WORK_ADDRESS 0x{SLOT_WORK_ADDRESS:08X}UL
#define SRK_SBL_CAL_SLOT_WORK_STRIDE 0x{SLOT_WORK_STRIDE:02X}UL
#define SRK_SBL_CAL_SLOT_COUNT {SLOT_COUNT}u
#define SRK_SBL_CAL_SCSP_SLOT_ADDRESS 0x{SCSP_SLOT_ADDRESS:08X}UL
#define SRK_SBL_CAL_SCSP_SLOT_STRIDE 0x{SCSP_SLOT_STRIDE:02X}UL
#define SRK_SBL_CAL_MANAGEMENT2_OFFSET 0x{MANAGEMENT2_OFFSET:04X}u
#define SRK_SBL_CAL_SLOT_NOTE_ON_MASK 0x08u
#define SRK_SBL_CAL_SLOT_KEY_ON_MASK 0x02u
#define SRK_SBL_CAL_SLOT_NONE 0xFFFFu
"""
    base = base.replace(macro_anchor, macro_anchor + macros, 1)

    sample_anchor = (
        "static void srk_cal_sample(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){\n"
    )
    if base.count(sample_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe sampling function anchor changed"
        )

    helpers = """static Uint8 srk_cal_probe_u8(Uint32 address){return *(volatile Uint8 *)address;}
static Uint16 srk_cal_probe_be16(Uint32 address){volatile Uint8 *p=(volatile Uint8 *)address;return (Uint16)(((Uint16)p[0]<<8)|(Uint16)p[1]);}
static Uint32 srk_cal_probe_be32(Uint32 address){volatile Uint8 *p=(volatile Uint8 *)address;return ((Uint32)p[0]<<24)|((Uint32)p[1]<<16)|((Uint32)p[2]<<8)|(Uint32)p[3];}
static Uint16 srk_cal_probe_reg16(Uint32 address){return *(volatile Uint16 *)address;}
static void srk_cal_probe_voice(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){
 unsigned int i;Uint32 w;Uint8 f2;if(!s)return;
 s->direct_midi_status=(unsigned int)srk_cal_probe_u8(SRK_SBL_CAL_DIRECT_MIDI_STATUS_ADDRESS);
 s->driver_program=(unsigned int)srk_cal_probe_u8(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x00UL);
 s->driver_bank_address=(unsigned long)srk_cal_probe_be32(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x04UL);
 s->midi_master_volume=(unsigned int)srk_cal_probe_be16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x10UL);
 s->midi_volume=(unsigned int)srk_cal_probe_be16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x12UL);
 s->midi_expression=(unsigned int)srk_cal_probe_be16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x14UL);
 s->noteon_master_volume=(unsigned int)srk_cal_probe_be16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x18UL);
 s->total_volume=(unsigned int)srk_cal_probe_be16(SRK_SBL_CAL_MANAGEMENT_WORK_ADDRESS+0x1AUL);
 s->active_slot_count=0u;s->active_slot_work_index=SRK_SBL_CAL_SLOT_NONE;s->active_scsp_slot=SRK_SBL_CAL_SLOT_NONE;
 s->slot_flag1=0u;s->slot_flag2=0u;s->slot_midi=0u;s->slot_note=0u;s->slot_velocity=0u;s->slot_direct_pan=0u;s->slot_management=0u;s->slot_layer_address=0UL;
 s->scsp_control=0u;s->scsp_sample_address_low=0u;s->scsp_loop_start=0u;s->scsp_loop_end=0u;s->scsp_total_level=0u;s->scsp_mixer=0u;
 for(i=0u;i<SRK_SBL_CAL_SLOT_COUNT;i++){
  w=SRK_SBL_CAL_SLOT_WORK_ADDRESS+(Uint32)i*SRK_SBL_CAL_SLOT_WORK_STRIDE;
  f2=srk_cal_probe_u8(w+0x05UL);
  if((f2&SRK_SBL_CAL_SLOT_NOTE_ON_MASK)!=0u){
   s->active_slot_count++;
   if(s->active_slot_work_index==SRK_SBL_CAL_SLOT_NONE&&srk_cal_probe_be16(w+0x06UL)==SRK_SBL_CAL_MANAGEMENT2_OFFSET){
    Uint32 r;s->active_slot_work_index=i;s->slot_flag1=(unsigned int)srk_cal_probe_u8(w+0x00UL);s->slot_flag2=(unsigned int)f2;
    s->slot_midi=(unsigned int)srk_cal_probe_u8(w+0x01UL);s->slot_note=(unsigned int)srk_cal_probe_u8(w+0x02UL);s->slot_velocity=(unsigned int)srk_cal_probe_u8(w+0x03UL);
    s->slot_direct_pan=(unsigned int)srk_cal_probe_u8(w+0x04UL);s->slot_management=(unsigned int)srk_cal_probe_be16(w+0x06UL);s->slot_layer_address=(unsigned long)srk_cal_probe_be32(w+0x08UL);
    s->active_scsp_slot=s->slot_flag1&0x1Fu;r=SRK_SBL_CAL_SCSP_SLOT_ADDRESS+(Uint32)s->active_scsp_slot*SRK_SBL_CAL_SCSP_SLOT_STRIDE;
    s->scsp_control=(unsigned int)srk_cal_probe_reg16(r+0x00UL);s->scsp_sample_address_low=(unsigned int)srk_cal_probe_reg16(r+0x02UL);
    s->scsp_loop_start=(unsigned int)srk_cal_probe_reg16(r+0x04UL);s->scsp_loop_end=(unsigned int)srk_cal_probe_reg16(r+0x06UL);
    s->scsp_total_level=(unsigned int)srk_cal_probe_reg16(r+0x0CUL);s->scsp_mixer=(unsigned int)srk_cal_probe_reg16(r+0x16UL);
   }
  }
 }
}
"""
    base = base.replace(sample_anchor, helpers + sample_anchor, 1)

    execution_anchor = (
        "if(s->commands_queued>0UL&&s->history_valid&&"
        "s->history_baseline>=SRK_SBL_CAL_HISTORY_RING_START&&"
        "history!=s->history_baseline)s->driver_executed=1u;\n"
    )
    if base.count(execution_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe execution sampling anchor changed"
        )
    base = base.replace(
        execution_anchor,
        execution_anchor + " srk_cal_probe_voice(s);\n",
        1,
    )

    reset_anchor = (
        " s->master_volume=SRK_SBL_CAL_MASTER_VOLUME_DEFAULT;\n"
    )
    if base.count(reset_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe reset anchor changed"
        )
    reset = """ s->direct_midi_status=0u;s->driver_program=0u;s->driver_bank_address=0UL;
 s->midi_master_volume=0u;s->midi_volume=0u;s->midi_expression=0u;s->noteon_master_volume=0u;s->total_volume=0u;
 s->active_slot_count=0u;s->active_slot_work_index=SRK_SBL_CAL_SLOT_NONE;s->active_scsp_slot=SRK_SBL_CAL_SLOT_NONE;
 s->slot_flag1=0u;s->slot_flag2=0u;s->slot_midi=0u;s->slot_note=0u;s->slot_velocity=0u;s->slot_direct_pan=0u;s->slot_management=0u;s->slot_layer_address=0UL;
 s->scsp_control=0u;s->scsp_sample_address_low=0u;s->scsp_loop_start=0u;s->scsp_loop_end=0u;s->scsp_total_level=0u;s->scsp_mixer=0u;
"""
    return base.replace(reset_anchor, reset_anchor + reset, 1)


def _main(base: str) -> str:
    instruction = 'srk_cal_field(2,24,22,"UP/DOWN Master volume");'
    if base.count(instruction) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe renderer instruction anchor changed"
        )

    probe = (
        'srk_cal_field(2,20,5,"M2 S:");'
        'srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.direct_midi_status);'
        'srk_cal_field(7,20,4,h4);'
        'srk_cal_field(12,20,2,"P:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.driver_program);srk_cal_field(14,20,3,n);'
        'srk_cal_field(18,20,5,"Bank:");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.driver_bank_address);srk_cal_field(23,20,10,h32);'
        'srk_cal_field(2,21,12,"Vol M/V/E/N/T");'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_master_volume);srk_cal_field(15,21,3,n);'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_volume);srk_cal_field(19,21,3,n);'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.midi_expression);srk_cal_field(23,21,3,n);'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.noteon_master_volume);srk_cal_field(27,21,3,n);'
        'srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.total_volume);srk_cal_field(31,21,3,n);'
        'srk_cal_field(2,22,6,"Slots:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.active_slot_count);srk_cal_field(8,22,2,n);'
        'srk_cal_field(11,22,2,"W:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.active_slot_work_index);srk_cal_field(13,22,5,n);'
        'srk_cal_field(19,22,3,"HW:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.active_scsp_slot);srk_cal_field(22,22,5,n);'
        'srk_cal_field(28,22,3,"F2:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.slot_flag2);srk_cal_field(31,22,4,h4);'
        'srk_cal_field(2,23,2,"M:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.slot_management);srk_cal_field(4,23,4,h4);'
        'srk_cal_field(9,23,3,"Ch:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.slot_midi);srk_cal_field(12,23,2,n);'
        'srk_cal_field(15,23,2,"N:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.slot_note);srk_cal_field(17,23,3,n);'
        'srk_cal_field(21,23,2,"V:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.slot_velocity);srk_cal_field(23,23,3,n);'
        'srk_cal_field(27,23,3,"LY:");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.slot_layer_address);srk_cal_field(30,23,10,h32);'
        'srk_cal_field(2,24,3,"KX:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.scsp_control);srk_cal_field(5,24,4,h4);'
        'srk_cal_field(10,24,3,"SA:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.scsp_sample_address_low);srk_cal_field(13,24,4,h4);'
        'srk_cal_field(18,24,3,"TL:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.scsp_total_level);srk_cal_field(21,24,4,h4);'
        'srk_cal_field(26,24,3,"MX:");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.scsp_mixer);srk_cal_field(29,24,4,h4);'
    )
    return base.replace(instruction, probe, 1)


@contextmanager
def _contract():
    old_header = _volume._header
    old_runtime = _volume._runtime
    old_main = _volume._main
    old_manifest = _volume._telemetry_manifest

    def header(base: str) -> str:
        return _header(old_header(base))

    def runtime(base: str) -> str:
        return _runtime(old_runtime(base))

    def main(base: str) -> str:
        return _main(old_main(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _volume._header = header
    _volume._runtime = runtime
    _volume._main = main
    _volume._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _volume._header = old_header
        _volume._runtime = old_runtime
        _volume._main = old_main
        _volume._telemetry_manifest = old_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build SDDRV210 with read-only internal voice-allocation telemetry."""

    with _contract():
        return _volume.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
