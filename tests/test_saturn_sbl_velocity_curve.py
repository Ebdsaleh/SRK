from __future__ import annotations

import pytest

from rikai_kotoba.hardware.saturn.sbl_velocity_curve import (
    SPACE_SPECTRE_SEGA_VELOCITY_TABLES,
    audit_velocity_table,
    sega_velocity_level,
    soundfont_velocity_linear_level,
)
from rikai_kotoba.tools import saturn_sbl_velocity_curve_audit as _cli


SEGA_BOOTTONE_VELOCITY_TABLE_0 = bytes.fromhex("08 00 7F 0C 7F 7F 08 7F 7F 08")


def test_driver_model_decodes_sega_boottone_table_zero_as_full_level():
    # NON.ASM selects K1 for every valid note-on velocity because V0=0 and
    # V1=127.  K1=0x0C is the constant branch with L0=127.
    assert {sega_velocity_level(SEGA_BOOTTONE_VELOCITY_TABLE_0, value) for value in range(1, 128)} == {127}


def test_soundfont_default_velocity_amount_is_square_law():
    for velocity in (15, 31, 63, 95, 127):
        expected = 127.0 * (velocity / 127.0) ** 2
        assert soundfont_velocity_linear_level(960, velocity) == pytest.approx(expected)


def test_space_spectre_velocity_tables_are_locked_and_full_scale_at_127():
    assert SPACE_SPECTRE_SEGA_VELOCITY_TABLES == {
        500: bytes.fromhex("13 03 01 02 50 4E 09 54 54 02"),
        600: bytes.fromhex("13 11 08 02 61 58 09 73 73 02"),
        800: bytes.fromhex("23 0B 02 13 26 0F 02 51 3A 09"),
    }
    for table in SPACE_SPECTRE_SEGA_VELOCITY_TABLES.values():
        assert sega_velocity_level(table, 127) == 127


def test_space_spectre_velocity_tables_track_sf2_curve_at_spec_checkpoints():
    limits = {500: 0.50, 600: 2.00, 800: 0.90}
    for amount, limit in limits.items():
        audit = audit_velocity_table(amount)
        assert audit.max_checkpoint_error_db <= limit
        assert audit.mean_checkpoint_error_db < 0.40
        assert audit.max_linear_error < 3.0


def test_velocity_curve_cli_is_read_only():
    parser = _cli._parser()
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--project" in option_strings
    assert "--soundfont" in option_strings
    for forbidden in ("--card-root", "--apply", "--confirm", "--output", "--saturn-root"):
        assert forbidden not in option_strings
