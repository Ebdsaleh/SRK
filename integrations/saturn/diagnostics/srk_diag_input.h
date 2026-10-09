#ifndef SRK_DIAG_INPUT_H
#define SRK_DIAG_INPUT_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_INPUT_BUTTON_COUNT 13
#define SRK_DIAG_INPUT_LR_MASK ((srk_u16)(SRK_DIAG_BUTTON_L | SRK_DIAG_BUTTON_R))


typedef struct SRK_DIAG_INPUT_STATE {
    srk_u16 raw_state;
    srk_u16 current;
    srk_u16 previous;
    srk_u16 pressed;
    srk_u16 released;
    srk_u32 sample_count;
    srk_u32 state_change_count;
    srk_u32 hold_started_us[SRK_DIAG_INPUT_BUTTON_COUNT];
    srk_u32 hold_duration_us[SRK_DIAG_INPUT_BUTTON_COUNT];
    int connected;
} SRK_DIAG_INPUT_STATE;


void srk_diag_input_reset(SRK_DIAG_INPUT_STATE *state);
void srk_diag_input_update(
    SRK_DIAG_INPUT_STATE *state,
    const SRK_DIAG_PAD_SAMPLE *sample,
    srk_u32 now_us
);

int srk_diag_input_is_down(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask);
int srk_diag_input_was_pressed(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask);
int srk_diag_input_was_released(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask);
srk_u32 srk_diag_input_hold_us(const SRK_DIAG_INPUT_STATE *state, srk_u16 button);
srk_u32 srk_diag_input_combination_hold_us(
    const SRK_DIAG_INPUT_STATE *state,
    srk_u16 mask
);

#ifdef __cplusplus
}
#endif

#endif
