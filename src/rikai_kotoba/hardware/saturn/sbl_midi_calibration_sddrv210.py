"""SDDRV Ver 2.10 contract for the current Sega Direct-MIDI one-shot diagnostic.

The historical consolidated builder remains unchanged so its physical evidence is
reproducible.  This module layers the Ver 2.10 sound-driver contract and corrected
system-interface/history telemetry onto current builds only.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json as _json

from . import sbl_midi_calibration_consolidated as _candidate


SaturnSblMidiCalibrationCandidateError = _candidate.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _candidate.SaturnSblMidiCalibrationCandidateResult

SDDRV210_SHA256 = "68890ee4a49fd0c341bc3f0a48643e4db4b175df0b0d7dacfeb88306340052b6"
SDDRV210_VERSION = "2.10"

_SOUND_RAM_BASE = 0x25A00000
_SYSTEM_INFORMATION_POINTER_ADDRESS = 0x25A00400
_HOST_INTERFACE_POINTER_ADDRESS = 0x25A00404
_AREA_MAP_CURRENT_POINTER_ADDRESS = 0x25A00408
_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS = 0x25A00412
_DRIVER_ERROR_ADDRESS = 0x25A00416
_COMMAND_HISTORY_OFFSET_ADDRESS = 0x25A0041A
_CPU_ERROR_ADDRESS = 0x25A00420

_SYSTEM_INFORMATION_POINTER_EXPECTED = 0x00000440
_HOST_INTERFACE_POINTER_EXPECTED = 0x00000700
_AREA_MAP_CURRENT_POINTER_EXPECTED = 0x00000500
_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED = 0x00000480
_COMMAND_HISTORY_RING_START = 0x0800
_COMMAND_HISTORY_RING_END = 0x0FFF
_COMMAND_HISTORY_ENTRY_BYTES = 16
_COMMAND_HISTORY_OFFSET_MASK = 0x07F0


def _sha(path: Path) -> str:
    return _candidate._gm._sha(path)


def _driver(saturn_root, sound_driver) -> Path:
    driver = _candidate._gm._driver(
        _candidate._gm._path(saturn_root),
        None if sound_driver is None else _candidate._gm._path(sound_driver),
    )
    digest = _sha(driver)
    if digest.lower() != SDDRV210_SHA256:
        raise SaturnSblMidiCalibrationCandidateError(
            "current Sega one-shot requires SDDRV Ver 2.10 exactly; "
            f"expected SHA-256 {SDDRV210_SHA256}, got {digest} from {driver}"
        )
    return driver


def _header(base: str) -> str:
    old = """ unsigned long commands_queued;\n unsigned int driver_executed;\n unsigned short history_baseline;\n unsigned short history_current;\n unsigned short driver_error;\n unsigned long cpu_error;\n"""
    new = """ unsigned long commands_queued;\n unsigned int driver_executed;\n unsigned int interface_valid;\n unsigned int history_valid;\n unsigned short history_offset_raw;\n unsigned short history_baseline;\n unsigned short history_current;\n unsigned short driver_error;\n unsigned long cpu_error;\n unsigned long system_information_pointer;\n unsigned long host_interface_pointer;\n unsigned long area_map_current_pointer;\n unsigned long system_interface_work_pointer;\n"""
    if base.count(old) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 runtime header telemetry anchor changed"
        )
    return base.replace(old, new, 1)


def _runtime(base: str) -> str:
    old_macros = (
        f"#define SRK_SBL_CAL_DRIVER_ERROR (*(volatile Uint16 *)0x{_candidate._DRIVER_ERROR_ADDRESS:08X}UL)\n"
        f"#define SRK_SBL_CAL_HISTORY (*(volatile Uint16 *)0x{_candidate._COMMAND_HISTORY_OFFSET_ADDRESS:08X}UL)\n"
    )
    new_macros = f"""#define SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_ADDRESS 0x{_SYSTEM_INFORMATION_POINTER_ADDRESS:08X}UL
