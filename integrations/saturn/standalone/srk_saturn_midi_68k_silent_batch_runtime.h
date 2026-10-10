#ifndef SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_H
#define SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_H

#include "srk_saturn_midi_68k_runtime.h"

#define SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS 27u

typedef struct SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY {
    unsigned short flags;
    unsigned short read_sequence;
    unsigned short read_index;
    unsigned short last_error;
} SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY;

unsigned int srk_saturn_midi_68k_silent_batch_protocol_begin(
    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops
);
unsigned int srk_saturn_midi_68k_silent_batch_protocol_poll(
    const SRK_SATURN_MIDI_68K_RUNTIME_OPS *ops,
    SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY *telemetry
);

#endif
