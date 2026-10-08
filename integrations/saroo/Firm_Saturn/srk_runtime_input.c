#include "main.h"
#include "srk_runtime_input.h"


void srk_runtime_input_reset(SRK_RUNTIME_INPUT_STATE *state)
{
    if(!state)
        return;

    state->hold_samples = 0;
    state->latched = 0;
}


int srk_runtime_input_sample(
    SRK_RUNTIME_INPUT_STATE *state,
    unsigned int buttons
)
{
    unsigned int shoulder_mask;
    unsigned int shoulders;

    if(!state)
        return SRK_RUNTIME_INPUT_NONE;

    shoulder_mask = (unsigned int)(PAD_LT | PAD_RT);
    shoulders = buttons & shoulder_mask;

    if(state->latched){
        /* Require both shoulders released before another activation. */
        if(shoulders==0){
            state->latched = 0;
            state->hold_samples = 0;
        }
        return SRK_RUNTIME_INPUT_NONE;
    }

    if(shoulders!=shoulder_mask){
        /* Any interrupted L+R hold starts the count over. */
        state->hold_samples = 0;
        return SRK_RUNTIME_INPUT_NONE;
    }

    if(state->hold_samples<SRK_RUNTIME_INPUT_HOLD_SAMPLES)
        state->hold_samples += 1;

    if(state->hold_samples>=SRK_RUNTIME_INPUT_HOLD_SAMPLES){
        state->latched = 1;
        return SRK_RUNTIME_INPUT_OPEN_MENU;
    }

    return SRK_RUNTIME_INPUT_NONE;
}
