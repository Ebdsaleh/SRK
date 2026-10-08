#include "main.h"
#include "srk_runtime_menu_state.h"


void srk_runtime_menu_state_reset(SRK_RUNTIME_MENU_STATE *state)
{
    if(!state)
        return;

    state->active = 0;
    state->input_armed = 0;
    state->previous_buttons = 0;
}


int srk_runtime_menu_request_open(SRK_RUNTIME_MENU_STATE *state)
{
    if(!state || state->active)
        return SRK_RUNTIME_MENU_EVENT_NONE;

    state->active = 1;
    state->input_armed = 0;
    state->previous_buttons = 0;
    return SRK_RUNTIME_MENU_EVENT_OPENED;
}


int srk_runtime_menu_state_sample(
    SRK_RUNTIME_MENU_STATE *state,
    unsigned int buttons
)
{
    unsigned int pressed;
    unsigned int release_gate;
    unsigned int resume_mask;

    if(!state)
        return SRK_RUNTIME_MENU_EVENT_NONE;

    if(!state->active){
        state->previous_buttons = buttons;
        return SRK_RUNTIME_MENU_EVENT_NONE;
    }

    /*
     * Opening is triggered by L+R. Do not accept menu controls until both
     * shoulders have been released, otherwise the trigger itself can leak into
     * the first menu interaction.
     */
    release_gate = (unsigned int)(PAD_LT | PAD_RT);
    if(!state->input_armed){
        state->previous_buttons = buttons;
        if((buttons & release_gate)==0)
            state->input_armed = 1;
        return SRK_RUNTIME_MENU_EVENT_NONE;
    }

    pressed = buttons & ~state->previous_buttons;
    state->previous_buttons = buttons;
    resume_mask = (unsigned int)(PAD_A | PAD_B | PAD_START);

    if(pressed & resume_mask){
        state->active = 0;
        state->input_armed = 0;
        return SRK_RUNTIME_MENU_EVENT_RESUMED;
    }

    return SRK_RUNTIME_MENU_EVENT_NONE;
}
