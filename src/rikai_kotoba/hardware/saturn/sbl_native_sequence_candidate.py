"""Build Space Spectre as a native Sega SDDRV sequence playback candidate.

This is the production-style successor to the Direct-MIDI GATE2 transport proof.
The SH-2 loads authored tone and sequence banks, starts one SDDRV sequence, and
then only observes driver status.  It never clocks or streams individual MIDI
events.

The builder intentionally reuses the already-generated real GeneralUser-derived
tone banks and real SDDRV from the user's successful GATE2 project, but replaces
the old guessed map with Sega's external .MP representation and adds a sequence
area containing the host-converted SPACESEQ.BNK.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import tempfile

from . import standalone_build as _build
from . import sbl_gm_physical_candidate as _gm
from .midi_68k_r26_double_impact import (
    SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256,
    build_srk_saturn_midi_68k_r26_space_spectre_profile,
)
from .sbl_direct_midi_compile_probe import _resolve_sdk_file
from .sbl_sequence import (
    SBL_AREA_SEQUENCE,
    SBL_AREA_TONE,
    SaturnSblArea,
    encode_sbl_external_area_map,
)
from .sbl_space_spectre_sequence import BANK_NAME as SEQUENCE_BANK_NAME
from .sbl_space_spectre_sequence import MANIFEST_NAME as SEQUENCE_MANIFEST_NAME


class SaturnSblNativeSequenceCandidateError(RuntimeError):
    """Raised when the native-sequence hardware candidate cannot be built safely."""


@dataclass(frozen=True)
class SaturnSblNativeSequenceAssets:
    sound_driver_sha256: str
    melodic_tone_bank_sha256: str
    drum_tone_bank_sha256: str
    sequence_bank_sha256: str
    sega_sound_library_sha256: str
    area_map_sha256: str
    melodic_start: int
    drum_start: int
    sequence_start: int


@dataclass(frozen=True)
class SaturnSblNativeSequenceCandidateResult:
    project_root: Path
    assets: SaturnSblNativeSequenceAssets
    note_count: int
    duration_us: int
    sequence_bank_bytes: int
    build: _build.SaturnStandaloneBuildResult


_DRIVER_CD = "SDDRVS.TSK"
_MAP_CD = "SRKMAP.BIN"
_MELODIC_CD = "SRKGM.BIN"
_DRUM_CD = "SRKDRUM.BIN"
_SEQUENCE_CD = "SPACESEQ.BNK"
_PROJECT_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_TONE_START = 0x0000B000
_SOUND_RAM_END = 0x00080000
_SEQUENCE_NUMBER = 1
_SEQUENCE_BANK = 0
_SEQUENCE_SONG = 0
_SEQUENCE_PRIORITY = 1


def _sha_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise SaturnSblNativeSequenceCandidateError(f"{label} missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SaturnSblNativeSequenceCandidateError(f"{label} is invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SaturnSblNativeSequenceCandidateError(f"{label} must contain a JSON object: {path}")
    return value


def _expected_file_hash(project: Path, manifest: dict, relative: str) -> str:
    entries = manifest.get("generated_files")
    if not isinstance(entries, list):
        raise SaturnSblNativeSequenceCandidateError("baseline generated_files missing")
    matches = [
        entry for entry in entries
        if isinstance(entry, dict) and entry.get("path") == relative
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("sha256"), str):
        raise SaturnSblNativeSequenceCandidateError(
            f"baseline manifest does not uniquely hash {relative}"
        )
    path = project / relative
    actual = _gm._sha(path) if path.is_file() else ""
    expected = matches[0]["sha256"].lower()
    if actual.lower() != expected:
        raise SaturnSblNativeSequenceCandidateError(
            f"baseline input hash mismatch for {relative}: {actual} != {expected}"
        )
    return actual


def _validate_baseline(project: Path) -> tuple[dict, Path, Path, Path]:
    manifest = _read_json(project / _PROJECT_MANIFEST, "baseline project manifest")
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or policy.get("synthetic_r26_r28_timbres_used") is not False:
        raise SaturnSblNativeSequenceCandidateError(
            "baseline is not locked as a real non-synthetic GM candidate"
        )
    driver = project / "cd" / _DRIVER_CD
    melodic = project / "cd" / _MELODIC_CD
    drum = project / "cd" / _DRUM_CD
    _expected_file_hash(project, manifest, f"cd/{_DRIVER_CD}")
    _expected_file_hash(project, manifest, f"cd/{_MELODIC_CD}")
    _expected_file_hash(project, manifest, f"cd/{_DRUM_CD}")
    if melodic == drum or not melodic.is_file() or not drum.is_file():
        raise SaturnSblNativeSequenceCandidateError("baseline tone banks are missing or aliased")
    return manifest, driver, melodic, drum


def _validate_sequence(directory: Path) -> tuple[dict, Path, str, int]:
    manifest = _read_json(directory / SEQUENCE_MANIFEST_NAME, "native sequence manifest")
    if manifest.get("schema") != "srk.saturn.sbl-space-spectre-sequence.v2":
        raise SaturnSblNativeSequenceCandidateError(
            "native sequence is not the tone-bank-bound v2 conversion"
        )
    source = manifest.get("source")
    native = manifest.get("native_sequence")
    bank_info = manifest.get("sequence_bank")
    policy = manifest.get("policy")
    if not all(isinstance(value, dict) for value in (source, native, bank_info, policy)):
        raise SaturnSblNativeSequenceCandidateError("native sequence manifest sections are missing")
    if source.get("sha256") != SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256:
        raise SaturnSblNativeSequenceCandidateError("native sequence source MIDI hash changed")
    if native.get("note_count") != 4381:
        raise SaturnSblNativeSequenceCandidateError("native sequence note count changed")
    if policy.get("direct_midi_streaming") is not False or policy.get("sh2_midi_priming") is not False:
        raise SaturnSblNativeSequenceCandidateError(
            "native sequence still depends on Direct MIDI or SH-2 priming"
        )
    bindings = native.get("tone_bank_bindings")
    if not isinstance(bindings, list):
        raise SaturnSblNativeSequenceCandidateError("native sequence tone-bank bindings missing")
    pairs = {
        (item.get("channel_zero_based"), item.get("bank"))
        for item in bindings if isinstance(item, dict)
    }
    if (9, 1) not in pairs or any(bank not in (0, 1) for _, bank in pairs):
        raise SaturnSblNativeSequenceCandidateError(
            "native sequence does not bind MIDI channel 10 to Saturn tone bank 1"
        )
    if any(channel != 9 and bank != 0 for channel, bank in pairs):
        raise SaturnSblNativeSequenceCandidateError(
            "native sequence melodic channels must use Saturn tone bank 0"
        )
    if native.get("percussion_program") != 0:
        raise SaturnSblNativeSequenceCandidateError("native sequence percussion voice must be program 0")

    filename = bank_info.get("filename")
    if filename != SEQUENCE_BANK_NAME:
        raise SaturnSblNativeSequenceCandidateError("native sequence bank filename changed")
    bank = directory / SEQUENCE_BANK_NAME
    if not bank.is_file():
        raise SaturnSblNativeSequenceCandidateError(f"native sequence bank missing: {bank}")
    actual_hash = _gm._sha(bank)
    expected_hash = bank_info.get("sha256")
    expected_bytes = bank_info.get("bytes")
    if not isinstance(expected_hash, str) or actual_hash != expected_hash:
        raise SaturnSblNativeSequenceCandidateError("native sequence bank SHA-256 mismatch")
    if not isinstance(expected_bytes, int) or expected_bytes != bank.stat().st_size:
        raise SaturnSblNativeSequenceCandidateError("native sequence bank byte count mismatch")
    if bank.read_bytes()[:6] != b"\x00\x01\x00\x00\x00\x06":
        raise SaturnSblNativeSequenceCandidateError("native sequence bank header changed")
    return manifest, bank, actual_hash, expected_bytes


def _area_map(melodic_size: int, drum_size: int, sequence_size: int) -> tuple[bytes, int, int]:
    drum_start = _gm._align4(_TONE_START + melodic_size)
    sequence_start = _gm._align4(drum_start + drum_size)
    if min(melodic_size, drum_size, sequence_size) <= 0:
        raise SaturnSblNativeSequenceCandidateError("sound-RAM assets must be non-empty")
    if sequence_start + sequence_size > _SOUND_RAM_END:
        raise SaturnSblNativeSequenceCandidateError(
            "tone + drum + native sequence banks do not fit Saturn Sound RAM "
            f"B000h..7FFFFh: melodic={melodic_size}, drum={drum_size}, "
            f"sequence={sequence_size}, end=0x{sequence_start + sequence_size:X}"
        )
    payload = encode_sbl_external_area_map(
        (
            SaturnSblArea(SBL_AREA_TONE, 0, _TONE_START, melodic_size),
            SaturnSblArea(SBL_AREA_TONE, 1, drum_start, drum_size),
            SaturnSblArea(SBL_AREA_SEQUENCE, 0, sequence_start, sequence_size),
        )
    )
    if len(payload) != 26 or payload[-2:] != b"\xFF\xFF":
        raise SaturnSblNativeSequenceCandidateError("external Sega area map encoding changed")
    return payload, drum_start, sequence_start


def _header(driver: int, area_map: int, melodic: int, drum: int, sequence: int,
            melodic_sha: str, drum_sha: str, sequence_sha: str) -> str:
    return f'''#ifndef SRK_SATURN_SBL_GM_CANDIDATE_H
#define SRK_SATURN_SBL_GM_CANDIDATE_H
#define SRK_SBL_GM_DRIVER_BYTES {driver}UL
#define SRK_SBL_GM_MAP_BYTES {area_map}UL
#define SRK_SBL_GM_TONE_BYTES {melodic}UL
#define SRK_SBL_GM_DRUM_BYTES {drum}UL
#define SRK_SBL_GM_SEQUENCE_BYTES {sequence}UL
#define SRK_SBL_GM_TONE_LABEL "GeneralUser melodic bank 0"
#define SRK_SBL_GM_DRUM_LABEL "GeneralUser drum bank 1"
#define SRK_SBL_GM_TONE_SHA12 "{melodic_sha[:12]}"
#define SRK_SBL_GM_DRUM_SHA12 "{drum_sha[:12]}"
#define SRK_SBL_GM_SEQ_SHA12 "{sequence_sha[:12]}"
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


def _runtime() -> str:
    return f'''#include "srk_saturn_sbl_gm_candidate.h"
#include "SEGA_GFS.H"
#include "sega_snd.h"
#define GFS_OPEN_MAX 2
#define GFS_MAX_DIR 32
#define ERR_GFS 1u
#define ERR_DRIVER 2u
#define ERR_MAP_LOAD 3u
#define ERR_TONE 4u
#define ERR_SEQUENCE 5u
#define ERR_MAP 6u
#define ERR_START 7u
static Uint32 gfs_work[GFS_WORK_SIZE(GFS_OPEN_MAX)/sizeof(Uint32)];
static GfsDirTbl gfs_table;
static GfsDirName gfs_names[GFS_MAX_DIR];
static Uint32 drv[(SRK_SBL_GM_DRIVER_BYTES+3UL)/4UL];
static Uint32 amap[(SRK_SBL_GM_MAP_BYTES+3UL)/4UL];
static Uint32 tone[(SRK_SBL_GM_TONE_BYTES+3UL)/4UL];
static Uint32 drum[(SRK_SBL_GM_DRUM_BYTES+3UL)/4UL];
static Uint32 sequence[(SRK_SBL_GM_SEQUENCE_BYTES+3UL)/4UL];
static int load_file(const char *name,Uint32 *dst,unsigned long bytes){{
 Sint32 id,n; id=GFS_NameToId((Sint8 *)name); if(id<0)return 0;
 n=GFS_Load(id,0,dst,(Sint32)((bytes+3UL)/4UL)); return n==(Sint32)bytes;
}}
static void fail(SRK_SBL_GM_STATE *s,unsigned int e){{s->error=e;s->status=SRK_SBL_GM_ERROR;}}
void srk_saturn_sbl_gm_reset(SRK_SBL_GM_STATE *s){{if(!s)return;memset(s,0,sizeof(*s));s->status=SRK_SBL_GM_NOT_STARTED;}}
unsigned int srk_saturn_sbl_gm_begin(SRK_SBL_GM_STATE *s){{
 SndIniDt ini;SndRet r;Sint32 g;if(!s)return 0u;
 s->attempted=1u;s->status=SRK_SBL_GM_NOT_STARTED;s->error=0u;s->prime=0u;s->event_index=0UL;s->retries=0UL;
 GFS_DIRTBL_TYPE(&gfs_table)=GFS_DIR_NAME;GFS_DIRTBL_NDIR(&gfs_table)=GFS_MAX_DIR;GFS_DIRTBL_DIRNAME(&gfs_table)=gfs_names;
 g=GFS_Init(GFS_OPEN_MAX,gfs_work,&gfs_table);if(g<0){{fail(s,ERR_GFS);return 0u;}}
 if(!load_file("{_DRIVER_CD}",drv,SRK_SBL_GM_DRIVER_BYTES)){{fail(s,ERR_DRIVER);return 0u;}}
 if(!load_file("{_MAP_CD}",amap,SRK_SBL_GM_MAP_BYTES)){{fail(s,ERR_MAP_LOAD);return 0u;}}
 if(!load_file("{_MELODIC_CD}",tone,SRK_SBL_GM_TONE_BYTES)){{fail(s,ERR_TONE);return 0u;}}
 if(!load_file("{_DRUM_CD}",drum,SRK_SBL_GM_DRUM_BYTES)){{fail(s,ERR_TONE);return 0u;}}
 if(!load_file("{_SEQUENCE_CD}",sequence,SRK_SBL_GM_SEQUENCE_BYTES)){{fail(s,ERR_SEQUENCE);return 0u;}}
 SND_INI_PRG_ADR(ini)=(Uint16 *)drv;SND_INI_PRG_SZ(ini)=(Uint16)SRK_SBL_GM_DRIVER_BYTES;
 SND_INI_ARA_ADR(ini)=(Uint16 *)amap;SND_INI_ARA_SZ(ini)=(Uint16)SRK_SBL_GM_MAP_BYTES;SND_Init(&ini);s->sound_initialized=1u;
 r=SND_ChgMap(0);s->last_ret=(unsigned int)r;if(r!=SND_RET_SET){{fail(s,ERR_MAP);return 0u;}}
 SND_MoveData((Uint16 *)tone,(Uint32)SRK_SBL_GM_TONE_BYTES,SND_KD_TONE,0);
 SND_MoveData((Uint16 *)drum,(Uint32)SRK_SBL_GM_DRUM_BYTES,SND_KD_TONE,1);
 SND_MoveData((Uint16 *)sequence,(Uint32)SRK_SBL_GM_SEQUENCE_BYTES,SND_KD_SEQ,{_SEQUENCE_BANK});
 r=SND_StartSeq({_SEQUENCE_NUMBER},{_SEQUENCE_BANK},{_SEQUENCE_SONG},{_SEQUENCE_PRIORITY});s->last_ret=(unsigned int)r;
 if(r!=SND_RET_SET){{fail(s,ERR_START);return 0u;}}
 s->status=SRK_SBL_GM_PRIMING;return 1u;
}}
unsigned int srk_saturn_sbl_gm_poll(SRK_SBL_GM_STATE *s){{
 SndSeqStat stat;SndSeqPlayPos pos;unsigned int mode;if(!s)return 0u;
 if(s->status!=SRK_SBL_GM_PRIMING&&s->status!=SRK_SBL_GM_PLAYING)return s->status==SRK_SBL_GM_PASS;
 SND_GetSeqStat(&stat,{_SEQUENCE_NUMBER});SND_GetSeqPlayPos(&pos,{_SEQUENCE_NUMBER});
 mode=(unsigned int)SND_SEQ_STAT_MODE(stat);s->event_index=(unsigned long)pos;s->retries=(unsigned long)SND_SEQ_STAT_STAT(stat);
 if(s->status==SRK_SBL_GM_PRIMING){{if(mode!=SND_MD_STOP){{s->prime=1u;s->status=SRK_SBL_GM_PLAYING;}}return 0u;}}
 if(mode==SND_MD_STOP){{s->status=SRK_SBL_GM_PASS;return 1u;}}return 0u;
}}
void srk_saturn_sbl_gm_stop(SRK_SBL_GM_STATE *s){{
 if(!s)return;if(s->sound_initialized){{(void)SND_StopSeq({_SEQUENCE_NUMBER});(void)SND_OffAllSound();}}
 if(s->status!=SRK_SBL_GM_ERROR)s->status=SRK_SBL_GM_STOPPED;
}}
'''


def _native_main(base: str) -> str:
    result = _gm._main(base)
    replacements = {
        "SEGA DIRECT MIDI / REAL GM": "SEGA NATIVE SEQUENCE / REAL GM",
        'gm_field(2,7,9,"Events:")': 'gm_field(2,7,9,"Position:")',
        'gm_field(22,7,10,"/ 9154")': 'gm_field(22,7,10,"")',
        'gm_field(2,8,9,"Retries:")': 'gm_field(2,8,12,"Drv status:")',
        "PASS: Sega driver accepted 9154 events": "PASS: native sequence completed",
        "Space Spectre via Sega sound driver": "Space Spectre via SDDRV sequencer",
    }
    for old, new in replacements.items():
        if old not in result:
            raise SaturnSblNativeSequenceCandidateError(f"native main anchor changed: {old}")
        result = result.replace(old, new, 1)
    return result


def build_saturn_sbl_native_sequence_candidate(
    baseline_project: os.PathLike[str] | str,
    sequence_directory: os.PathLike[str] | str,
    saturn_root: os.PathLike[str] | str,
    output_directory: os.PathLike[str] | str,
) -> SaturnSblNativeSequenceCandidateResult:
    baseline = _gm._path(baseline_project)
    sequence_dir = _gm._path(sequence_directory)
    saturn = _gm._path(saturn_root)
    output = _gm._path(output_directory)
    if not baseline.is_dir():
        raise SaturnSblNativeSequenceCandidateError(f"baseline project missing: {baseline}")
    if not sequence_dir.is_dir():
        raise SaturnSblNativeSequenceCandidateError(f"native sequence directory missing: {sequence_dir}")
    if not saturn.is_dir():
        raise SaturnSblNativeSequenceCandidateError(f"Saturn root missing: {saturn}")
    if output.exists():
        raise SaturnSblNativeSequenceCandidateError(f"output already exists; refusing overwrite: {output}")

    baseline_manifest, driver, melodic, drum = _validate_baseline(baseline)
    sequence_manifest, sequence_bank, sequence_sha, sequence_bytes = _validate_sequence(sequence_dir)
    sega_snd = _resolve_sdk_file(saturn, "sega_snd.a", kind="library")
    sega_snd_sha = _gm._sha(sega_snd)
    driver_sha = _gm._sha(driver)
    melodic_sha = _gm._sha(melodic)
    drum_sha = _gm._sha(drum)

    repo = _gm._root()
    profile = build_srk_saturn_midi_68k_r26_space_spectre_profile(repo)
    if (
        profile.member_sha256 != SATURN_MIDI_68K_R26_SPACE_SPECTRE_SHA256
        or profile.note_on_count != 4381
        or profile.note_off_count != 4381
    ):
        raise SaturnSblNativeSequenceCandidateError("Space Spectre source/profile changed")

    map_bytes, drum_start, sequence_start = _area_map(
        melodic.stat().st_size,
        drum.stat().st_size,
        sequence_bytes,
    )
    map_sha = _sha_bytes(map_bytes)
    assets = SaturnSblNativeSequenceAssets(
        sound_driver_sha256=driver_sha,
        melodic_tone_bank_sha256=melodic_sha,
        drum_tone_bank_sha256=drum_sha,
        sequence_bank_sha256=sequence_sha,
        sega_sound_library_sha256=sega_snd_sha,
        area_map_sha256=map_sha,
        melodic_start=_TONE_START,
        drum_start=drum_start,
        sequence_start=sequence_start,
    )

    standalone = repo / "integrations" / "saturn" / "standalone"
    diagnostics = repo / "integrations" / "saturn" / "diagnostics"
    main = _native_main((standalone / "srk_saturn_main.c").read_text(encoding="utf-8"))
    menu = (diagnostics / "srk_diag_menu.c").read_text(encoding="utf-8").replace(
        '"Timing / Interrupt Test"', '"SEGA Native Sequence / GM"', 1
    )
    runtime_base = (standalone / "srk_saturn_runtime.c").read_text(encoding="utf-8")
    native_runtime = _runtime()
    if "SND_CtrlDirMidi" in native_runtime or "srk_saturn_sbl_direct_midi" in native_runtime:
        raise SaturnSblNativeSequenceCandidateError("native runtime regressed to Direct MIDI")
    header = _header(
        driver.stat().st_size,
        len(map_bytes),
        melodic.stat().st_size,
        drum.stat().st_size,
        sequence_bytes,
        melodic_sha,
        drum_sha,
        sequence_sha,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent)))
    stage = tmp / "stage"
    stage.mkdir()
    try:
        _gm._copy_baseline(baseline, stage, baseline_manifest)
        (stage / "build").mkdir(exist_ok=True)
        (stage / "cd").mkdir(exist_ok=True)
        (stage / "src/srk_saturn_main.c").write_text(main, encoding="utf-8", newline="\n")
        (stage / "src/srk_diag_menu.c").write_text(menu, encoding="utf-8", newline="\n")
        (stage / "src/srk_saturn_sbl_gm_candidate.h").write_text(header, encoding="utf-8", newline="\n")
        (stage / "src/srk_saturn_runtime.c").write_text(
            runtime_base.rstrip() + "\n\n" + native_runtime,
            encoding="utf-8",
            newline="\n",
        )
        obsolete = stage / "src/srk_saturn_sbl_direct_midi.h"
        if obsolete.exists():
            obsolete.unlink()

        shutil.copy2(driver, stage / "cd" / _DRIVER_CD)
        (stage / "cd" / _MAP_CD).write_bytes(map_bytes)
        shutil.copy2(melodic, stage / "cd" / _MELODIC_CD)
        shutil.copy2(drum, stage / "cd" / _DRUM_CD)
        shutil.copy2(sequence_bank, stage / "cd" / _SEQUENCE_CD)

        manifest = dict(baseline_manifest)
        policy = dict(manifest.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "sbl_direct_midi_gm_candidate": False,
                "sbl_native_sequence_gm_candidate": True,
                "direct_midi_streaming": False,
                "sh2_midi_priming": False,
                "synthetic_r26_r28_timbres_used": False,
                "hardware_executed_during_build": False,
            }
        )
        manifest["policy"] = policy
        manifest.pop("sbl_direct_midi_gm", None)
        manifest["sbl_native_sequence_gm"] = {
            "schema": "srk.saturn.sbl-native-sequence-gm-candidate.v1",
            "source_midi_sha256": profile.member_sha256,
            "note_count": 4381,
            "duration_us": profile.duration_us,
            "playback": {
                "api": "SND_StartSeq",
                "sequence_number": _SEQUENCE_NUMBER,
                "bank": _SEQUENCE_BANK,
                "song": _SEQUENCE_SONG,
                "priority": _SEQUENCE_PRIORITY,
                "direct_midi_streaming": False,
                "sh2_event_scheduler": False,
            },
            "sound_driver": {"sha256": driver_sha, "bytes": driver.stat().st_size},
            "melodic_bank": {"sha256": melodic_sha, "bank": 0, "bytes": melodic.stat().st_size},
            "drum_bank": {"sha256": drum_sha, "bank": 1, "bytes": drum.stat().st_size},
            "sequence_bank": {
                "sha256": sequence_sha,
                "bytes": sequence_bytes,
                "conversion_manifest_schema": sequence_manifest["schema"],
            },
            "area_map": {
                "format": "sega-external-mp",
                "bytes": len(map_bytes),
                "sha256": map_sha,
                "melodic_start": _TONE_START,
                "drum_start": drum_start,
                "sequence_start": sequence_start,
            },
            "sega_snd": {"path": str(sega_snd), "sha256": sega_snd_sha},
            "off_card_only": True,
        }
        manifest["generated_files"] = _gm._inventory(stage)
        (stage / _PROJECT_MANIFEST).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        stage.replace(output)
        tmp.rmdir()
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    before = (driver_sha, melodic_sha, drum_sha, sequence_sha, sega_snd_sha)
    with _gm._sound_link(sega_snd):
        build = _build.build_saturn_standalone_project(output)
    after = (
        _gm._sha(driver),
        _gm._sha(melodic),
        _gm._sha(drum),
        _gm._sha(sequence_bank),
        _gm._sha(sega_snd),
    )
    if before != after:
        raise SaturnSblNativeSequenceCandidateError("external native-sequence inputs changed during build")
    if not build.successful:
        raise SaturnSblNativeSequenceCandidateError(f"candidate build failed; see {build.log_path}")

    built_runtime = (output / "src/srk_saturn_runtime.c").read_text(encoding="utf-8")
    if "SND_StartSeq" not in built_runtime or "SND_KD_SEQ" not in built_runtime:
        raise SaturnSblNativeSequenceCandidateError("built runtime lost native sequence calls")
    if "SND_CtrlDirMidi" in built_runtime:
        raise SaturnSblNativeSequenceCandidateError("built runtime contains forbidden Direct MIDI call")
    if (output / "cd" / _MAP_CD).read_bytes() != map_bytes:
        raise SaturnSblNativeSequenceCandidateError("built external area map changed")
    if _gm._sha(output / "cd" / _SEQUENCE_CD) != sequence_sha:
        raise SaturnSblNativeSequenceCandidateError("built native sequence bank changed")

    return SaturnSblNativeSequenceCandidateResult(
        project_root=output,
        assets=assets,
        note_count=4381,
        duration_us=profile.duration_us,
        sequence_bank_bytes=sequence_bytes,
        build=build,
    )
