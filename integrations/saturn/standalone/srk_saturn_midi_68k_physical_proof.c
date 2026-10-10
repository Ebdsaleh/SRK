#include "srk_saturn_midi_68k_physical_proof.h"
#include "srk_saturn_midi_68k_hardware_adapter.h"

void srk_saturn_midi_68k_physical_proof_reset(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
)
{
    if(!state)
        return;

    state->attempted = 0u;
    state->runtime_status = SRK_MIDI_68K_RUNTIME_NOT_STARTED;
    state->poll_count = 0u;
    state->telemetry.flags = 0u;
    state->telemetry.read_sequence = 0u;
    state->telemetry.read_index = 0u;
    state->telemetry.last_error = 0u;
}

unsigned int srk_saturn_midi_68k_physical_proof_begin(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
)
{
    if(!state)
        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;
    if(state->attempted)
        return state->runtime_status;

    state->attempted = 1u;
    state->runtime_status = srk_saturn_midi_68k_protocol_begin(
        srk_saturn_midi_68k_hardware_adapter_ops()
    );
    return state->runtime_status;
}

unsigned int srk_saturn_midi_68k_physical_proof_poll(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
)
{
    if(!state || !state->attempted)
        return SRK_MIDI_68K_RUNTIME_NOT_STARTED;
    if(state->runtime_status != SRK_MIDI_68K_RUNTIME_RUNNING)
        return state->runtime_status;

    state->runtime_status = srk_saturn_midi_68k_protocol_poll(
        srk_saturn_midi_68k_hardware_adapter_ops(),
        &state->telemetry
    );
    state->poll_count += 1u;
    return state->runtime_status;
}
