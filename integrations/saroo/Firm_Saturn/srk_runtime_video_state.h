#ifndef SRK_RUNTIME_VIDEO_STATE_H
#define SRK_RUNTIME_VIDEO_STATE_H

/*
 * SRK runtime-video preservation contract.
 *
 * This tranche captures only the VDP2 color-offset register set that a later
 * visible canary may use.  It performs no rendering and writes no VDP state.
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

#endif
