"""Build the current consolidated Sega SBL MIDI calibration diagnostic.

This is deliberately not another numbered hardware gate.  It replaces the two
architectural mistakes exposed by physical GATE4 validation while preserving the
physically proven GATE3F ownership model:

* the generic raw-SCSP Audio Test remains bound and usable outside MIDI Test;
* SBL/SDDRV initialization is lazy and owned by the MIDI calibration screen;
* leaving MIDI Test stops SBL and resets raw-SCSP host state for the next test;
* sixteen real eight-program General MIDI family banks cover programs 0..127;
* GATE3F's corrected static attenuation and velocity-table policy is retained;
* live SDDRV command-history/error telemetry distinguishes command queueing from
  actual MC68EC000 driver execution.

Generation/building is off-card only.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import shutil
import tempfile

from . import standalone_build as _build
from . import sbl_gm_physical_candidate as _gm
from .sbl_direct_midi_compile_probe import _resolve_sdk_file
from .sbl_gm_calibration_family_banks import (
    GM_FAMILY_COUNT,
    SaturnGmCalibrationFamilyBanks,
    build_gm_calibration_family_banks,
)
from .sbl_sequence import SBL_AREA_TONE, SaturnSblArea, encode_sbl_external_area_map


class SaturnSblMidiCalibrationConsolidatedError(RuntimeError):
    """Raised when the consolidated calibration project cannot be built safely."""


SaturnSblMidiCalibrationCandidateError = SaturnSblMidiCalibrationConsolidatedError


@dataclass(frozen=True)
class SaturnSblMidiCalibrationAssets:
    sound_driver: Path
    sound_driver_sha256: str
    soundfont: Path
    soundfont_sha256: str
    sega_sound_library: Path
    sega_sound_library_sha256: str
    area_map_sha256: str
    family_sha256: tuple[str, ...]


@dataclass(frozen=True)
class SaturnSblMidiCalibrationCandidateResult:
    project_root: Path
    assets: SaturnSblMidiCalibrationAssets
    family_banks: SaturnGmCalibrationFamilyBanks
    build: _build.SaturnStandaloneBuildResult


_DRIVER_CD = "SDDRVS.TSK"
_MAP_CD = "SRKMAP.BIN"
_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_HEADER = "srk_saturn_sbl_midi_calibration_runtime.h"
_TONE_START = 0x0000B000
_SOUND_RAM_END = 0x00080000

# Sega SBL system-interface telemetry documented in the supplied sound manuals.
_DRIVER_ERROR_ADDRESS = 0x25A00416
_COMMAND_HISTORY_OFFSET_ADDRESS = 0x25A0041A
_CPU_ERROR_ADDRESS = 0x25A00420


def _area_map(max_bank_bytes: int) -> bytes:
    if max_bank_bytes <= 0 or _TONE_START + max_bank_bytes > _SOUND_RAM_END:
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"largest GM calibration family does not fit Sound RAM: {max_bank_bytes} bytes"
        )
    payload = encode_sbl_external_area_map(
        (SaturnSblArea(SBL_AREA_TONE, 0, _TONE_START, max_bank_bytes),)
    )
    if len(payload) != 10 or payload[-2:] != b"\xFF\xFF":
        raise SaturnSblMidiCalibrationConsolidatedError(
            "single-family external Sega .MP encoding changed"
        )
    return payload


def _header(driver_bytes: int, map_bytes: int, max_family_bytes: int) -> str:
    return f'''#ifndef SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#define SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#include "srk_diag_host.h"
#define SRK_SBL_CAL_DRIVER_BYTES {driver_bytes}UL
#define SRK_SBL_CAL_MAP_BYTES {map_bytes}UL
#define SRK_SBL_CAL_MAX_FAMILY_BYTES {max_family_bytes}UL
#define SRK_SBL_CAL_FAMILY_COUNT {GM_FAMILY_COUNT}u
#define SRK_SBL_CAL_FAMILY_NONE 0xffffu
typedef struct SRK_SBL_MIDI_CAL_RUNTIME_STATE {{
 unsigned int initialized;
 unsigned int error;
 unsigned int last_ret;
 unsigned int current_family;
 unsigned long commands_queued;
 unsigned int driver_executed;
 unsigned short history_baseline;
 unsigned short history_current;
 unsigned short driver_error;
 unsigned long cpu_error;
}} SRK_SBL_MIDI_CAL_RUNTIME_STATE;
void srk_saturn_sbl_midi_calibration_runtime_reset(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
void srk_saturn_sbl_midi_calibration_runtime_bind(SRK_DIAG_HOST *host,SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
void srk_saturn_sbl_midi_calibration_runtime_poll(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
void srk_saturn_sbl_midi_calibration_runtime_stop(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
#endif
'''


def _runtime(families: SaturnGmCalibrationFamilyBanks) -> str:
    names = ",".join(f'"{bank.filename}"' for bank in families.banks)
    sizes = ",".join(f"{bank.size}UL" for bank in families.banks)
    return f'''#include "{_RUNTIME_HEADER}"
#include "srk_saturn_audio.h"
#include "srk_saturn_host.h"
#include "srk_saturn_sbl_direct_midi.h"
#include "SEGA_GFS.H"
#include "sega_snd.h"
#define SRK_GFS_OPEN_MAX 2
#define SRK_GFS_MAX_DIR 64
#define SRK_SBL_CAL_ERR_GFS 1u
#define SRK_SBL_CAL_ERR_DRIVER 2u
#define SRK_SBL_CAL_ERR_MAP_LOAD 3u
#define SRK_SBL_CAL_ERR_MAP 4u
#define SRK_SBL_CAL_ERR_VOLUME 5u
#define SRK_SBL_CAL_ERR_FAMILY 6u
#define SRK_SBL_CAL_ERR_PROGRAM 7u
#define SRK_SBL_CAL_ERR_PAN 8u
#define SRK_SBL_CAL_ERR_NOTE_ON 9u
#define SRK_SBL_CAL_ERR_NOTE_OFF 10u
#define SRK_SBL_CAL_ERR_MIX 11u
#define SRK_SBL_CAL_NOTE_OFF 0u
#define SRK_SBL_CAL_NOTE_ON 1u
#define SRK_SBL_CAL_CONTROL_CHANGE 3u
#define SRK_SBL_CAL_PROGRAM_CHANGE 4u
#define SRK_SBL_CAL_BANK_CONTROLLER 32u
#define SRK_SBL_CAL_PAN_CONTROLLER 10u
#define SRK_SBL_CAL_SEQ_NO 2u
#define SRK_SBL_CAL_SEQ_PRI 0u
#define SRK_SBL_CAL_CHANNEL 0u
#define SRK_SBL_CAL_FAMILY_SIZE 8u
#define SRK_SBL_CAL_MIDI_MAX 127u
#define SRK_SBL_CAL_DRIVER_ERROR (*(volatile Uint16 *)0x{_DRIVER_ERROR_ADDRESS:08X}UL)
#define SRK_SBL_CAL_HISTORY (*(volatile Uint16 *)0x{_COMMAND_HISTORY_OFFSET_ADDRESS:08X}UL)
static Uint32 srk_cal_gfs_work[GFS_WORK_SIZE(SRK_GFS_OPEN_MAX)/sizeof(Uint32)];
static GfsDirTbl srk_cal_gfs_table;
static GfsDirName srk_cal_gfs_names[SRK_GFS_MAX_DIR];
static Uint32 srk_cal_driver[(SRK_SBL_CAL_DRIVER_BYTES+3UL)/4UL];
static Uint32 srk_cal_map[(SRK_SBL_CAL_MAP_BYTES+3UL)/4UL];
static Uint32 srk_cal_family[(SRK_SBL_CAL_MAX_FAMILY_BYTES+3UL)/4UL];
static const char *srk_cal_family_names[SRK_SBL_CAL_FAMILY_COUNT]={{{names}}};
static const unsigned long srk_cal_family_sizes[SRK_SBL_CAL_FAMILY_COUNT]={{{sizes}}};
static SRK_DIAG_HOST *srk_cal_host;
static SRK_SBL_MIDI_CAL_RUNTIME_STATE *srk_cal_state;
static Uint32 srk_cal_cpu_error(void){{
 volatile Uint16 *p=(volatile Uint16 *)0x{_CPU_ERROR_ADDRESS:08X}UL;
 return ((Uint32)p[0]<<16)|(Uint32)p[1];
}}
static void srk_cal_sample(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){{
 Uint16 history;if(!s)return;
 s->driver_error=(unsigned short)SRK_SBL_CAL_DRIVER_ERROR;
 s->cpu_error=(unsigned long)srk_cal_cpu_error();
 history=SRK_SBL_CAL_HISTORY;s->history_current=(unsigned short)history;
 if(s->commands_queued>0UL&&history!=s->history_baseline)s->driver_executed=1u;
}}
static int srk_cal_load(const char *name,Uint32 *dst,unsigned long bytes){{
 Sint32 id,n;id=GFS_NameToId((Sint8 *)name);if(id<0)return 0;
 n=GFS_Load(id,0,dst,(Sint32)bytes);return n==(Sint32)bytes;
}}
static unsigned int srk_cal_fail(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s,unsigned int error){{
 if(s){{s->error=error;s->last_ret=(unsigned int)SND_RET_NSET;srk_cal_sample(s);}}
 return 0u;
}}
static SndRet srk_cal_send(Uint8 command,Uint8 channel,Uint8 data1,Uint8 data2){{
 SndRet result=srk_saturn_sbl_direct_midi(
  SRK_SBL_CAL_SEQ_NO,SRK_SBL_CAL_SEQ_PRI,command,channel,data1,data2);
 if(srk_cal_state){{srk_cal_state->commands_queued++;srk_cal_state->last_ret=(unsigned int)result;srk_cal_sample(srk_cal_state);}}
 return result;
}}
void srk_saturn_sbl_midi_calibration_runtime_reset(SRK_SBL_MIDI_CAL_RUNTIME_STATE *s){{
 if(!s)return;s->initialized=0u;s->error=0u;s->last_ret=0u;s->current_family=SRK_SBL_CAL_FAMILY_NONE;
 s->commands_queued=0UL;s->driver_executed=0u;s->history_baseline=0u;s->history_current=0u;s->driver_error=0u;s->cpu_error=0UL;
}}
static unsigned int srk_cal_begin(void *context){{
 SndIniDt ini;SndRet result;Sint32 gfs_result;
 if(!srk_cal_state||!srk_cal_host)return 0u;if(srk_cal_state->initialized)return 1u;
 if(srk_cal_host->stop_audio)srk_cal_host->stop_audio(context);
 srk_saturn_sbl_midi_calibration_runtime_reset(srk_cal_state);
 GFS_DIRTBL_TYPE(&srk_cal_gfs_table)=GFS_DIR_NAME;GFS_DIRTBL_NDIR(&srk_cal_gfs_table)=SRK_GFS_MAX_DIR;GFS_DIRTBL_DIRNAME(&srk_cal_gfs_table)=srk_cal_gfs_names;
 gfs_result=GFS_Init(SRK_GFS_OPEN_MAX,srk_cal_gfs_work,&srk_cal_gfs_table);if(gfs_result<0)return srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_GFS);
 if(!srk_cal_load("{_DRIVER_CD}",srk_cal_driver,SRK_SBL_CAL_DRIVER_BYTES))return srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_DRIVER);
 if(!srk_cal_load("{_MAP_CD}",srk_cal_map,SRK_SBL_CAL_MAP_BYTES))return srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_MAP_LOAD);
 SND_INI_PRG_ADR(ini)=(Uint16 *)srk_cal_driver;SND_INI_PRG_SZ(ini)=(Uint16)SRK_SBL_CAL_DRIVER_BYTES;
 SND_INI_ARA_ADR(ini)=(Uint16 *)srk_cal_map;SND_INI_ARA_SZ(ini)=(Uint16)SRK_SBL_CAL_MAP_BYTES;
 SND_Init(&ini);
 result=SND_ChgMap(0);srk_cal_state->last_ret=(unsigned int)result;if(result!=SND_RET_SET)return srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_MAP);
 srk_cal_state->initialized=1u;srk_cal_state->history_baseline=(unsigned short)SRK_SBL_CAL_HISTORY;srk_cal_state->history_current=srk_cal_state->history_baseline;
 srk_cal_sample(srk_cal_state);return 1u;
}}
static int srk_cal_select_program(void *context,unsigned int program){{
 unsigned int family,voice;SndRet result;
 if(program>SRK_SBL_CAL_MIDI_MAX)return 0;if(!srk_cal_begin(context))return 0;
 family=program/SRK_SBL_CAL_FAMILY_SIZE;voice=program%SRK_SBL_CAL_FAMILY_SIZE;
 if(family>=SRK_SBL_CAL_FAMILY_COUNT)return 0;
 if(srk_cal_state->current_family!=family){{
  (void)SND_OffAllSound();
  if(!srk_cal_load(srk_cal_family_names[family],srk_cal_family,srk_cal_family_sizes[family]))return (int)srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_FAMILY);
  SND_MoveData((Uint16 *)srk_cal_family,(Uint32)srk_cal_family_sizes[family],SND_KD_TONE,0);
  result=SND_ChgMix(0,0);srk_cal_state->last_ret=(unsigned int)result;if(result!=SND_RET_SET)return (int)srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_MIX);
  result=SND_SetTlVl(15);srk_cal_state->last_ret=(unsigned int)result;if(result!=SND_RET_SET)return (int)srk_cal_fail(srk_cal_state,SRK_SBL_CAL_ERR_VOLUME);
  srk_cal_state->current_family=family;
 }}
 result=srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,SRK_SBL_CAL_CHANNEL,SRK_SBL_CAL_BANK_CONTROLLER,0u);
 if(result!=SND_RET_SET){{srk_cal_state->error=SRK_SBL_CAL_ERR_PROGRAM;return 0;}}
 result=srk_cal_send(SRK_SBL_CAL_PROGRAM_CHANGE,SRK_SBL_CAL_CHANNEL,(Uint8)voice,0u);
 if(result!=SND_RET_SET){{srk_cal_state->error=SRK_SBL_CAL_ERR_PROGRAM;return 0;}}
 return 1;
}}
static int srk_cal_set_pan(void *context,unsigned int channel,unsigned int pan){{
 SndRet result;(void)context;if(channel>15u||pan>SRK_SBL_CAL_MIDI_MAX||!srk_cal_state||!srk_cal_state->initialized)return 0;
 result=srk_cal_send(SRK_SBL_CAL_CONTROL_CHANGE,(Uint8)channel,SRK_SBL_CAL_PAN_CONTROLLER,(Uint8)pan);
 if(result!=SND_RET_SET){{srk_cal_state->error=SRK_SBL_CAL_ERR_PAN;return 0;}}return 1;
}}
static int srk_cal_note_on(void *context,unsigned int channel,unsigned int note,unsigned int velocity){{
 SndRet result;(void)context;if(channel>15u||note>SRK_SBL_CAL_MIDI_MAX||velocity>SRK_SBL_CAL_MIDI_MAX||!srk_cal_state||!srk_cal_state->initialized)return 0;
 result=srk_cal_send(SRK_SBL_CAL_NOTE_ON,(Uint8)channel,(Uint8)note,(Uint8)velocity);
 if(result!=SND_RET_SET){{srk_cal_state->error=SRK_SBL_CAL_ERR_NOTE_ON;return 0;}}return 1;
}}
static int srk_cal_note_off(void *context,unsigned int channel,unsigned int note,unsigned int velocity){{
 SndRet result;(void)context;if(channel>15u||note>SRK_SBL_CAL_MIDI_MAX||velocity>SRK_SBL_CAL_MIDI_MAX||!srk_cal_state||!srk_cal_state->initialized)return 0;
 result=srk_cal_send(SRK_SBL_CAL_NOTE_OFF,(Uint8)channel,(Uint8)note,(Uint8)velocity);
 if(result!=SND_RET_SET){{srk_cal_state->error=SRK_SBL_CAL_ERR_NOTE_OFF;return 0;}}return 1;
}}
void srk_saturn_sbl_midi_calibration_runtime_bind(SRK_DIAG_HOST *host,SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{
 if(!host||!state)return;srk_cal_host=host;srk_cal_state=state;
 host->midi_select_program=srk_cal_select_program;host->midi_set_pan=srk_cal_set_pan;host->midi_note_on=srk_cal_note_on;host->midi_note_off=srk_cal_note_off;host->midi_persist_review=0;
}}
void srk_saturn_sbl_midi_calibration_runtime_poll(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{srk_cal_sample(state);}}
void srk_saturn_sbl_midi_calibration_runtime_stop(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{
 SRK_SATURN_HOST_STATE *host_state;if(!state)return;if(state->initialized)(void)SND_OffAllSound();
 host_state=(srk_cal_host&&srk_cal_host->context)?(SRK_SATURN_HOST_STATE *)srk_cal_host->context:0;
 srk_saturn_sbl_midi_calibration_runtime_reset(state);
 if(srk_cal_host&&host_state)srk_saturn_audio_bind(srk_cal_host,host_state);
}}
'''


def _main(base: str) -> str:
    include = '#include "srk_saturn_host.h"\n'
    state = 'static SRK_SATURN_HOST_STATE srk_host_state;\n'
    app_reset = '    srk_diag_app_reset(&srk_app);\n'
    loop = '        srk_diag_app_frame(&srk_app, &srk_host);\n'
    if any(base.count(anchor) != 1 for anchor in (include, state, app_reset, loop)):
        raise SaturnSblMidiCalibrationConsolidatedError(
            "generic Saturn main calibration anchors changed"
        )
    base = base.replace(include, include + f'#include "{_RUNTIME_HEADER}"\n', 1)
    block = r'''
static SRK_SBL_MIDI_CAL_RUNTIME_STATE srk_midi_calibration_runtime;
static int srk_midi_calibration_screen_was_active;
static void srk_cal_num(char out[11],srk_u32 v){char r[10];int n=0,i;if(!v){out[0]='0';out[1]=0;return;}while(v&&n<10){r[n++]=(char)('0'+v%10u);v/=10u;}for(i=0;i<n;i++)out[i]=r[n-i-1];out[n]=0;}
static void srk_cal_hex16(char out[7],srk_u16 v){static const char h[]="0123456789ABCDEF";out[0]='0';out[1]='x';out[2]=h[(v>>12)&15u];out[3]=h[(v>>8)&15u];out[4]=h[(v>>4)&15u];out[5]=h[v&15u];out[6]=0;}
static void srk_cal_hex32(char out[11],srk_u32 v){static const char h[]="0123456789ABCDEF";int i;out[0]='0';out[1]='x';for(i=0;i<8;i++)out[2+i]=h[(v>>(28-i*4))&15u];out[10]=0;}
static void srk_cal_field(int x,int y,int w,const char *t){char b[41];int i;if(!srk_host.draw_text)return;if(w>40)w=40;for(i=0;i<w;i++)b[i]=' ';b[w]=0;if(t)for(i=0;i<w&&t[i];i++)b[i]=t[i];srk_host.draw_text(srk_host.context,x,y,b);}
static void srk_cal_render(void){char n[11],h16[7],h32[11];srk_cal_field(2,17,12,"SDDRV exec:");srk_cal_field(15,17,5,srk_midi_calibration_runtime.driver_executed?"YES":"WAIT");srk_cal_field(22,17,7,"DrvErr:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.driver_error);srk_cal_field(30,17,7,h16);srk_cal_field(2,18,8,"68K err:");srk_cal_hex32(h32,(srk_u32)srk_midi_calibration_runtime.cpu_error);srk_cal_field(11,18,10,h32);srk_cal_field(22,18,5,"Hist:");srk_cal_hex16(h16,(srk_u16)srk_midi_calibration_runtime.history_current);srk_cal_field(28,18,7,h16);srk_cal_field(2,19,7,"Queued:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.commands_queued);srk_cal_field(10,19,6,n);srk_cal_field(17,19,4,"Ret:");srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.last_ret);srk_cal_field(22,19,3,n);srk_cal_field(26,19,7,"Family:");if(srk_midi_calibration_runtime.current_family==SRK_SBL_CAL_FAMILY_NONE)srk_cal_field(34,19,4,"--");else{srk_cal_num(n,(srk_u32)srk_midi_calibration_runtime.current_family);srk_cal_field(34,19,4,n);}srk_cal_field(20,11,3,"0 /");srk_cal_num(n,(srk_u32)(srk_app.midi.program&7u));srk_cal_field(24,11,4,n);}
static void srk_cal_frame(void){int active=srk_app.menu.active&&srk_app.menu.active_screen==SRK_DIAG_SCREEN_MIDI_TEST;if(active){srk_saturn_sbl_midi_calibration_runtime_poll(&srk_midi_calibration_runtime);srk_cal_render();}else if(srk_midi_calibration_screen_was_active){srk_saturn_sbl_midi_calibration_runtime_stop(&srk_midi_calibration_runtime);}srk_midi_calibration_screen_was_active=active;}
'''
    base = base.replace(state, state + "\n" + block + "\n", 1)
    base = base.replace(
        app_reset,
        app_reset
        + '    srk_saturn_sbl_midi_calibration_runtime_reset(&srk_midi_calibration_runtime);\n'
        + '    srk_saturn_sbl_midi_calibration_runtime_bind(&srk_host, &srk_midi_calibration_runtime);\n'
        + '    srk_midi_calibration_screen_was_active = 0;\n',
        1,
    )
    base = base.replace(loop, loop + '        srk_cal_frame();\n', 1)
    if "srk_host.present_audio_tone = 0" in base:
        raise SaturnSblMidiCalibrationConsolidatedError(
            "consolidated main still disables raw SCSP Audio Test"
        )
    return base


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    baseline, saturn_root, output = map(
        _gm._path, (baseline_project, saturn_root, output_directory)
    )
    if not baseline.is_dir():
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"baseline project missing: {baseline}"
        )
    if not saturn_root.is_dir():
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"Saturn root missing: {saturn_root}"
        )
    if output.exists():
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"output already exists; refusing overwrite: {output}"
        )

    manifest_path = baseline / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"baseline manifest missing: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    families = build_gm_calibration_family_banks(soundfont)
    driver = _gm._driver(saturn_root, sound_driver)
    sound_library = _resolve_sdk_file(saturn_root, "sega_snd.a", kind="library")
    map_payload = _area_map(families.max_bank_bytes)
    assets = SaturnSblMidiCalibrationAssets(
        sound_driver=driver,
        sound_driver_sha256=_gm._sha(driver),
        soundfont=families.source_path,
        soundfont_sha256=families.source_sha256,
        sega_sound_library=sound_library,
        sega_sound_library_sha256=_gm._sha(sound_library),
        area_map_sha256=sha256(map_payload).hexdigest(),
        family_sha256=tuple(bank.sha256 for bank in families.banks),
    )

    repo = _gm._root()
    standalone = repo / "integrations" / "saturn" / "standalone"
    main = _main((standalone / "srk_saturn_main.c").read_text(encoding="utf-8"))
    base_runtime = (standalone / "srk_saturn_runtime.c").read_text(encoding="utf-8")
    direct = (standalone / "srk_saturn_sbl_direct_midi.c").read_text(encoding="utf-8")
    direct_header = (standalone / "srk_saturn_sbl_direct_midi.h").read_text(
        encoding="utf-8"
    )
    runtime_header = _header(driver.stat().st_size, len(map_payload), families.max_bank_bytes)
    runtime_body = _runtime(families)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output.name}.consolidated-", dir=str(output.parent)))
    stage = temp_root / "stage"
    stage.mkdir()
    try:
        _gm._copy_baseline(baseline, stage, manifest)
        (stage / "build").mkdir(exist_ok=True)
        (stage / "cd").mkdir(exist_ok=True)
        (stage / "src/srk_saturn_main.c").write_text(main, encoding="utf-8", newline="\n")
        (stage / "src/srk_saturn_sbl_direct_midi.h").write_text(
            direct_header, encoding="utf-8", newline="\n"
        )
        (stage / f"src/{_RUNTIME_HEADER}").write_text(
            runtime_header, encoding="utf-8", newline="\n"
        )
        (stage / "src/srk_saturn_runtime.c").write_text(
            base_runtime.rstrip() + "\n\n" + direct.rstrip() + "\n\n" + runtime_body,
            encoding="utf-8",
            newline="\n",
        )
        shutil.copy2(driver, stage / "cd" / _DRIVER_CD)
        (stage / "cd" / _MAP_CD).write_bytes(map_payload)
        for bank in families.banks:
            (stage / "cd" / bank.filename).write_bytes(bank.payload)

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "sbl_midi_calibration_candidate": True,
                "sbl_midi_calibration_consolidated": True,
                "gate3f_fidelity_policy": True,
                "hardware_executed_during_build": False,
                "raw_scsp_audio_callbacks_disabled": False,
                "screen_owned_sbl_lifecycle": True,
                "silent_placeholder_gm_voices": False,
            }
        )
        candidate_manifest["policy"] = policy
        candidate_manifest["sbl_midi_calibration"] = {
            "schema": "srk.saturn.sbl-midi-calibration-consolidated.v1",
            "sound_driver": {"path": str(driver), "sha256": assets.sound_driver_sha256},
            "soundfont": {"path": str(families.source_path), "sha256": families.source_sha256},
            "area_map": {
                "sha256": assets.area_map_sha256,
                "bytes": len(map_payload),
                "bank0_start": _TONE_START,
                "reserved_bytes": families.max_bank_bytes,
            },
            "families": [
                {
                    "family": bank.family,
                    "filename": bank.filename,
                    "programs": list(bank.programs),
                    "bytes": bank.size,
                    "sha256": bank.sha256,
                    "velocity_amounts": list(bank.velocity_amounts),
                }
                for bank in families.banks
            ],
            "sega_snd": {"path": str(sound_library), "sha256": assets.sega_sound_library_sha256},
            "direct_midi": {
                "sequence": 2,
                "priority": 0,
                "melodic_channel": 0,
                "bank_select_controller": 32,
                "loaded_bank": 0,
                "family_local_voice": True,
                "pan_controller": 10,
                "reference_note": 60,
                "reference_velocity": 100,
                "reference_pan": 64,
            },
            "telemetry": {
                "driver_error_address": f"0x{_DRIVER_ERROR_ADDRESS:08X}",
                "command_history_offset_address": f"0x{_COMMAND_HISTORY_OFFSET_ADDRESS:08X}",
                "cpu_error_address": f"0x{_CPU_ERROR_ADDRESS:08X}",
                "command_history_proves_driver_execution": True,
            },
            "review_persistence_bound": False,
            "raw_scsp_audio_callbacks_disabled": False,
            "screen_owned_sbl_lifecycle": True,
            "off_card_only": True,
        }
        candidate_manifest["generated_files"] = _gm._inventory(stage)
        (stage / _MANIFEST).write_text(
            json.dumps(candidate_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        stage.replace(output)
        temp_root.rmdir()
    except BaseException:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    before = (_gm._sha(driver), _gm._sha(sound_library), sha256(families.source_path.read_bytes()).hexdigest())
    with _gm._sound_link(sound_library):
        build = _build.build_saturn_standalone_project(output)
    after = (_gm._sha(driver), _gm._sha(sound_library), sha256(families.source_path.read_bytes()).hexdigest())
    if before != after:
        raise SaturnSblMidiCalibrationConsolidatedError(
            "external sound inputs changed during build"
        )
    if not build.successful:
        raise SaturnSblMidiCalibrationConsolidatedError(
            f"consolidated calibration build failed; see {build.log_path}"
        )
    return SaturnSblMidiCalibrationCandidateResult(output, assets, families, build)