#define SRK_SBL_CAL_HOST_INTERFACE_POINTER_ADDRESS 0x{_HOST_INTERFACE_POINTER_ADDRESS:08X}UL
#define SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_ADDRESS 0x{_AREA_MAP_CURRENT_POINTER_ADDRESS:08X}UL
#define SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS 0x{_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS:08X}UL
#define SRK_SBL_CAL_DRIVER_ERROR (*(volatile Uint16 *)0x{_DRIVER_ERROR_ADDRESS:08X}UL)
#define SRK_SBL_CAL_HISTORY_OFFSET (*(volatile Uint16 *)0x{_COMMAND_HISTORY_OFFSET_ADDRESS:08X}UL)
#define SRK_SBL_CAL_HISTORY_RING_START 0x{_COMMAND_HISTORY_RING_START:04X}u
#define SRK_SBL_CAL_HISTORY_RING_END 0x{_COMMAND_HISTORY_RING_END:04X}u
#define SRK_SBL_CAL_HISTORY_ENTRY_BYTES {_COMMAND_HISTORY_ENTRY_BYTES}u
#define SRK_SBL_CAL_HISTORY_OFFSET_MASK 0x{_COMMAND_HISTORY_OFFSET_MASK:04X}u
#define SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_EXPECTED 0x{_SYSTEM_INFORMATION_POINTER_EXPECTED:08X}UL
#define SRK_SBL_CAL_HOST_INTERFACE_POINTER_EXPECTED 0x{_HOST_INTERFACE_POINTER_EXPECTED:08X}UL
#define SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_EXPECTED 0x{_AREA_MAP_CURRENT_POINTER_EXPECTED:08X}UL
#define SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED 0x{_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED:08X}UL
"""
    if base.count(old_macros) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 runtime memory-map macro anchor changed"
        )
    base = base.replace(old_macros, new_macros, 1)

    old_sample = f"""static Uint32 srk_cal_cpu_error(void){{
 volatile Uint16 *p=(volatile Uint16 *)0x{_candidate._CPU_ERROR_ADDRESS:08X}UL;
 return ((Uint32)p[0]<<16)|(Uint32)p[1];
}}
static void srk_cal_sample(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){{
 Uint16 history;if(!s)return;
 s->driver_error=(unsigned short)SRK_SBL_CAL_DRIVER_ERROR;
 s->cpu_error=(unsigned long)srk_cal_cpu_error();
 history=SRK_SBL_CAL_HISTORY;s->history_current=(unsigned short)history;
 if(s->commands_queued>0UL&&history!=s->history_baseline)s->driver_executed=1u;
}}
"""
    new_sample = f"""static Uint32 srk_cal_read_u32(Uint32 address){{
 volatile Uint16 *p=(volatile Uint16 *)address;
 return ((Uint32)p[0]<<16)|(Uint32)p[1];
}}
static Uint32 srk_cal_cpu_error(void){{return srk_cal_read_u32(0x{_CPU_ERROR_ADDRESS:08X}UL);}}
static Uint16 srk_cal_history_address(Uint16 raw,unsigned int *valid){{
 if((raw&0x000Fu)!=0u||raw>SRK_SBL_CAL_HISTORY_OFFSET_MASK){{if(valid)*valid=0u;return 0u;}}
 if(valid)*valid=1u;return (Uint16)(SRK_SBL_CAL_HISTORY_RING_START+raw);
}}
static void srk_cal_sample(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){{
 Uint16 raw,history;unsigned int history_valid;if(!s)return;
 s->system_information_pointer=(unsigned long)srk_cal_read_u32(SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_ADDRESS);
 s->host_interface_pointer=(unsigned long)srk_cal_read_u32(SRK_SBL_CAL_HOST_INTERFACE_POINTER_ADDRESS);
 s->area_map_current_pointer=(unsigned long)srk_cal_read_u32(SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_ADDRESS);
 s->system_interface_work_pointer=(unsigned long)srk_cal_read_u32(SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS);
 s->interface_valid=(s->system_information_pointer==SRK_SBL_CAL_SYSTEM_INFORMATION_POINTER_EXPECTED&&s->host_interface_pointer==SRK_SBL_CAL_HOST_INTERFACE_POINTER_EXPECTED&&s->area_map_current_pointer==SRK_SBL_CAL_AREA_MAP_CURRENT_POINTER_EXPECTED&&s->system_interface_work_pointer==SRK_SBL_CAL_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED)?1u:0u;
 s->driver_error=(unsigned short)SRK_SBL_CAL_DRIVER_ERROR;s->cpu_error=(unsigned long)srk_cal_cpu_error();
 raw=SRK_SBL_CAL_HISTORY_OFFSET;s->history_offset_raw=(unsigned short)raw;
 history=srk_cal_history_address(raw,&history_valid);s->history_current=(unsigned short)history;
 s->history_valid=(s->interface_valid&&history_valid&&history>=SRK_SBL_CAL_HISTORY_RING_START&&history<=SRK_SBL_CAL_HISTORY_RING_END)?1u:0u;
 if(s->commands_queued>0UL&&s->history_valid&&s->history_baseline>=SRK_SBL_CAL_HISTORY_RING_START&&history!=s->history_baseline)s->driver_executed=1u;
}}
"""
    if base.count(old_sample) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 runtime sampling anchor changed"
        )
    base = base.replace(old_sample, new_sample, 1)

    old_reset = """ s->commands_queued=0UL;s->driver_executed=0u;s->history_baseline=0u;s->history_current=0u;s->driver_error=0u;s->cpu_error=0UL;\n"""
    new_reset = """ s->commands_queued=0UL;s->driver_executed=0u;s->interface_valid=0u;s->history_valid=0u;s->history_offset_raw=0u;s->history_baseline=0u;s->history_current=0u;s->driver_error=0u;s->cpu_error=0UL;\n s->system_information_pointer=0UL;s->host_interface_pointer=0UL;s->area_map_current_pointer=0UL;s->system_interface_work_pointer=0UL;\n"""
    if base.count(old_reset) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 runtime reset anchor changed"
        )
    base = base.replace(old_reset, new_reset, 1)

    old_begin = """ srk_cal_state->initialized=1u;srk_cal_state->history_baseline=(unsigned short)SRK_SBL_CAL_HISTORY;srk_cal_state->history_current=srk_cal_state->history_baseline;\n srk_cal_sample(srk_cal_state);return 1u;\n"""
    new_begin = """ srk_cal_state->initialized=1u;srk_cal_sample(srk_cal_state);\n srk_cal_state->history_baseline=srk_cal_state->history_valid?srk_cal_state->history_current:0u;return 1u;\n"""
    if base.count(old_begin) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 runtime history-baseline anchor changed"
        )
    return base.replace(old_begin, new_begin, 1)


def _main(base: str) -> str:
    helper_anchor = "static void srk_cal_hex32(char out[11],srk_u32 v){static const char h[]=\"0123456789ABCDEF\";int i;out[0]='0';out[1]='x';for(i=0;i<8;i++)out[2+i]=h[(v>>(28-i*4))&15u];out[10]=0;}\n"
    helper = "static void srk_cal_hex4(char out[5],srk_u16 v){static const char h[]=\"0123456789ABCDEF\";out[0]=h[(v>>12)&15u];out[1]=h[(v>>8)&15u];out[2]=h[(v>>4)&15u];out[3]=h[v&15u];out[4]=0;}\n"
    if base.count(helper_anchor) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 main hex helper anchor changed"
        )
    base = base.replace(helper_anchor, helper_anchor + helper, 1)

    start = base.find("static void srk_cal_render(void){")
    end = base.find("static void srk_cal_frame(void){", start)
    if start < 0 or end < 0:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 main telemetry renderer anchor changed"
        )
    renderer = """static void srk_cal_render(void){char n[11],h16[7],h32[11],h4[5];/* Queued: retained in runtime state; SDDRV210 HUD prioritizes interface proof. */srk_cal_field(2,17,12,\"SDDRV exec:\");srk_cal_field(15,17,4,srk_midi_calibration_runtime.driver_executed?\"YES\":\"WAIT\");srk_cal_field(20,17,3,\"IF:\");srk_cal_field(23,17,3,srk_midi_calibration_runtime.interface_valid?\"OK\":\"BAD\");srk_cal_field(27,17,4,\"Drv:\");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.driver_error);srk_cal_field(31,17,6,h16);srk_cal_field(2,18,8,\"68K err:\");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.cpu_error);srk_cal_field(11,18,10,h32);srk_cal_field(22,18,5,\"Hist:\");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.history_current);srk_cal_field(28,18,6,h16);srk_cal_field(35,18,2,\"H:\");srk_cal_field(37,18,3,srk_midi_calibration_runtime.history_valid?\"OK\":\"BAD\");srk_cal_field(2,19,4,\"400:\");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.system_information_pointer);srk_cal_field(6,19,4,h4);srk_cal_field(11,19,4,\"404:\");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.host_interface_pointer);srk_cal_field(15,19,4,h4);srk_cal_field(20,19,4,\"408:\");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.area_map_current_pointer);srk_cal_field(24,19,4,h4);srk_cal_field(29,19,4,\"412:\");srk_cal_hex4(h4,(srk_u16)srk_midi_calibration_runtime.system_interface_work_pointer);srk_cal_field(33,19,4,h4);srk_cal_field(20,11,3,\"0 /\");srk_cal_num(n,(srk_u32)(srk_app.midi.program&7u));srk_cal_field(24,11,4,n);}\n"""
    return base[:start] + renderer + base[end:]


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_telemetry_contract"] = True
    candidate["policy"] = policy
    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "driver_version": SDDRV210_VERSION,
            "driver_sha256": SDDRV210_SHA256,
            "sound_ram_base": f"0x{_SOUND_RAM_BASE:08X}",
            "system_information_pointer_address": f"0x{_SYSTEM_INFORMATION_POINTER_ADDRESS:08X}",
            "system_information_pointer_expected": f"0x{_SYSTEM_INFORMATION_POINTER_EXPECTED:08X}",
            "host_interface_pointer_address": f"0x{_HOST_INTERFACE_POINTER_ADDRESS:08X}",
            "host_interface_pointer_expected": f"0x{_HOST_INTERFACE_POINTER_EXPECTED:08X}",
            "area_map_current_pointer_address": f"0x{_AREA_MAP_CURRENT_POINTER_ADDRESS:08X}",
            "area_map_current_pointer_expected": f"0x{_AREA_MAP_CURRENT_POINTER_EXPECTED:08X}",
            "system_interface_work_pointer_address": f"0x{_SYSTEM_INTERFACE_WORK_POINTER_ADDRESS:08X}",
            "system_interface_work_pointer_expected": f"0x{_SYSTEM_INTERFACE_WORK_POINTER_EXPECTED:08X}",
            "driver_error_address": f"0x{_DRIVER_ERROR_ADDRESS:08X}",
            "command_history_offset_address": f"0x{_COMMAND_HISTORY_OFFSET_ADDRESS:08X}",
            "command_history_ring_start": f"0x{_COMMAND_HISTORY_RING_START:04X}",
            "command_history_ring_end": f"0x{_COMMAND_HISTORY_RING_END:04X}",
            "command_history_entry_bytes": _COMMAND_HISTORY_ENTRY_BYTES,
            "command_history_offset_mask": f"0x{_COMMAND_HISTORY_OFFSET_MASK:04X}",
            "cpu_error_address": f"0x{_CPU_ERROR_ADDRESS:08X}",
            "command_history_proves_driver_execution": True,
            "interface_table_must_match_before_execution_proof": True,
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


class _JsonProxy:
    @staticmethod
    def loads(*args, **kwargs):
        return _json.loads(*args, **kwargs)

    @staticmethod
    def dumps(document, *args, **kwargs):
        if isinstance(document, dict) and "sbl_midi_calibration" in document:
            document = _telemetry_manifest(document)
        return _json.dumps(document, *args, **kwargs)


@contextmanager
def _contract():
    old_header = _candidate._header
    old_runtime = _candidate._runtime
    old_main = _candidate._main
    old_json = _candidate.json

    def header(driver_bytes: int, map_bytes: int, max_family_bytes: int) -> str:
        return _header(old_header(driver_bytes, map_bytes, max_family_bytes))

    def runtime(families) -> str:
        return _runtime(old_runtime(families))

    def main(base: str) -> str:
        return _main(old_main(base))

    _candidate._header = header
    _candidate._runtime = runtime
    _candidate._main = main
    _candidate.json = _JsonProxy()
    try:
        yield
    finally:
        _candidate._header = old_header
        _candidate._runtime = old_runtime
        _candidate._main = old_main
        _candidate.json = old_json


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build the current one-shot only with the exact SDDRV Ver 2.10 binary."""

    driver = _driver(saturn_root, sound_driver)
    with _contract():
        result = _candidate.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=driver,
        )
    if result.assets.sound_driver_sha256.lower() != SDDRV210_SHA256:
        raise SaturnSblMidiCalibrationCandidateError(
            "built candidate escaped the SDDRV Ver 2.10 hash lock"
        )
    return result
