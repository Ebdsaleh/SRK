from __future__ import annotations

from types import SimpleNamespace

from rikai_kotoba.hardware.saturn.sbl_fidelity_tone_build_audit import _row_map


def test_row_map_accepts_projected_level_row_shape_without_key_property() -> None:
    row = SimpleNamespace(kind="melodic", program=30, note=64)
    mapped = _row_map((row,))

    assert mapped == {("melodic", 30, 64): row}
