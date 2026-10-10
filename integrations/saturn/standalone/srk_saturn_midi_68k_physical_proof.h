#ifndef SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_H
#define SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_H

#include "srk_saturn_midi_68k_runtime.h"

typedef struct SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE {
    unsigned int attempted;
    unsigned int runtime_status;
    unsigned int poll_count;
    SRK_SATURN_MIDI_68K_TELEMETRY telemetry;
} SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE;

void srk_saturn_midi_68k_physical_proof_reset(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
);
unsigned int srk_saturn_midi_68k_physical_proof_begin(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
);
unsigned int srk_saturn_midi_68k_physical_proof_poll(
    SRK_SATURN_MIDI_68K_PHYSICAL_PROOF_STATE *state
);

#endif
