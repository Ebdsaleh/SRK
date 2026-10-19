#ifndef SRK_DIAG_MIDI_TEST_H
#define SRK_DIAG_MIDI_TEST_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_MIDI_PROGRAM_COUNT 128u
#define SRK_DIAG_MIDI_FAMILY_COUNT 16u
#define SRK_DIAG_MIDI_PROGRAMS_PER_FAMILY 8u
#define SRK_DIAG_MIDI_DEFAULT_CHANNEL 0u
#define SRK_DIAG_MIDI_DEFAULT_NOTE 60u
#define SRK_DIAG_MIDI_DEFAULT_VELOCITY 100u
#define SRK_DIAG_MIDI_DEFAULT_PAN 64u
#define SRK_DIAG_MIDI_PAN_STEP 8u
#define SRK_DIAG_MIDI_VELOCITY_STEP 8u


typedef struct SRK_DIAG_MIDI_TEST_STATE {
    srk_u8 program;
    srk_u8 channel;
    srk_u8 note;
    srk_u8 velocity;
    srk_u8 pan;
    srk_u8 note_active;
    srk_u8 prepared;
    srk_u8 last_error;
    srk_u32 last_hold_us;
    srk_u32 review_bits[4];
    srk_u32 review_count;
    srk_u32 persisted_review_count;
} SRK_DIAG_MIDI_TEST_STATE;


void srk_diag_midi_test_reset(SRK_DIAG_MIDI_TEST_STATE *state);
void srk_diag_midi_test_move_program(SRK_DIAG_MIDI_TEST_STATE *state, int delta);
void srk_diag_midi_test_move_pan(SRK_DIAG_MIDI_TEST_STATE *state, int delta);
void srk_diag_midi_test_move_velocity(SRK_DIAG_MIDI_TEST_STATE *state, int delta);
unsigned int srk_diag_midi_test_family(const SRK_DIAG_MIDI_TEST_STATE *state);
const char *srk_diag_midi_program_name(unsigned int program);
const char *srk_diag_midi_family_name(unsigned int family);
int srk_diag_midi_review_marked(const SRK_DIAG_MIDI_TEST_STATE *state, unsigned int program);
int srk_diag_midi_mark_review(SRK_DIAG_MIDI_TEST_STATE *state);

#ifdef __cplusplus
}
#endif

#endif
