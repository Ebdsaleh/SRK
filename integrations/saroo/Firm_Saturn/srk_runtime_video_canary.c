#include "main.h"
#include "vdp2.h"
#include "srk_runtime_video_canary.h"


#define SRK_RUNTIME_VIDEO_COLOR_TARGETS 0x007fu
#define SRK_RUNTIME_VIDEO_CANARY_RED     0x0060u
#define SRK_RUNTIME_VIDEO_CANARY_GREEN   0x0000u
#define SRK_RUNTIME_VIDEO_CANARY_BLUE    0x0000u
#define SRK_RUNTIME_VIDEO_CANARY_FRAMES  3


static void srk_runtime_video_canary_restore(
    const SRK_RUNTIME_VIDEO_STATE *state
)
{
    COAR = state->coar;
    COAG = state->coag;
    COAB = state->coab;
    COBR = state->cobr;
    COBG = state->cobg;
    COBB = state->cobb;
    CLOFSL = state->clofsl;
    CLOFEN = state->clofen;
}


int srk_runtime_video_canary_pulse(const SRK_RUNTIME_VIDEO_STATE *state)
{
    int frame;

    if(!state || !state->valid)
        return 0;

    /*
     * 0x007F enables the seven Saturn color-offset targets.  Preserve the
     * title's A/B selection by leaving CLOFSL untouched and programming both
     * offset banks identically.  This creates a short red confirmation pulse
     * without claiming any VRAM, CRAM, tile-map, character, or VDP1 resource.
     */
    COAR = SRK_RUNTIME_VIDEO_CANARY_RED;
    COAG = SRK_RUNTIME_VIDEO_CANARY_GREEN;
    COAB = SRK_RUNTIME_VIDEO_CANARY_BLUE;
    COBR = SRK_RUNTIME_VIDEO_CANARY_RED;
    COBG = SRK_RUNTIME_VIDEO_CANARY_GREEN;
    COBB = SRK_RUNTIME_VIDEO_CANARY_BLUE;
    CLOFEN = (unsigned short)(state->clofen | SRK_RUNTIME_VIDEO_COLOR_TARGETS);

    /*
     * Keep the write bounded to three display frames while execution remains
     * inside the controller hook.  Restore the exact captured register set
     * before returning to the title.
     */
    WaitForVBLANKIn();
    for(frame=0; frame<SRK_RUNTIME_VIDEO_CANARY_FRAMES; frame++){
        WaitForVBLANKOut();
        WaitForVBLANKIn();
    }

    srk_runtime_video_canary_restore(state);
    return 1;
}
