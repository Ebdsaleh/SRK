#include "srk_diag_audio.h"


static const char *srk_diag_audio_tones[SRK_DIAG_AUDIO_TONE_COUNT] = {
    "LOW",
    "MID",
    "HIGH"
};

static const char *srk_diag_audio_pans[3] = {
    "LEFT",
    "CENTER",
    "RIGHT"
};


void srk_diag_audio_reset(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->tone = SRK_DIAG_AUDIO_TONE_MID;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 0;
    state->muted = 0;
    state->submitted = 0;
}


void srk_diag_audio_control(
    SRK_DIAG_AUDIO_STATE *state,
    srk_u16 pressed_buttons
)
{
    if(!state)
        return;

    if(pressed_buttons & SRK_DIAG_BUTTON_A)
        state->playing = !state->playing;

    if(pressed_buttons & SRK_DIAG_BUTTON_C)
        state->muted = !state->muted;

    /* Center takes precedence over the directional extremes on one sample. */
    if(pressed_buttons & SRK_DIAG_BUTTON_UP){
        state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_LEFT){
        state->pan = SRK_DIAG_AUDIO_PAN_LEFT;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_RIGHT){
        state->pan = SRK_DIAG_AUDIO_PAN_RIGHT;
    }

    /* Match the VDP1 palette convention: Z > Y > X if pressed together. */
    if(pressed_buttons & SRK_DIAG_BUTTON_Z){
        state->tone = SRK_DIAG_AUDIO_TONE_HIGH;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_Y){
        state->tone = SRK_DIAG_AUDIO_TONE_MID;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_X){
        state->tone = SRK_DIAG_AUDIO_TONE_LOW;
    }

    if((pressed_buttons & SRK_DIAG_BUTTON_L) &&
       !(pressed_buttons & SRK_DIAG_BUTTON_R)){
        if(state->volume > 0)
            state->volume -= 1;
    }else if((pressed_buttons & SRK_DIAG_BUTTON_R) &&
             !(pressed_buttons & SRK_DIAG_BUTTON_L)){
        if(state->volume < SRK_DIAG_AUDIO_VOLUME_MAX)
            state->volume += 1;
    }
}


void srk_diag_audio_make_request(
    const SRK_DIAG_AUDIO_STATE *state,
    SRK_DIAG_AUDIO_REQUEST *request
)
{
    if(!state || !request)
        return;

    request->tone_id = (unsigned int)state->tone;
    request->pan_id = (unsigned int)state->pan;
    request->volume_level = (unsigned int)state->volume;
    request->playing = state->playing;
    request->muted = state->muted;
}


void srk_diag_audio_mark_submitted(SRK_DIAG_AUDIO_STATE *state, int submitted)
{
    if(state)
        state->submitted = submitted ? 1 : 0;
}


const char *srk_diag_audio_tone_label(SRK_DIAG_AUDIO_TONE tone)
{
    if((int)tone < 0 || (int)tone >= SRK_DIAG_AUDIO_TONE_COUNT)
        return "UNKNOWN";
    return srk_diag_audio_tones[(int)tone];
}


const char *srk_diag_audio_pan_label(SRK_DIAG_AUDIO_PAN pan)
{
    if((int)pan < 0 || (int)pan > (int)SRK_DIAG_AUDIO_PAN_RIGHT)
        return "UNKNOWN";
    return srk_diag_audio_pans[(int)pan];
}
