#include "main.h"
#include "vdp2.h"
#include "srk_runtime_video_state.h"


#define SRK_RUNTIME_VIDEO_COLOR_TARGETS 0x007fu
#define SRK_RUNTIME_VIDEO_CANARY_RED     0x0060u
#define SRK_RUNTIME_VIDEO_CANARY_GREEN   0x0000u
#define SRK_RUNTIME_VIDEO_CANARY_BLUE    0x0000u
#define SRK_RUNTIME_VIDEO_CANARY_FRAMES  3


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


int srk_runtime_video_state_restore(const SRK_RUNTIME_VIDEO_STATE *state)
{
    if(!state || !state->valid)
        return 0;

    /* Restore value registers before their enable/select controls. */
    COAR = state->coar;
    COAG = state->coag;
    COAB = state->coab;
    COBR = state->cobr;
    COBG = state->cobg;
    COBB = state->cobb;
    CLOFSL = state->clofsl;
    CLOFEN = state->clofen;

    return 1;
}


int srk_runtime_video_canary_apply(const SRK_RUNTIME_VIDEO_STATE *state)
{
    if(!state || !state->valid)
        return 0;

    /*
     * The Saturn color-offset enable/select registers expose seven targets.
     * Enable all seven, but preserve the title's A/B selection. Program both
     * offset banks identically so no CLOFSL write is needed for the canary.
     * The exact pre-canary values are restored by srk_runtime_video_state_restore.
     */
    COAR = SRK_RUNTIME_VIDEO_CANARY_RED;
    COAG = SRK_RUNTIME_VIDEO_CANARY_GREEN;
    COAB = SRK_RUNTIME_VIDEO_CANARY_BLUE;
    COBR = SRK_RUNTIME_VIDEO_CANARY_RED;
    COBG = SRK_RUNTIME_VIDEO_CANARY_GREEN;
    COBB = SRK_RUNTIME_VIDEO_CANARY_BLUE;
    CLOFEN = (unsigned short)(state->clofen | SRK_RUNTIME_VIDEO_COLOR_TARGETS);

    return 1;
}


int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state)
{
    int frame;

    if(!state || !state->valid)
        return 0;
    if(!srk_runtime_video_canary_apply(state))
        return 0;

    /*
     * Keep the canary bounded to three display frames while execution is still
     * inside the controller hook. The title cannot advance its normal game
     * loop during this pulse, so the captured register values remain the exact
     * values to restore before returning control.
     */
    WaitForVBLANKIn();
    for(frame=0; frame<SRK_RUNTIME_VIDEO_CANARY_FRAMES; frame++){
        WaitForVBLANKOut();
        WaitForVBLANKIn();
    }

    return srk_runtime_video_state_restore(state);
}
