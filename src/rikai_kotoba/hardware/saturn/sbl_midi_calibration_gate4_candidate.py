"""GATE4 SBL Direct-MIDI calibration candidate with Sega external .MP area map.

GATE3 proved that the reusable MIDI calibration UI reaches the concrete
``SND_CtrlDirMidi`` callbacks on real Saturn hardware: NOTE ON / HELD is only
entered after the callback returns success.  Hardware nevertheless remained
silent.  The largest remaining startup difference from SRK's later audible
native-sequence candidate is the sound-area-map representation.

GATE4 therefore changes one hardware variable only.  It keeps the same SDDRV,
melodic/drum banks, mixer/volume setup and Direct-MIDI binding, but emits the
Sound Simulator/SBL external ``.MP`` representation already used by the audible
native-sequence path.  Existing GATE3 builders and audits remain immutable.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterator

from . import sbl_midi_calibration_candidate as _candidate
from . import sbl_midi_calibration_candidate_contract as _contract
from .sbl_sequence import SBL_AREA_TONE, SaturnSblArea, encode_sbl_external_area_map


SaturnSblMidiCalibrationGate4Error = _candidate.SaturnSblMidiCalibrationCandidateError

_GATE4_MAP_BYTES = 18
_GATE4_MAP_TERMINATOR = b"\xFF\xFF"


@dataclass(frozen=True)
class SaturnSblMidiCalibrationGate4Result:
    candidate: _candidate.SaturnSblMidiCalibrationCandidateResult
    area_map_sha256: str
    area_map_bytes: int
    drum_start: int

    @property
    def project_root(self) -> Path:
        return self.candidate.project_root

    @property
    def assets(self):
        return self.candidate.assets

    @property
    def build(self):
        return self.candidate.build


def build_gate4_external_area_map(melodic_size: int, drum_size: int) -> tuple[bytes, int]:
    """Build the two-tone-bank Sega external .MP map used by GATE4."""

    if melodic_size <= 0 or drum_size <= 0:
        raise SaturnSblMidiCalibrationGate4Error("GATE4 tone-bank sizes must be positive")

    drum_start = _candidate._gm._align4(_candidate._gm._TONE_START + melodic_size)
    if drum_start + drum_size > _candidate._gm._SOUND_RAM_END:
        raise SaturnSblMidiCalibrationGate4Error(
            "GATE4 melodic + drum banks exceed Saturn Sound RAM: "
            f"melodic={melodic_size}, drum={drum_size}"
        )

    payload = encode_sbl_external_area_map(
        (
            SaturnSblArea(SBL_AREA_TONE, 0, _candidate._gm._TONE_START, melodic_size),
            SaturnSblArea(SBL_AREA_TONE, 1, drum_start, drum_size),
        )
    )
    if len(payload) != _GATE4_MAP_BYTES:
        raise SaturnSblMidiCalibrationGate4Error(
            f"GATE4 external area map must be {_GATE4_MAP_BYTES} bytes, got {len(payload)}"
        )
    if not payload.endswith(_GATE4_MAP_TERMINATOR):
        raise SaturnSblMidiCalibrationGate4Error("GATE4 external area map lost FF FF terminator")
    if payload.endswith(b"\x80\x00\x00\x00"):
        raise SaturnSblMidiCalibrationGate4Error(
            "GATE4 refused the legacy internal-style 0x80000000 terminator"
        )
    return payload, drum_start


def _gate4_header(driver_bytes: int, melodic_bytes: int, drum_bytes: int) -> str:
    return f'''#ifndef SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#define SRK_SATURN_SBL_MIDI_CALIBRATION_RUNTIME_H
#define SRK_SBL_CAL_DRIVER_BYTES {driver_bytes}UL
#define SRK_SBL_CAL_MAP_BYTES {_GATE4_MAP_BYTES}UL
#define SRK_SBL_CAL_TONE_BYTES {melodic_bytes}UL
#define SRK_SBL_CAL_DRUM_BYTES {drum_bytes}UL
#define SRK_SBL_CAL_GATE4_EXTERNAL_MP 1u
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


@contextmanager
def _gate4_external_map_contract() -> Iterator[None]:
    original_map_builder = _candidate.build_sega_sbl_area_map
    original_header_builder = _candidate._header
    _candidate.build_sega_sbl_area_map = build_gate4_external_area_map
    _candidate._header = _gate4_header
    try:
        yield
    finally:
        _candidate.build_sega_sbl_area_map = original_map_builder
        _candidate._header = original_header_builder


def _verify_gate4_output(
    result: _candidate.SaturnSblMidiCalibrationCandidateResult,
) -> tuple[str, int]:
    project = result.project_root
    map_path = project / "cd" / "SRKMAP.BIN"
    header_path = project / "src" / "srk_saturn_sbl_midi_calibration_runtime.h"
    runtime_path = project / "src" / "srk_saturn_runtime.c"
    main_path = project / "src" / "srk_saturn_main.c"

    melodic_size = (project / "cd" / "SRKGM.BIN").stat().st_size
    drum_size = (project / "cd" / "SRKDRUM.BIN").stat().st_size
    expected_map, drum_start = build_gate4_external_area_map(melodic_size, drum_size)

    actual_map = map_path.read_bytes()
    if actual_map != expected_map:
        raise SaturnSblMidiCalibrationGate4Error(
            "built GATE4 project does not contain the exact external .MP area map"
        )
    if actual_map[-2:] != _GATE4_MAP_TERMINATOR:
        raise SaturnSblMidiCalibrationGate4Error("built GATE4 map terminator changed")

    header = header_path.read_text(encoding="utf-8", errors="strict")
    for anchor in (
        "#define SRK_SBL_CAL_MAP_BYTES 18UL",
        "#define SRK_SBL_CAL_GATE4_EXTERNAL_MP 1u",
    ):
        if anchor not in header:
            raise SaturnSblMidiCalibrationGate4Error(
                f"built GATE4 runtime header lost anchor: {anchor}"
            )

    runtime = runtime_path.read_text(encoding="utf-8", errors="strict")
    for anchor in (
        "SND_Init(&ini);",
        "SND_ChgMap(0)",
        "SND_MoveData((Uint16 *)srk_cal_tone",
        "SND_MoveData((Uint16 *)srk_cal_drum",
        "SND_ChgMix(0,0)",
        "SND_SetTlVl(15)",
        "return SND_CtrlDirMidi(seq_no, seq_pri, md_com, ch, dt1, dt2);",
        "host->midi_select_program = srk_saturn_sbl_midi_select_program;",
        "host->midi_note_on = srk_saturn_sbl_midi_note_on;",
    ):
        if anchor not in runtime:
            raise SaturnSblMidiCalibrationGate4Error(
                f"built GATE4 runtime lost Direct-MIDI/startup anchor: {anchor}"
            )

    main = main_path.read_text(encoding="utf-8", errors="strict")
    bind_gate = (
        "if(srk_saturn_sbl_midi_calibration_runtime_begin(&srk_midi_calibration_runtime))\n"
        "        srk_saturn_sbl_midi_calibration_bind(&srk_host);"
    )
    if bind_gate not in main:
        raise SaturnSblMidiCalibrationGate4Error(
            "GATE4 main no longer gates callback binding on successful SBL runtime startup"
        )
    for disabled in (
        "srk_host.present_audio_tone = 0;",
        "srk_host.stop_audio = 0;",
        "srk_host.read_audio_status = 0;",
    ):
        if disabled not in main:
            raise SaturnSblMidiCalibrationGate4Error(
                f"GATE4 main lost raw-SCSP isolation: {disabled}"
            )

    return sha256(actual_map).hexdigest(), drum_start


def build_saturn_sbl_midi_calibration_gate4_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    melodic_tone_bank=None,
    drum_tone_bank=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationGate4Result:
    """Build GATE4 while retaining the proven GATE3 runtime/callback path."""

    with _gate4_external_map_contract():
        candidate = _contract.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            melodic_tone_bank=melodic_tone_bank,
            drum_tone_bank=drum_tone_bank,
            sound_driver=sound_driver,
        )

    map_sha, drum_start = _verify_gate4_output(candidate)
    return SaturnSblMidiCalibrationGate4Result(
        candidate=candidate,
        area_map_sha256=map_sha,
        area_map_bytes=_GATE4_MAP_BYTES,
        drum_start=drum_start,
    )
