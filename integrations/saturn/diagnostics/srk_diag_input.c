#include "srk_diag_input.h"


static int srk_diag_input_index(srk_u16 button)
{
    int i;

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        if(button == (srk_u16)(1u << i))
            return i;
    }
    return -1;
}


void srk_diag_input_reset(SRK_DIAG_INPUT_STATE *state)
{
    int i;

    if(!state)
        return;

    state->raw_state = 0;
    state->current = 0;
    state->previous = 0;
    state->pressed = 0;
    state->released = 0;
    state->sample_count = 0;
    state->state_change_count = 0;
    state->connected = 0;

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        state->hold_started_us[i] = 0;
        state->hold_duration_us[i] = 0;
    }
}


void srk_diag_input_update(
    SRK_DIAG_INPUT_STATE *state,
    const SRK_DIAG_PAD_SAMPLE *sample,
    srk_u32 now_us
)
{
    srk_u16 changed;
    srk_u16 bit;
    int i;

    if(!state || !sample)
        return;

    state->previous = state->current;
    state->raw_state = sample->raw_state;
    state->current = sample->buttons;
    state->connected = sample->connected;
    state->pressed = (srk_u16)(state->current & (srk_u16)~state->previous);
    state->released = (srk_u16)(state->previous & (srk_u16)~state->current);
    state->sample_count += 1;

    changed = (srk_u16)(state->current ^ state->previous);
    if(changed)
        state->state_change_count += 1;

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        bit = (srk_u16)(1u << i);

        if(state->pressed & bit){
            state->hold_started_us[i] = now_us;
            state->hold_duration_us[i] = 0;
        }else if(state->current & bit){
            state->hold_duration_us[i] = now_us - state->hold_started_us[i];
        }else if(state->released & bit){
            state->hold_duration_us[i] = now_us - state->hold_started_us[i];
        }
    }
}


int srk_diag_input_is_down(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask)
{
    if(!state || !mask)
        return 0;
    return (state->current & mask) == mask;
}


int srk_diag_input_was_pressed(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask)
{
    if(!state || !mask)
        return 0;
    return (state->pressed & mask) == mask;
}


int srk_diag_input_was_released(const SRK_DIAG_INPUT_STATE *state, srk_u16 mask)
{
    if(!state || !mask)
        return 0;
    return (state->released & mask) == mask;
}


srk_u32 srk_diag_input_hold_us(const SRK_DIAG_INPUT_STATE *state, srk_u16 button)
{
    int index;

    if(!state)
        return 0;

    index = srk_diag_input_index(button);
    if(index < 0)
        return 0;

    return state->hold_duration_us[index];
}


srk_u32 srk_diag_input_combination_hold_us(
    const SRK_DIAG_INPUT_STATE *state,
    srk_u16 mask
)
{
    srk_u32 shortest;
    srk_u32 duration;
    srk_u16 bit;
    int found;
    int i;

    if(!state || !mask || !srk_diag_input_is_down(state, mask))
        return 0;

    shortest = 0xffffffffu;
    found = 0;

    for(i=0; i<SRK_DIAG_INPUT_BUTTON_COUNT; i++){
        bit = (srk_u16)(1u << i);
        if(!(mask & bit))
            continue;

        duration = state->hold_duration_us[i];
        if(duration < shortest)
            shortest = duration;
        found = 1;
    }

    return found ? shortest : 0;
}
