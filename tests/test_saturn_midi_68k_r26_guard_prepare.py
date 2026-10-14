from __future__ import annotations

from types import SimpleNamespace
import json

import pytest

from rikai_kotoba.hardware.saturn import midi_68k_r26_guard_prepare as guard
from rikai_kotoba.hardware.saturn import midi_68k_r26_pre_media_gate as pre


def _accepted_pre_media():
    return SimpleNamespace(
        manifest_sha256="a" * 64,
        report_sha256="b" * 64,
        resident_image_sha256=pre.ACCEPTED_R26_RESIDENT_IMAGE_SHA256,
        resident_source_sha256=pre.ACCEPTED_R26_RESIDENT_SOURCE_SHA256,
        resident_header_sha256=pre.ACCEPTED_R26_RESIDENT_HEADER_SHA256,
        voice_header_sha256=pre.ACCEPTED_R26_VOICE_HEADER_SHA256,
        player_source_sha256=pre.ACCEPTED_R26_PLAYER_SOURCE_SHA256,
        player_header_sha256=pre.ACCEPTED_R26_PLAYER_HEADER_SHA256,
        proof_source_sha256=pre.ACCEPTED_R26_PROOF_SOURCE_SHA256,
        proof_header_sha256=pre.ACCEPTED_R26_PROOF_HEADER_SHA256,
        candidate_main_sha256=pre.ACCEPTED_R26_MAIN_SHA256,
        candidate_menu_sha256=pre.ACCEPTED_R26_MENU_SHA256,
        runtime_after_sha256=pre.ACCEPTED_R26_RUNTIME_SHA256,
        build_bin_sha256=pre.ACCEPTED_R26_BUILD_BIN_SHA256,
        build_iso_sha256=pre.ACCEPTED_R26_BUILD_ISO_SHA256,
        build_map_sha256=pre.ACCEPTED_R26_BUILD_MAP_SHA256,
        deployable_bin_sha256=pre.ACCEPTED_R26_BIN_SHA256,
        deployable_cue_sha256=pre.ACCEPTED_R26_CUE_SHA256,
        sector_count=pre.ACCEPTED_R26_SECTOR_COUNT,
        raw_bytes=pre.ACCEPTED_R26_RAW_BYTES,
        user_bytes=pre.ACCEPTED_R26_USER_BYTES,
    )


def test_r26_guard_prepare_anchor_accepts_exact_eridu_candidate():
    guard._require_pre_media_anchor(_accepted_pre_media())


def test_r26_guard_prepare_anchor_rejects_candidate_drift():
    value = _accepted_pre_media()
    value.resident_image_sha256 = "0" * 64
    with pytest.raises(guard.SaturnMidi68KR26GuardPrepareError):
        guard._require_pre_media_anchor(value)


def test_r26_guard_receipt_is_canonical_and_self_verifying(tmp_path):
    path = tmp_path / "receipt.json"
    payload = {
        "schema": guard.PREPARE_RECEIPT_SCHEMA,
        "candidate": {"deployable_bin_sha256": pre.ACCEPTED_R26_BIN_SHA256},
        "policy": {"prepare_only": True, "saroo_writes": False},
    }
    digest = guard._publish_receipt(path, payload)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["receipt_sha256"] == digest
    copy = dict(loaded)
    copy.pop("receipt_sha256")
    assert guard.sha256(guard._payload_bytes(copy)).hexdigest() == digest


def test_r26_guard_receipt_refuses_overwrite(tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(guard.SaturnMidi68KR26GuardPrepareError):
        guard._publish_receipt(path, {"schema": guard.PREPARE_RECEIPT_SCHEMA})
