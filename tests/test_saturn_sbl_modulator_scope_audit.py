from __future__ import annotations

from rikai_kotoba.hardware.saturn.sbl_level_model_audit import Sf2ModulatorRecord
from rikai_kotoba.hardware.saturn.sbl_modulator_scope_audit import (
    SF2_DEFAULT_VELOCITY_ATTENUATION_CB,
    decode_modulator_source,
    default_velocity_identity,
    resolve_effective_modulators,
)
from rikai_kotoba.tools.saturn_sbl_modulator_scope_audit import build_parser


def _mod(
    *,
    table: str,
    index: int,
    source: int = 0x0502,
    destination: int = 48,
    amount: int = 800,
    amount_source: int = 0,
    transform: int = 0,
) -> Sf2ModulatorRecord:
    return Sf2ModulatorRecord(
        table=table,
        index=index,
        source=source,
        destination=destination,
        amount=amount,
        amount_source=amount_source,
        transform=transform,
    )


def test_default_velocity_source_decodes_as_negative_unipolar_concave_velocity():
    assert decode_modulator_source(0x0502) == "velocity/negative/unipolar/concave"


def test_implicit_velocity_attenuation_default_is_960_cb_without_explicit_override():
    effective = resolve_effective_modulators((), (), (), ())
    velocity = next(mod for mod in effective if mod.identity == default_velocity_identity())

    assert velocity.amount == SF2_DEFAULT_VELOCITY_ATTENUATION_CB
    assert velocity.provenance == ("implicit-default",)


def test_instrument_local_replaces_global_and_default_then_preset_local_adds():
    instrument_global = (_mod(table="imod", index=1, amount=800),)
    instrument_local = (_mod(table="imod", index=2, amount=700),)
    preset_global = (_mod(table="pmod", index=3, amount=100),)
    preset_local = (_mod(table="pmod", index=4, amount=200),)

    effective = resolve_effective_modulators(
        instrument_global,
        instrument_local,
        preset_global,
        preset_local,
    )
    velocity = next(mod for mod in effective if mod.identity == default_velocity_identity())

    # local instrument 700 replaces both implicit 960 and instrument-global 800;
    # local preset 200 replaces preset-global 100 and then adds to instrument.
    assert velocity.amount == 900
    assert velocity.provenance == ("instrument-local", "preset-local")


def test_distinct_destination48_modulator_adds_without_replacing_velocity_identity():
    key_mod = _mod(table="imod", index=5, source=0x0203, amount=150)

    effective = resolve_effective_modulators((), (key_mod,), (), ())
    attenuation = [mod for mod in effective if mod.identity.destination == 48]

    assert len(attenuation) == 2
    velocity = next(mod for mod in attenuation if mod.identity == default_velocity_identity())
    other = next(mod for mod in attenuation if mod.identity != default_velocity_identity())
    assert velocity.amount == 960
    assert other.amount == 150
    assert other.identity.source == 0x0203


def test_zero_amount_instrument_velocity_modulator_cancels_implicit_default():
    cancel = _mod(table="imod", index=6, amount=0)

    effective = resolve_effective_modulators((), (cancel,), (), ())
    velocity = next(mod for mod in effective if mod.identity == default_velocity_identity())

    assert velocity.amount == 0
    assert velocity.provenance == ("instrument-local",)


def test_scope_audit_cli_is_read_only_and_has_no_candidate_or_media_arguments():
    parser = build_parser()
    args = parser.parse_args(["--project", "GATE3E"])
    assert str(args.project) == "GATE3E"
    option_strings = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    assert "--soundfont" in option_strings
    assert "--card-root" not in option_strings
    assert "--apply" not in option_strings
    assert "--output" not in option_strings
    assert "--confirm" not in option_strings
