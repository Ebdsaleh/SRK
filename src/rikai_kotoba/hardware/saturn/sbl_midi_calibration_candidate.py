"""Build an isolated Sega SBL-backed MIDI calibration diagnostic candidate.

This candidate is deliberately separate from the raw-SCSP Audio Test and from
the full-song Space Spectre SBL proof.  It initializes Sega's real SDDRV sound
runtime and real tone banks once at startup, disables the generic raw-SCSP audio
callbacks in that executable, and binds the existing MIDI Test / GM Calibration
screen to Sega Direct MIDI.

Review persistence remains unbound until a real Saturn/SAROO persistence path is
proven.  Candidate generation/building is off-card only.
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
from .sbl_gm_candidate_contract import build_sega_sbl_area_map


SaturnSblMidiCalibrationCandidateError = _gm.SaturnSblGmCandidateError


@dataclass(frozen=True)
class SaturnSblMidiCalibrationCandidateResult:
    project_root: Path
    assets: _gm.SaturnSblGmAssets
    build: _build.SaturnStandaloneBuildResult


_DRIVER_CD = "SDDRVS.TSK"
_MAP_CD = "SRKMAP.BIN"
_MELODIC_CD = "SRKGM.BIN"
_DRUM_CD = "SRKDRUM.BIN"
_MANIFEST = "SRK_STANDALONE_PROJECT.json"
_RUNTIME_HEADER = "srk_saturn_sbl_midi_calibration_runtime.h"


def _header(driver_bytes: int, melodic_bytes: int, drum_bytes: int) -> str:
    return f'''#ifndef SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#define SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#define SRK_SBL_CAL_DRIVER_BYTES {driver_bytes}UL
#define SRK_SBL_CAL_MAP_BYTES 20UL
#define SRK_SBL_CAL_TONE_BYTES {melodic_bytes}UL
#define SRK_SBL_CAL_DRUM_BYTES {drum_bytes}UL
typedef struct SRK_SBL_MIDI_CAL_RUNTIME_STATE {{
 unsigned int initialized;
 unsigned int error;
 unsigned int last_ret;
}} SRK_SBL_MIDI_CAL_RUNTIME_STATE;
void srk_saturn_sbl_midi_calibration_runtime_reset(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
unsigned int srk_saturn_sbl_midi_calibration_runtime_begin(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
void srk_saturn_sbl_midi_calibration_runtime_stop(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state);
#endif
'''


def _runtime() -> str:
    return f'''#include "{_RUNTIME_HEADER}"
#include "SEGA_GFS.H"
#include "sega_snd.h"
#define SRK_GFS_OPEN_MAX 2
#define SRK_GFS_MAX_DIR 32
#define SRK_SBL_CAL_ERR_GFS 1u
#define SRK_SBL_CAL_ERR_DRIVER 2u
#define SRK_SBL_CAL_ERR_MAP_LOAD 3u
#define SRK_SBL_CAL_ERR_TONE 4u
#define SRK_SBL_CAL_ERR_MAP 5u
#define SRK_SBL_CAL_ERR_MIX 6u
#define SRK_SBL_CAL_ERR_VOLUME 7u
static Uint32 srk_cal_gfs_work[GFS_WORK_SIZE(SRK_GFS_OPEN_MAX)/sizeof(Uint32)];
static GfsDirTbl srk_cal_gfs_table;
static GfsDirName srk_cal_gfs_names[SRK_GFS_MAX_DIR];
static Uint32 srk_cal_driver[(SRK_SBL_CAL_DRIVER_BYTES+3UL)/4UL];
static Uint32 srk_cal_map[(SRK_SBL_CAL_MAP_BYTES+3UL)/4UL];
static Uint32 srk_cal_tone[(SRK_SBL_CAL_TONE_BYTES+3UL)/4UL];
static Uint32 srk_cal_drum[(SRK_SBL_CAL_DRUM_BYTES+3UL)/4UL];
static int srk_cal_load(const char *name, Uint32 *dst, unsigned long bytes){{
 Sint32 id,n;
 id=GFS_NameToId((Sint8 *)name);
 if(id<0)return 0;
 n=GFS_Load(id,0,dst,(Sint32)bytes);
 return n==(Sint32)bytes;
}}
static unsigned int srk_cal_fail(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state,unsigned int error){{
 if(state){{state->initialized=0u;state->error=error;}}
 return 0u;
}}
void srk_saturn_sbl_midi_calibration_runtime_reset(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{
 if(!state)return;
 state->initialized=0u;
 state->error=0u;
 state->last_ret=0u;
}}
unsigned int srk_saturn_sbl_midi_calibration_runtime_begin(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{
 SndIniDt ini;
 SndRet result;
 Sint32 gfs_result;
 if(!state)return 0u;
 state->initialized=0u;state->error=0u;state->last_ret=0u;
 GFS_DIRTBL_TYPE(&srk_cal_gfs_table)=GFS_DIR_NAME;
 GFS_DIRTBL_NDIR(&srk_cal_gfs_table)=SRK_GFS_MAX_DIR;
 GFS_DIRTBL_DIRNAME(&srk_cal_gfs_table)=srk_cal_gfs_names;
 gfs_result=GFS_Init(SRK_GFS_OPEN_MAX,srk_cal_gfs_work,&srk_cal_gfs_table);
 if(gfs_result<0)return srk_cal_fail(state,SRK_SBL_CAL_ERR_GFS);
 if(!srk_cal_load("{_DRIVER_CD}",srk_cal_driver,SRK_SBL_CAL_DRIVER_BYTES))return srk_cal_fail(state,SRK_SBL_CAL_ERR_DRIVER);
 if(!srk_cal_load("{_MAP_CD}",srk_cal_map,SRK_SBL_CAL_MAP_BYTES))return srk_cal_fail(state,SRK_SBL_CAL_ERR_MAP_LOAD);
 if(!srk_cal_load("{_MELODIC_CD}",srk_cal_tone,SRK_SBL_CAL_TONE_BYTES))return srk_cal_fail(state,SRK_SBL_CAL_ERR_TONE);
 if(!srk_cal_load("{_DRUM_CD}",srk_cal_drum,SRK_SBL_CAL_DRUM_BYTES))return srk_cal_fail(state,SRK_SBL_CAL_ERR_TONE);
 SND_INI_PRG_ADR(ini)=(Uint16 *)srk_cal_driver;
 SND_INI_PRG_SZ(ini)=(Uint16)SRK_SBL_CAL_DRIVER_BYTES;
 SND_INI_ARA_ADR(ini)=(Uint16 *)srk_cal_map;
 SND_INI_ARA_SZ(ini)=(Uint16)SRK_SBL_CAL_MAP_BYTES;
 SND_Init(&ini);
 result=SND_ChgMap(0);state->last_ret=(unsigned int)result;
 if(result!=SND_RET_SET)return srk_cal_fail(state,SRK_SBL_CAL_ERR_MAP);
 SND_MoveData((Uint16 *)srk_cal_tone,(Uint32)SRK_SBL_CAL_TONE_BYTES,SND_KD_TONE,0);
 SND_MoveData((Uint16 *)srk_cal_drum,(Uint32)SRK_SBL_CAL_DRUM_BYTES,SND_KD_TONE,1);
 result=SND_ChgMix(0,0);state->last_ret=(unsigned int)result;
 if(result!=SND_RET_SET)return srk_cal_fail(state,SRK_SBL_CAL_ERR_MIX);
 result=SND_SetTlVl(15);state->last_ret=(unsigned int)result;
 if(result!=SND_RET_SET)return srk_cal_fail(state,SRK_SBL_CAL_ERR_VOLUME);
 state->initialized=1u;
 return 1u;
}}
void srk_saturn_sbl_midi_calibration_runtime_stop(SRK_SBL_MIDI_CAL_RUNTIME_STATE *state){{
 if(!state)return;
 if(state->initialized)(void)SND_OffAllSound();
 state->initialized=0u;
}}
'''


def _main(base: str) -> str:
    include = '#include "srk_saturn_host.h"\n'
    state = 'static SRK_SATURN_HOST_STATE srk_host_state;\n'
    audio_bind = '    srk_saturn_audio_bind(&srk_host, &srk_host_state);\n'
    app_reset = '    srk_diag_app_reset(&srk_app);\n'
    anchors = (include, state, audio_bind, app_reset)
    if any(base.count(anchor) != 1 for anchor in anchors):
        raise SaturnSblMidiCalibrationCandidateError(
            "generic Saturn main calibration anchors changed"
        )

    base = base.replace(
        include,
        include
        + '#include "srk_saturn_sbl_midi_calibration.h"\n'
        + f'#include "{_RUNTIME_HEADER}"\n',
        1,
    )
    base = base.replace(
        state,
        state + 'static SRK_SBL_MIDI_CAL_RUNTIME_STATE srk_midi_calibration_runtime;\n',
        1,
    )
    base = base.replace(
        audio_bind,
        audio_bind
        + '    /* SBL owns SCSP/68K state in this candidate; raw Audio Test is disabled. */\n'
        + '    srk_host.present_audio_tone = 0;\n'
        + '    srk_host.stop_audio = 0;\n'
        + '    srk_host.read_audio_status = 0;\n',
        1,
    )
    base = base.replace(
        app_reset,
        app_reset
        + '    srk_saturn_sbl_midi_calibration_runtime_reset(&srk_midi_calibration_runtime);\n'
        + '    if(srk_saturn_sbl_midi_calibration_runtime_begin(&srk_midi_calibration_runtime))\n'
        + '        srk_saturn_sbl_midi_calibration_bind(&srk_host);\n',
        1,
    )
    return base


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    melodic_tone_bank=None,
    drum_tone_bank=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    baseline, saturn_root, output = map(
        _gm._path, (baseline_project, saturn_root, output_directory)
    )
    if not baseline.is_dir():
        raise SaturnSblMidiCalibrationCandidateError(
            f"baseline project missing: {baseline}"
        )
    if not saturn_root.is_dir():
        raise SaturnSblMidiCalibrationCandidateError(
            f"Saturn root missing: {saturn_root}"
        )
    if output.exists():
        raise SaturnSblMidiCalibrationCandidateError(
            f"output already exists; refusing overwrite: {output}"
        )

    manifest_path = baseline / _MANIFEST
    if not manifest_path.is_file():
        raise SaturnSblMidiCalibrationCandidateError(
            f"baseline manifest missing: {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    driver = _gm._driver(saturn_root, sound_driver)
    tone = _gm._bank(saturn_root, melodic_tone_bank, False)
    drum = _gm._bank(saturn_root, drum_tone_bank, True)
    if tone == drum:
        raise SaturnSblMidiCalibrationCandidateError(
            "melodic and drum banks resolved to same file; refusing to guess"
        )
    sound_library = _resolve_sdk_file(saturn_root, "sega_snd.a", kind="library")
    assets = _gm.SaturnSblGmAssets(
        driver,
        _gm._sha(driver),
        tone,
        _gm._sha(tone),
        drum,
        _gm._sha(drum),
        sound_library,
        _gm._sha(sound_library),
    )
    map_bytes, drum_start = build_sega_sbl_area_map(
        tone.stat().st_size, drum.stat().st_size
    )

    repo = _gm._root()
    standalone = repo / "integrations" / "saturn" / "standalone"
    main = _main((standalone / "srk_saturn_main.c").read_text(encoding="utf-8"))
    base_runtime = (standalone / "srk_saturn_runtime.c").read_text(encoding="utf-8")
    direct = (standalone / "srk_saturn_sbl_direct_midi.c").read_text(encoding="utf-8")
    direct_header = (standalone / "srk_saturn_sbl_direct_midi.h").read_text(
        encoding="utf-8"
    )
    calibration = (standalone / "srk_saturn_sbl_midi_calibration.c").read_text(
        encoding="utf-8"
    )
    calibration_header = (
        standalone / "srk_saturn_sbl_midi_calibration.h"
    ).read_text(encoding="utf-8")
    runtime_header = _header(
        driver.stat().st_size, tone.stat().st_size, drum.stat().st_size
    )
    runtime_body = _runtime()

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.", dir=str(output.parent))
    )
    stage = temp_root / "stage"
    stage.mkdir()
    try:
        _gm._copy_baseline(baseline, stage, manifest)
        (stage / "build").mkdir(exist_ok=True)
        (stage / "cd").mkdir(exist_ok=True)
        (stage / "src/srk_saturn_main.c").write_text(
            main, encoding="utf-8", newline="\n"
        )
        (stage / "src/srk_saturn_sbl_direct_midi.h").write_text(
            direct_header, encoding="utf-8", newline="\n"
        )
        (stage / "src/srk_saturn_sbl_midi_calibration.h").write_text(
            calibration_header, encoding="utf-8", newline="\n"
        )
        (stage / f"src/{_RUNTIME_HEADER}").write_text(
            runtime_header, encoding="utf-8", newline="\n"
        )
        (stage / "src/srk_saturn_runtime.c").write_text(
            base_runtime.rstrip()
            + "\n\n"
            + direct.rstrip()
            + "\n\n"
            + calibration.rstrip()
            + "\n\n"
            + runtime_body,
            encoding="utf-8",
            newline="\n",
        )
        shutil.copy2(driver, stage / "cd" / _DRIVER_CD)
        (stage / "cd" / _MAP_CD).write_bytes(map_bytes)
        shutil.copy2(tone, stage / "cd" / _MELODIC_CD)
        shutil.copy2(drum, stage / "cd" / _DRUM_CD)

        candidate_manifest = dict(manifest)
        policy = dict(candidate_manifest.get("policy") or {})
        policy.update(
            {
                "sd_writes": False,
                "sbl_midi_calibration_candidate": True,
                "synthetic_r26_r28_timbres_used": False,
                "hardware_executed_during_build": False,
                "raw_scsp_audio_callbacks_disabled": True,
            }
        )
        candidate_manifest["policy"] = policy
        candidate_manifest["sbl_midi_calibration"] = {
            "schema": "srk.saturn.sbl-midi-calibration-candidate.v1",
            "sound_driver": {
                "path": str(driver),
                "sha256": assets.sound_driver_sha256,
            },
            "area_map": {
                "sha256": sha256(map_bytes).hexdigest(),
                "bank0_start": _gm._TONE_START,
                "bank1_start": drum_start,
            },
            "melodic_bank": {
                "path": str(tone),
                "sha256": assets.melodic_tone_bank_sha256,
                "bank": 0,
            },
            "drum_bank": {
                "path": str(drum),
                "sha256": assets.drum_tone_bank_sha256,
                "bank": 1,
            },
            "sega_snd": {
                "path": str(sound_library),
                "sha256": assets.sega_sound_library_sha256,
            },
            "direct_midi": {
                "sequence": 2,
                "priority": 0,
                "melodic_channel": 0,
                "bank_select_controller": 32,
                "melodic_bank": 0,
                "pan_controller": 10,
                "reference_note": 60,
                "reference_velocity": 100,
                "reference_pan": 64,
            },
            "review_persistence_bound": False,
            "raw_scsp_audio_callbacks_disabled": True,
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

    before = (
        _gm._sha(driver),
        _gm._sha(tone),
        _gm._sha(drum),
        _gm._sha(sound_library),
    )
    with _gm._sound_link(sound_library):
        build = _build.build_saturn_standalone_project(output)
    after = (
        _gm._sha(driver),
        _gm._sha(tone),
        _gm._sha(drum),
        _gm._sha(sound_library),
    )
    if before != after:
        raise SaturnSblMidiCalibrationCandidateError(
            "external sound inputs changed during build"
        )
    if not build.successful:
        raise SaturnSblMidiCalibrationCandidateError(
            f"calibration candidate build failed; see {build.log_path}"
        )
    return SaturnSblMidiCalibrationCandidateResult(output, assets, build)
