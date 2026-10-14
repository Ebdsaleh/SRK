from __future__ import annotations

import pytest

from rikai_kotoba.hardware.saturn import midi_68k_r26_pre_media_gate as gate


def test_r26_pre_media_pins_eridu_physical_build_artifacts():
    assert gate.ACCEPTED_R26_SOURCE_MIDI_SHA256 == (
        "984c55f7c7713a19d31a66344c174c22d072349022aa4ef1e38f8ea19d296e01"
    )
    assert gate.ACCEPTED_R26_RESIDENT_IMAGE_SHA256 == (
        "7bcc139b2a689f77f03de79c0efae5e018e3584bfe15826baafa09c7aef32b40"
    )
    assert gate.ACCEPTED_R26_BIN_SIZE == 489216
    assert gate.ACCEPTED_R26_BIN_SHA256 == (
        "4e1e45c411c78a1b08460e788ca4667044d2fed8769fc2d182da878e17ad47d7"
    )
    assert gate.ACCEPTED_R26_CUE_SIZE == 81
    assert gate.ACCEPTED_R26_CUE_SHA256 == (
        "5d3de34e75e7c86bb18b474bb9047dd2edf67c1e26eb87e0f0b70ff6c9022950"
    )
    assert gate.ACCEPTED_R26_SECTOR_COUNT == 208
    assert gate.ACCEPTED_R26_RAW_BYTES == 489216
    assert gate.ACCEPTED_R26_USER_BYTES == 425984


def test_r26_pre_media_pins_all_generated_representation_hashes():
    values = (
        gate.ACCEPTED_R26_RESIDENT_SOURCE_SHA256,
        gate.ACCEPTED_R26_RESIDENT_HEADER_SHA256,
        gate.ACCEPTED_R26_VOICE_HEADER_SHA256,
        gate.ACCEPTED_R26_PLAYER_SOURCE_SHA256,
        gate.ACCEPTED_R26_PLAYER_HEADER_SHA256,
        gate.ACCEPTED_R26_PROOF_SOURCE_SHA256,
        gate.ACCEPTED_R26_PROOF_HEADER_SHA256,
        gate.ACCEPTED_R26_MAIN_SHA256,
        gate.ACCEPTED_R26_MENU_SHA256,
        gate.ACCEPTED_R26_RUNTIME_SHA256,
        gate.ACCEPTED_R26_BUILD_BIN_SHA256,
        gate.ACCEPTED_R26_BUILD_ISO_SHA256,
        gate.ACCEPTED_R26_BUILD_MAP_SHA256,
    )
    assert len(values) == len(set(values))
    assert all(len(value) == 64 for value in values)


def test_r26_pre_media_expect_is_fail_closed():
    gate._expect("same", "same", "control")
    with pytest.raises(gate.SaturnMidi68KR26PreMediaGateError):
        gate._expect("changed", "accepted", "test anchor")
