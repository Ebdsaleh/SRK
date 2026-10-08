#ifndef SRK_RUNTIME_VIDEO_STATE_H
#define SRK_RUNTIME_VIDEO_STATE_H

/*
 * SRK runtime-video preservation contract.
 *
 * SRK reserves only the VDP2 color-offset register family for the first
 * visible runtime canary. The caller must capture state before applying the
 * canary and restore that exact snapshot before returning normal title control.
 * No VRAM, CRAM, VDP1, SD-card, or capture resources are owned here.
 */

typedef struct {
    unsigned short clofen;
    unsigned short clofsl;
    unsigned short coar;
    unsigned short coag;
    unsigned short coab;
    unsigned short cobr;
    unsigned short cobg;
    unsigned short cobb;
    int valid;
} SRK_RUNTIME_VIDEO_STATE;

void srk_runtime_video_state_reset(SRK_RUNTIME_VIDEO_STATE *state);
int srk_runtime_video_state_capture(SRK_RUNTIME_VIDEO_STATE *state);
int srk_runtime_video_state_restore(const SRK_RUNTIME_VIDEO_STATE *state);
int srk_runtime_video_canary_apply(const SRK_RUNTIME_VIDEO_STATE *state);
int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state);

#endif
