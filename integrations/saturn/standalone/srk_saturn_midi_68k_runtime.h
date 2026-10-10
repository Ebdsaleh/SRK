#ifndef SRK_SATURN_MIDI_68K_RUNTIME_H
#define SRK_SATURN_MIDI_68K_RUNTIME_H

#define SRK_MIDI_68K_RUNTIME_NOT_STARTED 0u
#define SRK_MIDI_68K_RUNTIME_SOUND_STOP_FAILED 1u
#define SRK_MIDI_68K_RUNTIME_INSTALL_FAILED 2u
#define SRK_MIDI_68K_RUNTIME_PRELOAD_FAILED 3u
#define SRK_MIDI_68K_RUNTIME_SOUND_START_FAILED 4u
#define SRK_MIDI_68K_RUNTIME_RUNNING 5u
#define SRK_MIDI_68K_RUNTIME_ACKNOWLEDGED 6u
#define SRK_MIDI_68K_RUNTIME_CONSUMER_ERROR 7u

typedef struct SRK_SATURN_MIDI_68K_TELEMETRY {
    unsigned short flags;
    unsigned short read_sequence;
    unsigned short read_index;
    unsigned short last_error;
} SRK_SATURN_MIDI_68K_TELEMETRY;

/* This source tranche defines the path but production does not call it yet. */
unsigned int srk_saturn_midi_68k_protocol_begin(void);
unsigned int srk_saturn_midi_68k_protocol_poll(
    SRK_SATURN_MIDI_68K_TELEMETRY *telemetry
);

#endif
