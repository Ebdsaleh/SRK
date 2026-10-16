from __future__ import annotations

from hashlib import sha256
import json

from rikai_kotoba.hardware.saturn.sbl_native_sequence_fidelity_candidate_fix1 import (
    _no_post_build_manifest_mutation,
    _stage_fidelity_baseline_with_final_policy,
)


def _sha(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def test_gate3f_final_policy_is_authored_before_build(tmp_path) -> None:
    baseline = tmp_path / "baseline"
    destination = tmp_path / "staged"
    (baseline / "cd").mkdir(parents=True)
    old_melodic = b"old-melodic"
    old_drums = b"old-drums"
    (baseline / "cd" / "SRKGM.BIN").write_bytes(old_melodic)
    (baseline / "cd" / "SRKDRUM.BIN").write_bytes(old_drums)
    manifest = {
        "policy": {},
        "generated_files": [
            {
                "path": "cd/SRKGM.BIN",
                "size": len(old_melodic),
                "sha256": _sha(old_melodic),
            },
            {
                "path": "cd/SRKDRUM.BIN",
                "size": len(old_drums),
                "sha256": _sha(old_drums),
            },
        ],
    }
    (baseline / "SRK_STANDALONE_PROJECT.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )

    _stage_fidelity_baseline_with_final_policy(
        baseline,
        destination,
        b"new-melodic",
        b"new-drums",
        tmp_path / "GeneralUser.sf2",
    )

    manifest_path = destination / "SRK_STANDALONE_PROJECT.json"
    staged = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = staged["policy"]
    assert policy["sbl_native_sequence_fidelity_gate3f"] is True
    assert policy["gate3f_off_card_only"] is True
    assert policy["saroo_writes"] is False
    assert policy["hardware_executed_during_build"] is False

    before = manifest_path.read_bytes()
    _no_post_build_manifest_mutation(destination, tmp_path / "GeneralUser.sf2")
    assert manifest_path.read_bytes() == before
