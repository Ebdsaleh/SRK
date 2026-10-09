#include "srk_diag_audio.h"


static const char *srk_diag_audio_tones[SRK_DIAG_AUDIO_TONE_COUNT] = {
    "LOW",
    "MID",
    "HIGH",
    "STEREO"
};

static const char *srk_diag_audio_pans[3] = {
    "LEFT",
    "CENTER",
    "RIGHT"
};


static void srk_diag_audio_enter_stereo_pair(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    if(state->tone != SRK_DIAG_AUDIO_TONE_STEREO_PAIR)
        state->mono_tone = state->tone;
    state->stereo_pair = 1;
    state->tone = SRK_DIAG_AUDIO_TONE_STEREO_PAIR;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
}


void srk_diag_audio_reset(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->tone = SRK_DIAG_AUDIO_TONE_MID;
    state->mono_tone = SRK_DIAG_AUDIO_TONE_MID;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 0;
    state->muted = 0;
    state->stereo_pair = 0;
    state->submitted = 0;
}


void srk_diag_audio_control(
    SRK_DIAG_AUDIO_STATE *state,
    srk_u16 pressed_buttons
)
{
    SRK_DIAG_AUDIO_TONE selected_tone;
    int stereo_both_play;

    if(!state)
        return;

    /*
     * Stage-2 physical feedback showed that A+UP is a poor activation chord:
     * UP already has the stable CENTER/BOTH selection meaning. DOWN is unused
     * on the audio screen, so DOWN+A is the explicit, deterministic shortcut
     * for "enter stereo pair, select both voices, and play". The chord has
     * precedence over the ordinary A toggle and B mode toggle on that sample.
     */
    stereo_both_play =
        (pressed_buttons & SRK_DIAG_BUTTON_DOWN) &&
        (pressed_buttons & SRK_DIAG_BUTTON_A);

    if(stereo_both_play){
        srk_diag_audio_enter_stereo_pair(state);
        state->playing = 1;
    }else{
        if(pressed_buttons & SRK_DIAG_BUTTON_A)
            state->playing = !state->playing;

        if(pressed_buttons & SRK_DIAG_BUTTON_B){
            if(state->stereo_pair){
                state->stereo_pair = 0;
                state->tone = state->mono_tone;
            }else{
                srk_diag_audio_enter_stereo_pair(state);
            }
        }
    }

    if(pressed_buttons & SRK_DIAG_BUTTON_C)
        state->muted = !state->muted;

    /*
     * In single-slot mode this is ordinary pan selection. In stereo-pair mode
     * CENTER means both voices, LEFT means left voice only, and RIGHT means
     * right voice only. UP therefore remains a selector, not a play command.
     */
    if(pressed_buttons & SRK_DIAG_BUTTON_UP){
        state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_LEFT){
        state->pan = SRK_DIAG_AUDIO_PAN_LEFT;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_RIGHT){
        state->pan = SRK_DIAG_AUDIO_PAN_RIGHT;
    }

    /* Match the VDP1 palette convention: Z > Y > X if pressed together. */
    selected_tone = state->mono_tone;
    if(pressed_buttons & SRK_DIAG_BUTTON_Z){
        selected_tone = SRK_DIAG_AUDIO_TONE_HIGH;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_Y){
        selected_tone = SRK_DIAG_AUDIO_TONE_MID;
    }else if(pressed_buttons & SRK_DIAG_BUTTON_X){
        selected_tone = SRK_DIAG_AUDIO_TONE_LOW;
    }

    if(selected_tone != state->mono_tone){
        state->mono_tone = selected_tone;
        if(!state->stereo_pair)
            state->tone = selected_tone;
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
