#include "main.h"
#include "vdp2.h"
#include "srk_runtime_video_state.h"


void srk_runtime_video_state_reset(SRK_RUNTIME_VIDEO_STATE *state)
{
    if(!state)
        return;

    state->clofen = 0;
    state->clofsl = 0;
    state->coar = 0;
    state->coag = 0;
    state->coab = 0;
    state->cobr = 0;
    state->cobg = 0;
    state->cobb = 0;
    state->valid = 0;
}


int srk_runtime_video_state_capture(SRK_RUNTIME_VIDEO_STATE *state)
{
    if(!state)
        return 0;

    /*
     * Read-only snapshot.  Do not write VDP2 state in this tranche.  The
     * captured registers are exactly the color-offset resources reserved for
     * the later visible-canary experiment.
     */
    state->clofen = CLOFEN;
    state->clofsl = CLOFSL;
    state->coar = COAR;
    state->coag = COAG;
    state->coab = COAB;
    state->cobr = COBR;
    state->cobg = COBG;
    state->cobb = COBB;
    state->valid = 1;

    return 1;
}
