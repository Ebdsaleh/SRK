#include "srk_diag_audio.h"


static const char *srk_diag_audio_tones[SRK_DIAG_AUDIO_TONE_COUNT] = {
    "LOW",
    "MID",
    "HIGH",
    "STEREO",
    "MIXED"
};

static const char *srk_diag_audio_pans[3] = {
    "LEFT",
    "CENTER",
    "RIGHT"
};


static int srk_diag_audio_is_pair_tone(SRK_DIAG_AUDIO_TONE tone)
{
    return tone == SRK_DIAG_AUDIO_TONE_STEREO_PAIR ||
           tone == SRK_DIAG_AUDIO_TONE_MIXED_PAIR;
}


static void srk_diag_audio_enter_stereo_pair(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    if(!srk_diag_audio_is_pair_tone(state->tone))
        state->mono_tone = state->tone;
    state->stereo_pair = 1;
    state->sweep_active = 0;
    state->sample_mode = 0;
    state->sweep_frame = 0u;
    state->tone = SRK_DIAG_AUDIO_TONE_STEREO_PAIR;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
}


static void srk_diag_audio_enter_mixed_pair(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    if(!srk_diag_audio_is_pair_tone(state->tone))
        state->mono_tone = state->tone;
    state->stereo_pair = 1;
    state->sweep_active = 0;
    state->sample_mode = 0;
    state->sweep_frame = 0u;
    state->tone = SRK_DIAG_AUDIO_TONE_MIXED_PAIR;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 1;
    state->muted = 0;
}


static void srk_diag_audio_leave_pair(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->stereo_pair = 0;
    state->sweep_active = 0;
    state->sample_mode = 0;
    state->sweep_frame = 0u;
    state->tone = state->mono_tone;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 0;
    state->muted = 0;
}


static void srk_diag_audio_enter_sweep(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    if(!srk_diag_audio_is_pair_tone(state->tone))
        state->mono_tone = state->tone;

    state->stereo_pair = 0;
    state->sample_mode = 0;
    state->sweep_active = 1;
    state->sweep_frame = 0u;
    state->tone = SRK_DIAG_AUDIO_TONE_LOW;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = 0u;
    state->playing = 1;
    state->muted = 0;
}


static void srk_diag_audio_leave_sweep(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->sweep_active = 0;
    state->sweep_frame = 0u;
    state->stereo_pair = 0;
    state->sample_mode = 0;
    state->tone = state->mono_tone;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 0;
    state->muted = 0;
}


static void srk_diag_audio_enter_sample_mode(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    if(!srk_diag_audio_is_pair_tone(state->tone))
        state->mono_tone = state->tone;

    state->stereo_pair = 0;
    state->sweep_active = 0;
    state->sample_mode = 1;
    state->sweep_frame = 0u;
    state->tone = state->mono_tone;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 1;
    state->muted = 0;
}


static void srk_diag_audio_leave_sample_mode(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->sample_mode = 0;
    state->stereo_pair = 0;
    state->sweep_active = 0;
    state->sweep_frame = 0u;
    state->tone = state->mono_tone;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->playing = 0;
    state->muted = 0;
}


static void srk_diag_audio_advance_sweep(SRK_DIAG_AUDIO_STATE *state)
{
    unsigned int step;
    unsigned int phase;
    unsigned int level;
    unsigned int total_frames;

    if(!state || !state->sweep_active)
        return;

    step = state->sweep_frame / SRK_DIAG_AUDIO_SWEEP_FRAMES_PER_STEP;
    step %= SRK_DIAG_AUDIO_SWEEP_STEP_COUNT;
    phase = step / 8u;
    level = step & 7u;

    if(phase == 0u){
        state->tone = SRK_DIAG_AUDIO_TONE_LOW;
        state->volume = (srk_u8)level;
    }else if(phase == 1u){
        state->tone = SRK_DIAG_AUDIO_TONE_MID;
        state->volume = (srk_u8)level;
    }else if(phase == 2u){
        state->tone = SRK_DIAG_AUDIO_TONE_HIGH;
        state->volume = (srk_u8)level;
    }else if(phase == 3u){
        state->tone = SRK_DIAG_AUDIO_TONE_HIGH;
        state->volume = (srk_u8)(7u - level);
    }else if(phase == 4u){
        state->tone = SRK_DIAG_AUDIO_TONE_MID;
        state->volume = (srk_u8)(7u - level);
    }else{
        state->tone = SRK_DIAG_AUDIO_TONE_LOW;
        state->volume = (srk_u8)(7u - level);
    }

    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    total_frames =
        SRK_DIAG_AUDIO_SWEEP_STEP_COUNT * SRK_DIAG_AUDIO_SWEEP_FRAMES_PER_STEP;
    state->sweep_frame += 1u;
    if(state->sweep_frame >= total_frames)
        state->sweep_frame = 0u;
}


