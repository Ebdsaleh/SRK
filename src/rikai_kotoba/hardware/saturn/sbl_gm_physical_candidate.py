"""Build the first real Sega Sound-Driver/Direct-MIDI Space Spectre candidate.

R26-R28 remain transport/SCSP bring-up proofs.  This candidate deliberately
uses Sega's SDDRVS.TSK, ``sega_snd.a``, Direct MIDI, and two external Sega-
compatible GM tone banks: bank 0 for melodic programs and bank 1 for the GM
percussion map.  No synthetic SRK timbre is used.

Private Sega assets are discovered/read from the user's Saturn development tree,
recorded by hash, copied only into the fresh generated project, and never added
to the SRK repository.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import tempfile

from . import standalone_build as _build
from .midi_68k_r24_physical_candidate import (
    SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ,
    SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ,
    SATURN_MIDI_68K_R24_FRT_TCR_ADDRESS,
    SATURN_MIDI_68K_R24_VDP2_TVMD_ADDRESS,
    SATURN_MIDI_68K_R24_VDP2_TVSTAT_ADDRESS,
)
from .midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from .sbl_direct_midi import srkm_program_to_sbl_direct_midi
from .sbl_direct_midi_compile_probe import _resolve_sdk_file


class SaturnSblGmCandidateError(RuntimeError):
    pass


@dataclass(frozen=True)
class SaturnSblGmAssets:
    sound_driver: Path
    sound_driver_sha256: str
    melodic_tone_bank: Path
    melodic_tone_bank_sha256: str
    drum_tone_bank: Path
    drum_tone_bank_sha256: str
    sega_sound_library: Path
    sega_sound_library_sha256: str


@dataclass(frozen=True)
class SaturnSblGmCandidateResult:
    project_root: Path
    assets: SaturnSblGmAssets
    record_count: int
    duration_us: int
    build: _build.SaturnStandaloneBuildResult


_DRIVER_CD = "SDDRVS.TSK"
_MAP_CD = "SRKMAP.BIN"
_MELODIC_CD = "SRKGM.BIN"
_DRUM_CD = "SRKDRUM.BIN"
_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_TONE_START = 0x0000B000
_SOUND_RAM_END = 0x00080000
_PERCUSSION_CHANNEL = 9
_DRUM_BANK = 1
_DRUM_PROGRAM = 0
_SKIP = {".git", ".svn", "__pycache__", "node_modules", "build"}
_GM = re.compile(r"(^|[^a-z0-9])gm([^a-z0-9]|$)", re.I)


def _root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "integrations" / "saturn" / "standalone").is_dir():
            return parent
    raise SaturnSblGmCandidateError("cannot locate SRK repository root")


def _path(value: os.PathLike[str] | str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk(root: Path):
    depth0 = len(root.parts)
    for current_text, dirs, files in os.walk(root):
        current = Path(current_text)
        depth = len(current.parts) - depth0
        dirs[:] = [
            name for name in sorted(dirs, key=str.casefold)
            if name.casefold() not in _SKIP and depth < 12
        ]
        for name in sorted(files, key=str.casefold):
            candidate = current / name
            try:
                if candidate.is_file():
                    yield candidate.resolve(strict=False)
            except OSError:
                pass


def _driver(root: Path, explicit) -> Path:
    if explicit is not None:
        result = _path(explicit)
        if not result.is_file() or result.name.casefold() != "sddrvs.tsk":
            raise SaturnSblGmCandidateError(f"real Saturn sound driver must be SDDRVS.TSK: {result}")
        return result
    values = [p for p in _walk(root) if p.name.casefold() == "sddrvs.tsk"]
    if not values:
        raise SaturnSblGmCandidateError(f"SDDRVS.TSK was not found under {root}")
    def score(p: Path):
        text = p.as_posix().casefold()
        value = (80 if "sbl_601" in text else 0) + (40 if "segalib" in text else 0)
        value += 40 if "segasmp/snd" in text else 0
        value += 5 if "saturnorbit-inspect" not in text else 0
        return (-value, text)
    return sorted(values, key=score)[0]


def _bank_score(path: Path, drum: bool) -> int:
    try:
        size = path.stat().st_size
    except OSError:
        return -10000
    if path.suffix.casefold() != ".bin" or not (0 < size <= _SOUND_RAM_END - _TONE_START):
        return -10000
    text = path.as_posix().casefold()
    if path.name.casefold() in {"0.bin", "ip.bin", "srkpcm.bin"}:
        return -10000
    if "srk-diagnostics" in text or "/saroo/" in text:
        return -10000
    gm = (
        "general midi" in text or "general-midi" in text or "general_midi" in text
        or _GM.search(text) is not None or path.name.casefold().startswith("gm")
    )
    is_drum = any(word in text for word in ("drum", "rhythm", "percussion", "perc", "kit"))
    value = 170 if gm else 0
    value += 60 if "tone" in text else 0
    value += 45 if "bank" in text else 0
    value += 20 if "sound" in text else 0
    value += 20 if "dts" in text else 0
    value += 20 if size >= 8192 else 0
    if drum:
        value += 240 if is_drum else -120
    else:
        value += 80 if gm else 0
        value -= 260 if is_drum else 0
    return value


def _bank_listing(root: Path, drum: bool) -> str:
    values = [(_bank_score(p, drum), p) for p in _walk(root)]
    values = [(s, p) for s, p in values if s > -10000]
    values.sort(key=lambda item: (-item[0], item[1].as_posix().casefold()))
    if not values:
        return "  [no plausible .BIN tone-bank files found]"
    return "\n".join(
        f"  {score:4d}  {path}  ({path.stat().st_size} bytes)"
        for score, path in values[:20]
    )


def _bank(root: Path, explicit, drum: bool) -> Path:
    label = "GM drum-kit tone bank" if drum else "GM melodic tone bank"
    if explicit is not None:
        result = _path(explicit)
        if not result.is_file():
            raise SaturnSblGmCandidateError(f"{label} is not a file: {result}")
        return result
    threshold = 220 if drum else 260
    values = [(_bank_score(p, drum), p) for p in _walk(root)]
    values = [(score, p) for score, p in values if score >= threshold]
    values.sort(key=lambda item: (-item[0], item[1].as_posix().casefold()))
    if not values:
        option = "--drum-tone-bank" if drum else "--melodic-tone-bank"
        raise SaturnSblGmCandidateError(
            f"no high-confidence {label} was found; refusing to fake it.\n"
            f"Best local candidates:\n{_bank_listing(root, drum)}\n"
            f"Re-run this same candidate build with {option} <real-bank.bin>."
        )
    best = values[0][0]
    tied = [path for score, path in values if score == best]
    if len(tied) != 1:
        option = "--drum-tone-bank" if drum else "--melodic-tone-bank"
        raise SaturnSblGmCandidateError(
            f"{label} selection is ambiguous; refusing to guess.\n"
            f"Best local candidates:\n{_bank_listing(root, drum)}\n"
            f"Re-run with {option} <real-bank.bin>."
        )
    return tied[0]


def _align4(value: int) -> int:
    return (value + 3) & ~3


def _area_map(melodic_size: int, drum_size: int) -> tuple[bytes, int]:
    drum_start = _align4(_TONE_START + melodic_size)
    if melodic_size <= 0 or drum_size <= 0 or drum_start + drum_size > _SOUND_RAM_END:
        raise SaturnSblGmCandidateError(
            "GM instrument + drum banks do not fit Saturn Sound RAM B000h..7FFFFh: "
            f"melodic={melodic_size}, drum={drum_size}"
        )
    def entry(bank: int, start: int, size: int) -> bytes:
        return bytes((
            0x00, bank & 0xFF,
            (start >> 16) & 0xFF, (start >> 8) & 0xFF, start & 0xFF,
            (size >> 16) & 0xFF, (size >> 8) & 0xFF, size & 0xFF,
        ))
    return entry(0, _TONE_START, melodic_size) + entry(1, drum_start, drum_size) + b"\xFF\xFF\xFF\xFF", drum_start


def _header(driver: int, melodic: int, drum: int, melodic_name: str, drum_name: str,
            melodic_sha: str, drum_sha: str, duration: int) -> str:
    melodic_name = melodic_name.replace("\\", "/").replace('"', "'")[-26:]
    drum_name = drum_name.replace("\\", "/").replace('"', "'")[-26:]
    return f'''#ifndef SRK_SATURN_SBL_GM_CANDIDATE_H
#define SRK_SATURN_SBL_GM_CANDIDATE_H
#define SRK_SBL_GM_DRIVER_BYTES {driver}UL
#define SRK_SBL_GM_MAP_BYTES 20UL
#define SRK_SBL_GM_TONE_BYTES {melodic}UL
#define SRK_SBL_GM_DRUM_BYTES {drum}UL
#define SRK_SBL_GM_RECORD_COUNT 9154UL
#define SRK_SBL_GM_DURATION_US {duration}UL
#define SRK_SBL_GM_TONE_LABEL "{melodic_name}"
#define SRK_SBL_GM_DRUM_LABEL "{drum_name}"
#define SRK_SBL_GM_TONE_SHA12 "{melodic_sha[:12]}"
#define SRK_SBL_GM_DRUM_SHA12 "{drum_sha[:12]}"
#define SRK_SBL_GM_NOT_STARTED 0u
#define SRK_SBL_GM_PRIMING 1u
#define SRK_SBL_GM_PLAYING 2u
#define SRK_SBL_GM_PASS 3u
#define SRK_SBL_GM_STOPPED 4u
#define SRK_SBL_GM_ERROR 5u
typedef struct SRK_SBL_GM_STATE {{
 unsigned int attempted,status,error,last_ret,prime;
 unsigned long event_index,retries,clock_us,source_hz,ticks,origin;
 unsigned short last_counter;
 unsigned char original_tcr,frt_configured,sound_initialized;
}} SRK_SBL_GM_STATE;
void srk_saturn_sbl_gm_reset(SRK_SBL_GM_STATE *s);
unsigned int srk_saturn_sbl_gm_begin(SRK_SBL_GM_STATE *s);
unsigned int srk_saturn_sbl_gm_poll(SRK_SBL_GM_STATE *s);
void srk_saturn_sbl_gm_stop(SRK_SBL_GM_STATE *s);
#endif
'''


def _runtime(profile, assets: SaturnSblGmAssets) -> str:
    commands = list(srkm_program_to_sbl_direct_midi(profile.program, seq_no=2, seq_pri=0))
    if len(commands) != 9154:
        raise SaturnSblGmCandidateError(f"Space Spectre Direct-MIDI count changed: {len(commands)}")
    # GM channel 10 is percussion.  Sega Direct MIDI is channel-agnostic, so
    # bind it to dedicated tone bank 1 / voice 0.  A source channel-10 Program
    # Change is normalized to drum voice 0 instead of selecting a melodic voice.
    for index, cmd in enumerate(commands):
        if cmd.channel == _PERCUSSION_CHANNEL and cmd.midi_command == 4:
            commands[index] = type(cmd)(cmd.time_us, cmd.seq_no, cmd.seq_pri, cmd.midi_command,
                                        cmd.channel, _DRUM_PROGRAM, 0)
    melodic_channels = sorted({cmd.channel for cmd in commands if cmd.channel != _PERCUSSION_CHANNEL})
    events = "\n".join(
        f" {{{cmd.time_us}UL,{cmd.midi_command}u,{cmd.channel}u,{cmd.data1}u,{cmd.data2}u}},"
        for cmd in commands
    )
    channel_values = ",".join(f"{value}u" for value in melodic_channels)
    return f'''#include "srk_saturn_sbl_gm_candidate.h"
#include "srk_saturn_sbl_direct_midi.h"
#include "SEGA_GFS.H"
#include "sega_snd.h"
#define FRC_H (*(volatile unsigned char *)0xFFFFFE12UL)
#define FRC_L (*(volatile unsigned char *)0xFFFFFE13UL)
#define FRT_TCR (*(volatile unsigned char *)0x{SATURN_MIDI_68K_R24_FRT_TCR_ADDRESS:08X}UL)
#define TVMD (*(volatile unsigned short *)0x{SATURN_MIDI_68K_R24_VDP2_TVMD_ADDRESS:08X}UL)
#define TVSTAT (*(volatile unsigned short *)0x{SATURN_MIDI_68K_R24_VDP2_TVSTAT_ADDRESS:08X}UL)
#define FRT_DIV 128UL
#define FRT_DIV128 0x02u
#define GFS_OPEN_MAX 2
#define GFS_MAX_DIR 32
#define ERR_GFS 1u
#define ERR_DRIVER 2u
#define ERR_MAP_LOAD 3u
#define ERR_TONE 4u
#define ERR_MAP 5u
#define ERR_MIX 6u
#define ERR_VOLUME 7u
#define ERR_TIMEOUT 8u
typedef struct EV {{ unsigned long t; unsigned char c,ch,d1,d2; }} EV;
static Uint32 gfs_work[GFS_WORK_SIZE(GFS_OPEN_MAX)/sizeof(Uint32)];
static GfsDirTbl gfs_table;
static GfsDirName gfs_names[GFS_MAX_DIR];
static Uint32 drv[(SRK_SBL_GM_DRIVER_BYTES+3UL)/4UL];
static Uint32 amap[(SRK_SBL_GM_MAP_BYTES+3UL)/4UL];
static Uint32 tone[(SRK_SBL_GM_TONE_BYTES+3UL)/4UL];
static Uint32 drum[(SRK_SBL_GM_DRUM_BYTES+3UL)/4UL];
static const unsigned char melodic_channels[]={{ {channel_values} }};
static const EV ev[SRK_SBL_GM_RECORD_COUNT]={{
{events}
}};
static int load_file(const char *name,Uint32 *dst,unsigned long bytes){{
 Sint32 id,n; id=GFS_NameToId((Sint8 *)name); if(id<0)return 0;
 n=GFS_Load(id,0,dst,(Sint32)bytes); return n==(Sint32)bytes;
}}
static unsigned long clock_source(void){{
 unsigned short pal=(unsigned short)(TVSTAT&1u), b=(unsigned short)(TVMD&1u);
 if(pal)return b?{SATURN_MIDI_68K_R24_CLOCK_PAL_B_HZ}UL:{SATURN_MIDI_68K_R24_CLOCK_PAL_A_HZ}UL;
 return b?{SATURN_MIDI_68K_R24_CLOCK_NTSC_B_HZ}UL:{SATURN_MIDI_68K_R24_CLOCK_NTSC_A_HZ}UL;
}}
static unsigned short frc(void){{ unsigned char a,b,l; do{{a=FRC_H;l=FRC_L;b=FRC_H;}}while(a!=b); return (unsigned short)(((unsigned short)b<<8)|l); }}
static void clock_begin(SRK_SBL_GM_STATE *s){{
 unsigned short c; s->source_hz=clock_source(); s->original_tcr=FRT_TCR;
 FRT_TCR=(unsigned char)((s->original_tcr&0xFCu)|FRT_DIV128); s->frt_configured=1u;
 c=frc(); s->last_counter=c; s->ticks=(unsigned long)c; s->origin=(unsigned long)c; s->clock_us=0UL;
}}
static void clock_restore(SRK_SBL_GM_STATE *s){{ if(s&&s->frt_configured){{FRT_TCR=s->original_tcr;s->frt_configured=0u;}} }}
static void clock_sample(SRK_SBL_GM_STATE *s){{
 unsigned short c=frc(); unsigned long d,elapsed; unsigned long long n;
 d=c>=s->last_counter?(unsigned long)(c-s->last_counter):65536UL-(unsigned long)s->last_counter+(unsigned long)c;
 s->last_counter=c; s->ticks+=d; elapsed=s->ticks-s->origin;
 n=(unsigned long long)elapsed*1000000ULL*FRT_DIV;
 s->clock_us=(unsigned long)(n/(unsigned long long)s->source_hz);
}}
static void fail(SRK_SBL_GM_STATE *s,unsigned int e){{ clock_restore(s);s->error=e;s->status=SRK_SBL_GM_ERROR; }}
void srk_saturn_sbl_gm_reset(SRK_SBL_GM_STATE *s){{ if(!s)return; memset(s,0,sizeof(*s));s->status=SRK_SBL_GM_NOT_STARTED; }}
unsigned int srk_saturn_sbl_gm_begin(SRK_SBL_GM_STATE *s){{
 SndIniDt ini; SndRet r; Sint32 g;
 if(!s)return 0u; s->attempted=1u;s->status=SRK_SBL_GM_NOT_STARTED;s->error=0u;s->event_index=0UL;s->retries=0UL;s->prime=0u;
 GFS_DIRTBL_TYPE(&gfs_table)=GFS_DIR_NAME;GFS_DIRTBL_NDIR(&gfs_table)=GFS_MAX_DIR;GFS_DIRTBL_DIRNAME(&gfs_table)=gfs_names;
 g=GFS_Init(GFS_OPEN_MAX,gfs_work,&gfs_table); if(g<0){{fail(s,ERR_GFS);return 0u;}}
 if(!load_file("{_DRIVER_CD}",drv,SRK_SBL_GM_DRIVER_BYTES)){{fail(s,ERR_DRIVER);return 0u;}}
 if(!load_file("{_MAP_CD}",amap,SRK_SBL_GM_MAP_BYTES)){{fail(s,ERR_MAP_LOAD);return 0u;}}
 if(!load_file("{_MELODIC_CD}",tone,SRK_SBL_GM_TONE_BYTES)){{fail(s,ERR_TONE);return 0u;}}
 if(!load_file("{_DRUM_CD}",drum,SRK_SBL_GM_DRUM_BYTES)){{fail(s,ERR_TONE);return 0u;}}
 SND_INI_PRG_ADR(ini)=(Uint16 *)drv;SND_INI_PRG_SZ(ini)=(Uint16)SRK_SBL_GM_DRIVER_BYTES;
 SND_INI_ARA_ADR(ini)=(Uint16 *)amap;SND_INI_ARA_SZ(ini)=(Uint16)SRK_SBL_GM_MAP_BYTES;SND_Init(&ini);s->sound_initialized=1u;
 r=SND_ChgMap(0);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{fail(s,ERR_MAP);return 0u;}}
 SND_MoveData((Uint16 *)tone,(Uint32)SRK_SBL_GM_TONE_BYTES,SND_KD_TONE,0);
 SND_MoveData((Uint16 *)drum,(Uint32)SRK_SBL_GM_DRUM_BYTES,SND_KD_TONE,1);
 r=SND_ChgMix(0,0);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{fail(s,ERR_MIX);return 0u;}}
 r=SND_SetTlVl(15);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{fail(s,ERR_VOLUME);return 0u;}}
 s->status=SRK_SBL_GM_PRIMING;return 1u;
}}
unsigned int srk_saturn_sbl_gm_poll(SRK_SBL_GM_STATE *s){{
 SndRet r; const EV *e; if(!s)return 0u;
 if(s->status==SRK_SBL_GM_PRIMING){{
  if(s->prime<{len(melodic_channels)}u){{r=srk_saturn_sbl_direct_midi(2,0,3,melodic_channels[s->prime],0x20,0);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{s->retries++;return 0u;}}s->prime++;return 0u;}}
  if(s->prime=={len(melodic_channels)}u){{r=srk_saturn_sbl_direct_midi(2,0,3,9,0x20,1);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{s->retries++;return 0u;}}s->prime++;return 0u;}}
  if(s->prime=={len(melodic_channels)+1}u){{r=srk_saturn_sbl_direct_midi(2,0,4,9,0,0);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{s->retries++;return 0u;}}s->prime++;return 0u;}}
  clock_begin(s);s->status=SRK_SBL_GM_PLAYING;return 0u;
 }}
 if(s->status!=SRK_SBL_GM_PLAYING)return s->status==SRK_SBL_GM_PASS;
 clock_sample(s);
 while(s->event_index<SRK_SBL_GM_RECORD_COUNT){{e=&ev[s->event_index];if(e->t>s->clock_us)break;r=srk_saturn_sbl_direct_midi(2,0,e->c,e->ch,e->d1,e->d2);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{s->retries++;return 0u;}}s->event_index++;}}
 if(s->event_index>=SRK_SBL_GM_RECORD_COUNT){{clock_restore(s);s->status=SRK_SBL_GM_PASS;return 1u;}}
 if(s->clock_us>SRK_SBL_GM_DURATION_US+10000000UL)fail(s,ERR_TIMEOUT);return 0u;
}}
void srk_saturn_sbl_gm_stop(SRK_SBL_GM_STATE *s){{ if(!s)return;clock_restore(s);if(s->sound_initialized)(void)SND_OffAllSound();if(s->status!=SRK_SBL_GM_ERROR)s->status=SRK_SBL_GM_STOPPED; }}
'''


def _main(base: str) -> str:
    include = '#include "srk_saturn_host.h"\n'
    state = 'static SRK_SATURN_HOST_STATE srk_host_state;\n'
    init = '    srk_diag_app_reset(&srk_app);\n'
    loop = '        srk_diag_app_frame(&srk_app, &srk_host);\n'
    if any(base.count(anchor) != 1 for anchor in (include, state, init, loop)):
        raise SaturnSblGmCandidateError("generic Saturn main anchors changed")
    base = base.replace(include, include + '#include "srk_saturn_sbl_gm_candidate.h"\n', 1)
    block = r'''
static SRK_SBL_GM_STATE srk_gm;
static void gm_num(char out[11],srk_u32 v){char r[10];int n=0,i;if(!v){out[0]='0';out[1]=0;return;}while(v&&n<10){r[n++]=(char)('0'+v%10u);v/=10u;}for(i=0;i<n;i++)out[i]=r[n-i-1];out[n]=0;}
static void gm_field(int x,int y,int w,const char *t){char b[41];int i;if(!srk_host.draw_text)return;if(w>40)w=40;for(i=0;i<w;i++)b[i]=' ';b[w]=0;if(t)for(i=0;i<w&&t[i];i++)b[i]=t[i];srk_host.draw_text(srk_host.context,x,y,b);}
static const char *gm_status(unsigned int s){switch(s){case SRK_SBL_GM_NOT_STARTED:return "NOT STARTED";case SRK_SBL_GM_PRIMING:return "PRIMING";case SRK_SBL_GM_PLAYING:return "PLAYING";case SRK_SBL_GM_PASS:return "PASS";case SRK_SBL_GM_STOPPED:return "STOPPED";case SRK_SBL_GM_ERROR:return "ERROR";}return "?";}
static void gm_render(void){char n[11];gm_field(2,1,36,"SEGA DIRECT MIDI / REAL GM");gm_field(2,2,36,SRK_SBL_GM_TONE_LABEL);gm_field(2,3,36,SRK_SBL_GM_DRUM_LABEL);gm_field(2,5,10,"Status:");gm_field(12,5,20,gm_status(srk_gm.status));gm_num(n,(srk_u32)srk_gm.event_index);gm_field(2,7,9,"Events:");gm_field(11,7,10,n);gm_field(22,7,10,"/ 9154");gm_num(n,(srk_u32)srk_gm.retries);gm_field(2,8,9,"Retries:");gm_field(11,8,10,n);gm_num(n,(srk_u32)srk_gm.error);gm_field(2,9,9,"Error:");gm_field(11,9,10,n);if(srk_gm.status==SRK_SBL_GM_PASS)gm_field(2,12,36,"PASS: Sega driver accepted 9154 events");else if(srk_gm.status==SRK_SBL_GM_ERROR)gm_field(2,12,36,"ERROR: preserve this screen");else gm_field(2,12,36,"Space Spectre via Sega sound driver");gm_field(2,17,36,"START: stop + return to menu");}
static void gm_frame(void){int active=srk_app.menu.active&&srk_app.menu.active_screen==SRK_DIAG_SCREEN_TIMING_INTERRUPT_TEST;if(!active){if(srk_gm.attempted)srk_saturn_sbl_gm_stop(&srk_gm);srk_saturn_sbl_gm_reset(&srk_gm);return;}if(!srk_gm.attempted)(void)srk_saturn_sbl_gm_begin(&srk_gm);if(srk_gm.status==SRK_SBL_GM_PRIMING||srk_gm.status==SRK_SBL_GM_PLAYING)(void)srk_saturn_sbl_gm_poll(&srk_gm);gm_render();}
'''
    base = base.replace(state, state + '\n' + block + '\n', 1)
    base = base.replace(init, init + '    srk_saturn_sbl_gm_reset(&srk_gm);\n', 1)
    base = base.replace(loop, loop + '        gm_frame();\n', 1)
    return base


def _inventory(root: Path) -> list[dict[str, object]]:
    result=[]
    for path in sorted(root.rglob("*"),key=lambda p:str(p).casefold()):
        if not path.is_file() or path.name==_MANIFEST: continue
        rel=path.relative_to(root).as_posix()
        if rel=="SRK_STANDALONE_BUILD.json" or rel.startswith("build/"): continue
        result.append({"path":rel,"size":path.stat().st_size,"sha256":_sha(path)})
    return result


def _copy_baseline(baseline: Path, staging: Path, manifest: dict) -> None:
    entries=manifest.get("generated_files")
    if not isinstance(entries,list): raise SaturnSblGmCandidateError("baseline generated_files missing")
    for entry in entries:
        if not isinstance(entry,dict) or not isinstance(entry.get("path"),str): continue
        rel=entry["path"]
        if rel=="cd/0.bin" or rel.startswith("build/"): continue
        src=baseline/rel
        if not src.is_file(): raise SaturnSblGmCandidateError(f"baseline input missing: {rel}")
        expected=entry.get("sha256")
        if isinstance(expected,str) and _sha(src).lower()!=expected.lower(): raise SaturnSblGmCandidateError(f"baseline hash mismatch: {rel}")
        dst=staging/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)


@contextmanager
def _sound_link(library: Path):
    original=_build._stage6b_link_tail
    _build._stage6b_link_tail=lambda deps:(str(library),*original(deps))
    try: yield
    finally: _build._stage6b_link_tail=original


def build_saturn_sbl_gm_candidate(baseline_project, saturn_root, output_directory, *,
                                  melodic_tone_bank=None, drum_tone_bank=None, sound_driver=None) -> SaturnSblGmCandidateResult:
    baseline,saturn_root,output=map(_path,(baseline_project,saturn_root,output_directory))
    if not baseline.is_dir(): raise SaturnSblGmCandidateError(f"baseline project missing: {baseline}")
    if not saturn_root.is_dir(): raise SaturnSblGmCandidateError(f"Saturn root missing: {saturn_root}")
    if output.exists(): raise SaturnSblGmCandidateError(f"output already exists; refusing overwrite: {output}")
    manifest_path=baseline/_MANIFEST
    if not manifest_path.is_file(): raise SaturnSblGmCandidateError(f"baseline manifest missing: {manifest_path}")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    repo=_root();profile=build_srk_saturn_midi_68k_r26_space_spectre_profile(repo)
    if profile.member_sha256!=SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256 or profile.record_count!=9154 or profile.note_on_count!=4381 or profile.note_off_count!=4381:
        raise SaturnSblGmCandidateError("Space Spectre source/profile changed")
    drv=_driver(saturn_root,sound_driver);tone=_bank(saturn_root,melodic_tone_bank,False);drum=_bank(saturn_root,drum_tone_bank,True)
    if tone==drum: raise SaturnSblGmCandidateError("melodic and drum banks resolved to same file; refusing to guess")
    snd=_resolve_sdk_file(saturn_root,"sega_snd.a",kind="library")
    assets=SaturnSblGmAssets(drv,_sha(drv),tone,_sha(tone),drum,_sha(drum),snd,_sha(snd))
    map_bytes,drum_start=_area_map(tone.stat().st_size,drum.stat().st_size)
    standalone=repo/"integrations"/"saturn"/"standalone";diagnostics=repo/"integrations"/"saturn"/"diagnostics"
    main=_main((standalone/"srk_saturn_main.c").read_text(encoding="utf-8"))
    menu=(diagnostics/"srk_diag_menu.c").read_text(encoding="utf-8").replace('"Timing / Interrupt Test"','"SEGA Direct MIDI / GM"',1)
    runtime=(standalone/"srk_saturn_runtime.c").read_text(encoding="utf-8")
    direct=(standalone/"srk_saturn_sbl_direct_midi.c").read_text(encoding="utf-8")
    direct_h=(standalone/"srk_saturn_sbl_direct_midi.h").read_text(encoding="utf-8")
    header=_header(drv.stat().st_size,tone.stat().st_size,drum.stat().st_size,tone.name,drum.name,assets.melodic_tone_bank_sha256,assets.drum_tone_bank_sha256,profile.duration_us)
    body=_runtime(profile,assets)
    output.parent.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix=f".{output.name}.",dir=str(output.parent)));stage=tmp/"stage";stage.mkdir()
    try:
        _copy_baseline(baseline,stage,manifest);(stage/"build").mkdir(exist_ok=True);(stage/"cd").mkdir(exist_ok=True)
        (stage/"src/srk_saturn_main.c").write_text(main,encoding="utf-8",newline="\n")
        (stage/"src/srk_diag_menu.c").write_text(menu,encoding="utf-8",newline="\n")
        (stage/"src/srk_saturn_sbl_direct_midi.h").write_text(direct_h,encoding="utf-8",newline="\n")
        (stage/"src/srk_saturn_sbl_gm_candidate.h").write_text(header,encoding="utf-8",newline="\n")
        (stage/"src/srk_saturn_runtime.c").write_text(runtime.rstrip()+"\n\n"+direct.rstrip()+"\n\n"+body,encoding="utf-8",newline="\n")
        shutil.copy2(drv,stage/"cd"/_DRIVER_CD);(stage/"cd"/_MAP_CD).write_bytes(map_bytes);shutil.copy2(tone,stage/"cd"/_MELODIC_CD);shutil.copy2(drum,stage/"cd"/_DRUM_CD)
        m=dict(manifest);policy=dict(m.get("policy") or {});policy.update({"sd_writes":False,"sbl_direct_midi_gm_candidate":True,"synthetic_r26_r28_timbres_used":False,"hardware_executed_during_build":False});m["policy"]=policy
        m["sbl_direct_midi_gm"]={"schema":"srk.saturn.sbl-direct-midi-gm-candidate.v1","source_midi_sha256":profile.member_sha256,"record_count":9154,"duration_us":profile.duration_us,"percussion_channel_zero_based":9,"percussion_notes":list(profile.percussion_notes),"sound_driver":{"path":str(drv),"sha256":assets.sound_driver_sha256},"area_map":{"sha256":sha256(map_bytes).hexdigest(),"bank0_start":_TONE_START,"bank1_start":drum_start},"melodic_bank":{"path":str(tone),"sha256":assets.melodic_tone_bank_sha256,"bank":0},"drum_bank":{"path":str(drum),"sha256":assets.drum_tone_bank_sha256,"bank":1,"program":0,"gm_note_map_preserved":True},"sega_snd":{"path":str(snd),"sha256":assets.sega_sound_library_sha256},"channel10_program_changes_normalized_to_drum_voice":True,"off_card_only":True}
        m["generated_files"]=_inventory(stage);(stage/_MANIFEST).write_text(json.dumps(m,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
        stage.replace(output);tmp.rmdir()
    except BaseException:
        shutil.rmtree(tmp,ignore_errors=True);raise
    before=(_sha(drv),_sha(tone),_sha(drum),_sha(snd))
    with _sound_link(snd): build=_build.build_saturn_standalone_project(output)
    if before!=(_sha(drv),_sha(tone),_sha(drum),_sha(snd)): raise SaturnSblGmCandidateError("external sound inputs changed during build")
    if not build.successful: raise SaturnSblGmCandidateError(f"candidate build failed; see {build.log_path}")
    return SaturnSblGmCandidateResult(output,assets,9154,profile.duration_us,build)
