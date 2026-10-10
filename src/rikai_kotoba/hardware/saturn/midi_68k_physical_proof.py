"""Bounded one-shot controller for SRK's first physical Saturn MIDI 68K proof.

This tranche deliberately separates *proof control* from controller/menu binding.
The committed C controller can call the already-reviewed adapter-neutral runtime
with the already-reviewed Saturn hardware adapter, but no production path calls
this controller yet.

The first physical proof remains silent: it proves SH-2 -> Sound RAM ->
MC68EC000 acknowledgement only.  It does not drive SCSP voices.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .midi_68k_runtime import (
    SaturnMidi68KProtocolSnapshot,
    SaturnMidi68KRuntimeStatus,
    classify_srk_saturn_midi_68k_protocol_snapshot,
)


@dataclass
class SaturnMidi68KPhysicalProofState:
    """Host-side model of the bounded one-shot C proof controller."""

    attempted: bool = False
    runtime_status: SaturnMidi68KRuntimeStatus = SaturnMidi68KRuntimeStatus.NOT_STARTED
    poll_count: int = 0
    telemetry: SaturnMidi68KProtocolSnapshot = field(
        default_factory=lambda: SaturnMidi68KProtocolSnapshot(0, 0, 0, 0)
    )


def begin_srk_saturn_midi_68k_physical_proof(
    state: SaturnMidi68KPhysicalProofState,
    begin_status: SaturnMidi68KRuntimeStatus,
) -> SaturnMidi68KRuntimeStatus:
    """Model one bounded begin attempt; repeated begin requests are inert."""

    if state.attempted:
        return state.runtime_status

    state.attempted = True
    state.runtime_status = begin_status
    return state.runtime_status


def poll_srk_saturn_midi_68k_physical_proof(
    state: SaturnMidi68KPhysicalProofState,
    snapshot: SaturnMidi68KProtocolSnapshot,
) -> SaturnMidi68KRuntimeStatus:
    """Model one non-blocking poll after a successful RUNNING begin."""

    if not state.attempted:
        return SaturnMidi68KRuntimeStatus.NOT_STARTED
    if state.runtime_status != SaturnMidi68KRuntimeStatus.RUNNING:
        return state.runtime_status

    state.telemetry = snapshot
    state.poll_count += 1
    state.runtime_status = classify_srk_saturn_midi_68k_protocol_snapshot(snapshot)
    return state.runtime_status


def render_srk_saturn_midi_68k_physical_proof_header() -> str:
    """Render the C89 header for the still-unbound physical-proof controller."""

    return "\n".join(
        (
            "#ifndef SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_H",
            "#define SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_H",
            "",
            '#include "srk_saturn_midi_68k_runtime.h"',
            "",
            "typedef struct SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE {",
            "    unsigned int attempted;",
            "    unsigned int runtime_status;",
            "    unsigned int poll_count;",
            "    SRK_SATURN_MIDI_68K_TELEMETRY telemetry;",
            "} SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE;",
            "",
            "void srk_saturn_midi_68k_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ");",
            "unsigned int srk_saturn_midi_68k_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ");",
            "unsigned int srk_saturn_midi_68k_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ");",
            "",
            "#endif",
            "",
        )
    )


def render_srk_saturn_midi_68k_physical_proof_source() -> str:
    """Render the bounded C89 controller with no controller/menu binding."""

    return "\n".join(
        (
            '#include "srk_saturn_midi_68k_physical_proof.h"',
            '#include "srk_saturn_midi_68k_hardware_adapter.h"',
            "",
            "void srk_saturn_midi_68k_physical_proof_reset(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ")",
            "{",
            "    if(!state)",
            "        return;",
            "",
            "    state->attempted = 0u;",
            "    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    state->poll_count = 0u;",
            "    state->telemetry.flags = 0u;",
            "    state->telemetry.read_sequence = 0u;",
            "    state->telemetry.read_index = 0u;",
            "    state->telemetry.last_error = 0u;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_physical_proof_begin(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ")",
            "{",
            "    if(!state)",
            "        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->attempted)",
            "        return state->runtime_status;",
            "",
            "    state->attempted = 1u;",
            "    state->runtime_status = srk_saturn_midi_68k_protocol_begin(",
            "        srk_saturn_midi_68k_hardware_adapter_ops()",
            "    );",
            "    return state->runtime_status;",
            "}",
            "",
            "unsigned int srk_saturn_midi_68k_physical_proof_poll(",
            "    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state",
            ")",
            "{",
            "    if(!state || !state->attempted)",
            "        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;",
            "    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)",
            "        return state->runtime_status;",
            "",
            "    state->runtime_status = srk_saturn_midi_68k_protocol_poll(",
            "        srk_saturn_midi_68k_hardware_adapter_ops(),",
            "        &state->telemetry",
            "    );",
            "    state->poll_count += 1u;",
            "    return state->runtime_status;",
            "}",
            "",
        )
    )
