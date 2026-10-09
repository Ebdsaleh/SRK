#ifndef SRK_DIAG_AUDIO_H
#define SRK_DIAG_AUDIO_H

#include "srk_diag_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SRK_DIAG_AUDIO_TONE_COUNT 4
#define SRK_DIAG_AUDIO_VOLUME_MAX 7
#define SRK_DIAG_AUDIO_DEFAULT_VOLUME 4
#define SRK_DIAG_AUDIO_SWEEP_STEP_COUNT 48
#define SRK_DIAG_AUDIO_SWEEP_FRAMES_PER_STEP 15


typedef enum SRK_DIAG_AUDIO_TONE {
    SRK_DIAG_AUDIO_TONE_LOW = 0,
    SRK_DIAG_AUDIO_TONE_MID = 1,
    SRK_DIAG_AUDIO_TONE_HIGH = 2,
    SRK_DIAG_AUDIO_TONE_STEREO_PAIR = 3
} SRK_DIAG_AUDIO_TONE;


typedef enum SRK_DIAG_AUDIO_PAN {
    SRK_DIAG_AUDIO_PAN_LEFT = 0,
    SRK_DIAG_AUDIO_PAN_CENTER = 1,
    SRK_DIAG_AUDIO_PAN_RIGHT = 2
} SRK_DIAG_AUDIO_PAN;


typedef struct SRK_DIAG_AUDIO_STATE {
    SRK_DIAG_AUDIO_TONE tone;
    SRK_DIAG_AUDIO_TONE mono_tone;
    SRK_DIAG_AUDIO_PAN pan;
    srk_u8 volume;
    unsigned int sweep_frame;
    int playing;
    int muted;
    int stereo_pair;
    int sweep_active;
    int submitted;
} SRK_DIAG_AUDIO_STATE;


void srk_diag_audio_reset(SRK_DIAG_AUDIO_STATE *state);
void srk_diag_audio_control(
    SRK_DIAG_AUDIO_STATE *state,
    srk_u16 pressed_buttons
);
void srk_diag_audio_make_request(
    SRK_DIAG_AUDIO_STATE *state,
    SRK_DIAG_AUDIO_REQUEST *request
);
void srk_diag_audio_mark_submitted(SRK_DIAG_AUDIO_STATE *state, int submitted);
const char *srk_diag_audio_tone_label(SRK_DIAG_AUDIO_TONE tone);
const char *srk_diag_audio_pan_label(SRK_DIAG_AUDIO_PAN pan);

#ifdef __cplusplus
}
#endif

#endif