void srk_diag_audio_reset(SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return;

    state->tone = SRK_DIAG_AUDIO_TONE_MID;
    state->mono_tone = SRK_DIAG_AUDIO_TONE_MID;
    state->pan = SRK_DIAG_AUDIO_PAN_CENTER;
    state->volume = SRK_DIAG_AUDIO_DEFAULT_VOLUME;
    state->sweep_frame = 0u;
    state->playing = 0;
    state->muted = 0;
    state->stereo_pair = 0;
    state->sweep_active = 0;
    state->sample_mode = 0;
    state->submitted = 0;
}


void srk_diag_audio_control(
    SRK_DIAG_AUDIO_STATE *state,
    srk_u16 pressed_buttons
)
{
    SRK_DIAG_AUDIO_TONE selected_tone;
    int stereo_both_play;
    int sweep_toggle;
    int sample_toggle;
    int mixed_pair_toggle;

    if(!state)
        return;

    /*
     * DOWN+B owns Stage 3 automated sweep entry/exit. Give that chord priority
     * over the ordinary B mode toggle so the control cannot enter two modes on
     * one controller sample. While the sweep owns the logical tone/volume
     * sequence, all ordinary audio controls are ignored until DOWN+B exits it.
     */
    sweep_toggle =
        (pressed_buttons & SRK_DIAG_BUTTON_DOWN) &&
        (pressed_buttons & SRK_DIAG_BUTTON_B);

    if(state->sweep_active){
        if(sweep_toggle)
            srk_diag_audio_leave_sweep(state);
        return;
    }

    if(sweep_toggle){
        if(state->sample_mode)
            srk_diag_audio_leave_sample_mode(state);
        srk_diag_audio_enter_sweep(state);
        return;
    }

    /*
     * Stage 4 uses DOWN+C as an explicit shaped-PCM source toggle. The chord
     * takes precedence over ordinary C mute/unmute. Unlike the automated sweep,
     * sample mode still allows the normal play, mute, pan, pitch and volume
     * controls so the alternate Sound-RAM source can be tested directly.
     */
    sample_toggle =
        (pressed_buttons & SRK_DIAG_BUTTON_DOWN) &&
        (pressed_buttons & SRK_DIAG_BUTTON_C);

    if(sample_toggle){
        if(state->sample_mode)
            srk_diag_audio_leave_sample_mode(state);
        else
            srk_diag_audio_enter_sample_mode(state);
        return;
    }

    /*
     * Stage 5 combines the two physically accepted PCM regions on independent
     * SCSP slots. DOWN+Z is explicit so ordinary Z remains HIGH selection in
     * single-slot mode. Entering establishes both-source playback; repeating
     * the chord returns to a stopped single-slot tone state.
     */
    mixed_pair_toggle =
        (pressed_buttons & SRK_DIAG_BUTTON_DOWN) &&
        (pressed_buttons & SRK_DIAG_BUTTON_Z);

    if(mixed_pair_toggle){
        if(state->stereo_pair && state->tone == SRK_DIAG_AUDIO_TONE_MIXED_PAIR)
            srk_diag_audio_leave_pair(state);
        else{
            if(state->sample_mode)
                srk_diag_audio_leave_sample_mode(state);
            srk_diag_audio_enter_mixed_pair(state);
        }
        return;
    }

    /*
     * Stage-2 physical feedback showed that A+UP is a poor activation chord:
     * UP already has the stable CENTER/BOTH selection meaning. DOWN+A is the
     * explicit shortcut for "enter stereo pair, select both voices, and play".
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

        if((pressed_buttons & SRK_DIAG_BUTTON_B) && !state->sample_mode){
            if(state->stereo_pair)
                srk_diag_audio_leave_pair(state);
            else
                srk_diag_audio_enter_stereo_pair(state);
        }
    }

    if(pressed_buttons & SRK_DIAG_BUTTON_C)
        state->muted = !state->muted;

    /*
     * In single-slot mode this is ordinary pan selection. In either pair mode,
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
    SRK_DIAG_AUDIO_STATE *state,
    SRK_DIAG_AUDIO_REQUEST *request
)
{
    if(!state || !request)
        return;

    /*
     * START is handled by the app shell and forces playing=0 before the audio
     * screen is left. If that happened during a sweep, cancel the automation on
     * the next request rather than silently resuming it when the screen reopens.
     */
    if(state->sweep_active){
        if(!state->playing)
            srk_diag_audio_leave_sweep(state);
        else
            srk_diag_audio_advance_sweep(state);
    }

    request->tone_id = (unsigned int)state->tone;
    request->pan_id = (unsigned int)state->pan;
    request->waveform_id = state->sample_mode
        ? (unsigned int)SRK_DIAG_AUDIO_WAVEFORM_SHAPED_PCM
        : (unsigned int)SRK_DIAG_AUDIO_WAVEFORM_TONE;
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


const char *srk_diag_audio_source_label(const SRK_DIAG_AUDIO_STATE *state)
{
    if(!state)
        return "UNKNOWN";
    if(state->tone == SRK_DIAG_AUDIO_TONE_MIXED_PAIR)
        return "TONE+PCM";
    return state->sample_mode ? "SHAPED PCM" : "TONE";
}
