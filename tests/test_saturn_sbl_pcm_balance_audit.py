from __future__ import annotations

import math
import struct

import pytest

from rikai_kotoba.hardware.saturn.sbl_fidelity_audit import SaturnScspLayerAudit
from rikai_kotoba.hardware.saturn.sbl_pcm_balance_audit import (
    _pcm_metrics,
    scsp_tl_attenuation_db,
)
from rikai_kotoba.tools.saturn_sbl_pcm_balance_audit import build_parser


def _layer(*, raw_sa: int, sample_address: int, sample_count: int, total_level: int = 0):
    return SaturnScspLayerAudit(
        index=0,
        start_note=60,
        end_note=60,
        raw_sa=raw_sa,
        sample_address=sample_address,
        loop_start=0,
        loop_end=sample_count,
        total_level=total_level,
        direct_send_pan=0,
        base_note=60,
        fine_tune=0,
        velocity_table=0,
    )


def test_scsp_tl_bit_attenuation_matches_sega_manual_examples():
    assert scsp_tl_attenuation_db(0x00) == pytest.approx(0.0)
    assert scsp_tl_attenuation_db(0xFF) == pytest.approx(95.7)
    assert scsp_tl_attenuation_db(13) == pytest.approx(4.9)
    assert scsp_tl_attenuation_db(60) == pytest.approx(22.5)


def test_pcm_metrics_decode_saturn_16bit_big_endian():
    values = (0, 32767, -32768, 16384)
    prefix = b"HEAD"
    payload = prefix + b"".join(struct.pack(">h", value) for value in values)
    layer = _layer(raw_sa=len(prefix), sample_address=len(prefix), sample_count=len(values))

    count, pcm8, peak_dbfs, rms_dbfs = _pcm_metrics(payload, layer)

    expected_rms = math.sqrt(sum(float(value) ** 2 for value in values) / len(values)) / 32768.0
    assert count == 4
    assert pcm8 is False
    assert peak_dbfs == pytest.approx(0.0, abs=0.001)
    assert rms_dbfs == pytest.approx(20.0 * math.log10(expected_rms), abs=0.001)


def test_pcm_metrics_decode_saturn_signed_8bit():
    # raw_sa bit20 is PCM8B; low 20 bits remain the sample address.
    sample_address = 3
    payload = b"PAD" + bytes((0x00, 0x7F, 0x80, 0x40))
    layer = _layer(
        raw_sa=0x00100000 | sample_address,
        sample_address=sample_address,
        sample_count=4,
    )

    count, pcm8, peak_dbfs, _rms_dbfs = _pcm_metrics(payload, layer)

    assert count == 4
    assert pcm8 is True
    assert peak_dbfs == pytest.approx(0.0, abs=0.001)


def test_pcm_balance_cli_exposes_read_only_project_input_only():
    parser = build_parser()
    args = parser.parse_args(["--project", "GATE3E"])
    assert str(args.project) == "GATE3E"
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--card-root" not in option_strings
    assert "--apply" not in option_strings
    assert "--output" not in option_strings
