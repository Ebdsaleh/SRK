#ifndef SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_H
#define SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_H

#include "srk_saturn_midi_68k_runtime.h"

#define SRK_MIDI_68K_SILENT_BATCH_EXPECTED_RECORDS 27u
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC 0x5342u
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION 1u
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_MAGIC_OFFSET 0UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_VERSION_OFFSET 2UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_PROCESSED_OFFSET 4UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_CURRENT_RECORD_OFFSET 6UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_HI_OFFSET 8UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_FINAL_TIME_LO_OFFSET 10UL
#define SRK_MIDI_68K_SILENT_BATCH_TELEMETRY_STATE_READY_OFFSET 12UL

typedef struct SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY {
    unsigned short flags;
    unsigned short read_sequence;
    unsigned short read_index;
    unsigned short last_error;
    unsigned short telemetry_magic;
    unsigned short telemetry_version;
    unsigned short processed_records;
    unsigned short current_record;
    unsigned short final_time_hi;
    unsigned short final_time_lo;
    unsigned short state_ready;
} SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY;

typedef struct SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS {
    int (*stop_sound_cpu)(void);
    int (*install_program)(void);
    void (*publish_preload)(void);
    int (*verify_preload)(void);
    int (*start_sound_cpu)(void);
    unsigned short (*read_mailbox_word)(unsigned int word_index);
    unsigned short (*read_sound_word)(unsigned long byte_address);
} SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS;

unsigned int srk_saturn_midi_68k_silent_batch_protocol_begin(
    const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *ops
);
unsigned int srk_saturn_midi_68k_silent_batch_protocol_poll(
    const SRK_SATURN_MIDI_68K_SILENT_BATCH_RUNTIME_OPS *ops,
    SRK_SATURN_MIDI_68K_SILENT_BATCH_TELEMETRY *telemetry
);

#endif
