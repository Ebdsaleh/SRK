"""SDDRV210 voice-probe R2: Sound-RAM word-bus access correction.

The first physical voice-allocation probe used volatile Uint8 loads against the
68000 Sound-RAM work structures.  Physical Saturn evidence showed that this
cannot be trusted: BANK_init must initialize management #2/channel 0 volume
words to 0x007F, while the byte-load probe displayed zeros.

This layer preserves every R1 probe address and interpretation, but reads 68000
Sound RAM using the same 16-bit access discipline already proven by the SDDRV210
system-interface telemetry:
  * aligned 16-bit Sound-RAM reads;
  * 32-bit 68000 values composed from two 16-bit words;
  * byte fields extracted from the high/low byte of an aligned 16-bit word.

SCSP hardware registers remain native 16-bit reads.
"""

from __future__ import annotations

from contextlib import contextmanager

from . import sbl_midi_calibration_sddrv210_voice_probe as _probe


SaturnSblMidiCalibrationCandidateError = _probe.SaturnSblMidiCalibrationCandidateError
SaturnSblMidiCalibrationCandidateResult = _probe.SaturnSblMidiCalibrationCandidateResult

WORD_BUS_ACCESS = "UINT16_ALIGNED"
BANK_INIT_DEFAULT_VOLUME = 0x007F


def _telemetry_manifest(document: dict) -> dict:
    candidate = dict(document)
    policy = dict(candidate.get("policy") or {})
    policy["sddrv210_voice_probe_word_bus"] = True
    candidate["policy"] = policy

    calibration = dict(candidate.get("sbl_midi_calibration") or {})
    telemetry = dict(calibration.get("telemetry") or {})
    telemetry.update(
        {
            "voice_probe_revision": "R2_WORDBUS",
            "sound_ram_access": WORD_BUS_ACCESS,
            "bank_init_default_volume_expected": BANK_INIT_DEFAULT_VOLUME,
            "byte_fields_via_aligned_word_read": True,
            "u32_fields_via_two_word_read": True,
        }
    )
    calibration["telemetry"] = telemetry
    candidate["sbl_midi_calibration"] = calibration
    return candidate


def _runtime(base: str) -> str:
    old = """static Uint8 srk_cal_probe_u8(Uint32 address){return *(volatile Uint8 *)address;}
static Uint16 srk_cal_probe_be16(Uint32 address){volatile Uint8 *p=(volatile Uint8 *)address;return (Uint16)(((Uint16)p[0]<<8)|(Uint16)p[1]);}
static Uint32 srk_cal_probe_be32(Uint32 address){volatile Uint8 *p=(volatile Uint8 *)address;return ((Uint32)p[0]<<24)|((Uint32)p[1]<<16)|((Uint32)p[2]<<8)|(Uint32)p[3];}
static Uint16 srk_cal_probe_reg16(Uint32 address){return *(volatile Uint16 *)address;}
"""
    new = """static Uint16 srk_cal_probe_word16(Uint32 address){return *(volatile Uint16 *)(address&~1UL);}
static Uint8 srk_cal_probe_u8(Uint32 address){Uint16 w=srk_cal_probe_word16(address);return (Uint8)((address&1UL)?(w&0x00FFu):(w>>8));}
static Uint16 srk_cal_probe_u16(Uint32 address){return *(volatile Uint16 *)address;}
static Uint32 srk_cal_probe_u32(Uint32 address){volatile Uint16 *p=(volatile Uint16 *)address;return ((Uint32)p[0]<<16)|(Uint32)p[1];}
static Uint16 srk_cal_probe_reg16(Uint32 address){return *(volatile Uint16 *)address;}
"""
    if base.count(old) != 1:
        raise SaturnSblMidiCalibrationCandidateError(
            "SDDRV210 voice-probe byte-access helper anchor changed"
        )
    base = base.replace(old, new, 1)
    base = base.replace("srk_cal_probe_be16(", "srk_cal_probe_u16(")
    base = base.replace("srk_cal_probe_be32(", "srk_cal_probe_u32(")
    return base


@contextmanager
def _contract():
    old_runtime = _probe._runtime
    old_manifest = _probe._telemetry_manifest

    def runtime(base: str) -> str:
        return _runtime(old_runtime(base))

    def telemetry_manifest(document: dict) -> dict:
        return _telemetry_manifest(old_manifest(document))

    _probe._runtime = runtime
    _probe._telemetry_manifest = telemetry_manifest
    try:
        yield
    finally:
        _probe._runtime = old_runtime
        _probe._telemetry_manifest = old_manifest


def build_saturn_sbl_midi_calibration_candidate(
    baseline_project,
    saturn_root,
    output_directory,
    *,
    soundfont=None,
    sound_driver=None,
) -> SaturnSblMidiCalibrationCandidateResult:
    """Build R2 probe with word-safe 68000 Sound-RAM telemetry reads."""

    with _contract():
        return _probe.build_saturn_sbl_midi_calibration_candidate(
            baseline_project,
            saturn_root,
            output_directory,
            soundfont=soundfont,
            sound_driver=sound_driver,
        )
